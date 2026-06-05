"""썬데이 임베드 빌드 단위테스트 (순수 — 작업지시서 Q6). discord 발송은 안 함."""
from __future__ import annotations

from maple_mate.bot.embeds import BRAND_COLOR
from maple_mate.notification.scheduler import build_event_embeds
from maple_mate.notification.service import SundayEvent


def _event(
    thumbnail_url: str | None = "https://x/thumb.jpg",
    detail_image_url: str | None = "https://lwi/banner.png",
) -> SundayEvent:
    return SundayEvent(
        title="썬데이 메이플 이벤트",
        url="https://maplestory.nexon.com/News/Event/1",
        thumbnail_url=thumbnail_url,
        period_text="2026-05-14 10:00 ~ 2026-05-17 23:59",
        detail_image_url=detail_image_url,
    )


def test_embed_has_hyperlinked_title_period_thumbnail_and_banner():
    [embed] = build_event_embeds([_event()])
    assert embed.title == "썬데이 메이플 이벤트"
    assert embed.url == "https://maplestory.nexon.com/News/Event/1"  # 제목=클릭 하이퍼링크
    assert embed.description == "2026-05-14 10:00 ~ 2026-05-17 23:59"  # 기간
    assert embed.thumbnail.url == "https://x/thumb.jpg"  # 목록 작은 썸네일
    assert embed.image.url == "https://lwi/banner.png"  # 상세 본문 큰 배너
    assert embed.color == BRAND_COLOR
    assert embed.footer.text is None  # 데이터-푸터 없음


def test_embed_omits_thumbnail_when_none():
    [embed] = build_event_embeds([_event(thumbnail_url=None)])
    assert embed.thumbnail.url is None


def test_embed_omits_banner_when_detail_image_none():
    [embed] = build_event_embeds([_event(detail_image_url=None)])
    assert embed.image.url is None


def test_embed_empty_url_becomes_none():
    event = SundayEvent(title="썬데이 메이플", url="", thumbnail_url=None, period_text="기간 미정")
    [embed] = build_event_embeds([event])
    assert embed.url is None


def test_multi_match_builds_one_embed_each():
    embeds = build_event_embeds([_event(), _event(thumbnail_url=None)])
    assert len(embeds) == 2
