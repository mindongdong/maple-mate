"""스케줄러 알리미 Discord 어댑터 + 명령 본체 공유 (작업지시서 #4).

전달-무관 service 위에 넥슨 페치·임베드·DM 발송을 얹는 얇은 어댑터. `build_homeworks` 는
`/스케줄러` 온디맨드와 매시 정각 DM 잡이 공유하는 산출물 빌더(결정 6) — realm 캐릭터 전부를
캐릭터별 Homework 리스트로 낸다. `run_scheduler_reminder_job` 은 그 시각 구독 0개면 스킵(넥슨
0콜) → 구독별 캐릭터 전부 빌드 → 캐릭터당 DM. 키없음·4xx·빈 숙제·DM 차단은 모두 **조용히
스킵 + 앱로그만**(결정 7 — "친구 개인 키 실패는 자가 발견").
"""

from __future__ import annotations

import logging
from datetime import datetime

import discord

from ..bot.dm import send_dm
from ..bot.embeds import BRAND_COLOR, append_source, format_footer, make_embed
from ..dependencies import Deps
from ..nexon.client import KST
from ..nexon.errors import NexonAPIError
from ..registration.realm import is_challengers
from . import service
from .category_filter import BUCKET_BOSS, BUCKET_DAILY, BUCKET_GUILD, BUCKET_WEEKLY
from .service import Homework

log = logging.getLogger(__name__)


def _embed_title(name: str, world: str | None) -> str:
    """임베드 제목 뱃지 — 캐릭터 world 로 per-character 파생(ADR-0017). 챌린저스 '🏆 챌린저스', 그 외 '🗓'."""
    prefix = "🏆 챌린저스" if is_challengers(world) else "🗓"
    return f"{prefix} {name} 의 스케줄러 숙제"


# 전부 완료(잔여 0) 상태색 — 디스코드 그린. 잔여>0 은 브랜드 오렌지(상태색 2색, ADR-0013).
_DONE_COLOR = discord.Color.from_rgb(87, 242, 135)


def _subtitle(hw: Homework, done: int, total: int) -> str | None:
    """제목 아래 부제 — `Lv.276 · 챌린저스2` + 전체 잔여 한 줄(집계대상 있을 때)."""
    parts = [f"Lv.{hw.character_level}"] if hw.character_level else []
    if hw.world_name:
        parts.append(hw.world_name)
    head = " · ".join(parts)
    if total <= 0:
        return head or None
    remaining = total - done
    mark = "✅" if remaining == 0 else "🔥"  # 0 일 때 🔥 어색 → ✅ 로 스왑(문구는 동일)
    line = f"{mark} 남은 숙제 {remaining}개 ({done}/{total} 완료)"
    return f"{head}\n{line}" if head else line


def _content_field(
    embed: discord.Embed, label: str, items: list[service.ContentItem]
) -> None:
    """퀘스트/완료미완료/회수 필드 — 헤더 `완료/총`(진행바 없음), 본문 todo-first. 빈 건 생략."""
    if not items:
        return
    done, total = service.field_counts(items)
    if total == 0:  # 전부 qs0(기타) 만 → 표시할 게 없음
        return
    embed.add_field(
        name=f"{label} — {done}/{total}",
        value=service.content_field_value(items),
        inline=False,
    )


def _guild_field(
    embed: discord.Embed, label: str, items: list[service.ContentItem]
) -> None:
    """길드 콘텐츠 필드(점수제) — 완료개념 없어 헤더 카운트 없이 본문만. 빈 건 생략."""
    if not items:
        return
    embed.add_field(name=label, value=service.guild_field_value(items), inline=False)


def _boss_field(
    embed: discord.Embed,
    label: str,
    items: list[service.BossItem],
    clear: tuple[int, int] | None = None,
) -> None:
    """보스 cycle 필드 — 헤더 `처치/총`(진행바 없음), 주간은 (처치 c/12) 부가. 빈 건 생략."""
    if not items:
        return
    done, total = service.boss_counts(items)
    name = f"{label} — {done}/{total}"
    if clear is not None:
        count, limit = clear
        name += f"  (처치 {count}/{limit})"
    embed.add_field(name=name, value=service.boss_cycle_value(items), inline=False)


