"""`/가이드` 명령 단위테스트 — 등록·ephemeral 응답·드리프트 가드.

discord 게이트웨이 없이: 봇을 오프라인 생성해 트리에 등록된 실제 명령을 검사하고,
가짜 Interaction 으로 콜백을 직접 호출한다(tests/test_cooldowns.py 패턴 재사용).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from maple_mate.bot.core import MapleMateBot
from maple_mate.guide.commands import build_guide_embed


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


def test_bitik_hidden_from_tree_and_guide(bot):
    """/비틱은 봇 트리·가이드에서 숨김(코드 보존, ADR-0017 #1)."""
    assert bot.tree.get_command("비틱") is None
    embed = build_guide_embed()
    text = embed.description + "".join(f.name + f.value for f in embed.fields)
    assert "비틱" not in text


def test_guide_alert_groups_unified_and_sunday_renamed(bot):
    """4종 알림 그룹(켜기·끄기)이 가이드에 통일 표기되고 썬데이→썬데이알림 개명(ADR-0017)."""
    embed = build_guide_embed()
    text = embed.description + "".join(f.name + f.value for f in embed.fields)
    for name in ("경험치알림", "공지알림", "썬데이알림", "스케줄러알림"):
        assert name in text
    # 평면 `/썬데이`(구명)는 더 이상 트리에 없다.
    assert bot.tree.get_command("썬데이") is None


async def test_guide_responds_ephemeral_embed(bot):
    guide = bot.tree.get_command("가이드")
    interaction = SimpleNamespace(response=_Response())
    await guide.callback(interaction)
    [sent] = interaction.response.sent
    assert sent["ephemeral"] is True
    assert sent["embed"].title == "메이트 가이드"


def test_guide_mentions_challengers_mode():
    """챌린저스 모드 안내가 가이드에 등장해야 한다(ADR-0009 — 모드 한 줄 설명)."""
    embed = build_guide_embed()
    text = embed.description + "".join(f.name + f.value for f in embed.fields)
    assert "챌린저스" in text and "모드" in text


def test_guide_covers_all_top_level_commands(bot):
    """드리프트 가드: '가이드' 외 모든 최상위 명령명이 임베드 본문에 등장해야 한다.

    새 명령을 추가하고 가이드 갱신을 잊으면 여기서 깨진다.
    """
    embed = build_guide_embed()
    text = embed.description + "".join(f.name + f.value for f in embed.fields)
    missing = [
        cmd.name
        for cmd in bot.tree.get_commands()
        if cmd.name != "가이드" and cmd.name not in text
    ]
    assert not missing, f"가이드 임베드에 누락된 명령: {missing}"
