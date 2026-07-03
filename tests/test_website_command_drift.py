"""홍보 웹사이트(`site/`) 명령어 문서 ↔ 봇 트리 드리프트 가드.

website-docs-plan 결정 4: "`guide/commands.py` 명령이름 ⊆ 사이트 명령목록 CI검증".
여기서는 더 강하게 **봇 트리에 실제 등록된 공개 명령 == 사이트 문서 명령**을 요구한다.
비틱은 트리에서 숨김(ADR-0017)이라 양쪽 모두에서 자동 제외된다.

사이트 정본 = `site/data/commands.json`(명령어 페이지 렌더 소스). 새 명령 추가/개명 시
이 테스트가 CI 에서 문서 갱신 누락을 잡는다(tests/test_guide.py 의 가이드 가드와 짝).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from maple_mate.bot.core import MapleMateBot

_COMMANDS_JSON = Path(__file__).resolve().parents[1] / "site" / "data" / "commands.json"

# 트리에는 있지만 사이트 카드에서 의도적으로 뺀 명령.
# `/가이드`는 웹사이트로 연결하는 안내 명령이라 사이트에서 다시 문서화할 이유가 없다.
_SITE_EXEMPT = {"가이드"}


@pytest.fixture(scope="module")
def tree_command_names() -> set[str]:
    """봇 트리에 등록된 최상위 슬래시 명령/그룹 이름(비틱 등 숨김 제외)."""
    bot = MapleMateBot(deps=object(), dev_guild_id=None)
    bot._register_commands()
    return {cmd.name for cmd in bot.tree.get_commands()}


@pytest.fixture(scope="module")
def site_command_names() -> set[str]:
    """웹사이트가 문서화한 명령 이름(site/data/commands.json)."""
    data = json.loads(_COMMANDS_JSON.read_text(encoding="utf-8"))
    return {cmd["name"] for group in data["groups"] for cmd in group["commands"]}


def test_site_documents_every_public_command(
    tree_command_names: set[str], site_command_names: set[str]
) -> None:
    """공개 명령이 전부 사이트에 문서화돼 있어야 한다(누락 금지, _SITE_EXEMPT 제외)."""
    missing = tree_command_names - site_command_names - _SITE_EXEMPT
    assert not missing, (
        f"웹사이트 명령어 문서 누락: {sorted(missing)} "
        f"— site/data/commands.json 에 카드를 추가하세요."
    )


def test_site_has_no_phantom_commands(
    tree_command_names: set[str], site_command_names: set[str]
) -> None:
    """사이트가 존재하지 않는/숨긴 명령을 문서화하면 안 된다(오타·유령 항목 방지)."""
    phantom = site_command_names - tree_command_names
    assert not phantom, (
        f"봇 트리에 없는 명령을 문서화함: {sorted(phantom)} "
        f"— 오타이거나 숨김(예: 비틱) 명령입니다."
    )


def test_site_command_names_unique() -> None:
    """commands.json 내 명령 이름 중복 금지(그룹 배치 실수 방지)."""
    data = json.loads(_COMMANDS_JSON.read_text(encoding="utf-8"))
    names = [cmd["name"] for group in data["groups"] for cmd in group["commands"]]
    dups = sorted({n for n in names if names.count(n) > 1})
    assert not dups, f"commands.json 명령 이름 중복: {dups}"
