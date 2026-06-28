"""`/스타포스` 디스코드 어댑터 (얇은 전달 계층). 운지수·손익메소 비교 PNG 표.

대상 = 키 등록된 등록자(키 없으면 '키 미등록' 행). 기간 페치 → 레벨 3단 매칭 → 집계.
운지수 낮을수록 운 좋음 → 최저 행 강조. 부분 성공(키미등록·기록없음·조회실패)은 묶음 필드.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime

import discord
from discord import app_commands

from ..bot import comparison, cooldowns, table_image
from ..bot.embeds import KST, append_source, defer, make_embed
from ..character.service import format_eok
from ..dependencies import Deps
from ..error_log import service as error_log
from ..nexon.errors import NexonAPIError, to_error_log_type
from ..registration.service import Target, TargetOutcome, classify_target_error
from .equipment_level import (
    fetch_equipped_levels,
    learn_equipment_levels,
    load_learned_levels,
    match_level,
)
from .service import (
    DEFAULT_PRESET,
    HistoryTarget,
    StarforceSummary,
    aggregate_starforce,
    fetch_starforce_records,
    get_history_targets,
    resolve_period,
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


def _to_spec_target(t: HistoryTarget, display_name: str) -> Target:
    """범례·부분성공 행용 스펙류 Target 으로 변환(닉=디스코드 서버 표시명, 키 제외, ADR-0015)."""
    return Target(
        guild_id=t.guild_id,
        discord_user_id=t.discord_user_id,
        nickname=display_name,
        ocid=t.ocid,
    )


def resolve_member_displays(
    guild: discord.Guild | None, targets: list[HistoryTarget]
) -> tuple[dict[int, str], list[HistoryTarget]]:
    """등록자 → {discord_user_id: 서버 표시명} 맵 + 현재 서버 멤버만 남긴 대상 목록(ADR-0015 결정 3).

    이력류 표시는 캐릭터 닉이 아니라 디스코드 유저(계정)다 — `get_member`(members 인텐트 필요)로
    서버 표시명을 해석한다. 서버를 떠난 등록자(get_member=None, 길드 미캐시 포함)는 표시명이
    없어 결과에서 제외한다(표·범례·실패 모두 미표시). `/스타포스`·`/잠재` 가 공유한다.
    """
    display_by_uid: dict[int, str] = {}
    present: list[HistoryTarget] = []
    for t in targets:
        member = guild.get_member(t.discord_user_id) if guild is not None else None
        if member is None:
            continue
        display_by_uid[t.discord_user_id] = member.display_name
        present.append(t)
    return display_by_uid, present


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


def _format_luck(summary: StarforceSummary) -> str:
    """행운 백분위 → '상위 X%' (L 높을수록 = 상위 X 작을수록 운 좋음). 시도 없으면 '—'.

    정수 표기 — MC 표본의 실제 정밀도가 ±1%p 수준이라 소수점은 노이즈다(과대 표기 방지).
    양극단은 클램프(ADR-0016): '상위 0%'(전원 떼몰림 착시) 금지 → '상위 1% 미만',
    대칭으로 극단 불운은 '상위 99% 초과'.
    """
    if summary.luck_score is None:
        return "—"
    top = 100.0 - summary.luck_score
    if top < 1.0:
        return "상위 1% 미만"
    if top > 99.0:
        return "상위 99% 초과"
    return f"상위 {top:.0f}%"


def _format_count(summary: StarforceSummary) -> str:
    """기준건수 — 11성 필터로 미상이 사라져 분자=분모라 단일 건수로 표시(ADR-0016)."""
    return f"{summary.matched_count}건"


async def _process_target(
    deps: Deps,
    target: HistoryTarget,
    dates: list[date],
    learned: dict[str, int],
    display_name: str,
) -> tuple[Target, StarforceSummary] | TargetOutcome:
    """대상 1명 처리. 성공 시 (Target, summary), 실패 시 TargetOutcome(error).

    개인 키가 반환하는 계정 전체(본서버+챌린저스)를 한 값으로 합산한다(realm 무필터, ADR-0015).
    """
    spec_target = _to_spec_target(target, display_name)
    try:
        attempts = await fetch_starforce_records(deps, target, dates)
    except NexonAPIError as exc:
        log_type = to_error_log_type(exc.error_class)
        if log_type is not None:
            await error_log.record(
                deps.session_factory,
                error_type=log_type,
                command="스타포스",
                guild_id=target.guild_id,
                discord_user_id=target.discord_user_id,
                target_ocid=target.ocid,
                detail=f"{exc.code}: {exc.message}"[:500],
            )
        return TargetOutcome(target=spec_target, error=classify_target_error(exc))

    if not attempts:  # 키는 있으나 기간 내 강화 없음 = 기록 없음(키 미등록과 구분)
        return TargetOutcome(target=spec_target, error="기간 내 강화 기록이 없어요.")

    # (A) 현재 장착 레벨 — best effort. 실패해도 학습/시드로 매칭 시도.
    try:
        equipped = await fetch_equipped_levels(deps.nexon, target.ocid)
    except NexonAPIError as exc:
        log.debug("장착 레벨 조회 실패(학습/시드로 폴백): %s", exc)
        equipped = {}
    if equipped:
        await learn_equipment_levels(
            deps.session_factory, equipped
        )  # 관측 레벨 자동 학습

    known = {**learned, **equipped}  # (B)학습 위에 (A)현재 장착을 덮어씀(현재가 우선)
    # 마르코프 기대값 계산(CPU)은 워커 스레드로 — 이벤트루프 비차단(D6).
    summary = await asyncio.to_thread(
        aggregate_starforce, attempts, lambda item: match_level(item, known)
    )
    await _report_unmatched(deps, target, summary)  # 11성+ 미상 제보(유저 비노출)
    if summary.matched_count == 0:
        # 강화는 했으나 11성 이상이 없거나(저성만) 전부 레벨 미상 → 보여줄 게 없음(ADR-0016).
        return TargetOutcome(
            target=spec_target, error="기간 내 11성 이상 강화 기록이 없어요."
        )
    return spec_target, summary


async def _report_unmatched(
    deps: Deps, target: HistoryTarget, summary: StarforceSummary
) -> None:
    """레벨 미상으로 제외된 장비를 error_log 에 제보(점진 시드 확장용)."""
    for item in summary.unmatched_items:
        await error_log.record(
            deps.session_factory,
            error_type="unmatched_equipment",
            command="스타포스",
            guild_id=target.guild_id,
            discord_user_id=target.discord_user_id,
            target_ocid=target.ocid,
            detail=item[:500],
        )


def _rank_results(
    results: list[tuple[Target, StarforceSummary]],
) -> list[tuple[Target, StarforceSummary]]:
    """운빨수치 내림차순(높을수록 운 좋음) 정렬. 동점은 손익(이득) 큰 쪽이 위(ADR-0016 결정 6).

    운빨 클램프('상위 1% 미만' 등)로 표시가 겹칠 때, net_meso 오름차순(가장 음수=가장 큰
    이득)을 3차 키로 둬 이득 큰 사람이 상위에 온다.
    """
    return sorted(
        results,
        key=lambda rs: (
            rs[1].luck_score is None,
            -(rs[1].luck_score or 0.0),
            rs[1].net_meso,
        ),
    )


def _build_table(
    results: list[tuple[Target, StarforceSummary]],
    outcomes: list[TargetOutcome],
    footer: str,
) -> tuple[discord.Embed, discord.File]:
    """운빨수치 내림차순(높을수록 운 좋음) 표. 최상위 운빨 행 강조.

    '기댓값 대비 손익'은 표시하지 않는다(ADR-0016 개정) — 미완성·윈도우 등반에서 기댓값
    baseline 이 무의미(무진행이면 expected=0 → 손익=−전액)해 절대 금액이 오해를 부른다.
    표시는 사실 그대로인 총 사용 메소 + 상대 지표인 운빨만. net_meso 는 동점 정렬용으로만 유지.
    """
    ranked = _rank_results(results)
    luck_values = [s.luck_score for _, s in ranked]
    best = comparison.highest_indices(luck_values) if len(ranked) > 1 else set()

    headers = [
        "순위",
        "대상",  # 디스코드 유저(서버 표시명) — 이력은 계정 전체 합산이라 캐릭터 닉을 안 쓴다(ADR-0015)
        "운빨수치",
        "총 사용 메소",
        "기준건수",
    ]
    rows: list[list] = []
    for i, (tgt, summary) in enumerate(ranked):
        luck_text = _format_luck(summary)
        rows.append(
            [
                str(i + 1),
                comparison.truncate_display(tgt.nickname, 14),
                table_image.Highlight(luck_text) if i in best else luck_text,
                format_eok(summary.total_meso),
                _format_count(summary),
            ]
        )
    embed, file = comparison.table_image_message(
        "스타포스 운빨 비교",
        headers,
        rows,
        [t for t, _ in ranked],
        aligns=["center", "left", "right", "right", "right"],
        footer=footer,
        outcomes=outcomes,
        filename="starforce.png",
    )
    embed.add_field(
        name="ℹ️ 계정 전체 합산",
        value="이력은 등록 캐릭터 본인 계정의 **전체 캐릭터(부캐 포함)** 를 합산한 값이에요.",
        inline=False,
    )
    embed.add_field(
        name="ℹ️ 11성 이상 강화만 집계",
        value="저성·이벤트 장비는 빼고 **11성 이상** 강화만 비교해요. 강화 당시 이벤트(파괴 확률 감소·비용 할인)도 반영했어요.",
        inline=False,
    )
    return embed, file


async def handle_starforce(
    deps: Deps,
    interaction: discord.Interaction,
    members: list[discord.Member],
    preset: str,
    start_raw: str | None,
    end_raw: str | None,
) -> None:
    await defer(interaction)
    if interaction.guild_id is None:
        await interaction.followup.send(
            embed=make_embed("스타포스", "서버(길드) 안에서만 쓸 수 있어요.")
        )
        return

    start, ok_start = _parse_date(start_raw)
    end, ok_end = _parse_date(end_raw)
    if not (ok_start and ok_end):
        await interaction.followup.send(
            embed=make_embed("스타포스", "날짜는 `YYYY-MM-DD` 형식으로 입력해 주세요.")
        )
        return

    user_ids = [m.id for m in members] or None
    targets = await get_history_targets(
        deps.session_factory, interaction.guild_id, user_ids
    )

    # 표시명 해석(디스코드 서버 표시명) — 서버 이탈(get_member=None) 등록자는 제외(ADR-0015 결정 3).
    display_by_uid, targets = resolve_member_displays(interaction.guild, targets)

    # 지정했지만 미등록인 멤버 → '미등록' 부분성공 행.
    missing: list[TargetOutcome] = []
    if user_ids is not None:
        registered = {t.discord_user_id for t in targets}
        missing = [
            TargetOutcome(
                target=Target(
                    guild_id=interaction.guild_id,
                    discord_user_id=m.id,
                    nickname=m.display_name,
                    ocid="",
                ),
                error="이 서버에 등록되지 않았어요. `/캐릭터등록` 먼저 해주세요.",
            )
            for m in members
            if m.id not in registered
        ]

    # 키 미등록(이력류 조회 불가) 분리 — 기록 없음과 반드시 구분(CONTEXT.md).
    keyed = [t for t in targets if t.api_key_encrypted is not None]
    no_key = [
        TargetOutcome(
            target=_to_spec_target(t, display_by_uid[t.discord_user_id]),
            error="개인 키 미등록이라 이력을 볼 수 없어요. `/키등록`으로 키를 추가해 주세요.",
        )
        for t in targets
        if t.api_key_encrypted is None
    ]

    if not keyed:
        outcomes = missing + no_key
        if outcomes:
            await interaction.followup.send(
                embed=comparison.all_failed_embed("스타포스", outcomes)
            )
        else:
            await interaction.followup.send(
                embed=make_embed(
                    "스타포스",
                    "이 서버에 키 등록자가 없어요. `/키등록`으로 개인 키를 추가해 주세요.",
                )
            )
        return

    today_kst = datetime.now(KST).date()
    dates = resolve_period(preset, start, end, today_kst)

    learned = await load_learned_levels(
        deps.session_factory
    )  # (B) 자동 학습 레벨 1회 로드
    results: list[tuple[Target, StarforceSummary]] = []
    failures: list[TargetOutcome] = []
    for target in keyed:
        processed = await _process_target(
            deps, target, dates, learned, display_by_uid[target.discord_user_id]
        )
        if isinstance(processed, TargetOutcome):
            failures.append(processed)
        else:
            results.append(processed)

    outcomes = failures + no_key + missing
    footer = _period_footer(dates)

    if not results:
        await interaction.followup.send(
            embed=comparison.all_failed_embed(
                "스타포스 운지수 비교", outcomes, footer=footer
            )
        )
        return

    # 데이터 임베드(성공 표)에만 넥슨 출처표시 — 전체실패 에러 임베드(위)는 결과데이터 아님.
    # 표 PNG 렌더(CPU)는 워커 스레드로 — 이벤트루프 비차단(D6).
    embed, file = await asyncio.to_thread(
        _build_table, results, outcomes, append_source(footer)
    )
    await interaction.followup.send(embed=embed, file=file)


def setup(bot: discord.Client) -> None:
    deps: Deps = bot.deps  # type: ignore[attr-defined]

    @bot.tree.command(  # type: ignore[attr-defined]
        name="스타포스",
        description="스타포스 운지수·손익메소를 비교합니다 (개인 키 등록자 대상, 대상 미지정 시 서버 전체).",
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
    @cooldowns.history_cooldown()
    async def starforce_command(
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
        members = [
            m for m in (member1, member2, member3, member4, member5) if m is not None
        ]
        preset = period.value if period is not None else DEFAULT_PRESET
        await handle_starforce(deps, interaction, members, preset, start, end)
