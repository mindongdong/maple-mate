# 작업 지시서 — 수동 썬데이 HTTP 엔드포인트 (Phase 4 마지막)

> 설계 §4 "수동 썬데이 발송(HTTP API)". 자동 `/썬데이`(PR #3)가 남긴 `broadcast_sunday`·주차 마커를 재사용해
> 운영자 트리거 발송 엔드포인트를 얹는다. **왜 이렇게 짓는가**는 짝 문서 [manual-sunday-handoff.md](manual-sunday-handoff.md)
> (결정 #1~#8·근거·리스크)를 먼저 읽을 것. 이 문서는 **무엇을 어떻게 짓는가**(빌드 단위·시그니처·검증)만 담는다.
> 복잡도 낮음 → `executor`(표준)로 충분. 테스트는 순수 로직 단위테스트(실용 테스트 합의).

## 참조 (중복 금지 — 경로로 참조)

- **[manual-sunday-handoff.md](manual-sunday-handoff.md) — 결정 #1~#8·근거·마킹 게이트 분기 이유·리스크. 반드시 먼저 읽을 것.**
- [maple-discord-bot-design.md](../maple-discord-bot-design.md) §4·§6 — 수동 발송·운영자 명세(SSOT)
- [sunday-work-order.md](sunday-work-order.md) — 자동 `/썬데이` 완성 지시서(발송 어댑터·주차 dedup 패턴)
- [CONTEXT.md](../CONTEXT.md) — `수동 썬데이 발송`·`운영자`(이 세션 추가)

## 확정 결정 (핸드오프 요약)

| # | 결정 | 선택 |
|---|---|---|
| #1 | HTTP→봇 배선 | `serve()`에서 `app.state.bot = bot` 주입 → `request.app.state.bot` |
| #2 | 주차 dedup | 무조건 발송(체크 안 함) 후 마킹 — 운영자 override |
| #3 | 0채널 | 마킹 스킵, `200 {sent:0,total:0}` |
| #4 | 바디 | `title` 필수 / `link`·`period` 선택, 단일 이벤트, `period` 없으면 "기간 미정" |
| #5 | 인증 | Bearer ↔ `operator_token` `secrets.compare_digest`, 실패 401 단일 + 앱로그만(error_log 미적재) |
| #6 | 경로/응답 | `POST /sunday/broadcast` → `200 {sent,total}`, 검증실패 422 |
| #7 | 마킹 게이트 | **`sent>0` 일 때만** 마킹(자동잡 `channels>0`과 의도적 분기 — 주석 명시) |
| #8 | 테스트 | 순수(매핑·auth) + 오케스트레이션 mock(401·마킹분기) |

## 현황 진단

**재사용 (import만, 새로 만들지 말 것):**
- [scheduler.py:82](../maple_mate/notification/scheduler.py#L82) `broadcast_sunday(bot, channels, events) -> int`
- [service.py](../maple_mate/notification/service.py): `SundayEvent`(32)·`enabled_sunday_channels`(178)·`mark_week_sent`(161)·`current_week_id`(60)
- [config.py:47](../maple_mate/config.py#L47) `Config.operator_token` (← `deps.config.operator_token`)
- [bot/embeds.py](../maple_mate/bot/embeds.py) `BRAND_COLOR`(임베드는 `build_event_embeds`가 이미 처리)

**마이그레이션:** 불필요(`sunday_alert`·`notice_state` 기존).

## 빌드 단위 (의존 순서)

### 1. `maple_mate/security/auth.py` — Bearer 검증 (신규)
[security/__init__.py](../maple_mate/security/__init__.py)가 "OPERATOR_TOKEN 상수시간 비교 추가 예정"으로 예고한 자리.
```python
from fastapi import Request, HTTPException

def verify_operator_token(request: Request) -> None:
    """Authorization: Bearer <token> 를 operator_token 과 상수시간 비교. 실패 시 401.
    FastAPI 의존성(Depends)으로 라우트에 부착. 누락·형식오류·불일치 모두 동일 401(정보 누출 차단)."""
    import secrets
    header = request.headers.get("Authorization", "")
    expected = request.app.state.deps.config.operator_token
    token = header[7:] if header.startswith("Bearer ") else ""
    if not token or not secrets.compare_digest(token, expected):
        log.warning("수동 썬데이: 인증 실패")          # 앱로그만, error_log 미적재(#5)
        raise HTTPException(status_code=401, detail="unauthorized")
```
- 평문 `==` 금지(상수시간 비교 고정). `expected`가 빈 문자열일 일은 없음(config fail-fast).
- *검증: 정상 통과 / 헤더 누락 / `Bearer ` 접두 없음 / 토큰 불일치 → 401. fake Request 또는 TestClient 단위테스트.*

### 2. `maple_mate/notification/scheduler.py` — `manual_broadcast_sunday` 추가 (기존 수정)
`broadcast_sunday` 바로 아래에, delivery-aware 오케스트레이션을 추가(봇 의존이라 전달-무관 service.py가 아닌 여기).
```python
async def manual_broadcast_sunday(
    bot: discord.Client, deps: Deps, event: SundayEvent
) -> tuple[int, int]:
    """운영자 수동 발송: 채널 조회 → 즉시 발송 → sent>0 이면 주차 마킹. (sent, total) 반환.

    자동 run_sunday_job 과 달리 already_sent_this_week 체크 없음(운영자 override, #2).
    마킹 게이트도 자동잡(channels>0)과 달리 **sent>0** — 실제 전달 0이면 그 주는
    미처리로 남겨 금요일 자동발송을 살린다(#3·#7).
    """
    session_factory = deps.session_factory
    channels = await service.enabled_sunday_channels(session_factory)
    total = len(channels)
    if total == 0:
        return (0, 0)                                  # 0채널 → 마킹 안 함(#3)
    sent = await broadcast_sunday(bot, channels, [event])
    if sent > 0:                                       # sent>0 일 때만 마킹(#7)
        week_id = service.current_week_id(datetime.now(KST))
        await service.mark_week_sent(session_factory, week_id)
    return (sent, total)
```
- `datetime.now(KST)`·`service`·`broadcast_sunday`·`SundayEvent`는 이미 이 모듈 import 범위 안.
- *검증: 0채널→(0,0)·미마킹 / sent>0→마킹 호출 / sent=0(전채널 실패)→미마킹. `broadcast_sunday`·`enabled_sunday_channels`·`mark_week_sent` mock.*

### 3. `maple_mate/notification/views.py` — FastAPI 라우터 (신규)
[api/core.py:5](../maple_mate/api/core.py#L5) 주석이 예고한 모듈.
```python
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from ..security.auth import verify_operator_token
from .scheduler import manual_broadcast_sunday
from .service import SundayEvent

router = APIRouter()

class SundayBroadcastBody(BaseModel):
    title: str = Field(min_length=1)                   # 필수(#4)
    link: str | None = None
    period: str | None = None

def _to_event(body: SundayBroadcastBody) -> SundayEvent:   # 순수 매퍼 — 단위테스트 대상
    return SundayEvent(
        title=body.title,
        url=body.link or "",
        thumbnail_url=None,
        period_text=body.period or "기간 미정",          # format_period 폴백과 일관(#4)
        detail_image_url=None,
    )

@router.post("/sunday/broadcast", dependencies=[Depends(verify_operator_token)])
async def manual_sunday(body: SundayBroadcastBody, request: Request) -> dict[str, int]:
    sent, total = await manual_broadcast_sunday(
        request.app.state.bot, request.app.state.deps, _to_event(body)
    )
    return {"sent": sent, "total": total}
```
- `title` 빈/누락 → pydantic이 422 자동 반환(#6). Bearer 실패 → `Depends`가 401(빌드 1).
- pydantic은 FastAPI 의존이라 신규 패키지 불필요.
- *검증: `_to_event` 매핑(link/period None → ""·"기간 미정")·title 빈 문자열 422·인증 실패 401(TestClient + mock bot/deps).*

### 4. 배선 — `api/core.py` + `main.py` (기존 수정, 외과적 2곳)
- [api/core.py](../maple_mate/api/core.py): import + `api_router.include_router(router)` (파일 주석대로).
```python
from ..notification.views import router as sunday_router
api_router.include_router(sunday_router)
```
- [main.py:45](../maple_mate/main.py#L45) `serve()`의 `app = create_app(deps)` **직후** 한 줄:
```python
app.state.bot = bot       # 수동 썬데이 HTTP 핸들러가 broadcast 에 쓸 봇 레퍼런스(#1)
```
- *검증: `uv run python -m maple_mate` 기동 후 `/health` 정상 + 라우트 등록 확인.*

### 5. `scripts/trigger_sunday.py` — 라이브 검증 도구 (신규, `trigger_notice.py` 패턴)
- 로컬에서 `POST http://localhost:8080/sunday/broadcast` 호출(`httpx`, 이미 의존). `Authorization: Bearer $OPERATOR_TOKEN` + JSON 바디(제목·링크·기간 CLI 인자 또는 상수). 응답 `{sent,total}` 출력.
- 용도: 봇 가동 중 테스트 채널(`sunday_alert` on)로 실제 발송 1회 눈 확인 + 401/422 수동 확인.

### 6. 테스트 — `tests/` (신규)
- `test_manual_sunday_auth.py`: `verify_operator_token` 정상/누락/접두오류/불일치(401).
- `test_manual_sunday_view.py`: `_to_event` 매핑·422(빈 title)·401(TestClient, bot/deps mock).
- `test_manual_sunday_orchestration.py`: `manual_broadcast_sunday` 0채널→(0,0)·미마킹 / sent>0→마킹 / sent=0→미마킹(`broadcast_sunday`·`enabled_sunday_channels`·`mark_week_sent` mock).
- discord/DB는 mock. E2E 생략.

## 영향 파일 요약
```
신규:  maple_mate/security/auth.py
       maple_mate/notification/views.py
       scripts/trigger_sunday.py
       tests/test_manual_sunday_{auth,view,orchestration}.py
수정:  maple_mate/notification/scheduler.py  (manual_broadcast_sunday 추가)
       maple_mate/api/core.py               (sunday_router include)
       maple_mate/main.py                   (app.state.bot 주입 1줄)
```

## 산출물
- 위 코드 + 단위테스트 통과 + `uv run pytest` 그린 + `uvx ruff check maple_mate/`.
- 봇 가동 시 `scripts/trigger_sunday.py`로 라이브 발송 1회 + 401/422 눈 확인.
- 문서 갱신: [work-plan.md](work-plan.md) line 83(미착수→완료)·Phase 4 상태(🟡→✅).

## 미실측 / 리스크 (핸드오프 §미해결 참조)
- ⚠️ HTTP 노출면(`0.0.0.0:8080`) — 운영 배포 시 바인딩/방화벽 검토(코드 밖).
- 중복 POST 멱등성 없음(운영자 책임) · 봇 미준비 시 sent=0(재시도) · 제목 검증 없음(운영자 신뢰).

## 스코프 밖
- 발송 이력 영속화·재발송 UI·복수 운영자 권한 등급 — 백로그.
- 썸네일/상세 배너 입력 — 수동은 텍스트만.
