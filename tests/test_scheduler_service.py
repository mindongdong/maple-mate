"""스케줄러 service 순수 로직 단위테스트 (DB·넥슨 불요 — 작업지시서 #3·#5, ADR-0013).

DB 함수(구독 토글·조회)·resolve_self 는 pg_insert/delete 통합 영역이라 제외(기존 방침).
여기서는 응답 파싱·카테고리 파생·필드 렌더·집계·클램프만 검증한다.
"""

from __future__ import annotations

from maple_mate.scheduler.service import (
    CAT_BINARY,
    CAT_COUNT,
    CAT_GUILD,
    CAT_QUEST,
    CYCLE_DAILY,
    CYCLE_MONTHLY,
    CYCLE_WEEKLY,
    BossItem,
    ContentItem,
    boss_counts,
    boss_cycle_value,
    bosses_by_cycle,
    bosses_other_cycle,
    by_category,
    content_field_value,
    difficulty_ko,
    field_counts,
    guild_field_value,
    join_clamp,
    parse_homework,
    section_text,
    strip_prefix,
    truncate,
    weekly_boss_limit,
)


def _sample() -> dict:
    """라이브 실측 필드 형태(type/quest_state/cycle·영문 난이도·[길드]프리픽스·max=0)를 모사."""
    return {
        "character_name": "내캐릭터",
        "world_name": "스카니아",
        "character_level": 285,
        "daily_contents": [
            {  # 회수형: contents max>1, 진행 중
                "content_name": "몬스터파크",
                "type": "contents",
                "registration_flag": "true",
                "now_count": 2,
                "max_count": 14,
            },
            {  # 퀘스트 미완료(0/100 은 무의미)
                "content_name": "[일일 퀘스트] 소멸의 여로 조사",
                "type": "quest",
                "registration_flag": "true",
                "now_count": 0,
                "max_count": 100,
                "quest_state": "1",
            },
            {  # 퀘스트 완료
                "content_name": "[일일 퀘스트] 리멘 조사",
                "type": "quest",
                "registration_flag": "true",
                "now_count": 0,
                "max_count": 100,
                "quest_state": "2",
            },
            {  # 퀘스트 기타(미해금) → 제외
                "content_name": "[일일 퀘스트] 탈라하트",
                "type": "quest",
                "registration_flag": "true",
                "now_count": 0,
                "max_count": 0,
                "quest_state": "0",
            },
            {  # 미등록 → 제외
                "content_name": "안 한 콘텐츠",
                "registration_flag": "false",
                "now_count": 0,
                "max_count": 3,
            },
        ],
        "weekly_contents": [
            {  # 길드 콘텐츠(점수제): [길드] 프리픽스 + max==0
                "content_name": "[길드] 지하 수로",
                "type": "contents",
                "registration_flag": "true",
                "now_count": 0,
                "max_count": 0,
            },
            {  # 완료미완료(보스성): contents max==1, 미완료
                "content_name": "에르다 스펙트럼",
                "type": "contents",
                "registration_flag": "true",
                "now_count": 0,
                "max_count": 1,
            },
            {  # 완료미완료(에픽던전): max==0 비길드 → now>0=완료
                "content_name": "에픽 던전 : 하이마운틴",
                "type": "contents",
                "registration_flag": "true",
                "now_count": 5,
                "max_count": 0,
            },
        ],
        "boss_contents": [
            {
                "content_name": "스우",
                "difficulty": "hard",
                "cycle": "bossWeekly",
                "list_order_no": 2,
                "registration_flag": "true",
                "complete_flag": "false",
            },
            {
                "content_name": "검은 마법사",
                "difficulty": "hard",
                "cycle": "bossMonthly",
                "list_order_no": 1,
                "registration_flag": "true",
                "complete_flag": "true",
            },
            {
                "content_name": "핑크빈",
                "difficulty": "chaos",
                "cycle": "bossDaily",
                "list_order_no": 3,
                "registration_flag": "true",
                "complete_flag": "false",
            },
            {  # 미등록 → 제외
                "content_name": "안 잡는 보스",
                "difficulty": "chaos",
                "cycle": "bossWeekly",
                "list_order_no": 4,
                "registration_flag": "false",
                "complete_flag": "false",
            },
        ],
        "weekly_boss_clear_count": 8,
        "weekly_boss_clear_limit_count": 12,
    }


# ── parse_homework: 필터 + 신규 필드 캡처 ────────────────────────────────────


def test_parse_filters_unregistered():
    hw = parse_homework(_sample())
    assert "안 한 콘텐츠" not in [c.name for c in hw.daily]
    assert "안 잡는 보스" not in [b.name for b in hw.boss]


def test_parse_captures_type_quest_state_cycle():
    hw = parse_homework(_sample())
    assert hw.daily[0].name == "몬스터파크" and hw.daily[0].category == CAT_COUNT
    quest = next(c for c in hw.daily if c.name.endswith("소멸의 여로 조사"))
    assert quest.type == "quest" and quest.quest_state == "1"
    pinkbean = next(b for b in hw.boss if b.name == "핑크빈")
    assert pinkbean.cycle == CYCLE_DAILY


