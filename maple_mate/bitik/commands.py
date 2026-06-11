"""`/비틱` 디스코드 어댑터 (얇은 전달 계층). 스타포스·잠재·득템 자랑 카드.

`app_commands.Group` 서브커맨드 3개(Q2). 대상은 실행자 본인만(Q1, 개인 키 필수).
흐름(Q4): 목록 ephemeral(select) → 선택 확정 시 채널에 **공개** 카드 발송.
select View 는 코드베이스 최초의 동적 컴포넌트 — 120초 타임아웃, 선택 1회 후 비활성.
"""

from __future__ import annotations

import asyncio
import io
import logging
import random
from collections.abc import Awaitable, Callable
from datetime import date, datetime

import discord
from discord import app_commands
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..bot import bitik_card, comparison, cooldowns
from ..bot.embeds import KST, append_source, defer, make_embed
from ..character.service import format_eok
from ..dependencies import Deps
from ..error_log import service as error_log
from ..history import potential_cost
from ..history.equipment_level import (
    fetch_equipped_levels,
    learn_equipment_levels,
    load_learned_levels,
    match_level,
)
from ..history.potential_service import fetch_potential_records
from ..history.service import (
    DEFAULT_PRESET,
    HistoryTarget,
    fetch_starforce_records,
    get_history_targets,
    resolve_period,
)
from ..nexon.errors import NexonAPIError, to_error_log_type
from ..registration.service import classify_target_error
from .service import (
    ExcludedItems,
    PotentialBitik,
    StarforceBitik,
    group_potential,
    group_starforce,
)

log = logging.getLogger(__name__)

_PERIOD_CHOICES = [
    app_commands.Choice(name=p, value=p)
    for p in (
        "오늘",
        "어제",
        "최근7일",
        "최근30일",
        "최근90일",
        "최근1년",
        "이번주",
        "이번달",
    )
]

_SELECT_LIMIT = 25  # Discord select 옵션 상한(Q3)
_VIEW_TIMEOUT = 120.0  # select 타임아웃(파생 결정)
_NO_RECORD = "자랑할 기록이 없네요."

# 득템 비틱 톤 랜덤 문구 풀(Q9). `코멘트` 파라미터 입력 시 그 문구 사용.
PICKUP_PHRASES: tuple[str, ...] = (
    "이거 좋은건가요? ㅎㅎ",
    "별거 아닌데 그냥 올려봐요 ㅎ",
    "방금 주웠는데 쓸만한가요?",
    "오늘 운이 좀 따르네요 ㅎㅎ",
    "처분하기도 그렇고... 일단 올립니다",
    "이런 게 다 떨어지네요;;",
    "겸손하게 한 장 올려봅니다",
    "줍줍 성공 ㅎㅎ",
)


# ── 순수 헬퍼 ───────────────────────────────────────────────────────────────


def _parse_date(raw: str | None) -> tuple[date | None, bool]:
    """YYYY-MM-DD → (date, ok). 빈 입력은 (None, True), 형식 오류는 (None, False)."""
    if not raw:
        return None, True
    try:
        return date.fromisoformat(raw.strip()), True
    except ValueError:
        return None, False


def _period_footer(dates: list[date]) -> str:
    """기간 범위 푸터 텍스트."""
    if not dates:
        return ""
    s, e = dates[0], dates[-1]
    return s.isoformat() if s == e else f"{s.isoformat()} ~ {e.isoformat()}"


def _signed_eok(net: int) -> str:
    """손익 부호 표기. net = 기대 − 실제 (양수=이득=+)."""
    if net > 0:
        return f"+{format_eok(net)}"
    if net < 0:
        return f"-{format_eok(-net)}"
    return "±0"


def starforce_label(b: StarforceBitik) -> str:
    """select 라벨: `아이템명 ★12→19 · +3.2억` (Q3 손익 표기, 100자 제한 방어)."""
    name = comparison.truncate_display(b.item, 56)
    return f"{name} ★{b.start_star}→{b.end_star} · {_signed_eok(b.net_meso)}"[:100]


