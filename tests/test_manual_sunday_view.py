"""수동 썬데이 라우터 단위테스트 — _to_event 매핑·422(빈 title)·401(인증) (핸드오프 #4·#6).

성공 경로(200)는 발송 오케스트레이션 쪽(test_manual_sunday_orchestration)에서 다룬다.
여기선 매퍼 순수성과 HTTP 검증/인증 경계만 본다(bot/deps mock, discord·DB 미접근).
"""

from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from maple_mate.notification import views

TOKEN = "tok"


def _client() -> TestClient:
    """라우터만 단 최소 앱. 401/422 는 핸들러 본체에 도달하기 전 끊기므로 bot 은 더미."""
    app = FastAPI()
    app.state.deps = SimpleNamespace(config=SimpleNamespace(operator_token=TOKEN))
    app.state.bot = object()
    app.include_router(views.router)
    return TestClient(app)


# ── _to_event: 순수 매퍼 ──────────────────────────────────────────────────


def test_to_event_maps_all_fields():
    event = views._to_event(
        views.SundayBroadcastBody(
            title="썬데이",
            link="https://x",
            period="6/9 ~ 6/15",
            image="https://img/banner.jpg",
        )
    )
    assert event.title == "썬데이"
    assert event.url == "https://x"
    assert event.period_text == "6/9 ~ 6/15"
    assert event.detail_image_url == "https://img/banner.jpg"  # 본문 배너로 실림
    assert event.thumbnail_url is None  # 수동은 썸네일 미입력


def test_to_event_defaults_when_optional_none():
    event = views._to_event(views.SundayBroadcastBody(title="t"))
    assert event.url == ""  # link None → ""
    assert event.period_text == "기간 미정"  # period None → 폴백
    assert event.detail_image_url is None  # image None → 배너 생략


# ── HTTP 경계: 422 / 401 ──────────────────────────────────────────────────


def test_empty_title_returns_422():
    resp = _client().post(
        "/sunday/broadcast",
        json={"title": ""},
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert resp.status_code == 422


def test_bad_token_returns_401():
    resp = _client().post(
        "/sunday/broadcast",
        json={"title": "x"},
        headers={"Authorization": "Bearer nope"},
    )
    assert resp.status_code == 401
