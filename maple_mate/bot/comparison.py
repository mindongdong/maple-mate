"""비교 명령 공통 렌더 헬퍼 (handoff §2·§4). 얇은 discord 어댑터 — service 결과 → 임베드.

- 부분 성공: 성공분은 각 명령이 렌더, 실패분은 '⚠️ 조회 실패' 묶음 필드로 하단에 모음.
- 전체 실패: 에러 임베드 하나(실패 사유 행).
- 페이지네이션: `EmbedPaginator` 재사용.
- 데이터 기준 시점 푸터: 넥슨 응답 date(무지정 호출은 null → '최신 기준')를 format_footer 로.
"""
from __future__ import annotations

from datetime import datetime, timezone

import discord
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..registration.service import Target, TargetOutcome, get_targets
from .embeds import EmbedPaginator, format_footer, make_embed

_MAX_FIELD = 1024


async def resolve_targets(
    session_factory: async_sessionmaker[AsyncSession],
    guild_id: int,
    members: list[discord.Member],
) -> tuple[list[Target], list[TargetOutcome]]:
    """지정 멤버 → 등록 Target 목록 + 미등록 멤버의 실패 outcome.

    members 비어 있으면 서버 전체 등록자(미등록 outcome 없음). 지정했지만 미등록인 멤버는
    부분 성공 행("미등록")으로 돌려준다(handoff §4: 미등록 유저는 대상에서 제외하되 안내).
    """
    user_ids = [m.id for m in members] or None
    targets = await get_targets(session_factory, guild_id, user_ids)
    if user_ids is None:
        return targets, []
    registered = {t.discord_user_id for t in targets}
    missing = [
        TargetOutcome(
            target=Target(
                guild_id=guild_id,
                discord_user_id=m.id,
                nickname=m.display_name,
                ocid="",
            ),
            error="이 서버에 등록되지 않았어요. `/등록` 먼저 해주세요.",
        )
        for m in members
        if m.id not in registered
    ]
    return targets, missing


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


def all_failed_embed(title: str, outcomes: list[TargetOutcome], *, footer: str | None = None) -> discord.Embed:
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