def potential_label(b: PotentialBitik) -> str:
    """select 라벨: `아이템명 · 재설정 ×136`."""
    name = comparison.truncate_display(b.item, 56)
    return f"{name} · 재설정 ×{b.reset_count}"[:100]


def excluded_note(excluded: ExcludedItems) -> str | None:
    """목록 하단 제외 안내(Q10). 슈페리얼도 같은 카운트에 합산(파생 결정)."""
    if excluded.count == 0:
        return None
    return f"레벨 미상 {excluded.count}개 제외"


def pickup_text(comment: str | None) -> str:
    """득템 문구: 코멘트 입력 시 그 문구, 아니면 랜덤 풀(Q9)."""
    if comment and comment.strip():
        return comment.strip()
    return random.choice(PICKUP_PHRASES)


def find_icon_url(data: dict, item_name: str) -> str | None:
    """item-equipment 응답(현재 장착 + 프리셋 1~3)에서 이름 일치 장비의 아이콘 URL(Q5)."""
    keys = (
        "item_equipment",
        "item_equipment_preset_1",
        "item_equipment_preset_2",
        "item_equipment_preset_3",
    )
    for key in keys:
        for raw in data.get(key) or []:
            if isinstance(raw, dict) and raw.get("item_name") == item_name:
                icon = raw.get("item_icon")
                if icon:
                    return icon
    return None


# ── 대상 해석·아이콘 페치 ───────────────────────────────────────────────────


async def _self_target(
    session_factory: async_sessionmaker[AsyncSession],
    guild_id: int,
    user_id: int,
) -> tuple[HistoryTarget | None, str | None]:
    """실행자 본인 대상 해석(Q1). 실패 시 (None, ephemeral 안내문)."""
    targets = await get_history_targets(session_factory, guild_id, [user_id])
    if not targets:
        return None, "이 서버에 등록되지 않았어요. `/등록` 먼저 해주세요."
    target = targets[0]
    if target.api_key_encrypted is None:
        return (
            None,
            "개인 키 미등록이라 이력을 볼 수 없어요. `/등록`에 키를 추가해 주세요.",
        )
    return target, None


async def _fetch_item_icon(deps: Deps, ocid: str, item_name: str) -> bytes | None:
    """장착 장비 이름 매칭 → 아이콘 다운로드. 실패해도 카드는 진행(None 폴백, Q5)."""
    try:
        data = await deps.nexon.character_item_equipment(ocid)
        url = find_icon_url(data, item_name)
        if not url:
            return None
        return await deps.nexon.fetch_image(url)
    except NexonAPIError as exc:
        log.warning("비틱 아이콘 조회 실패(%s): %s", item_name, exc)
        return None


async def _record_nexon_error(
    deps: Deps, target: HistoryTarget, exc: NexonAPIError
) -> None:
    """넥슨 조회 실패 error_log 적재(이력류 _process_target 패턴)."""
    log_type = to_error_log_type(exc.error_class)
    if log_type is not None:
        await error_log.record(
            deps.session_factory,
            error_type=log_type,
            command="비틱",
            guild_id=target.guild_id,
            discord_user_id=target.discord_user_id,
            target_ocid=target.ocid,
            detail=f"{exc.code}: {exc.message}"[:500],
        )


# ── Select View (코드베이스 최초의 동적 컴포넌트) ────────────────────────────


