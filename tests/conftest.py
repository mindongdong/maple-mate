import pytest

from maple_mate.leaderboard import broadcast
from maple_mate.registration import realm


@pytest.fixture
def challengers_enabled(monkeypatch):
    """챌린저스 판정 스위치를 켠다 — 비활성(기본) 상태에서도 챌린저스 경로를 검증하기 위함."""
    monkeypatch.setattr(realm, "CHALLENGERS_ENABLED", True)
    monkeypatch.setattr(broadcast, "CHALLENGERS_ENABLED", True)
