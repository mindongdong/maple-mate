"""aggregate 순수 단위테스트 (Phase 5, 작업지시서 §빌드단위 4).

ErrorLog 인스턴스를 직접 구성(세션 없이, timestamp 미설정 — 입력 순서=시간순). DB·discord 없음.
aggregate 는 error_type/discord_user_id/command/detail 만 읽으므로 세션 없이 검증된다.
"""

from __future__ import annotations

from maple_mate.error_log.models import ErrorLog
from maple_mate.error_log.summary import UNMATCHED_TOP_N, aggregate


def _log(
    error_type: str,
    *,
    discord_user_id: int | None = None,
    command: str | None = None,
    detail: str | None = None,
) -> ErrorLog:
    """aggregate 가 읽는 필드만 채운 transient ErrorLog 행(세션 비의존)."""
    return ErrorLog(
        error_type=error_type,
        discord_user_id=discord_user_id,
        command=command,
        detail=detail,
    )


# ─── ① 앱키 vs 개인키 분기 ────────────────────────────────────────────────────


def test_app_key_included_personal_key_excluded():
    """discord_user_id=None(앱키) → 포함 / 채워짐(개인키) → 제외."""
    rows = [
        _log("auth_invalid", discord_user_id=None, detail="app_key_err_1"),
        _log("auth_invalid", discord_user_id=12345, detail="personal_err"),  # 제외
        _log("auth_invalid", discord_user_id=None, detail="app_key_err_2"),
    ]
    s = aggregate(rows)
    assert s.app_key_failures == 2
    # recent_detail = 마지막 앱키 행(last-wins)
    assert s.app_key_recent_detail == "app_key_err_2"
    assert s.is_empty is False


def test_only_personal_key_is_empty():
    """개인 키 행만 있으면 집계 0 → is_empty."""
    rows = [_log("auth_invalid", discord_user_id=99, detail="x")]
    s = aggregate(rows)
    assert s.app_key_failures == 0
    assert s.app_key_recent_detail is None
    assert s.is_empty is True


# ─── ② 미상 장비: distinct+횟수, 빈도 내림차순, 상위 10, "외 N종" ────────────


def test_unmatched_distinct_count_and_frequency_sort():
    """distinct 장비명 카운트, 빈도 내림차순 정렬."""
    rows = [
        _log("unmatched_equipment", detail="검"),
        _log("unmatched_equipment", detail="검"),
        _log("unmatched_equipment", detail="활"),
    ]
    s = aggregate(rows)
    # "검" 2번, "활" 1번 → 검이 먼저
    assert s.unmatched == (("검", 2), ("활", 1))
    assert s.unmatched_kinds == 2


def test_unmatched_top_n_and_kinds_for_extra():
    """11종 이상 입력 시 상위 10종만 + unmatched_kinds 에 전체 종수 보존."""
    # 11가지 장비(각 1회) + 첫 번째를 2회로 만들어 순서 고정
    equipments = [f"장비{i:02d}" for i in range(11)]
    rows = []
    # 장비00 = 2회, 나머지 = 1회
    rows.append(_log("unmatched_equipment", detail=equipments[0]))
    rows.append(_log("unmatched_equipment", detail=equipments[0]))
    for eq in equipments[1:]:
        rows.append(_log("unmatched_equipment", detail=eq))

    s = aggregate(rows)
    assert len(s.unmatched) == UNMATCHED_TOP_N  # 상위 10종
    assert s.unmatched_kinds == 11  # 전체 11종
    assert s.unmatched[0] == (equipments[0], 2)  # 빈도 1위


def test_unmatched_detail_none_skipped():
    """detail=None 인 unmatched_equipment 행은 스킵."""
    rows = [
        _log("unmatched_equipment", detail=None),
        _log("unmatched_equipment", detail="지팡이"),
    ]
    s = aggregate(rows)
    assert s.unmatched == (("지팡이", 1),)
    assert s.unmatched_kinds == 1


# ─── ③ 헬스: 타입별 그룹·by_command 분해·recent_detail=마지막 행·count 내림차순 ─


def test_health_groups_and_by_command():
    """같은 타입 다른 command 섞어 by_command 집계·내림차순 검증."""
    rows = [
        _log("nexon_api", command="스타포스", detail="err1"),
        _log("nexon_api", command="잠재", detail="err2"),
        _log("nexon_api", command="스타포스", detail="err3"),
        _log("timeout", command="스펙", detail="tout"),
    ]
    s = aggregate(rows)
    assert len(s.health) == 2  # nexon_api, timeout

    # 헬스는 count 내림차순 → nexon_api(3건)이 먼저
    nexon = s.health[0]
    assert nexon.error_type == "nexon_api"
    assert nexon.count == 3
    # by_command: 스타포스(2), 잠재(1)
    assert nexon.by_command[0] == ("스타포스", 2)
    assert nexon.by_command[1] == ("잠재", 1)
    # recent_detail = 마지막 nexon_api 행(last-wins)
    assert nexon.recent_detail == "err3"

    timeout = s.health[1]
    assert timeout.error_type == "timeout"
    assert timeout.count == 1


def test_health_command_none_becomes_기타():
    """command=None 은 '기타' 키로 치환해 by_command 에 집계된다."""
    rows = [
        _log("rate_limit", command=None, detail="d1"),
        _log("rate_limit", command=None, detail="d2"),
        _log("rate_limit", command="공지알림", detail="d3"),
    ]
    s = aggregate(rows)
    assert len(s.health) == 1
    entry = s.health[0]
    # "기타" 2건, "공지알림" 1건 → "기타" 먼저
    assert entry.by_command[0] == ("기타", 2)
    assert entry.by_command[1] == ("공지알림", 1)


def test_health_count_desc_tiebreak_by_error_type():
    """count 동률이면 error_type 오름차순 정렬."""
    rows = [
        _log("timeout"),
        _log("nexon_api"),
    ]
    s = aggregate(rows)
    # 둘 다 1건 → error_type 알파벳순: nexon_api < timeout
    assert s.health[0].error_type == "nexon_api"
    assert s.health[1].error_type == "timeout"


def test_health_recent_detail_last_wins():
    """같은 타입 여러 행 → recent_detail 은 마지막 행(입력 순서)."""
    rows = [
        _log("nexon_api", detail="first"),
        _log("nexon_api", detail="second"),
        _log("nexon_api", detail="last"),
    ]
    s = aggregate(rows)
    assert s.health[0].recent_detail == "last"


# ─── ④ 빈 입력 ────────────────────────────────────────────────────────────────


def test_empty_rows_is_empty():
    """행 없으면 is_empty = True."""
    s = aggregate([])
    assert s.is_empty is True
    assert s.app_key_failures == 0
    assert s.unmatched == ()
    assert s.health == ()


# ─── 예상 밖 타입 방어 ───────────────────────────────────────────────────────


def test_unknown_error_type_goes_to_health():
    """미정의 error_type 은 헬스 섹션에 방어적으로 포함된다."""
    rows = [_log("some_future_type", command="cmd", detail="x")]
    s = aggregate(rows)
    assert len(s.health) == 1
    assert s.health[0].error_type == "some_future_type"
    assert s.is_empty is False
