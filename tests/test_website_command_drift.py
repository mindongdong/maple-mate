"""홍보 웹사이트(`site/`) 명령어 문서 ↔ 봇 트리 드리프트 가드.

website-docs-plan 결정 4: "`guide/commands.py` 명령이름 ⊆ 사이트 명령목록 CI검증".
여기서는 더 강하게 **봇 트리에 실제 등록된 공개 명령 == 사이트 문서 명령**을 요구한다.
비틱은 트리에서 숨김(ADR-0017)이라 양쪽 모두에서 자동 제외된다.

사이트 정본 = `site/data/commands.json`(명령어 페이지 렌더 소스). 새 명령 추가/개명 시
이 테스트가 CI 에서 문서 갱신 누락을 잡는다(tests/test_guide.py 의 가이드 가드와 짝).

튜토리얼(`site/data/tutorial-steps.tsx`)이 참조하는 명령도 같은 가드에 태운다:
이름은 봇 트리에 실재해야 하고, 공개/본인만(visibility) 라벨은
docs/tutorial-work-order.md §3.1 정본 매핑과 일치해야 한다.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from maple_mate.bot.core import MapleMateBot

_SITE = Path(__file__).resolve().parents[1] / "site"
_COMMANDS_JSON = _SITE / "data" / "commands.json"
_TUTORIAL_STEPS = _SITE / "data" / "tutorial-steps.tsx"

# 튜토리얼 명령 객체 리터럴(파일 상단 주석으로 형식 고정) 파서.
_TUTORIAL_CMD_RE = re.compile(
    r"\{\s*name:\s*'([^']+)'(?:\s*,\s*visibility:\s*'([^']+)')?\s*\}"
)

# 공개/비공개 정본 매핑 (작업지시서 §3.1 — 봇 코드 ephemeral 실태 기준).
_EXPECTED_VISIBILITY = {
    "스펙": "public",
    "아이템": "public",
    "유니온": "public",
    "스타포스": "public",
    "잠재": "public",
    "경험치": "public",
    "내캐릭터": "public",
    "스케줄러": "private",
    "캐릭터등록": "private",
    "키등록": "private",
    "캐릭터목록": "private",
    "대표지정": "private",
}

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


@pytest.fixture(scope="module")
def tutorial_commands() -> list[tuple[str, str | None]]:
    """튜토리얼 스텝이 참조하는 (명령, visibility) 쌍."""
    src = _TUTORIAL_STEPS.read_text(encoding="utf-8")
    found = _TUTORIAL_CMD_RE.findall(src)
    assert found, (
        "tutorial-steps.tsx 에서 명령 참조를 못 읽음 — "
        "명령 객체 리터럴 형식(파일 상단 주석)이 깨졌는지 확인하세요."
    )
    return [(name, vis or None) for name, vis in found]


def test_tutorial_references_only_real_commands(
    tree_command_names: set[str], tutorial_commands: list[tuple[str, str | None]]
) -> None:
    """튜토리얼이 봇 트리에 없는 명령을 언급하면 안 된다(개명·오타 드리프트 방지)."""
    phantom = {name for name, _ in tutorial_commands} - tree_command_names
    assert not phantom, (
        f"튜토리얼이 봇 트리에 없는 명령을 참조함: {sorted(phantom)} "
        f"— site/data/tutorial-steps.tsx 를 갱신하세요."
    )


def test_tutorial_visibility_matches_bot_reality(
    tutorial_commands: list[tuple[str, str | None]],
) -> None:
    """공개/본인만 라벨은 §3.1 정본 매핑과 일치해야 한다(잘못 가르치기 방지)."""
    wrong = [
        (name, vis, _EXPECTED_VISIBILITY.get(name))
        for name, vis in tutorial_commands
        if vis is not None and _EXPECTED_VISIBILITY.get(name) != vis
    ]
    assert not wrong, (
        f"튜토리얼 visibility 라벨이 정본(§3.1)과 다름 (명령, 표기, 정본): {wrong}"
    )
