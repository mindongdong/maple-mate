"""G1 미니스파이크 — `history/potential`(+`history/cube`) 1콜 덤프로 등업 의미 확정.

`/잠재` 등업 카운팅의 유일한 미검증 가정을 라이브로 확정하는 도구다(potential-handoff.md G1):
  ① 응답 스키마 키가 DTO(docs/api/history.md)와 일치하는가
  ② `item_upgrade_result == "성공"` 이 **등급 상승(등업)** 을 뜻하는가
  ③ 천장(`upgrade_guarantee == true`) 등업 시 결과 문자열은 무엇인가
  ④ `before_potential_option[0].grade` 가 **등업 전 등급(from-등급)** 인가
     (= before 최고 등급 < after 최고 등급 이면 등급 상승, 그 before 최고가 from)

개인 키 = 그 계정 이력(ocid 파라미터 없음). 메소 재설정/큐브 사용 기록이 있는 키로 호출한다.
0건이면 사용자가 메소 재설정(또는 큐브 사용) 1회 후 재시도. 결과를
potential-handoff.md "등업 메커니즘" 에 반영한다.

실행:
  NEXON_PERSONAL_KEY=<개인API키> uv run python -m scripts.spike_potential [YYYY-MM-DD]
  # 키 미지정 시 config 의 NEXON_APP_KEY 사용(Spike 0 처럼 앱 키=개인 키인 개발 환경 한정)
  # 날짜 미지정 시 오늘(KST)
"""
from __future__ import annotations

import asyncio
import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

from maple_mate.config import load_config
from maple_mate.nexon.client import NexonClient

KST = timezone(timedelta(hours=9))
_ORDER = {"레어": 1, "에픽": 2, "유니크": 3, "레전드리": 4}


def _grades(options: object) -> list[str]:
    """옵션 배열 → 등급 문자열 목록(빈/이상치는 건너뜀)."""
    if not isinstance(options, list):
        return []
    return [o.get("grade", "") for o in options if isinstance(o, dict)]


def _top(grades: list[str]) -> str | None:
    """등급 목록의 최고 등급(없으면 None)."""
    valid = [g for g in grades if g in _ORDER]
    return max(valid, key=lambda g: _ORDER[g]) if valid else None


def _inspect(label: str, records: list[dict]) -> None:
    print(f"\n=== {label}: {len(records)}건 ===")
    if not records:
        print("  (기록 0건 — 재설정/큐브 1회 후 재시도하면 등업 의미를 확정할 수 있어요)")
        return

    # ① 스키마 키
    keys = sorted({k for r in records for k in r.keys()})
    print(f"  ① 응답 키: {keys}")

    # 결과 문자열 분포
    print(f"  결과 분포: {dict(Counter(r.get('item_upgrade_result') for r in records))}")

    # ②③④ 성공행 = 등급 상승인가 / 천장 결과 문자열 / before[0]=from?
    success = [r for r in records if r.get("item_upgrade_result") == "성공"]
    print(f"  ② '성공' 레코드: {len(success)}건")
    for r in success:
        before = _grades(r.get("before_potential_option"))
        after = _grades(r.get("after_potential_option"))
        bt, at = _top(before), _top(after)
        rose = bt is not None and at is not None and _ORDER.get(at, 0) > _ORDER.get(bt, 0)
        first = before[0] if before else None
        print(
            f"    - {r.get('target_item')} (Lv{r.get('item_level')}, {r.get('item_equipment_part')}) "
            f"천장={r.get('upgrade_guarantee')}"
        )
        print(f"        before 최고={bt} → after 최고={at}  ⇒ 등급상승={rose}")
        print(f"        ④ before[0].grade={first}  (from-등급이 {bt} 와 일치하는지 확인)")

    guaranteed = [r for r in records if r.get("upgrade_guarantee")]
    if guaranteed:
        print(f"  ③ 천장(upgrade_guarantee=true) 레코드의 결과 문자열: "
              f"{dict(Counter(r.get('item_upgrade_result') for r in guaranteed))}")


async def main() -> None:
    config = load_config()
    key = os.environ.get("NEXON_PERSONAL_KEY") or config.nexon_app_key
    date_iso = sys.argv[1] if len(sys.argv) > 1 else datetime.now(KST).date().isoformat()
    print(f"date={date_iso}  key={key[:4]}…{key[-4:]}")

    async with NexonClient(config.nexon_app_key) as nexon:
        resets = await nexon.potential_history(key, date_iso)
        cubes = await nexon.cube_history(key, date_iso)
        _inspect("history/potential (메소 재설정)", resets)
        _inspect("history/cube (큐브)", cubes)

    print("\n결론 메모: 위 ②/④ 결과를 potential-handoff.md '등업 메커니즘' 에 반영하세요.")


if __name__ == "__main__":
    asyncio.run(main())
