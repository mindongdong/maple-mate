"""`/가이드` 디스코드 어댑터 — 봇 기능 안내 (얇은 전달 계층).

상세 명령 안내는 웹사이트 명령어 페이지(COMMANDS_URL)로 위임하고, 임베드는
디스코드 안에서 바로 행동 가능한 **온보딩 최소본**(소개 + 등록 순서)만 담는다.
명령 커버리지는 tests/test_website_command_drift.py(봇트리↔commands.json)가
지킨다. `/핑`(헬스체크)을 흡수 — 가이드가 응답하는 것 자체가 봇 생존 증명이다.
쿨다운 없음(순수 정적·ephemeral).
"""

from __future__ import annotations

import discord

from ..bot.embeds import make_embed

COMMANDS_URL = "https://maplemate.site/commands"

_ONBOARDING = (
    "메이트는 디스코드 채널 유저들의 메이플스토리 캐릭터 스펙·이력을 비교하는 봇이에요.\n"
    "처음이라면 → /캐릭터등록 → (이력 보려면) /키등록 → /대표지정 순으로 등록하세요."
)


def build_guide_embed() -> discord.Embed:
    """가이드 임베드를 만든다(순수 함수 — 테스트에서 직접 호출 가능)."""
    return make_embed(
        "메이트 가이드",
        _ONBOARDING,
        footer="각 명령 사용법은 / 입력 시 표시돼요 · 도움말 재호출: /가이드",
    )


def build_guide_view() -> discord.ui.View:
    """웹사이트 명령어 페이지로 가는 링크 버튼 뷰(순수 함수)."""
    view = discord.ui.View()
    view.add_item(
        discord.ui.Button(
            style=discord.ButtonStyle.link,
            label="📖 명령어 전체 보기",
            url=COMMANDS_URL,
        )
    )
    return view


def setup(bot: discord.Client) -> None:
    """가이드 슬래시 커맨드를 트리에 등록. 쿨다운 없음(도움말은 막지 않는다)."""

    @bot.tree.command(
        name="가이드",
        description="봇 사용법 안내와 명령어 페이지 링크를 보여줍니다.",
    )
    async def guide(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            embed=build_guide_embed(), view=build_guide_view(), ephemeral=True
        )