def test_parse_boss_sorted_by_list_order_no():
    hw = parse_homework(_sample())
    assert [b.name for b in hw.boss] == ["검은 마법사", "스우", "핑크빈"]  # 1,2,3


def test_parse_weekly_boss_limit_captured():
    hw = parse_homework(_sample())
    assert hw.weekly_boss_clear_count == 8
    assert hw.weekly_boss_clear_limit == 12


def test_parse_empty_when_nothing_registered():
    data = {
        "character_name": "신규",
        "daily_contents": [{"content_name": "x", "registration_flag": "false"}],
        "weekly_contents": [],
        "boss_contents": None,  # 누락 방어
    }
    hw = parse_homework(data)
    assert hw.daily == [] and hw.weekly == [] and hw.boss == []
    assert hw.is_empty is True


def test_parse_tolerates_missing_fields():
    data = {"daily_contents": [{"content_name": "x", "registration_flag": "true"}]}
    c = parse_homework(data).daily[0]
    assert c.now_count == 0 and c.max_count == 0
    assert c.category == CAT_BINARY  # 비길드 max=0 → 완료/미완료
    assert c.done is False  # now=0


# ── 카테고리·완료 파생 ────────────────────────────────────────────────────────


def test_category_derivation():
    assert ContentItem("a", 2, 14).category == CAT_COUNT  # max>1
    assert ContentItem("a", 0, 1).category == CAT_BINARY  # max==1
    assert ContentItem("에픽 던전 : x", 5, 0).category == CAT_BINARY  # 비길드 max==0
    assert (
        ContentItem("[길드] 지하 수로", 0, 0).category == CAT_GUILD
    )  # [길드] 프리픽스
    quest = ContentItem("a", 0, 100, type="quest", quest_state="1")
    assert quest.category == CAT_QUEST


def test_done_by_category():
    assert ContentItem("a", 14, 14).done is True  # 회수 완료
    assert ContentItem("a", 2, 14).done is False
    assert ContentItem("a", 1, 1).done is True  # binary max1
    assert ContentItem("에픽 : x", 5, 0).done is True  # binary max0, now>0 → 완료
    assert ContentItem("에픽 : x", 0, 0).done is False  # now=0 → 미완료
    assert ContentItem("[길드] 수로", 9, 0).done is False  # 길드는 완료개념 없음
    assert ContentItem("a", 0, 1, type="quest", quest_state="2").done is True
    assert ContentItem("a", 0, 1, type="quest", quest_state="1").done is False


def test_excluded_qs0_only():
    assert ContentItem("a", 0, 0, type="quest", quest_state="0").excluded is True
    assert ContentItem("a", 0, 1, type="quest", quest_state="1").excluded is False
    assert ContentItem("[길드] 수로", 0, 0).excluded is False  # 길드는 제외 아님


def test_in_progress_only_count_category():
    assert ContentItem("a", 2, 14).in_progress is True  # 회수 부분진행
    assert ContentItem("a", 14, 14).in_progress is False  # 완료
    assert ContentItem("a", 0, 14).in_progress is False  # 미시작
    assert ContentItem("에픽 : x", 5, 0).in_progress is False  # 이진은 게이지 없음


def test_remaining_total_excludes_guild_and_qs0():
    done, total = parse_homework(_sample()).remaining_total
    # 집계: daily 몬파(F)·소멸(F)·리멘(T) + weekly 에르다(F)·에픽(T) = 5(완2) ; 보스 3(완1)
    # 길드 지하수로·qs0 탈라하트 제외 → (3, 8)
    assert (done, total) == (3, 8)


# ── 작은 순수 헬퍼 ────────────────────────────────────────────────────────────


def test_difficulty_ko():
    assert difficulty_ko("hard") == "하드"
    assert difficulty_ko("chaos") == "카오스"
    assert difficulty_ko("normal") == "노멀"
    assert difficulty_ko("미상") == "미상"  # 미지정은 원문 유지


def test_weekly_boss_limit_fallback():
    assert weekly_boss_limit(12) == 12
    assert weekly_boss_limit(0) == 12  # (0,0) 캐릭 → 12 폴백
    assert weekly_boss_limit(-1) == 12


def test_strip_prefix_removes_leading_bracket():
    assert strip_prefix("[일일 퀘스트] 소멸의 여로") == "소멸의 여로"
    assert strip_prefix("[길드] 지하 수로") == "지하 수로"
    assert strip_prefix("무릉도장") == "무릉도장"  # 프리픽스 없으면 그대로


def test_truncate_strips_then_ellipsizes():
    assert truncate("[일일 퀘스트] 짧은") == "짧은"
    out = truncate("[길드] " + "가" * 30, limit=10)
    assert out.endswith("…") and len(out) == 10


# ── 버킷·집계 ────────────────────────────────────────────────────────────────


