"""비교 명령 공통 렌더 헬퍼 (handoff §2·§4). 얇은 discord 어댑터 — service 결과 → 임베드.

- 부분 성공: 성공분은 각 명령이 렌더, 실패분은 '⚠️ 조회 실패' 묶음 필드로 하단에 모음.
- 전체 실패: 에러 임베드 하나(실패 사유 행).
- 페이지네이션: `EmbedPaginator` 재사용.
- 데이터 기준 시점 푸터: 넥슨 응답 date(무지정 호출은 null → '최신 기준')를 format_footer 로.
"""

from __future__ import annotations

import io
import random
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

import discord
from discord import app_commands
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..nexon.client import NexonClient
from ..registration.realm import CHALLENGERS_NO_TARGET, Realm
from ..registration.service import (
    Target,
    TargetOutcome,
    find_guild_characters_by_nicknames,
    get_targets,
    resolve_guest_target,
)
from . import table_image
from .embeds import EmbedPaginator, append_source, format_footer, make_embed

_MAX_FIELD = 1024


# ── 유저 태그(멘션) + 이미지 정렬표 — 비교 가독성 (디스코드 임베드 표 부재 대응) ──
#
# 디스코드 텍스트표(코드블록)는 한글 폭·임베드 너비 때문에 정렬을 보장 못 한다(깨짐).
# → 수치 비교표는 PNG 이미지(픽셀 고정)로 첨부하고, 닉↔주인 매핑은 이미지 위 '범례'(클릭 태그)로.
# 멘션은 이미지 안엔 못 넣으므로(이미지=픽셀) 범례에만 둔다. 핑(알림)은 봇 전역
# allowed_mentions=none 으로 막으므로 태그가 도배 알림을 만들지 않는다.


def mention(target: Target) -> str:
    """대상의 디스코드 유저 클릭 태그. 미등록(ocid 빈) 등 id 없으면 빈 문자열."""
    return f"<@{target.discord_user_id}>" if target.discord_user_id else ""


def _display_width(text: str) -> int:
    """표시 폭(한글·전각=2, 그 외=1) — 긴 닉/직업을 폭 기준으로 자를 때 사용."""
    return sum(
        2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text
    )


def truncate_display(text: str, max_width: int) -> str:
    """표시 폭 기준 자르기(넘으면 '…'). 긴 닉/직업이 표를 과하게 넓히지 않도록."""
    if _display_width(text) <= max_width:
        return text
    out: list[str] = []
    width = 0
    for ch in text:
        cw = 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
        if width + cw > max_width - 1:
            break
        out.append(ch)
        width += cw
    return "".join(out) + "…"


def highest_indices(values: Sequence[float | None]) -> set[int]:
    """단순 수치 비교가 가능한 컬럼에서 '가장 높은 값'을 가진 행 인덱스 집합.

    None(미조회·해당없음)은 후보에서 제외하고, 동률이면 모두 포함한다. 유효값이 하나도
    없으면 빈 집합(강조 없음). 호출자는 이 인덱스의 셀을 `table_image.Highlight` 로 감싼다.
    """
    valid = [v for v in values if v is not None]
    if not valid:
        return set()
    top = max(valid)
    return {i for i, v in enumerate(values) if v is not None and v == top}


def owner_legend(targets: list[Target]) -> str:
    """이미지 위 범례: '닉 @주인 · 닉2 @주인2' (클릭 태그). 닉↔디스코드 유저 매핑."""
    parts = [f"{t.nickname} {mention(t)}".strip() for t in targets]
    return "👤 " + "  ·  ".join(parts) if parts else ""


def image_message(
    title: str,
    png: bytes,
    targets: list[Target],
    *,
    footer: str | None = None,
    outcomes: list[TargetOutcome] | None = None,
    filename: str = "image.png",
) -> tuple[discord.Embed, discord.File]:
    """이미 렌더된 PNG 를 비교 임베드로. (임베드, 첨부파일) 반환 — 호출자가 send.

    임베드 설명=범례(닉↔태그 클릭), 이미지=PNG, 실패분은 '조회 실패' 묶음 필드.
    표(render_table_image)·아이템 카드(item_card) 등 어떤 PNG 든 공통으로 쓴다.
    """
    file = discord.File(io.BytesIO(png), filename=filename)
    embed = make_embed(title, owner_legend(targets) or None, footer=footer)
    embed.set_image(url=f"attachment://{filename}")
    if outcomes:
        attach_failures([embed], outcomes)
    return embed, file