class BitikSelectView(discord.ui.View):
    """ephemeral 아이템 목록 select. 선택 1회 → 공개 카드 발송 → 비활성(Q4·파생 결정).

    persistent view 미사용 — 120초 수명이라 봇 재시작 무효는 무관(작업지시서 잔류 리스크).
    """

    def __init__(
        self,
        *,
        origin: discord.Interaction,
        labels: list[str],
        placeholder: str,
        on_pick: Callable[[discord.Interaction, int], Awaitable[None]],
    ) -> None:
        super().__init__(timeout=_VIEW_TIMEOUT)
        self._origin = origin
        self._on_pick = on_pick
        self._select: discord.ui.Select = discord.ui.Select(
            placeholder=placeholder,
            options=[
                discord.SelectOption(label=label, value=str(i))
                for i, label in enumerate(labels)
            ],
        )
        self._select.callback = self._picked  # type: ignore[method-assign]
        self.add_item(self._select)

    async def _picked(self, interaction: discord.Interaction) -> None:
        index = int(self._select.values[0])
        self._select.disabled = True  # 선택 1회 후 비활성(중복 발송 방지)
        self.stop()
        await self._origin.edit_original_response(view=self)
        await self._on_pick(interaction, index)

    async def on_timeout(self) -> None:
        self._select.disabled = True
        try:
            await self._origin.edit_original_response(view=self)
        except discord.HTTPException:
            pass  # 원응답이 이미 사라졌으면 무시(ephemeral 만료 등)


async def _send_list(
    interaction: discord.Interaction,
    *,
    title: str,
    labels: list[str],
    note: str | None,
    footer: str,
    on_pick: Callable[[discord.Interaction, int], Awaitable[None]],
) -> None:
    """ephemeral select 목록 발송(Q4). 라벨 수는 호출자가 25개로 제한."""
    lines = ["자랑할 아이템을 골라주세요. 선택하면 채널에 **공개 카드**가 올라가요."]
    if note:
        lines.append(f"-# {note}")
    view = BitikSelectView(
        origin=interaction,
        labels=labels,
        placeholder="자랑할 아이템 선택",
        on_pick=on_pick,
    )
    await interaction.followup.send(
        embed=make_embed(title, "\n".join(lines), footer=footer),
        view=view,
        ephemeral=True,
    )


# ── 서브커맨드 핸들러 ───────────────────────────────────────────────────────


async def _resolve_common(
    deps: Deps,
    interaction: discord.Interaction,
    title: str,
    start_raw: str | None,
    end_raw: str | None,
    preset: str,
) -> tuple[HistoryTarget, list[date]] | None:
    """defer(ephemeral) → 길드/날짜/본인 대상 검증. 실패 시 ephemeral 안내 후 None."""
    await defer(interaction, ephemeral=True)
    if interaction.guild_id is None:
        await interaction.followup.send(
            embed=make_embed(title, "서버(길드) 안에서만 쓸 수 있어요."), ephemeral=True
        )
        return None

    start, ok_start = _parse_date(start_raw)
    end, ok_end = _parse_date(end_raw)
    if not (ok_start and ok_end):
        await interaction.followup.send(
            embed=make_embed(title, "날짜는 `YYYY-MM-DD` 형식으로 입력해 주세요."),
            ephemeral=True,
        )
        return None

    target, error = await _self_target(
        deps.session_factory, interaction.guild_id, interaction.user.id
    )
    if target is None:
        await interaction.followup.send(embed=make_embed(title, error), ephemeral=True)
        return None

    today_kst = datetime.now(KST).date()
    return target, resolve_period(preset, start, end, today_kst)


def _card_embed(target: HistoryTarget, title: str, footer: str) -> discord.Embed:
    """공개 카드 임베드(작성자 멘션 + 넥슨 출처표시 푸터)."""
    embed = make_embed(title, f"<@{target.discord_user_id}>", footer=footer)
    embed.set_image(url="attachment://bitik.png")
    return embed


