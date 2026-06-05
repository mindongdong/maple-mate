"""비교 명령 공통 렌더 헬퍼 (handoff §2·§4). 얇은 discord 어댑터 — service 결과 → 임베드.

- 부분 성공: 성공분은 각 명령이 렌더, 실패분은 '⚠️ 조회 실패' 묶음 필드로 하단에 모음.
- 전체 실패: 에러 임베드 하나(실패 사유 행).
- 페이지네이션: `EmbedPaginator` 재사용.
- 데이터 기준 시점 푸터: 넥슨 응답 date(무지정 호출은 null → '최신 기준')를 format_footer 로.
"""
from __future__ import annotations

import io
import unicodedata
from collections.abc import Sequence
from datetime import datetime, timezone

import discord
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..registration.service import Target, TargetOutcome, get_targets
from . import table_image
from .embeds import EmbedPaginator, format_footer, make_embed

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
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


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
