"""history_cache prune 단위테스트 (스케일 튜닝 3-5, D4).

기준은 **조회대상 날짜(date) < 오늘 KST − 400일** — fetched_at 아님(불변 과거 캐시를
지우면 `최근1년` 재조회 시 개인 키 수백 콜 재발생). DB 쿼리 자체는 통합 영역이라
가짜 세션으로 DELETE 문·기준일만 검증하고, 경계는 순수 cutoff 함수로 확인한다.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

from maple_mate.history.service import (
    KST,
    history_cache_cutoff,
    prune_old_history_cache,
)
from maple_mate.notification import scheduler

_NOW = datetime(2026, 6, 10, 9, 0, tzinfo=KST)


# ── 경계 (순수): 401일 전 삭제 · 400/399일 전 보존 ────────────────────


def test_cutoff_is_400_days_before_today_kst():
    assert history_cache_cutoff(_NOW) == _NOW.date() - timedelta(days=400)


def test_row_older_than_400_days_is_pruned():
    cutoff = history_cache_cutoff(_NOW)
    assert (_NOW.date() - timedelta(days=401)) < cutoff  # 삭제 대상


def test_rows_within_400_days_are_preserved():
    cutoff = history_cache_cutoff(_NOW)
    assert not ((_NOW.date() - timedelta(days=400)) < cutoff)  # 경계 보존
    assert not ((_NOW.date() - timedelta(days=399)) < cutoff)  # 보존


# ── DELETE 문 실행 (가짜 세션) ────────────────────────────────────────


def _capture_factory(captured: list, rowcount: int = 3):
    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def execute(self, stmt):
            captured.append(stmt)
            return SimpleNamespace(rowcount=rowcount)

        async def commit(self):
            return None

    return lambda: _Session()


async def test_prune_deletes_history_cache_by_date_cutoff():
    captured: list = []
    deleted = await prune_old_history_cache(_capture_factory(captured), _NOW)
    assert deleted == 3
    [stmt] = captured
    assert stmt.table.name == "history_cache"
    # where 절 비교값 = 오늘 KST − 400일 (date 컬럼 기준).
    assert list(stmt.compile().params.values()) == [history_cache_cutoff(_NOW)]


# ── 운영 요약 일일 잡 편승: error_log prune 와 같은 주기 ──────────────


async def test_ops_summary_job_runs_both_prunes(monkeypatch):
    calls: list[str] = []

    async def fetch_yesterday_errors(sf, now):
        return []

    async def prune_old_errors(sf, now):
        calls.append("error_log")
        return 0

    async def prune_old_history_cache_fake(sf, now):
        calls.append("history_cache")
        return 0

    monkeypatch.setattr(
        scheduler.ops_summary, "fetch_yesterday_errors", fetch_yesterday_errors
    )
    monkeypatch.setattr(scheduler.ops_summary, "prune_old_errors", prune_old_errors)
    monkeypatch.setattr(
        scheduler.history_cache,
        "prune_old_history_cache",
        prune_old_history_cache_fake,
    )
    deps = type("Deps", (), {"session_factory": object(), "config": None})()
    await scheduler.run_ops_summary_job(bot=object(), deps=deps)
    assert calls == ["error_log", "history_cache"]
