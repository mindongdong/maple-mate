"""realm(본서버/챌린저스) 판정 — 순수 술어 + 모드 enum (ADR-0009).

realm 신호 = `Character.world` 접두 `챌린저스`. NULL/빈값 = 본서버(레거시). `챌린저스N` 은
전부 한 realm 으로 본다. discord/sqlalchemy 비의존 — 어디서든 import 가능(순환 회피).

핵심 불변식: 본서버 비교·리더보드에 챌린저스 캐릭터가 절대 섞이지 않는다(위반=버그).
"""

from __future__ import annotations

from enum import Enum

# realm 신호 접두. `챌린저스3` 처럼 번호가 붙어도 전부 한 realm(결정 3).
CHALLENGERS_PREFIX = "챌린저스"


class Realm(str, Enum):
    """캐릭터/명령이 속한 서버 구분. 값은 `모드` 파라미터 choices 와 일치(본서버/챌린저스, 결정 2)."""

    MAIN = "본서버"
    CHALLENGERS = "챌린저스"


def is_challengers(world: str | None) -> bool:
    """world_name 이 챌린저스 서버인지(realm 신호). NULL/빈값 = 본서버(레거시)."""
    return bool(world) and world.startswith(CHALLENGERS_PREFIX)


def realm_of(world: str | None) -> Realm:
    """world_name → realm. 챌린저스 접두면 CHALLENGERS, 그 외(NULL 포함)는 MAIN."""
    return Realm.CHALLENGERS if is_challengers(world) else Realm.MAIN


def in_realm(world: str | None, realm: Realm) -> bool:
    """이 world 의 캐릭터가 주어진 realm 에 속하는가(get_targets realm 필터 술어)."""
    return realm_of(world) is realm


_LABEL_PREFIX = "🏆 챌린저스"


def realm_prefix(realm: Realm) -> str:
    """제목 프리픽스. 챌린저스만 `🏆 챌린저스 `, 본서버는 빈 문자열(시각적 회귀 0, 결정 9)."""
    return f"{_LABEL_PREFIX} " if realm is Realm.CHALLENGERS else ""


def realm_title(base: str, realm: Realm) -> str:
    """임베드/표 제목에 realm 라벨 적용. 본서버는 base 그대로(무라벨)."""
    return f"{realm_prefix(realm)}{base}"
