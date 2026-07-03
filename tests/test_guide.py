"""`/가이드` 명령 단위테스트 — 등록·ephemeral 응답·웹 링크 버튼.

discord 게이트웨이 없이: 봇을 오프라인 생성해 트리에 등록된 실제 명령을 검사하고,
가짜 Interaction 으로 콜백을 직접 호출한다(tests/test_cooldowns.py 패턴 재사용).

명령 커버리지 가드는 tests/test_website_command_drift.py(봇트리↔commands.json
양방향)가 단독 담당한다 — 임베드는 더 이상 명령을 나열하지 않는다.
"""

from __future__ import annotations

from types import SimpleNamespace

import discord
import pytest

from maple_mate.bot.core import MapleMateBot
from maple_mate.guide.commands import TUTORIAL_URL, build_guide_embed, build_guide_view


@pytest.fixture(scope="module")
def bot() -> MapleMateBot:
    bot = MapleMateBot(deps=object(), dev_guild_id=None)
    bot._register_commands()
    return bot


class _Response:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_message(self, **kwargs) -> None:
        self.sent.append(kwargs)


def test_guide_registered_and_ping_removed(bot):
    assert bot.tree.get_command("가이드") is not None
    assert bot.tree.get_command("핑") is None


def test_bitik_hidden_from_tree(bot):
    """/비틱은 봇 트리에서 숨김(코드 보존, ADR-0017 #1)."""
    assert bot.tree.get_command("비틱") is None


def test_guide_embed_is_minimal_onboarding():
    """임베드는 온보딩 최소본 — 등록 순서 3명령만 담고, 그룹 필드는 없다."""
    embed = build_guide_embed()
    assert not embed.fields
    for name in ("캐릭터등록", "키등록", "대표지정"):
        assert name in embed.description


def test_guide_view_links_to_tutorial_page():
    """버튼 1개 — link 스타일로 웹사이트 튜토리얼에 연결."""
    view = build_guide_view()
    [button] = view.children
    assert isinstance(button, discord.ui.Button)
    assert button.style is discord.ButtonStyle.link
    assert button.url == TUTORIAL_URL == "https://maplemate.site/tutorial"


async def test_guide_responds_ephemeral_embed_with_view(bot):
    guide = bot.tree.get_command("가이드")
    interaction = SimpleNamespace(response=_Response())
    await guide.callback(interaction)
    [sent] = interaction.response.sent
    assert sent["ephemeral"] is True
    assert sent["embed"].title == "메이트 가이드"
    assert isinstance(sent["view"], discord.ui.View)