def table_image_message(
    title: str,
    headers: list[str],
    rows: list[list[str]],
    targets: list[Target],
    *,
    aligns: list[str] | None = None,
    footer: str | None = None,
    outcomes: list[TargetOutcome] | None = None,
    filename: str = "table.png",
) -> tuple[discord.Embed, discord.File]:
    """수치 비교를 '깨지지 않는' PNG 표로. (임베드, 첨부파일) 반환 — 호출자가 send.

    임베드 설명=범례(targets 로 만든 닉↔태그 클릭 범례), 이미지=표 PNG, 실패분은 임베드 필드.
    """
    png = table_image.render_table_image(headers, rows, aligns=aligns)
    return image_message(
        title, png, targets, footer=footer, outcomes=outcomes, filename=filename
    )


async def resolve_targets(
    session_factory: async_sessionmaker[AsyncSession],
    guild_id: int,
    members: list[discord.Member],
    realm: Realm | None = None,
) -> tuple[list[Target], list[TargetOutcome]]:
    """지정 멤버 → 등록 Target 목록 + 미등록 멤버의 실패 outcome.

    members 비어 있으면 서버 전체 등록자(미등록 outcome 없음). 지정했지만 미등록인 멤버는
    부분 성공 행("미등록")으로 돌려준다(handoff §4: 미등록 유저는 대상에서 제외하되 안내).

    realm=None 은 realm 무필터(전 realm) — `/유니온`(realm 거름 '—', 코드 무변경)의 기존 동작.
    `/스펙`·`/아이템` 은 명시적 realm(본서버/챌린저스)을 넘긴다. 챌린저스 모드에선 그 realm
    캐릭터 미보유 멤버를 '챌린저스 캐릭터 미등록' 부분성공 행으로(결정 5). 본서버/무필터 문구는
    기존 유지(시각 회귀 0).
    """
    user_ids = [m.id for m in members] or None
    targets = await get_targets(session_factory, guild_id, user_ids, realm)
    if user_ids is None:
        return targets, []
    registered = {t.discord_user_id for t in targets}
    error = (
        CHALLENGERS_NO_TARGET
        if realm is Realm.CHALLENGERS
        else "이 서버에 등록되지 않았어요. `/캐릭터등록` 먼저 해주세요."
    )
    missing = [
        TargetOutcome(
            target=Target(
                guild_id=guild_id,
                discord_user_id=m.id,
                nickname=m.display_name,
                ocid="",
            ),
            error=error,
        )
        for m in members
        if m.id not in registered
    ]
    return targets, missing


# ── 닉네임 직접 지정 (ADR-0021) ───────────────────────────────────────────
#
# `/스펙`·`/아이템`·`/유니온` 의 `닉네임` 파라미터(쉼표 구분). 유저 슬롯과 합쳐 최대 5명.
# 등록 캐릭터와 닉이 일치하면 그 캐릭터, 아니면 `/id` 로 해석한 게스트 대상(미등록·비저장).

MAX_SPECIFIED_TARGETS = 5
NICKNAMES_DESCRIBE = (
    "메이플 닉네임 (쉼표로 여러 명 · 유저와 합쳐 최대 5명 · 미등록 캐릭터도 가능)"
)
TOO_MANY_TARGETS = (
    f"유저와 닉네임을 합쳐 최대 {MAX_SPECIFIED_TARGETS}명까지 지정할 수 있어요."
)


def parse_nicknames(raw: str | None) -> list[str]:
    """'a, b ,A' → ['a', 'b'] — 공백 제거·빈 토큰 무시·대소문자 무시 중복 제거(첫 표기 유지)."""
    if not raw:
        return []
    names: list[str] = []
    seen: set[str] = set()
    for token in raw.split(","):
        name = token.strip()
        if name and name.lower() not in seen:
            seen.add(name.lower())
            names.append(name)
    return names


def too_many_targets(members: Sequence[object], nicknames: Sequence[str]) -> bool:
    """유저 슬롯 + 닉네임 합계가 지정 상한을 넘는가(넘으면 조회 전 ephemeral 거부)."""
    return len(members) + len(nicknames) > MAX_SPECIFIED_TARGETS


class TooManyTargets(app_commands.CheckFailure):
    """지정 상한 초과 — 트리 공통 에러 핸들러가 ephemeral 로 안내한다(bot/core.py)."""


def target_limit_check() -> Callable:
    """유저 슬롯 + 닉네임 합계 상한 검사(명령 체크). 실패 시 TooManyTargets.

    **쿨다운 데코레이터 아래**(함수 쪽)에 둔다 — 체크는 함수에 가까운 것부터 실행되므로 거부가
    쿨다운 토큰을 소모하지 않는다. namespace 키는 rename 된 이름이라 닉네임은 '닉네임'으로 읽는다.
    """

    async def predicate(interaction: discord.Interaction) -> bool:
        namespace = interaction.namespace
        members = [
            v for _, v in namespace if isinstance(v, (discord.Member, discord.User))
        ]
        nicknames = parse_nicknames(getattr(namespace, "닉네임", None))
        if too_many_targets(members, nicknames):
            raise TooManyTargets(TOO_MANY_TARGETS)
        return True

    return app_commands.check(predicate)


