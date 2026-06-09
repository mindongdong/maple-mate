"""`/잠재` 디스코드 어댑터 (얇은 전달 계층). 잠재 재설정·사용 큐브·사용 메소·등업 비교 PNG 표.

스타포스(commands.py)와 쌍둥이 흐름이나 단일 명령으로 통합(`/잠재합계` 폐기, potential-handoff D1):
대상별 큐브+메소재설정을 합쳐 캐릭터당 1행 — 전체 재설정 수, 사용 큐브 수, 사용 메소(감정비+재설정비),
도달 등급별 등업 뱃지. 단일 대상 조회 시만 큐브종류·등급 분포 보조 노출(D5).
부분 성공(키미등록·기록없음·조회실패·미등록)은 묶음 필드.
"""
from __future__ import annotations

import logging
from datetime import date, datetime

import discord
from discord import app_commands

from ..bot import comparison, table_image
from ..bot.embeds import KST, append_source, defer, make_embed
from ..character.service import format_eok
from ..dependencies import Deps
from ..error_log import service as error_log
from ..nexon.errors import NexonAPIError, to_error_log_type
from ..registration.service import Target, TargetOutcome, classify_target_error
from . import potential_cost
from .potential_service import (
    DEFAULT_PRESET,
    HistoryTarget,
    PotentialSummary,
    aggregate_potential,
    fetch_potential_records,
    get_history_targets,
    resolve_period,
)

log = logging.getLogger(__name__)

_PERIOD_CHOICES = [
    app_commands.Choice(name=p, value=p)
    for p in ("오늘", "어제", "최근7일", "최근30일", "최근90일", "최근1년", "이번주", "이번달")
]


def _to_spec_target(t: HistoryTarget) -> Target:
    """범례·부분성공 행용 스펙류 Target 으로 변환(키 제외)."""
    return Target(guild_id=t.guild_id, discord_user_id=t.discord_user_id, nickname=t.nickname, ocid=t.ocid)


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


async def _process_target(
    deps: Deps, target: HistoryTarget, dates: list[date]
) -> tuple[Target, PotentialSummary] | TargetOutcome:
    """대상 1명 처리. 성공 시 (Target, summary), 실패 시 TargetOutcome(error)."""
    spec_target = _to_spec_target(target)
    try:
        cubes, resets = await fetch_potential_records(deps, target, dates)
    except NexonAPIError as exc:
        log_type = to_error_log_type(exc.error_class)
        if log_type is not None:
            await error_log.record(
                deps.session_factory,
                error_type=log_type,
                command="잠재",
                guild_id=target.guild_id,
                discord_user_id=target.discord_user_id,
                target_ocid=target.ocid,
                detail=f"{exc.code}: {exc.message}"[:500],
            )
        return TargetOutcome(target=spec_target, error=classify_target_error(exc))

    if not cubes and not resets:  # 키는 있으나 기간 내 기록 없음 = 기록 없음(키 미등록과 구분)
        return TargetOutcome(target=spec_target, error="기간 내 잠재(큐브·재설정) 기록이 없어요.")

    summary = aggregate_potential(cubes, resets, cost=potential_cost)  # 감정비+재설정비(G2 단가표)
    return spec_target, summary


# 등업 from-등급 → 도달(to) 등급. 집계는 from 으로 세지만 표시는 '올라간 결과' 등급으로 한다.
_TIERUP_TO = {"레어": "에픽", "에픽": "유니크", "유니크": "레전드리"}


def _upgrade_cell(summary: PotentialSummary):
    """등업 컬럼 셀 — 도달(to) 등급 색 뱃지(0건 제외) 또는 '—'. 예: 유니크→레전드리 = '레전드리' 뱃지."""
    items = tuple((_TIERUP_TO.get(g, g), cnt) for g, cnt in summary.tierups)
    return table_image.GradeBadges(items) if items else "—"