def test_by_category_excludes_qs0_and_splits():
    hw = parse_homework(_sample())
    quests = by_category(hw.daily, CAT_QUEST)
    assert all("탈라하트" not in c.name for c in quests)  # qs0 제외
    assert {c.name.split("] ")[-1] for c in quests} == {"소멸의 여로 조사", "리멘 조사"}
    assert [c.name for c in by_category(hw.daily, CAT_COUNT)] == ["몬스터파크"]
    assert [c.name for c in by_category(hw.weekly, CAT_GUILD)] == ["[길드] 지하 수로"]
    binaries = [c.name for c in by_category(hw.weekly, CAT_BINARY)]
    assert binaries == ["에르다 스펙트럼", "에픽 던전 : 하이마운틴"]  # 에픽던전 포함


def test_bosses_by_cycle():
    hw = parse_homework(_sample())
    assert [b.name for b in bosses_by_cycle(hw.boss, CYCLE_WEEKLY)] == ["스우"]
    assert [b.name for b in bosses_by_cycle(hw.boss, CYCLE_DAILY)] == ["핑크빈"]
    assert [b.name for b in bosses_by_cycle(hw.boss, CYCLE_MONTHLY)] == ["검은 마법사"]
    assert bosses_other_cycle(hw.boss) == []


def test_bosses_other_cycle_fallback():
    bosses = [BossItem("정체불명", "hard", False, "bossWeird")]
    assert bosses_other_cycle(bosses) == bosses


def test_field_counts_excludes_qs0():
    items = [
        ContentItem("a", 0, 1, type="quest", quest_state="2"),  # 완료
        ContentItem("b", 0, 1, type="quest", quest_state="1"),  # 미완료
        ContentItem("c", 0, 0, type="quest", quest_state="0"),  # 제외
    ]
    assert field_counts(items) == (1, 2)


def test_boss_counts():
    items = [BossItem("a", "hard", True), BossItem("b", "hard", False)]
    assert boss_counts(items) == (1, 2)


# ── 본문 렌더 ────────────────────────────────────────────────────────────────


def test_content_field_value_todo_first():
    items = [
        ContentItem("몬스터파크", 2, 14),  # 진행중 회수
        ContentItem("에픽 던전 : 하이마운틴", 5, 0),  # 이진 완료(now>0)
        ContentItem("[일일 퀘스트] 소멸의 여로", 0, 100, type="quest", quest_state="1"),
        ContentItem("[일일 퀘스트] 리멘", 0, 100, type="quest", quest_state="2"),
        ContentItem("[일일 퀘스트] 탈라하트", 0, 0, type="quest", quest_state="0"),
    ]
    out = content_field_value(items)
    lines = out.split("\n")
    assert lines[0] == "🟡 몬스터파크 `2/14`"  # 진행중 게이지 먼저
    assert "⬜ 소멸의 여로" in out  # 미완료 체크박스(0/100 소멸)
    assert (
        "✅ 완료 2개 · 에픽 던전 : 하이마운틴 · 리멘" in out
    )  # 완료 수+이름(에픽 포함)
    assert "탈라하트" not in out  # qs0 제외


def test_content_field_value_all_done_collapses():
    items = [
        ContentItem("a", 0, 1, type="quest", quest_state="2"),
        ContentItem("b", 1, 1),
    ]
    assert content_field_value(items) == "✅ 완료 2개 · a · b"


def test_guild_field_value():
    items = [
        ContentItem("[길드] 지하 수로", 0, 0),
        ContentItem("[길드] 주간 미션 포인트", 1240, 0),
    ]
    out = guild_field_value(items)
    assert "⬜ 지하 수로" in out  # now==0 → 아직
    assert "🔹 주간 미션 포인트 `1240`" in out  # now>0 → 점수


def test_boss_cycle_value_undone_first():
    items = [
        BossItem("자쿰", "chaos", True, CYCLE_WEEKLY),  # 처치
        BossItem("스우", "hard", False, CYCLE_WEEKLY),  # 미처치
        BossItem("이름만", "", False, CYCLE_WEEKLY),  # 난이도 없음
    ]
    out = boss_cycle_value(items)
    lines = out.split("\n")
    assert lines[0] == "⬜ 스우(하드)"  # 미처치 먼저 + 난이도 한글
    assert lines[1] == "⬜ 이름만"  # 난이도 없으면 생략
    assert "✅ 처치 1개 · 자쿰" in out


# ── 길이 안전(클램프) ─────────────────────────────────────────────────────────


def test_join_clamp_collapses_overflow():
    out = join_clamp([f"항목{i}" for i in range(50)], limit=20)
    assert "…외" in out and len(out) <= 30


def test_section_text_joins_and_clamps():
    assert section_text(["a", "b", "c"]) == "a\nb\nc"
    assert section_text([]) == ""
    out = section_text([f"⬜ 보스{i}(하드)" for i in range(200)])
    assert "…외" in out and len(out) <= 1024