async def handle_bitik_starforce(
    deps: Deps,
    interaction: discord.Interaction,
    preset: str,
    start_raw: str | None,
    end_raw: str | None,
) -> None:
    title = "비틱 — 스타포스"
    resolved = await _resolve_common(
        deps, interaction, title, start_raw, end_raw, preset
    )
    if resolved is None:
        return
    target, dates = resolved

    try:
        attempts = await fetch_starforce_records(deps, target, dates)
    except NexonAPIError as exc:
        await _record_nexon_error(deps, target, exc)
        await interaction.followup.send(
            embed=make_embed(title, classify_target_error(exc)), ephemeral=True
        )
        return

    if not attempts:
        await interaction.followup.send(
            embed=make_embed(title, _NO_RECORD), ephemeral=True
        )
        return

    # 레벨 매칭 소스: (B)학습 위에 (A)현재 장착(이력류 _process_target 패턴).
    learned = await load_learned_levels(deps.session_factory)
    try:
        equipped = await fetch_equipped_levels(deps.nexon, target.ocid)
    except NexonAPIError as exc:
        log.debug("장착 레벨 조회 실패(학습/시드로 폴백): %s", exc)
        equipped = {}
    if equipped:
        await learn_equipment_levels(deps.session_factory, equipped)
    known = {**learned, **equipped}

    bitiks, excluded = await asyncio.to_thread(
        group_starforce, attempts, lambda item: match_level(item, known)
    )
    for item in excluded.unmatched:  # 레벨 미상 제보(Q10, 기존 패턴 유지)
        await error_log.record(
            deps.session_factory,
            error_type="unmatched_equipment",
            command="비틱",
            guild_id=target.guild_id,
            discord_user_id=target.discord_user_id,
            target_ocid=target.ocid,
            detail=item[:500],
        )

    note = excluded_note(excluded)
    if not bitiks:
        body = _NO_RECORD if note is None else f"{_NO_RECORD}\n-# {note}"
        await interaction.followup.send(embed=make_embed(title, body), ephemeral=True)
        return

    top = bitiks[:_SELECT_LIMIT]
    period = _period_footer(dates)

    async def send_card(pick: discord.Interaction, index: int) -> None:
        await pick.response.defer(thinking=True)  # 공개(Q4)
        bitik = top[index]
        icon = await _fetch_item_icon(deps, target.ocid, bitik.item)
        png = await asyncio.to_thread(
            bitik_card.render_starforce_card, bitik, icon, period
        )
        await pick.followup.send(
            embed=_card_embed(
                target, f"⭐ {target.nickname} 의 스타포스 비틱", append_source(period)
            ),
            file=discord.File(io.BytesIO(png), filename="bitik.png"),
        )

    await _send_list(
        interaction,
        title=title,
        labels=[starforce_label(b) for b in top],
        note=note,
        footer=period,
        on_pick=send_card,
    )


async def handle_bitik_potential(
    deps: Deps,
    interaction: discord.Interaction,
    preset: str,
    start_raw: str | None,
    end_raw: str | None,
) -> None:
    title = "비틱 — 잠재"
    resolved = await _resolve_common(
        deps, interaction, title, start_raw, end_raw, preset
    )
    if resolved is None:
        return
    target, dates = resolved

    try:
        cubes, resets = await fetch_potential_records(deps, target, dates)
    except NexonAPIError as exc:
        await _record_nexon_error(deps, target, exc)
        await interaction.followup.send(
            embed=make_embed(title, classify_target_error(exc)), ephemeral=True
        )
        return

    bitiks = await asyncio.to_thread(
        group_potential, cubes, resets, cost=potential_cost
    )
    if not bitiks:
        await interaction.followup.send(
            embed=make_embed(title, _NO_RECORD), ephemeral=True
        )
        return

    top = bitiks[:_SELECT_LIMIT]
    period = _period_footer(dates)

    async def send_card(pick: discord.Interaction, index: int) -> None:
        await pick.response.defer(thinking=True)  # 공개(Q4)
        bitik = top[index]
        icon = await _fetch_item_icon(deps, target.ocid, bitik.item)
        png = await asyncio.to_thread(
            bitik_card.render_potential_card, bitik, icon, period
        )
        await pick.followup.send(
            embed=_card_embed(
                target, f"🎲 {target.nickname} 의 잠재 비틱", append_source(period)
            ),
            file=discord.File(io.BytesIO(png), filename="bitik.png"),
        )

    await _send_list(
        interaction,
        title=title,
        labels=[potential_label(b) for b in top],
        note=None,
        footer=period,
        on_pick=send_card,
    )