def _build_table(
    results: list[tuple[Target, PotentialSummary]],
    outcomes: list[TargetOutcome],
    footer: str,
) -> tuple[discord.Embed, discord.File]:
    """사용 메소 내림차순(동률 시 사용 큐브) 표. 최상위 사용 메소 셀 강조. 등업 뱃지 병기."""
    ranked = sorted(results, key=lambda rs: (-(rs[1].total_meso or 0), -rs[1].cube_count))
    meso_values = [float(s.total_meso) if s.total_meso is not None else None for _, s in ranked]
    best = comparison.highest_indices(meso_values) if len(ranked) > 1 else set()

    headers = ["순위", "캐릭터", "잠재 재설정", "사용 큐브", "사용 메소", "등업"]
    rows: list[list] = []
    for i, (tgt, summary) in enumerate(ranked):
        meso_text = format_eok(summary.total_meso) if summary.total_meso is not None else "—"
        rows.append(
            [
                str(i + 1),
                comparison.truncate_display(tgt.nickname, 14),
                str(summary.total_resets),  # 큐브 + 메소 전체 재설정 횟수
                str(summary.cube_count),
                table_image.Highlight(meso_text) if i in best else meso_text,
                _upgrade_cell(summary),
            ]
        )
    embed, file = comparison.table_image_message(
        "잠재 메소·큐브 비교",
        headers,
        rows,
        [t for t, _ in ranked],
        aligns=["center", "left", "right", "right", "right", "left"],
        footer=footer,
        outcomes=outcomes,
        filename="potential.png",
    )
    return embed, file


def _aux_fields(embed: discord.Embed, summary: PotentialSummary) -> None:
    """단일 대상 보조 노출(D5): 사용 메소 분해·큐브종류 분포·등급별 재설정·등업 진행."""
    if summary.total_meso is not None:
        parts = []
        if summary.reset_meso:
            parts.append(f"재설정 {format_eok(summary.reset_meso)}")
        if summary.appraisal_meso:
            parts.append(f"큐브 감정비 {format_eok(summary.appraisal_meso)}")
        breakdown = f" ({' · '.join(parts)})" if parts else ""
        embed.add_field(
            name="💰 사용 메소", value=f"**{format_eok(summary.total_meso)}**{breakdown}", inline=False
        )

    if summary.by_cube_type:
        lines = [f"• {ctype} ×{cnt}" for ctype, cnt in summary.by_cube_type[:8]]
        embed.add_field(name="🎲 큐브 종류 분포", value="\n".join(lines), inline=False)

    if summary.by_grade:
        lines = [
            f"• **{grade}** — 잠재 {pot}회 · 에디 {add}회" for grade, pot, add in summary.by_grade
        ]
        embed.add_field(name="📊 등급별 재설정 횟수", value="\n".join(lines), inline=False)

    if summary.tierups:
        # from → to 진행(유니크 → 레전드리 처럼 한 단계 위). 레전드리는 종착이라 from 에 없음.
        nxt = {"레어": "에픽", "에픽": "유니크", "유니크": "레전드리"}
        lines = [f"• {g} → {nxt.get(g, '?')} ×{cnt}" for g, cnt in summary.tierups]
        embed.add_field(name="⬆️ 등업 진행", value="\n".join(lines), inline=False)


