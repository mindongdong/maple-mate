"""`모드` 슬래시 파라미터 공용 정의 (본서버/챌린저스, ADR-0009).

명령별 무상태 파라미터(결정 2) — 공개 봇에서 숨은 토글 사고를 피한다. 6개 모드 명령
(`/스펙`·`/아이템`·`/스타포스`·`/잠재`·`/비틱`·`/경험치`)이 같은 choices·파서를 공유한다.
choice value 가 Realm.value(본서버/챌린저스)와 일치해 곧바로 realm 으로 해석된다.
"""

from __future__ import annotations

from discord import app_commands

from ..registration.realm import Realm

# 본서버가 첫 choice(기본). 파라미터는 optional 로 두고 미지정(None)을 본서버로 해석한다.
MODE_CHOICES = [
    app_commands.Choice(name=Realm.MAIN.value, value=Realm.MAIN.value),
    app_commands.Choice(name=Realm.CHALLENGERS.value, value=Realm.CHALLENGERS.value),
]

# 모드 파라미터 설명(rename 은 항상 "모드", describe 는 이 문구).
MODE_DESCRIBE = "조회할 서버 (기본 본서버, 챌린저스 캐릭터 등록 시 챌린저스 선택)"


def parse_mode(choice: app_commands.Choice[str] | None) -> Realm:
    """모드 choice → Realm. 미지정(None)·미상 값은 본서버(기본, 무상태)."""
    if choice is None:
        return Realm.MAIN
    return Realm.CHALLENGERS if choice.value == Realm.CHALLENGERS.value else Realm.MAIN
