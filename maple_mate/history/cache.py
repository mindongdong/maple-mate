"""history_cache TTL 판정 (빌드 단위 #4, design §5②).

핵심은 순수함수 `is_cache_fresh` — 단위테스트 대상. 과거 일자는 불변(항상 fresh),
오늘(KST)은 5분 TTL. DB 적재/조회(service)는 Phase 3 이력류 명령에서.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
TODAY_TTL = timedelta(minutes=5)


def is_cache_fresh(
    query_date: date,
    fetched_at: datetime,
    now: datetime,
    ttl: timedelta = TODAY_TTL,
) -> bool:
    """캐시 항목이 아직 신선한지 판정 (순수함수).

    - query_date 가 (KST) 오늘보다 과거 → 불변 데이터: 항상 True.
    - query_date == (KST) 오늘 → (now - fetched_at) < ttl 이면 True.
    - query_date 가 미래 → 캐시 의미 없음: False.

    now, fetched_at 은 tz-aware 여야 한다(서로 빼므로).
    """
    today_kst = now.astimezone(KST).date()
    if query_date < today_kst:
        return True
    if query_date == today_kst:
        return (now - fetched_at) < ttl
    return False
