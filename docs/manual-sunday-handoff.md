# 핸드오프 — 수동 썬데이 HTTP 엔드포인트 (그릴링 완료, 미착수)

> Phase 4 알림의 **마지막 조각**. 설계 §4 "수동 썬데이 발송(HTTP API)"이다. `/썬데이`(PR #3)에서
> `broadcast_sunday`·주차 마커를 **재사용 가능하게** 만들어 둔 상태에서, 이 세션의 그릴링(`/grill-with-docs`)으로
> 8개 결정을 모두 확정했다. 코드는 아직 미착수. 이 문서는 **왜 이렇게 짓는가(결정·근거·리스크)**를,
> 짝 문서 [manual-sunday-work-order.md](manual-sunday-work-order.md)는 **무엇을 어떻게 짓는가(빌드 단위·시그니처)**를 담는다.

## 참조 (중복 금지 — 경로로 참조)

- [manual-sunday-work-order.md](manual-sunday-work-order.md) — 이 기능의 빌드 단위·시그니처·검증(짝 문서, HOW)
- [maple-discord-bot-design.md](../maple-discord-bot-design.md) §4·§6·§5③④ — 수동 발송·운영자·데이터모델 명세(SSOT)
- [CONTEXT.md](../CONTEXT.md) — 도메인 용어. ⚠️ **이 세션에서 `수동 썬데이 발송`·`운영자` 신규 추가**
- [sunday-work-order.md](sunday-work-order.md) §3 Q3·Q7 — 자동 `/썬데이`의 주차 dedup·발송 어댑터 결정(재사용 대상의 원 결정)
- [work-plan.md](work-plan.md) — Phase 4 로드맵(line 83 = 이 작업)

## 현황 진단

**이미 있음 (재사용, 새로 만들지 말 것):**
- [notification/scheduler.py:82](../maple_mate/notification/scheduler.py#L82) `broadcast_sunday(bot, channels, events) -> int` — 채널 목록을 받도록 이미 일반화됨(주석에 "미래 수동 엔드포인트 재사용" 명시). 다중 임베드 발송·채널 해석 폴백·발송 실패 앱로그까지 완비.
- [notification/service.py](../maple_mate/notification/service.py) — `SundayEvent`(라인 32)·`enabled_sunday_channels`(178)·`mark_week_sent`(161)·`current_week_id`(60). 전부 전달-무관.
- [config.py:47](../maple_mate/config.py#L47) `operator_token` — `.env`의 `OPERATOR_TOKEN`이 이미 fail-fast 로딩됨. `deps.config.operator_token`로 접근.
- [api/core.py:5](../maple_mate/api/core.py#L5) — 주석이 `notification.views` 라우터 등록 자리까지 예고(`api_router.include_router(...)`).
- `channel_settings.sunday_alert` 컬럼, `notice_state(category="sunday")` 마커 — **Alembic 마이그레이션 불필요**.

**새로 만듦:** `security/auth.py`(Bearer 검증) · `notification/scheduler.py`에 `manual_broadcast_sunday` 추가 · `notification/views.py`(라우터+바디) · `api/core.py`·`main.py` 배선 2줄 · `scripts/trigger_sunday.py` · 테스트.

**핵심 공백 (이 세션의 발견):** [main.py:44-45](../maple_mate/main.py#L44)는 `bot`과 `app = create_app(deps)`를 **따로** 만들고, `app`에 봇 레퍼런스를 안 넘긴다. `Deps`(frozen)에도 봇이 없다. 즉 `broadcast_sunday`가 요구하는 디스코드 클라이언트에 HTTP 핸들러가 닿을 경로가 **현재 없다** → 결정 #1이 이를 메운다.

## 확정 결정 (그릴링 결과)

| # | 결정 | 선택 | 근거 |
|---|---|---|---|
| **#1** | HTTP→봇 배선 | `serve()`에서 `app.state.bot = bot` 주입, 핸들러는 `request.app.state.bot` | 기존 `app.state.deps` 패턴과 동일. 봇은 deps로 생성되므로 Deps에 넣으면 **순환의존** → state 주입이 정답. 봇·HTTP가 같은 asyncio 루프라 `channel.send` 스레드 안전 |
| **#2** | 주차 dedup | **무조건 발송**(`already_sent_this_week` 체크 안 함) 후 마킹 | 수동 = 운영자 **override**(공휴일 예외). 한 번 보낸 주엔 금요일 자동잡이 마커를 보고 스킵 → 중복 방지 |
| **#3** | 0채널 처리 | 마킹 스킵, `200 {sent:0, total:0}` | 자동잡과 동일(채널 0개면 마킹 안 함). 마킹하면 나중에 채널 켤 때 금요일 자동발송이 억제되는 버그 |
| **#4** | 바디 스키마 | `title` 필수 / `link`·`period` 선택, **단일 이벤트**, `period` 자유문자열(없으면 "기간 미정") | 설계 §4 "제목·링크·기간(직접 입력)". 운영자가 친 문자열을 그대로 `period_text`로(`format_period` 폴백과 일관). 수동은 1건이면 충분 |
| **#5** | 인증 | Bearer ↔ `operator_token` **상수시간 비교**(`secrets.compare_digest`), 실패 **401 단일 + 앱로그만** | 타이밍 공격 방지(보안 원칙). 누락·형식오류·불일치 구분 안 함(유효 토큰 존재 노출 차단). `error_log` 미적재(설계 §5 "재시도 건만", `auth_invalid` enum은 넥슨 키 검증용 맥락) |
| **#6** | 경로/응답 | `POST /sunday/broadcast` → `200 {sent, total}`, 검증실패 422 | 명확한 동사형 경로. `sent`/`total`로 운영자가 결과 확인 가능(204 대신 본문 반환) |
| **#7** | 마킹 게이트 | **`sent>0` 일 때만** 마킹 | #3을 일반화 + 봇 미준비·전채널 실패 레이스 동시 해소. **실제 전달 0이면 그 주는 미처리**로 남아 금요일 자동발송 생존. ⚠️ 자동잡(`channels>0`이면 부분실패도 마킹)과 **의도적 분기** — 수동은 자동 재시도 루프가 없어 의미가 다름 |
| **#8** | 테스트 | 순수(body→SundayEvent 매핑·auth verify) + 오케스트레이션(bot·session·broadcast mock) 401/마킹분기 | 프로젝트 "실용 테스트" 합의. 무거운 E2E 생략 |

## "마킹 게이트가 자동잡과 다른" 이유 (결정 #7 상세)

자동잡 [run_sunday_job](../maple_mate/notification/scheduler.py#L108)은 **채널이 있고 매칭 이벤트가 있으면 발송 성공 수와 무관하게 마킹**한다(`broadcast_sunday` 직후 `mark_week_sent` 무조건). 이유: 금요일 잡이 같은 주에 반복 실행될 때 마커가 중복 발송을 막아야 하므로, 채널 전부 실패해도 일단 마킹해 폭주를 끊는다.

수동은 다르다. **자동 재시도 루프가 없고**(운영자가 손으로 1회 트리거), 마킹의 부작용은 "그 주 금요일 자동발송 억제"다. 그래서 봇이 아직 ready가 아니거나 전 채널 발송이 실패한 상황(`sent==0`)에서 마킹하면 → 아무도 못 받았는데 금요일 정규 발송까지 막아 **그 주 썬데이 알림이 통째로 증발**한다. `sent>0` 게이트는 이걸 막는다: "한 명이라도 받았을 때만 그 주를 처리됨으로 표시." 0채널(#3)·봇 레이스·전채널 실패가 모두 한 규칙으로 떨어져 별도 readiness 가드도 불필요.

→ ADR은 생략. 되돌리기 비용이 낮고(국소적 한 줄 분기), 코드 주석으로 "수동은 자동과 달리 sent>0 게이트"만 남기면 충분.

## CONTEXT.md 갱신 (이 세션 반영 완료)

- **수동 썬데이 발송** — 운영자가 정규 금요일 예고와 별개로 트리거하는 1회성 발송. 자동과 같은 채널·주차 마커 공유. "썬데이 메이플" 제목 매칭에 구애받지 않음(운영자 직접 입력).
- **운영자** — 봇을 운영하는 단일 주체(개발자 본인). 일반 등록자와 권한 구별.
- Relationships에 "자동/수동이 발송 채널·주차 마커를 공유" 1줄 추가.

## 미해결 / 리스크

1. ⚠️ **HTTP 노출면** — uvicorn이 `0.0.0.0:8080`([main.py:28-29](../maple_mate/main.py#L28))로 바인딩. 유일한 방어선은 운영자 토큰이다. Mac Mini 홈서버에선 방화벽/리버스 프록시 또는 `127.0.0.1` 바인딩 검토(운영 배포 시 결정, 코드 범위 밖이나 기록).
2. ⚠️ **중복 POST 멱등성 없음** — 같은 요청을 두 번 보내면 두 번 발송(운영자 책임, 결정 #2). 손으로 트리거하는 단일 운영자라 수용.
3. **봇 미준비 레이스** — 결정 #7의 `sent>0` 게이트로 마킹 오염은 막지만, 그 호출 자체는 sent=0으로 끝난다(운영자가 응답 보고 재시도). 정상 동작.
4. **"썬데이 메이플" 제목 미매칭 발송** — 수동은 매칭 우회(의도). 운영자가 잘못된 제목·링크를 넣어도 그대로 발송됨(검증 없음, 운영자 신뢰).

## 스코프 밖 (이 작업 아님)

- 발송 이력 영속화·재발송 UI·복수 운영자/권한 등급 — 백로그(설계 §6 "운영자=단일").
- 썸네일·상세 배너 이미지 입력 — 수동은 텍스트(제목·링크·기간)만(`thumbnail_url`/`detail_image_url`=None).
- 일일 운영 요약(Phase 5) — 별개 작업.
