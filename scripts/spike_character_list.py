"""G0 스파이크 — 개인 키로 `character/list`(계정 캐릭터 목록) 실호출 검증 (PR3b 선행).

PR3b(키 기반 계정 동기화·가져오기)는 이 API 하나에 기대지만 아직 실호출로 확인한 적이 없다.
구현 전에 다음을 확인한다(docs/account-character-import-work-order.md §3):

  ① 목록의 ocid 가 공개 조회(`/id?character_name=`, 앱 키)의 ocid 와 **같은가** — 다르면 가져온 캐릭터로
     /스펙·/아이템 등 공개 조회가 전부 실패하고, ocid 대조 기반 동기화 설계가 무너진다(치명).
  ② 응답 스키마(account_list[].character_list[] · 필드명)가 문서와 같은가
  ③ 목록의 character_level 이 실시간인가(= character/basic 최신값과 같은가) 전일 기준인가
  ④ 캐릭터 수·월드(챌린저스 포함)·레벨 분포, 응답 시간 — 선택 메뉴(25개 상한) 후보 규칙 결정용

개인정보: 키는 출력·저장하지 않는다. 닉네임은 첫 글자만, ocid 는 앞 6자만 출력한다.

실행(둘 중 하나):
  # A. 로컬 — 본인 개인 키를 입력(화면에 표시되지 않음). .env 가 없어도 동작(앱 키 대신 개인 키로 /id 조회).
  uv run python -m scripts.spike_character_list
  #    또는 NEXON_PERSONAL_KEY 환경변수로 전달
  # B. 운영 셸 — 봇에 이미 등록한 본인 키를 복호화해서 사용(DB·FERNET 필요)
  uv run --no-sync python -m scripts.spike_character_list --from-db <guild_id> <discord_user_id>

옵션: --sample N  ①·③ 교차 확인할 캐릭터 수(레벨 상위, 기본 5)
"""

from __future__ import annotations

import asyncio
import getpass
import os
import sys
import time
from collections import Counter

from maple_mate.config import ConfigError, load_config
from maple_mate.nexon.client import NexonClient
from maple_mate.nexon.errors import NexonAPIError

_EXPECTED_FIELDS = {
    "ocid",
    "character_name",
    "world_name",
    "character_class",
    "character_level",
}
_SELECT_LIMIT = 25  # 디스코드 Select 옵션 상한


def _mask(name: object) -> str:
    text = str(name or "")
    return text[:1] + "*" * max(len(text) - 1, 0) if text else "(빈 값)"


def _short(ocid: object) -> str:
    return f"{str(ocid)[:6]}…" if ocid else "(없음)"


