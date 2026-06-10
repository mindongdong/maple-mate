"""동시 부하 시뮬레이션 (스케일 튜닝 3-6, D7) — deploy-plan 단계 2 완료 기준의 코드화.

httpx MockTransport 에 인위 지연(100ms)을 넣은 가짜 넥슨으로 **동시 20명령**
(스펙류 19건 + 이력류 cold 12일치 1건)을 투입한다. 라이브 부하테스트 없음(넥슨 한도·약관).

단언: ① 이력류 cold 진행 중에도 스펙류 전부 완료(키별 버킷 = 전역 비차단, ADR-0004)
② 같은 개인 키 호출 시작 간격 ≥ 0.2초 ③ 전 명령 완료(유실 없음).
"""

from __future__ import annotations

import asyncio
import time

import httpx
import pytest

from maple_mate.nexon.client import NexonClient

_LATENCY = 0.1  # 가짜 넥슨 응답 지연
_APP_THROTTLE = 0.05  # 앱 키 간격(시뮬용 — 실값 0.25 면 테스트가 5초+)
_SPEC_COMMANDS = 19
_COLD_DAYS = 12  # 1년(365일)의 축소판 — 직렬 개인 키 호출이라 12일 ≈ 2.4초


def _handler(requests: dict[str, list[float]]):
    async def handler(request: httpx.Request) -> httpx.Response:
        key = request.headers["x-nxopen-api-key"]
        requests.setdefault(key, []).append(time.monotonic())
        await asyncio.sleep(_LATENCY)
        return httpx.Response(
            200, json={"date": None, "starforce_history": [], "next_cursor": None}
        )

    return handler


async def _spec_command(client: NexonClient, i: int, done: list[float]) -> str:
    """스펙류 명령 1건: 앱 키 + 고유 ocid(캐시 비적중) 조회."""
    await client.character_basic(f"ocid-{i}")
    done.append(time.monotonic())
    return f"spec-{i}"


async def _cold_history_command(client: NexonClient, dates: list[str]) -> str:
    """이력류 cold 1건: 한 유저의 개인 키로 날짜별 직렬 호출(fetch_starforce_records 흐름)."""
    for date_iso in dates:
        await client.starforce_history("personal_key", date_iso)
    return "history-cold"


@pytest.mark.slow
async def test_spec_commands_complete_while_cold_history_runs():
    requests: dict[str, list[float]] = {}
    client = NexonClient(
        "app_key",
        throttle=_APP_THROTTLE,
        retry_wait=0.0,
        transport=httpx.MockTransport(_handler(requests)),
    )
    dates = [f"2026-05-{d:02d}" for d in range(1, _COLD_DAYS + 1)]
    spec_done: list[float] = []

    t0 = time.monotonic()
    async with client:
        results = await asyncio.gather(
            *(_spec_command(client, i, spec_done) for i in range(_SPEC_COMMANDS)),
            _cold_history_command(client, dates),
        )
    total = time.monotonic() - t0

    # ③ 전 명령 완료(유실 없음): 결과 20건 + HTTP 호출 수 일치.
    assert len(results) == _SPEC_COMMANDS + 1
    assert sorted(results)[:2] == ["history-cold", "spec-0"]
    assert len(requests["app_key"]) == _SPEC_COMMANDS
    assert len(requests["personal_key"]) == _COLD_DAYS

    # ② 같은 개인 키 호출 시작 간격 ≥ 0.2초(5/s 선제 준수).
    personal = requests["personal_key"]
    assert all(b - a >= 0.2 - 0.02 for a, b in zip(personal, personal[1:]))

    # ① 전역 비차단: cold(≥ 11×0.2s)가 끝나기 한참 전에 스펙류 19건 전부 응답.
    #    구 전역 단일 버킷이면 31콜이 한 줄로 직렬화돼 스펙류 후미가 cold 와 함께 끝난다.
    assert total >= (_COLD_DAYS - 1) * 0.2  # cold 가 실제로 오래 걸렸음(전제 확인)
    spec_last = max(spec_done) - t0
    assert spec_last < 2.0
    assert spec_last < total - 0.2  # 스펙류 완료 시점에 cold 는 아직 진행 중