async def resolve_mixed_targets(
    session_factory: async_sessionmaker[AsyncSession],
    nexon: NexonClient,
    guild_id: int,
    members: list[discord.Member],
    nicknames: list[str],
    realm: Realm | None = None,
    *,
    command: str | None = None,
) -> tuple[list[Target], list[TargetOutcome]]:
    """유저 슬롯 + 닉네임 → (Target 목록, 실패 outcome). 닉네임이 없으면 resolve_targets 그대로.

    순서 = 유저(입력순) → 닉네임(입력순), ocid 중복은 첫 번째만 남긴다. 닉은 등록 캐릭터 우선
    (넥슨 0콜·소유자 태그), 미일치만 `/id` 1콜로 게스트 대상. 무인자(둘 다 빈) 판정은 호출자 몫.
    """
    if not nicknames:
        return await resolve_targets(session_factory, guild_id, members, realm)

    targets: list[Target] = []
    missing: list[TargetOutcome] = []
    if members:
        targets, missing = await resolve_targets(
            session_factory, guild_id, members, realm
        )
    seen = {t.ocid for t in targets}
    matched = await find_guild_characters_by_nicknames(
        session_factory, guild_id, nicknames
    )
    for nickname in nicknames:
        target = matched.get(nickname.lower())
        if target is None:
            outcome = await resolve_guest_target(
                nexon, session_factory, guild_id, nickname, command=command
            )
            if not outcome.ok:
                missing.append(outcome)
                continue
            target = outcome.target
        if target.ocid in seen:
            continue
        seen.add(target.ocid)
        targets.append(target)
    return targets, missing


# ── 무인자 팬아웃 경계 (ADR-0008 부분개정) ─────────────────────────────────
#
# 무인자 실행(등록자 전원)은 인원이 늘수록 PNG 가 세로로 무한히 길어지고(가독성),
# 넥슨 팬아웃(전역 4req/s 스로틀)으로 응답이 느려진다 → K=10 명으로 경계.
# 선정 = **명령 실행 본인 무조건 포함 + 나머지 랜덤**(대표 레벨 상위 → 공평성 개정). 상위권만
# 반복 노출돼 불공평하다는 판단에 따라 랜덤 비복원 추출로 바꿨다(매 실행 독립).
# 대상을 지정하면 파라미터 슬롯(최대 5명)이 이미 상한이라 여기 적용하지 않는다.

MAX_UNSPECIFIED_TARGETS = 10


def select_with_self(
    targets: Sequence,
    self_id: int,
    cap: int = MAX_UNSPECIFIED_TARGETS,
    *,
    rng: random.Random | None = None,
) -> tuple[list, int, bool]:
    """무인자 대상 선정 — 실행 본인 무조건 포함 + 나머지 랜덤. (선정 목록, 전체 N, 본인 포함 여부).

    N ≤ cap 이면 전원(원 순서 유지, 랜덤 없음). N > cap 이면 본인(있으면) 고정 + 나머지는
    `random.sample`(비복원)로 cap 을 채운다 — 본인은 선정 목록 맨 앞. 본인이 풀에 없으면
    조용히 랜덤 cap 명(호출자가 사유별 안내 한 줄 붙임). 매 실행 독립(시드 없음) — `rng`
    주입은 테스트 결정성용. Target·HistoryTarget 둘 다 받는다(discord_user_id 덕 타이핑).
    """
    total = len(targets)
    if total <= cap:
        return list(targets), total, any(t.discord_user_id == self_id for t in targets)
    picker = rng or random
    self_targets = [t for t in targets if t.discord_user_id == self_id]
    others = [t for t in targets if t.discord_user_id != self_id]
    self_included = bool(self_targets)
    take = cap - len(self_targets)
    chosen = picker.sample(others, take)
    return self_targets + chosen, total, self_included


def fanout_note(
    total: int, cap: int = MAX_UNSPECIFIED_TARGETS, *, noun: str = "등록자"
) -> str:
    """무인자 푸터 한 줄 — 항상 표시, 인원수로 문구 분기(ADR-0008 부분개정 — 상시화).

    N ≤ cap 이면 '전원 비교' 안내, N > cap 이면 '본인 포함 랜덤 cap 명' 안내.
    """
    if total <= cap:
        return f"{noun} 전원({total}명)을 비교했어요"
    return (
        f"{noun} {total}명 중 본인 포함 랜덤 {cap}명을 비교했어요 · "
        f"특정 인원은 대상 지정(최대 5명)으로 볼 수 있어요"
    )