def _level(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _flatten(payload: dict) -> list[dict]:
    """account_list[].character_list[] → 캐릭터 목록(계정 순서 유지)."""
    chars: list[dict] = []
    for account in payload.get("account_list") or []:
        chars.extend(account.get("character_list") or [])
    return chars


async def _key_from_db(guild_id: int, user_id: int) -> str:
    from maple_mate.database.core import make_engine, make_session_factory
    from maple_mate.registration.models import Registration
    from maple_mate.security.crypto import KeyCipher

    config = load_config()
    engine = make_engine(config.database_url)
    try:
        async with make_session_factory(engine)() as session:
            reg = await session.get(Registration, (guild_id, user_id))
    finally:
        await engine.dispose()
    if reg is None or reg.api_key_encrypted is None:
        sys.exit("해당 (guild_id, discord_user_id) 에 등록된 개인 키가 없어요.")
    return KeyCipher(config.fernet_master_key).decrypt(reg.api_key_encrypted)


def _personal_key_from_input() -> str:
    key = os.environ.get("NEXON_PERSONAL_KEY", "").strip()
    if not key:
        key = getpass.getpass(
            "넥슨 개인 API 키(입력이 화면에 표시되지 않아요): "
        ).strip()
    if not key:
        sys.exit("개인 키가 필요해요.")
    return key


async def main(argv: list[str]) -> None:
    sample = 5
    if "--sample" in argv:
        sample = int(argv[argv.index("--sample") + 1])
    if "--from-db" in argv:
        i = argv.index("--from-db")
        personal_key = await _key_from_db(int(argv[i + 1]), int(argv[i + 2]))
    else:
        personal_key = _personal_key_from_input()

    try:
        app_key = load_config().nexon_app_key
        id_key_label = "앱 키(운영과 같은 경로)"
    except ConfigError:
        app_key = (
            personal_key  # .env 없는 로컬 — /id 는 어떤 키로도 같은 ocid 를 준다는 가정
        )
        id_key_label = "개인 키(.env 없음 — 앱 키 대체)"

    async with NexonClient(app_key) as nexon:
        # ── ② 스키마 + ④ 응답 시간 ────────────────────────────────────────
        started = time.monotonic()
        try:
            payload = await nexon._request(
                "maplestory/v1/character/list", api_key=personal_key
            )
        except NexonAPIError as exc:
            sys.exit(
                f"character/list 호출 실패: {exc.code} ({exc.error_class.value}) "
                f"http={exc.http_status} — 키 종류·권한을 확인해 주세요."
            )
        elapsed = time.monotonic() - started
        accounts = payload.get("account_list") or []
        chars = _flatten(payload)
        fields = set().union(*(c.keys() for c in chars)) if chars else set()

        print("=== ② 응답 스키마 ===")
        print(f"  최상위 키: {sorted(payload.keys())}")
        print(f"  메이플 계정 수(account_list): {len(accounts)}")
        print(f"  캐릭터 필드: {sorted(fields)}")
        missing, extra = _EXPECTED_FIELDS - fields, fields - _EXPECTED_FIELDS
        print(
            f"  문서 대비 누락: {sorted(missing) or '없음'} / 추가: {sorted(extra) or '없음'}"
        )

        print("\n=== ④ 규모·분포 ===")
        print(f"  응답 시간: {elapsed:.2f}s · 캐릭터 {len(chars)}개", end="")
        print(
            f" (선택 메뉴 상한 {_SELECT_LIMIT}개 초과)"
            if len(chars) > _SELECT_LIMIT
            else ""
        )
        worlds = Counter(str(c.get("world_name")) for c in chars)
        print(f"  월드 분포: {dict(worlds.most_common())}")
        challengers = sum(n for w, n in worlds.items() if w.startswith("챌린저스"))
        print(f"  챌린저스 캐릭터: {challengers}개")
        levels = [lv for lv in (_level(c.get("character_level")) for c in chars) if lv]
        bands = Counter(
            "200+" if lv >= 200 else "100~199" if lv >= 100 else "~99" for lv in levels
        )
        print(f"  레벨 구간: {dict(bands)} · 레벨 없음 {len(chars) - len(levels)}개")

        # ── ①·③ 교차 확인(레벨 상위 sample 개) ────────────────────────────
        picked = sorted(
            chars, key=lambda c: _level(c.get("character_level")) or -1, reverse=True
        )[:sample]
        print(
            f"\n=== ① ocid 일치 · ③ 레벨 신선도 (레벨 상위 {len(picked)}개, /id 조회 키: {id_key_label}) ==="
        )
        ocid_same = level_same = checked = 0
        for c in picked:
            name, list_ocid = c.get("character_name"), c.get("ocid")
            row = f"  - {_mask(name)} ({c.get('world_name')}) 목록 ocid {_short(list_ocid)}"
            try:
                public_ocid = await nexon.get_ocid(str(name))
            except NexonAPIError as exc:
                print(f"{row} → /id 실패 {exc.code} ({exc.error_class.value})")
                continue
            checked += 1
            same = public_ocid == list_ocid
            ocid_same += same
            row += (
                f" / 공개 ocid {_short(public_ocid)} → {'일치' if same else '불일치 ⚠️'}"
            )
            try:
                basic = await nexon.character_basic(str(list_ocid))
                list_lv, live_lv = (
                    _level(c.get("character_level")),
                    _level(basic.get("character_level")),
                )
                level_same += list_lv == live_lv
                row += f" · 레벨 목록 {list_lv} / 최신 {live_lv}"
                row += "" if list_lv == live_lv else " (차이)"
            except NexonAPIError as exc:
                row += f" · 목록 ocid 로 character/basic 실패 {exc.code} ⚠️"
            print(row)

        print("\n=== 요약 ===")
        print(
            f"  ① ocid 일치: {ocid_same}/{checked}"
            + ("" if ocid_same == checked else "  ⚠️ PR3b 설계 재검토 필요")
        )
        print(f"  ② 스키마: {'문서와 일치' if not missing else '누락 필드 있음 ⚠️'}")
        print(
            f"  ③ 레벨 최신값 일치: {level_same}/{checked}"
            + ("" if level_same == checked else " (목록 레벨이 실시간이 아닐 수 있음)")
        )
        print(
            f"  ④ 캐릭터 {len(chars)}개 · 계정 {len(accounts)}개 · 응답 {elapsed:.2f}s"
        )


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
