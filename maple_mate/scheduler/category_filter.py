"""스케줄러 숙제 카테고리 필터 — opt-out 4묶음 (ADR-0014). 순수.

8개 [필드 파생 카테고리](ADR-0013)를 사용자 어휘 **4묶음(일일·주간·보스·길드)** 으로 묶어
표시 필터를 건다. 기본은 전부 켜짐 — 제외집합이 비면 8필드 전부 표시(기존과 100% 동일).

- 온디맨드(`/스케줄러`)는 **무상태**: 안 적은 파라미터=켜기(보임), 매 호출이 완전 선언(`parse_ondemand`).
- 알림 구독은 **tri-state 병합**: 미지정(None)=기존 유지, 켜기/끄기=델타(`merge_excluded`).
- 저장은 **EXCLUDED 집합** CSV(NULL/빈=제외 없음=전부 표시) — 하위·상위호환(`to_csv`/`from_csv`).

`modes.py` 와 동류로 app_commands.Choice 를 들이지만 로직은 순수(I/O·부작용 없음).
"""

from __future__ import annotations

from discord import app_commands

# 사용자 어휘 4묶음(ADR-0014 결정 1). 8필드 파생 카테고리를 1:N 매핑한 사용자 묶음.
BUCKET_DAILY = "일일"  # 일일 퀘스트 + 일일 콘텐츠
BUCKET_WEEKLY = "주간"  # 주간 퀘스트 + 주간 콘텐츠
BUCKET_BOSS = "보스"  # 일간·주간·월간 보스 + 기타 cycle 폴백
BUCKET_GUILD = "길드"  # 길드 콘텐츠(점수제)

# 표시·확인 메시지·직렬화 순서 고정(사용자 어휘 순). 파라미터 순서와 일치.
ALL_BUCKETS: tuple[str, ...] = (BUCKET_DAILY, BUCKET_WEEKLY, BUCKET_BOSS, BUCKET_GUILD)

# 켜기/끄기 Choice — notification 패턴 재사용(신규 컴포넌트 0, ADR-0014 결정 2).
CATEGORY_ON_OFF = [
    app_commands.Choice(name="켜기", value="on"),
    app_commands.Choice(name="끄기", value="off"),
]

_ON = "on"
_OFF = "off"


def _pairs(
    daily: app_commands.Choice[str] | None,
    weekly: app_commands.Choice[str] | None,
    boss: app_commands.Choice[str] | None,
    guild: app_commands.Choice[str] | None,
) -> tuple[tuple[str, app_commands.Choice[str] | None], ...]:
    """(묶음, 그 묶음 파라미터) 쌍 — parse/merge 공유. ALL_BUCKETS 순서."""
    return (
        (BUCKET_DAILY, daily),
        (BUCKET_WEEKLY, weekly),
        (BUCKET_BOSS, boss),
        (BUCKET_GUILD, guild),
    )


def parse_ondemand(
    daily: app_commands.Choice[str] | None,
    weekly: app_commands.Choice[str] | None,
    boss: app_commands.Choice[str] | None,
    guild: app_commands.Choice[str] | None,
) -> frozenset[str]:
    """온디맨드 4파라미터 → 제외집합. `off` 인 묶음만 제외, `None`/`on`=표시(무상태). 순수."""
    return frozenset(
        bucket
        for bucket, choice in _pairs(daily, weekly, boss, guild)
        if choice is not None and choice.value == _OFF
    )


def merge_excluded(
    stored: frozenset[str],
    *,
    daily: app_commands.Choice[str] | None,
    weekly: app_commands.Choice[str] | None,
    boss: app_commands.Choice[str] | None,
    guild: app_commands.Choice[str] | None,
) -> frozenset[str]:
    """구독 제외집합 tri-state 병합 — `off`→추가, `on`→제거, `None`→유지(ADR-0014 결정 2). 순수.

    신규 구독은 baseline=빈 제외(전부 켜짐)로 호출한다. 시각만 바꾸려 None 으로 재실행해도
    꺼둔 묶음이 그대로 유지된다(read-modify-write).
    """
    excluded = set(stored)
    for bucket, choice in _pairs(daily, weekly, boss, guild):
        if choice is None:
            continue
        if choice.value == _OFF:
            excluded.add(bucket)
        elif choice.value == _ON:
            excluded.discard(bucket)
    return frozenset(excluded)


def to_csv(excluded: frozenset[str]) -> str | None:
    """제외집합 → CSV(빈 집합→None=제외 없음). ALL_BUCKETS 순서로 안정 직렬화. 순수."""
    ordered = [b for b in ALL_BUCKETS if b in excluded]
    return ",".join(ordered) if ordered else None


def from_csv(value: str | None) -> frozenset[str]:
    """CSV → 제외집합. None/빈=빈 집합, 미상 토큰은 무시(상위호환). 순수."""
    if not value:
        return frozenset()
    tokens = {t.strip() for t in value.split(",")}
    return frozenset(t for t in tokens if t in ALL_BUCKETS)


def is_all_excluded(excluded: frozenset[str]) -> bool:
    """4묶음 전부 제외(극단 가드 — 빈 출력 방지, ADR-0014 결정 5). 순수."""
    return all(b in excluded for b in ALL_BUCKETS)


def summarize(excluded: frozenset[str]) -> str:
    """제외집합 → `표시: 일일·주간·보스 / 숨김: 길드` 한 줄(숨김 없으면 절 생략). 순수."""
    shown = [b for b in ALL_BUCKETS if b not in excluded]
    hidden = [b for b in ALL_BUCKETS if b in excluded]
    line = "표시: " + "·".join(shown) if shown else "표시: 없음"
    if hidden:
        line += " / 숨김: " + "·".join(hidden)
    return line