@dataclass(frozen=True)
class ComparisonMessage:
    """비교 결과 1건(임베드 + 선택 첨부). 탭 전환이 같은 모양으로 교체한다(ADR-0022)."""

    embed: discord.Embed
    file: discord.File | None = None  # None = 첨부 없음(단일 상세·전원 실패)


def footer_with_notes(raw_date: str | None, notes: Sequence[str] = ()) -> str:
    """안내 줄들(위→아래 표시 순) + 데이터 시점·출처 푸터."""
    return "\n".join([*notes, append_source(data_footer(raw_date))])


def data_footer(raw_date: str | None, now: datetime | None = None) -> str:
    """넥슨 응답 date → 푸터 텍스트. null(무지정 최신 스냅샷) → '최신 기준'."""
    now = now or datetime.now(timezone.utc)
    if not raw_date:
        return "최신 기준"
    try:
        dt = datetime.fromisoformat(raw_date)
    except ValueError:
        return "최신 기준"
    return format_footer(dt, now)


def _failure_lines(outcomes: list[TargetOutcome]) -> list[str]:
    return [f"• **{o.target.nickname}** — {o.error}" for o in outcomes if not o.ok]


def _clip(value: str) -> str:
    if len(value) <= _MAX_FIELD:
        return value
    return value[: _MAX_FIELD - 2].rstrip() + "\n…"


def attach_failures(pages: list[discord.Embed], outcomes: list[TargetOutcome]) -> None:
    """실패 대상을 '조회 실패' 묶음 필드로 각 페이지 하단에 추가(실패 없으면 미추가).

    모든 페이지에 붙여 어느 페이지를 보든 누락 인원이 보이게 한다(handoff §4 부분 성공).
    """
    lines = _failure_lines(outcomes)
    if not lines:
        return
    name = f"⚠️ 조회 실패 ({len(lines)}명)"
    value = _clip("\n".join(lines))
    for embed in pages:
        embed.add_field(name=name, value=value, inline=False)


# 임베드 1장 누적 문자수 예산(Discord 6000 제한). attach_failures 가 페이지마다 실패 필드를
# (최대 ~1KB) 추가하므로 그만큼 여유를 두고 페이지를 나눈다.
_MAX_EMBED_TOTAL = 4500


def field_pages(
    title: str,
    fields: list[tuple[str, str]],
    *,
    per_page: int = 10,
    footer: str | None = None,
) -> list[discord.Embed]:
    """(이름, 값) 필드들을 페이지로 나눈다. per_page(필드 수) + 누적 문자수 예산 둘 다로 분할.

    2장+면 제목에 (i/N) 표기. 각 값은 1024 로 클립. 빈 입력은 빈 페이지 1장.
    """
    base_len = len(title) + (len(footer) if footer else 0)
    chunks: list[list[tuple[str, str]]] = []
    current: list[tuple[str, str]] = []
    current_len = 0
    for name, raw_value in fields:
        value = _clip(raw_value)
        field_len = len(name) + len(value)
        over_count = len(current) >= per_page
        over_budget = base_len + current_len + field_len > _MAX_EMBED_TOTAL
        if current and (over_count or over_budget):
            chunks.append(current)
            current = []
            current_len = 0
        current.append((name, value))
        current_len += field_len
    chunks.append(current)  # 마지막(또는 빈 입력 → 빈 페이지)

    total = len(chunks)
    pages: list[discord.Embed] = []
    for idx, chunk in enumerate(chunks, start=1):
        page_title = title if total == 1 else f"{title} ({idx}/{total})"
        embed = make_embed(page_title, footer=footer)
        for name, value in chunk:  # 이미 클립됨
            embed.add_field(name=name, value=value, inline=False)
        pages.append(embed)
    return pages


def all_failed_embed(
    title: str, outcomes: list[TargetOutcome], *, footer: str | None = None
) -> discord.Embed:
    """전체 실패 시 에러 임베드(실패 사유 행)."""
    body = _clip("\n".join(_failure_lines(outcomes)) or "조회된 대상이 없어요.")
    return make_embed(title, body, footer=footer)


async def respond_with_pages(
    interaction: discord.Interaction,
    pages: list[discord.Embed],
    *,
    author_id: int | None = None,
) -> None:
    """defer 된 상호작용에 페이지 전송. 2장+면 버튼 페이지네이션."""
    if len(pages) == 1:
        await interaction.followup.send(embed=pages[0])
        return
    view = EmbedPaginator(pages, author_id=author_id)
    await interaction.followup.send(embed=view.current, view=view)