async def handle_potential(
    deps: Deps,
    interaction: discord.Interaction,
    members: list[discord.Member],
    preset: str,
    start_raw: str | None,
    end_raw: str | None,
) -> None:
    await defer(interaction)
    if interaction.guild_id is None:
        await interaction.followup.send(embed=make_embed("잠재", "서버(길드) 안에서만 쓸 수 있어요."))
        return

    start, ok_start = _parse_date(start_raw)
    end, ok_end = _parse_date(end_raw)
    if not (ok_start and ok_end):
        await interaction.followup.send(
            embed=make_embed("잠재", "날짜는 `YYYY-MM-DD` 형식으로 입력해 주세요.")
        )
        return

    user_ids = [m.id for m in members] or None
    targets = await get_history_targets(deps.session_factory, interaction.guild_id, user_ids)

    # 지정했지만 미등록인 멤버 → '미등록' 부분성공 행.
    missing: list[TargetOutcome] = []
    if user_ids is not None:
        registered = {t.discord_user_id for t in targets}
        missing = [
            TargetOutcome(
                target=Target(guild_id=interaction.guild_id, discord_user_id=m.id, nickname=m.display_name, ocid=""),
                error="이 서버에 등록되지 않았어요. `/등록` 먼저 해주세요.",
            )
            for m in members
            if m.id not in registered
        ]

    # 키 미등록(이력류 조회 불가) 분리 — 기록 없음과 반드시 구분(CONTEXT.md).
    keyed = [t for t in targets if t.api_key_encrypted is not None]
    no_key = [
        TargetOutcome(target=_to_spec_target(t), error="개인 키 미등록이라 이력을 볼 수 없어요. `/등록`에 키를 추가해 주세요.")
        for t in targets
        if t.api_key_encrypted is None
    ]

    if not keyed:
        outcomes = missing + no_key
        if outcomes:
            await interaction.followup.send(embed=comparison.all_failed_embed("잠재", outcomes))
        else:
            await interaction.followup.send(
                embed=make_embed("잠재", "이 서버에 키 등록자가 없어요. `/등록`에 개인 키를 추가해 주세요.")
            )
        return

    today_kst = datetime.now(KST).date()
    dates = resolve_period(preset, start, end, today_kst)

    results: list[tuple[Target, PotentialSummary]] = []
    failures: list[TargetOutcome] = []
    for target in keyed:
        processed = await _process_target(deps, target, dates)
        if isinstance(processed, TargetOutcome):
            failures.append(processed)
        else:
            results.append(processed)

    outcomes = failures + no_key + missing
    footer = _period_footer(dates)

    if not results:
        await interaction.followup.send(embed=comparison.all_failed_embed("잠재 큐브·등업 비교", outcomes, footer=footer))
        return

    # 데이터 임베드(성공 표)에만 넥슨 출처표시 — 전체실패 에러 임베드(위)는 결과데이터 아님.
    embed, file = _build_table(results, outcomes, append_source(footer))
    # 단일 대상(키 등록자가 1명만 조회됨) → 큐브종류·등급 분포 보조 노출(D5). 다인 비교 시 생략.
    if len(keyed) == 1 and len(results) == 1:
        _aux_fields(embed, results[0][1])
    await interaction.followup.send(embed=embed, file=file)


def setup(bot: discord.Client) -> None:
    deps: Deps = bot.deps  # type: ignore[attr-defined]

    @bot.tree.command(  # type: ignore[attr-defined]
        name="잠재",
        description="잠재 재설정·사용 큐브·사용 메소·등업을 비교합니다 (개인 키 등록자 대상, 대상 미지정 시 서버 전체).",
    )
    @app_commands.choices(period=_PERIOD_CHOICES)
    @app_commands.rename(
        period="기간",
        start="시작일",
        end="종료일",
        member1="대상1",
        member2="대상2",
        member3="대상3",
        member4="대상4",
        member5="대상5",
    )
    @app_commands.describe(
        period="조회 기간 프리셋 (기본 최근7일, 시작/종료일 지정 시 무시)",
        start="시작일 YYYY-MM-DD (선택)",
        end="종료일 YYYY-MM-DD (선택)",
        member1="비교할 유저 (미지정 시 이 서버 키 등록자 전원)",
        member2="추가 비교 대상",
        member3="추가 비교 대상",
        member4="추가 비교 대상",
        member5="추가 비교 대상",
    )
    async def potential_command(
        interaction: discord.Interaction,
        period: app_commands.Choice[str] | None = None,
        start: str | None = None,
        end: str | None = None,
        member1: discord.Member | None = None,
        member2: discord.Member | None = None,
        member3: discord.Member | None = None,
        member4: discord.Member | None = None,
        member5: discord.Member | None = None,
    ) -> None:
        members = [m for m in (member1, member2, member3, member4, member5) if m is not None]
        preset = period.value if period is not None else DEFAULT_PRESET
        await handle_potential(deps, interaction, members, preset, start, end)
