"""스케줄러 알리미 비즈니스 로직 (전달-무관: 순수 + DB). discord/넥슨 타입 비의존.

- 순수: `parse_homework`(응답 → DTO, registration_flag 필터)·라인 빌더·`section_text`(1024 클램프).
- DB: 구독 토글/조회(scheduler_subscription)·`_resolve_self`(키 + realm 대표 ocid 해석).
DB 함수는 pg_insert/delete 통합 영역이라 단위테스트에서 제외한다(작업지시서 #5, 기존 방침).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql import func

from ..history.service import get_history_targets
from ..registration.realm import CHALLENGERS_NO_TARGET, Realm
from ..registration.service import get_targets
from .models import SchedulerSubscription

log = logging.getLogger(__name__)

# 기본 발송 시각(KST 시 단위). 앱이 켜기 upsert 마다 명시 → 모델/DB 에 default 없음(ADR-0012 결정 4).
DEFAULT_HOUR = 21

# Discord 임베드 필드 value 상한.
FIELD_LIMIT = 1024
_SEP = "\n"
# 오버플로 노트(`…외 NNNN개`) 자리 예약폭 — 마지막 직전까지 이만큼 남겨 합계가 한도를 안 넘게.
_NOTE_RESERVE = 12


# ── DTO (순수 파싱 산출) ─────────────────────────────────────────────────────


# 콘텐츠 카테고리 — 이름 특수케이스 없이 필드+구조프리픽스로 파생(ADR-0013, 라이브 9캐릭 조사).
# quest=완료/미완료(quest_state), [길드]프리픽스=길드 콘텐츠(점수제·완료개념 없음),
# max>1=회수형(몬스터파크), 그 외(max 0/1)=완료/미완료(에픽던전·무릉 포함, done=now>0).
CAT_QUEST = "quest"
CAT_GUILD = "guild"
CAT_BINARY = "binary"
CAT_COUNT = "count"

# 길드 콘텐츠 식별 — 콘텐츠명 `[길드]` 구조 프리픽스(주간 미션 포인트·플래그 레이스·지하 수로).
# 특정 이름이 아니라 NEXON 카테고리 프리픽스라 신규 길드 콘텐츠도 자동 분류(strip_prefix 와 동류).
_GUILD_PREFIX_RE = re.compile(r"^\s*\[길드\]")

# 보스 cycle(라이브 실측: bossDaily/bossWeekly/bossMonthly 3종뿐 — "시즌 보스"도 bossWeekly).
CYCLE_WEEKLY = "bossWeekly"
CYCLE_DAILY = "bossDaily"
CYCLE_MONTHLY = "bossMonthly"
_KNOWN_CYCLES = frozenset({CYCLE_WEEKLY, CYCLE_DAILY, CYCLE_MONTHLY})

# 주간 보스 처치 한도 — 실 API 는 12 를 반환하나 (0,0) 캐릭 관측 → 0/이상값이면 12 폴백.
WEEKLY_BOSS_LIMIT_FALLBACK = 12

# 보스 난이도 영문 enum → 한글(라이브: easy/normal/hard/chaos; extreme 대비).
_DIFFICULTY_KO = {
    "easy": "이지",
    "normal": "노멀",
    "hard": "하드",
    "chaos": "카오스",
    "extreme": "익스트림",
}


def difficulty_ko(difficulty: str) -> str:
    """보스 난이도 영문 → 한글(미상은 원문 유지). 순수."""
    return _DIFFICULTY_KO.get(difficulty.lower(), difficulty)


def weekly_boss_limit(value: int) -> int:
    """주간 보스 처치 한도 — API값 우선, 0/이상값이면 12 폴백(ADR-0013). 순수."""
    return value if value > 0 else WEEKLY_BOSS_LIMIT_FALLBACK


@dataclass(frozen=True)
class ContentItem:
    """일일/주간 콘텐츠 1건. type/quest_state/now/max 로 카테고리·완료를 파생(ADR-0013)."""

    name: str
    now_count: int
    max_count: int
    type: str = "contents"  # "contents" | "quest"
    quest_state: str = ""  # 퀘스트일 때 "0"기타 / "1"진행중(미완료) / "2"완료

    @property
    def category(self) -> str:
        if self.type == "quest":
            return CAT_QUEST
        if _GUILD_PREFIX_RE.match(self.name):
            return CAT_GUILD
        if self.max_count > 1:
            return CAT_COUNT
        return CAT_BINARY  # max 0/1 → 완료/미완료(에픽던전·무릉·에르다 등)

    @property
    def excluded(self) -> bool:
        """qs=0(기타: 미해금 엔드게임 일퀘 등)은 실행 불가 → 표시·집계 제외."""
        return self.type == "quest" and self.quest_state == "0"

    @property
    def done(self) -> bool:
        """완료 판정 — 퀘스트=quest_state '2', 길드=완료개념 없음(False), 회수형=now>=max,
        그 외(완료미완료)=now>0(상한 없는 에픽던전·무릉 포함)."""
        if self.category == CAT_QUEST:
            return self.quest_state == "2"
        if self.category == CAT_GUILD:
            return False
        if self.category == CAT_COUNT:
            return self.now_count >= self.max_count
        return self.now_count > 0

    @property
    def in_progress(self) -> bool:
        """게이지로 개별 표시할 부분 진행 — 회수형(max>1)의 0<now<max 만(퀘/길드/이진 제외)."""
        return self.category == CAT_COUNT and 0 < self.now_count < self.max_count

    @property
    def counts(self) -> bool:
        """전체 '남은/완료' 집계 대상 — 길드(점수제, 완료개념 없음)·제외(qs0)는 빠진다."""
        return not self.excluded and self.category != CAT_GUILD


@dataclass(frozen=True)
class BossItem:
    """보스 콘텐츠 1건. 완료는 complete_flag, 분류는 cycle(bossDaily/Weekly/Monthly)."""

    name: str
    difficulty: str
    done: bool
    cycle: str = ""


@dataclass(frozen=True)
class Homework:
    """한 캐릭터의 등록 숙제 묶음(registration_flag=='true' 필터 후)."""

    character_name: str
    world_name: str
    character_level: int
    daily: list[ContentItem]
    weekly: list[ContentItem]
    boss: list[BossItem]
    weekly_boss_clear_count: int
    weekly_boss_clear_limit: int

    @property
    def is_empty(self) -> bool:
        """등록된 숙제가 하나도 없음 → 빈 DM 금지(결정 7b)·온디맨드 안내."""
        return not (self.daily or self.weekly or self.boss)

    @property
    def remaining_total(self) -> tuple[int, int]:
        """(완료, 집계대상 총) — 점수형·qs0 제외, 보스는 전부 집계. 부제/상태색 신호용."""
        items = [c for c in (*self.daily, *self.weekly) if c.counts]
        done = sum(1 for c in items if c.done) + sum(1 for b in self.boss if b.done)
        return done, len(items) + len(self.boss)


# ── 파싱 (순수) ───────────────────────────────────────────────────────────────


def _to_int(value: object) -> int:
    """넥슨 정수 필드(가끔 문자열/None) → int. 실패는 0."""
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def _is_registered(raw: dict) -> bool:
    """인게임 스케줄러에 직접 등록한 항목인지(registration_flag 는 문자열 'true')."""
    return str(raw.get("registration_flag")) == "true"


def _parse_contents(raw_list: object) -> list[ContentItem]:
    items: list[ContentItem] = []
    for raw in raw_list or []:  # type: ignore[union-attr]
        if not isinstance(raw, dict) or not _is_registered(raw):
            continue
        items.append(
            ContentItem(
                name=str(raw.get("content_name", "")),
                now_count=_to_int(raw.get("now_count")),
                max_count=_to_int(raw.get("max_count")),
                type=str(raw.get("type") or "contents"),
                quest_state=str(raw.get("quest_state") or ""),
            )
        )
    return items


def _parse_bosses(raw_list: object) -> list[BossItem]:
    items: list[tuple[int, BossItem]] = []
    for raw in raw_list or []:  # type: ignore[union-attr]
        if not isinstance(raw, dict) or not _is_registered(raw):
            continue
        items.append(
            (
                _to_int(raw.get("list_order_no")),
                BossItem(
                    name=str(raw.get("content_name", "")),
                    difficulty=str(raw.get("difficulty") or ""),
                    done=str(raw.get("complete_flag")) == "true",
                    cycle=str(raw.get("cycle") or ""),
                ),
            )
        )
    # 리스트 순서(list_order_no) 오름차순 — 응답 순서가 흔들려도 안정 표시.
    items.sort(key=lambda pair: pair[0])
    return [boss for _, boss in items]


def parse_homework(data: dict) -> Homework:
    """넥슨 scheduler/character-state 응답 → Homework(등록 항목만). 순수 — 단위테스트 대상."""
    return Homework(
        character_name=str(data.get("character_name", "")),
        world_name=str(data.get("world_name") or ""),
        character_level=_to_int(data.get("character_level")),
        daily=_parse_contents(data.get("daily_contents")),
        weekly=_parse_contents(data.get("weekly_contents")),
        boss=_parse_bosses(data.get("boss_contents")),
        weekly_boss_clear_count=_to_int(data.get("weekly_boss_clear_count")),
        weekly_boss_clear_limit=_to_int(data.get("weekly_boss_clear_limit_count")),
    )


# ── 렌더링 (순수, 필드 파생 카테고리 — ADR-0013) ──────────────────────────────
#
# 할 일 우선(todo-first): 미완료를 주인공으로 개별 표시, 완료는 수+이름 한 줄로 접는다. 헤더는
# `남은 N + 완료/총` 숫자만(진행바 없음). 콘텐츠명 앞 `[..]` 구조 프리픽스는 떼고 길면 말줄임한다.

_PREFIX_RE = re.compile(r"^\s*\[[^\]]*\]\s*")  # 선두 `[..]` 한 그룹
_NAME_MAX = 18  # 표시 이름 최대 길이(모바일 줄바꿈 방지)
_DONE_BUDGET = 800  # 완료 이름 join 클램프(필드 1024 내 여유)


def section_text(lines: Sequence[str], limit: int = FIELD_LIMIT) -> str:
    """라인들을 줄바꿈으로 합치되 임베드 필드 상한(1024) 초과 시 `…외 N개`로 클램프(순수)."""
    if not lines:
        return ""
    out: list[str] = []
    used = 0
    last = len(lines) - 1
    for i, line in enumerate(lines):
        addition = (len(_SEP) if out else 0) + len(line)
        # 마지막 라인이 아니면 노트 자리(_NOTE_RESERVE)를 남겨 합계가 한도를 넘지 않게 한다.
        budget = limit if i == last else limit - _NOTE_RESERVE
        if used + addition > budget:
            out.append(f"…외 {len(lines) - i}개")
            break
        out.append(line)
        used += addition
    return _SEP.join(out)


def strip_prefix(name: str) -> str:
    """콘텐츠명 앞 `[...]` 프리픽스 제거(없으면 그대로). 순수."""
    return _PREFIX_RE.sub("", name, count=1).strip()


def truncate(name: str, limit: int = _NAME_MAX) -> str:
    """프리픽스 제거 후 말줄임(… 포함 limit 자). 순수."""
    name = strip_prefix(name)
    return name if len(name) <= limit else name[: limit - 1] + "…"


def join_clamp(names: Sequence[str], limit: int = _DONE_BUDGET) -> str:
    """이름들을 ` · ` 로 잇되 한도 초과분은 `…외 K개`로 접는다(완료 한 줄). 순수."""
    out: list[str] = []
    used = 0
    for i, name in enumerate(names):
        addition = (3 if out else 0) + len(name)  # " · "
        if used + addition > limit:
            return " · ".join(out) + f" …외 {len(names) - i}개"
        out.append(name)
        used += addition
    return " · ".join(out)


# ── 카테고리 버킷·집계(순수) ─────────────────────────────────────────────────


def by_category(items: Sequence[ContentItem], category: str) -> list[ContentItem]:
    """그 카테고리의 등록 항목(qs0 기타 제외). 순수."""
    return [c for c in items if c.category == category and not c.excluded]


def bosses_by_cycle(bosses: Sequence[BossItem], cycle: str) -> list[BossItem]:
    """그 cycle 보스. 순수."""
    return [b for b in bosses if b.cycle == cycle]


def bosses_other_cycle(bosses: Sequence[BossItem]) -> list[BossItem]:
    """알려진 3 cycle(일/주/월) 밖의 보스(폴백 필드용). 순수."""
    return [b for b in bosses if b.cycle not in _KNOWN_CYCLES]


def field_counts(items: Sequence[ContentItem]) -> tuple[int, int]:
    """(완료 수, 집계 수) — 카테고리 필드 헤더용(qs0 제외). 순수."""
    active = [c for c in items if not c.excluded]
    return sum(1 for c in active if c.done), len(active)


def boss_counts(items: Sequence[BossItem]) -> tuple[int, int]:
    """(처치 수, 전체 수). 순수."""
    return sum(1 for b in items if b.done), len(items)


# ── 카테고리 본문(순수) ───────────────────────────────────────────────────────


def content_field_value(items: Sequence[ContentItem]) -> str:
    """퀘스트/회수/완료미완료 본문 — 진행중(게이지) → 미완료 ⬜ → 완료 수+이름. 순수.

    진행중(회수형 0<now<max)만 달성률 내림차순 게이지. 나머지 미완료는 `⬜ 이름`(0/100 도배 소멸).
    완료는 수와 이름을 한 줄로 접는다(qs0 기타는 사전 제외).
    """
    active = [c for c in items if not c.excluded]
    in_progress = sorted(
        (c for c in active if c.in_progress),
        key=lambda c: c.now_count / c.max_count,
        reverse=True,
    )
    todo = [c for c in active if not c.done and not c.in_progress]
    done = [c for c in active if c.done]

    lines: list[str] = []
    for c in in_progress:
        lines.append(f"🟡 {truncate(c.name)} `{c.now_count}/{c.max_count}`")
    for c in todo:
        lines.append(f"⬜ {truncate(c.name)}")
    if done:
        names = join_clamp([truncate(c.name) for c in done])
        lines.append(f"✅ 완료 {len(done)}개 · {names}")
    return section_text(lines)


def guild_field_value(items: Sequence[ContentItem]) -> str:
    """길드 콘텐츠(점수제) 본문 — now==0 ⬜(아직 안 함), now>0 이름+점수. 완료개념 없음. 순수."""
    lines: list[str] = []
    for c in items:
        name = truncate(c.name)
        if c.now_count == 0:
            lines.append(f"⬜ {name}")
        else:
            lines.append(f"🔹 {name} `{c.now_count}`")
    return section_text(lines)


def boss_cycle_value(items: Sequence[BossItem]) -> str:
    """한 cycle 보스 본문 — 미처치 ⬜ 이름(난이도) → 처치 수+이름. '뭘 잡아야 하나' 우선. 순수."""
    not_done = [b for b in items if not b.done]
    done = [b for b in items if b.done]
    lines: list[str] = []
    for b in not_done:
        name = truncate(b.name)
        diff = difficulty_ko(b.difficulty)
        lines.append(f"⬜ {name}({diff})" if diff else f"⬜ {name}")
    if done:
        names = join_clamp([truncate(b.name) for b in done])
        lines.append(f"✅ 처치 {len(done)}개 · {names}")
    return section_text(lines)


# ── 구독(DB) ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Subscription:
    """구독 1건(전달/잡 공유). realm 은 Realm enum 으로 디코드."""

    guild_id: int
    discord_user_id: int
    realm: Realm
    hour: int


def _realm_of_value(value: str) -> Realm:
    """저장된 realm 디스크리미넌트 → Realm(예상 외 값은 본서버로 폴백)."""
    return Realm.CHALLENGERS if value == Realm.CHALLENGERS.value else Realm.MAIN


async def set_subscription(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    guild_id: int,
    discord_user_id: int,
    realm: Realm,
    hour: int,
) -> None:
    """구독 켜기 upsert — (guild, user, realm) 에 hour 저장(같은 realm 재호출 = 시각 갱신)."""
    async with session_factory() as session:
        stmt = (
            pg_insert(SchedulerSubscription)
            .values(
                guild_id=guild_id,
                discord_user_id=discord_user_id,
                realm=realm.value,
                hour=hour,
            )
            .on_conflict_do_update(
                index_elements=["guild_id", "discord_user_id", "realm"],
                set_={"hour": hour, "updated_at": func.now()},
            )
        )
        await session.execute(stmt)
        await session.commit()


async def clear_subscription(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    guild_id: int,
    discord_user_id: int,
    realm: Realm,
) -> bool:
    """구독 끄기 delete. 실제로 지운 행이 있으면 True(없던 구독 끄기는 False → 안내 분기)."""
    async with session_factory() as session:
        result = await session.execute(
            delete(SchedulerSubscription).where(
                SchedulerSubscription.guild_id == guild_id,
                SchedulerSubscription.discord_user_id == discord_user_id,
                SchedulerSubscription.realm == realm.value,
            )
        )
        await session.commit()
    return (result.rowcount or 0) > 0


async def subscriptions_at_hour(
    session_factory: async_sessionmaker[AsyncSession], hour: int
) -> list[Subscription]:
    """그 시각(hour) 구독 전체(cron 디스패치 조회). realm 별 독립 행."""
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(SchedulerSubscription).where(SchedulerSubscription.hour == hour)
            )
        ).scalars()
        subs = [
            Subscription(
                guild_id=r.guild_id,
                discord_user_id=r.discord_user_id,
                realm=_realm_of_value(r.realm),
                hour=r.hour,
            )
            for r in rows
        ]
    return subs


# ── 본인 키 + realm 대표 ocid 해석 (DB, bitik _self_target 패턴) ──────────────


async def resolve_self(
    session_factory: async_sessionmaker[AsyncSession],
    guild_id: int,
    discord_user_id: int,
    realm: Realm,
) -> tuple[str | None, str | None, str | None]:
    """(개인 키 암호문, realm 대표 ocid, 에러 메시지). 성공이면 에러 None, 실패면 앞 둘이 None.

    개인 키는 계정 단위(realm 무관), 대표 ocid 는 그 realm 대표(per-character). 가드 순서:
    미등록 → 키 미등록 → realm 대표 없음(fail fast 구독 가드·온디맨드 공통, 결정 7).
    """
    history_targets = await get_history_targets(
        session_factory, guild_id, [discord_user_id]
    )
    if not history_targets:
        return None, None, "이 서버에 등록되지 않았어요. `/캐릭터등록` 먼저 해주세요."
    key_encrypted = history_targets[0].api_key_encrypted
    if key_encrypted is None:
        return (
            None,
            None,
            "개인 키 미등록이라 스케줄러를 볼 수 없어요. `/키등록`으로 키를 추가해 주세요.",
        )
    rep_targets = await get_targets(session_factory, guild_id, [discord_user_id], realm)
    if not rep_targets:
        msg = (
            CHALLENGERS_NO_TARGET
            if realm is Realm.CHALLENGERS
            else "등록된 본서버 캐릭터가 없어요. `/캐릭터등록` 먼저 해주세요."
        )
        return None, None, msg
    return key_encrypted, rep_targets[0].ocid, None