def build_embed(
    hw: Homework,
    now: datetime,
    excluded: frozenset[str] = frozenset(),
) -> discord.Embed:
    """Homework → 필드 파생 카테고리 임베드(ADR-0013). 빈 카테고리는 생략.

    일일/주간을 퀘스트·회수·완료미완료·점수로 가르고, 보스는 cycle(일/주/월)별로 나눈다. excluded
    (ADR-0014)에 든 사용자 묶음(일일·주간·보스·길드)의 필드는 통째로 가리며, 부제 잔여·상태색은
    보이는 묶음만 재집계(visible_remaining)해 화면과 일치시킨다. 제목 뱃지는 캐릭터 world 로 파생
    (ADR-0017 — 한 구독에 본+챌 혼재 가능). 페치는 불변(표시 전용).
    """
    done, total = service.visible_remaining(hw, excluded)
    color = _DONE_COLOR if (total > 0 and done >= total) else BRAND_COLOR
    embed = make_embed(
        _embed_title(hw.character_name, hw.world_name),
        _subtitle(hw, done, total),
        color=color,
    )
    if BUCKET_DAILY not in excluded:
        # 일일 — 퀘스트 / 콘텐츠(회수형 몬파 + 완료형 에픽던전 병합, '회수' 라벨 폐기)
        _content_field(
            embed, "📝 일일 퀘스트", service.by_category(hw.daily, service.CAT_QUEST)
        )
        _content_field(
            embed,
            "📋 일일 콘텐츠",
            service.by_category(hw.daily, service.CAT_COUNT)
            + service.by_category(hw.daily, service.CAT_BINARY),
        )
    if BUCKET_WEEKLY not in excluded:
        # 주간 — 퀘스트 / 콘텐츠(완료형 + 회수형 병합)
        _content_field(
            embed, "📆 주간 퀘스트", service.by_category(hw.weekly, service.CAT_QUEST)
        )
        _content_field(
            embed,
            "⚔️ 주간 콘텐츠",
            service.by_category(hw.weekly, service.CAT_BINARY)
            + service.by_category(hw.weekly, service.CAT_COUNT),
        )
    if BUCKET_GUILD not in excluded:
        # 길드 콘텐츠(점수제) — 일+주 합산([길드] 주간 미션 포인트·플래그 레이스·지하 수로)
        _guild_field(
            embed,
            "🏰 길드 콘텐츠",
            service.by_category(hw.daily, service.CAT_GUILD)
            + service.by_category(hw.weekly, service.CAT_GUILD),
        )
    if BUCKET_BOSS not in excluded:
        # 보스 — cycle 별(주간만 처치 카운터 부가)
        _boss_field(
            embed,
            "🗡 주간 보스",
            service.bosses_by_cycle(hw.boss, service.CYCLE_WEEKLY),
            clear=(
                hw.weekly_boss_clear_count,
                service.weekly_boss_limit(hw.weekly_boss_clear_limit),
            ),
        )
        _boss_field(
            embed, "🗡 일간 보스", service.bosses_by_cycle(hw.boss, service.CYCLE_DAILY)
        )
        _boss_field(
            embed,
            "🗡 월간 보스",
            service.bosses_by_cycle(hw.boss, service.CYCLE_MONTHLY),
        )
        _boss_field(embed, "🗡 기타 보스", service.bosses_other_cycle(hw.boss))
    embed.set_footer(text=append_source(format_footer(now, now)))
    return embed


async def build_homeworks(
    deps: Deps, guild_id: int, user_id: int
) -> tuple[list[Homework], str | None]:
    """본인 키 + 등록 캐릭터 전부 → 각 캐릭터 오늘 스케줄러 페치 → 파싱. 온디맨드·DM 잡 공유.

    성공이면 (homeworks, None) — 캐릭터별 Homework 리스트(is_empty 포함 가능, 캐릭터 4xx 는
    조용히 스킵하고 나머지는 계속). 가드 실패(미등록·키없음·캐릭터 0)면 ([], 사용자메시지).
    개인 키 4xx(비대상·저활동)는 raise 하지 않고 error_log 미적재(결정 7 — 운영 요약 제외 철학).
    """
    key_encrypted, chars, error = await service.resolve_self_characters(
        deps.session_factory, guild_id, user_id
    )
    if error is not None:
        return [], error
    api_key = deps.cipher.decrypt(key_encrypted)  # type: ignore[arg-type]
    homeworks: list[Homework] = []
    for ocid, _nickname in chars:
        try:
            data = await deps.nexon.scheduler_character_state(
                api_key, ocid
            )  # 오늘=무지정
        except NexonAPIError as exc:
            log.warning(
                "스케줄러 조회 실패 (guild=%s user=%s ocid=%s): %s",
                guild_id,
                user_id,
                ocid,
                exc,
            )
            continue  # 캐릭터별 4xx → 조용히 스킵(나머지 캐릭터는 계속)
        homeworks.append(service.parse_homework(data))
    return homeworks, None


async def run_scheduler_reminder_job(bot: discord.Client, deps: Deps) -> None:
    """매시 정각 잡: now.hour 구독 조회 → 0개면 스킵 → 구독별 등록 캐릭터 전부 빌드 → 캐릭터당 DM.

    캐릭터마다 임베드 1개를 별도 DM 으로 보낸다(캐릭터 4개면 DM 4개). is_empty(등록 숙제 0개)·
    실패(키없음·4xx)·DM 차단은 모두 조용히 스킵(결정 7). 한 캐릭터/구독 실패가 다음을 막지 않는다.
    """
    now = datetime.now(KST)
    subs = await service.subscriptions_at_hour(deps.session_factory, now.hour)
    if not subs:
        log.info("스케줄러 알리미 스킵: %d시 구독 없음(넥슨 호출 안 함)", now.hour)
        return

    sent = 0
    for sub in subs:
        homeworks, _error = await build_homeworks(
            deps, sub.guild_id, sub.discord_user_id
        )
        for homework in homeworks:
            if service.is_empty_filtered(homework, sub.excluded):
                continue  # 필터 후 빈 캐릭터 스킵(빈 DM 금지)
            embed = build_embed(homework, now, sub.excluded)
            if await send_dm(bot, sub.discord_user_id, embed=embed):
                sent += 1
    log.info(
        "스케줄러 알리미: %d시 구독 %d건, 캐릭터 %d개 DM 발송",
        now.hour,
        len(subs),
        sent,
    )