async def handle_bitik_pickup(
    interaction: discord.Interaction,
    image: discord.Attachment,
    comment: str | None,
) -> None:
    """`/비틱 득템` — 이미지 중계(공개 embed, 렌더 없음). defer 불필요(파생 결정)."""
    content_type = image.content_type or ""
    if not content_type.startswith("image/"):
        await interaction.response.send_message(
            embed=make_embed("비틱 — 득템", "이미지 파일만 올릴 수 있어요."),
            ephemeral=True,
        )
        return

    file = await image.to_file()
    embed = make_embed(
        f"🎉 {interaction.user.display_name} 의 득템 비틱", pickup_text(comment)
    )
    embed.set_image(url=f"attachment://{file.filename}")
    await interaction.response.send_message(embed=embed, file=file)  # 공개


# ── 트리 등록 ───────────────────────────────────────────────────────────────


def setup(bot: discord.Client) -> None:
    deps: Deps = bot.deps  # type: ignore[attr-defined]

    group = app_commands.Group(
        name="비틱", description="스타포스·잠재·득템 자랑 카드를 채널에 올립니다."
    )

    @group.command(
        name="스타포스",
        description="기간 내 스타포스 자랑 카드를 만듭니다 (본인 개인 키 필요).",
    )
    @app_commands.choices(period=_PERIOD_CHOICES)
    @app_commands.rename(period="기간", start="시작일", end="종료일")
    @app_commands.describe(
        period="조회 기간 프리셋 (기본 최근7일, 시작/종료일 지정 시 무시)",
        start="시작일 YYYY-MM-DD (선택)",
        end="종료일 YYYY-MM-DD (선택)",
    )
    @cooldowns.history_cooldown()  # 이력류 동일 30초(파생 결정)
    async def bitik_starforce(
        interaction: discord.Interaction,
        period: app_commands.Choice[str] | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> None:
        preset = period.value if period is not None else DEFAULT_PRESET
        await handle_bitik_starforce(deps, interaction, preset, start, end)

    @group.command(
        name="잠재",
        description="기간 내 잠재(큐브·재설정) 자랑 카드를 만듭니다 (본인 개인 키 필요).",
    )
    @app_commands.choices(period=_PERIOD_CHOICES)
    @app_commands.rename(period="기간", start="시작일", end="종료일")
    @app_commands.describe(
        period="조회 기간 프리셋 (기본 최근7일, 시작/종료일 지정 시 무시)",
        start="시작일 YYYY-MM-DD (선택)",
        end="종료일 YYYY-MM-DD (선택)",
    )
    @cooldowns.history_cooldown()
    async def bitik_potential(
        interaction: discord.Interaction,
        period: app_commands.Choice[str] | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> None:
        preset = period.value if period is not None else DEFAULT_PRESET
        await handle_bitik_potential(deps, interaction, preset, start, end)

    @group.command(
        name="득템", description="득템 이미지를 자랑 문구와 함께 채널에 올립니다."
    )
    @app_commands.rename(image="이미지", comment="코멘트")
    @app_commands.describe(
        image="자랑할 득템 스크린샷 (이미지 파일)",
        comment="직접 쓸 문구 (미입력 시 랜덤 비틱 문구)",
    )
    @cooldowns.spec_cooldown()  # 10초 — API 콜 없음, 스팸 방지(파생 결정)
    async def bitik_pickup(
        interaction: discord.Interaction,
        image: discord.Attachment,
        comment: str | None = None,
    ) -> None:
        await handle_bitik_pickup(interaction, image, comment)

    bot.tree.add_command(group)  # type: ignore[attr-defined]
