"""`/가이드` 디스코드 어댑터 — 봇 기능 안내 (얇은 전달 계층).

구현된 전체 명령을 한 장의 ephemeral 임베드로 안내한다. Discord 의 `/` 입력 UI 가
이미 각 명령의 `description`·인자를 보여주므로, 가이드는 그것이 *못* 주는 것
(**그룹·등록 순서·키/권한 전제조건**)에만 집중한다.

본문은 정적 손작성이며, 새 명령 추가 시 갱신 누락은 드리프트 가드 테스트
(`tests/test_guide.py`)가 CI 에서 잡는다. `/핑`(헬스체크)을 흡수 — 가이드가
응답하는 것 자체가 봇 생존 증명이다. 쿨다운 없음(순수 정적·ephemeral).
"""

from __future__ import annotations

import discord

from ..bot.embeds import make_embed

_ONBOARDING = (
    "메이트는 디스코드 채널 유저들의 메이플스토리 캐릭터 스펙·이력을 비교하는 봇이에요.\n"
    "처음이라면 → /캐릭터등록 → (이력 보려면) /키등록 → /대표지정 순으로 등록하세요.\n"
    "🔓 스펙류는 등록만으로, 📜 이력류는 개인 API 키가 있어야 보입니다."
)

# (그룹 헤더, 한 줄 설명) — 그룹 헤더의 (키 불필요/개인 API 키 필요/서버 관리 권한)
# 라벨은 가이드의 핵심 가치라 유지한다.
_GROUPS: tuple[tuple[str, str], ...] = (
    (
        "📝 등록·관리",
        "`/캐릭터등록` 캐릭터 등록(유저당 여러 개) · "
        "`/키등록` 넥슨 개인 API 키 등록(이력류 개방) · "
        "`/대표지정` 공개 명령용 대표 캐릭터 지정 · "
        "`/캐릭터목록` 내 등록 현황(본인만)",
    ),
    (
        "⚔️ 스펙·장비 (스펙류 · 키 불필요)",
        "`/스펙` 전투력·어빌·심볼·HEXA 비교 · "
        "`/아이템` 부위별 스타포스·잠재·옵션 비교 · "
        "`/유니온` 유니온·아티팩트·챔피언 등급 비교",
    ),
    (
        "📜 이력 (이력류 · 개인 API 키 필요)",
        "`/스타포스` 운지수·손익메소 비교 · `/잠재` 재설정·큐브·메소·등업 비교",
    ),
    (
        "🎴 비틱 (자랑 카드)",
        "`/비틱 스타포스` 스타포스 자랑 카드(본인 키) · "
        "`/비틱 잠재` 잠재 자랑 카드(본인 키) · "
        "`/비틱 득템` 득템 이미지 자랑",
    ),
    (
        "📈 리더보드",
        "`/경험치` 등록 캐릭터 최근 7일 레벨 추이 그래프",
    ),
    (
        "🔔 알림 설정 (서버 관리 권한)",
        "`/경험치알림` 매일 경험치 리더보드 알림 · "
        "`/썬데이` 썬데이 메이플 알림 · "
        "`/공지알림` 메이플 공지·업데이트 알림",
    ),
)


def build_guide_embed() -> discord.Embed:
    """가이드 임베드를 만든다(순수 함수 — 테스트에서 직접 호출 가능)."""
    embed = make_embed(
        "메이트 가이드",
        _ONBOARDING,
        footer="각 명령 사용법은 / 입력 시 표시돼요 · 도움말 재호출: /가이드",
    )
    for header, line in _GROUPS:
        embed.add_field(name=header, value=line, inline=False)
    return embed


def setup(bot: discord.Client) -> None:
    """가이드 슬래시 커맨드를 트리에 등록. 쿨다운 없음(도움말은 막지 않는다)."""

    @bot.tree.command(
        name="가이드",
        description="봇의 명령 목록과 사용법을 안내합니다.",
    )
    async def guide(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            embed=build_guide_embed(), ephemeral=True
        )
