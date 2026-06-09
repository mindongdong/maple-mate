# 배포·확장 계획서 — maple-mate

> 구현(Spike 0 ~ Phase 5)은 완료. 이 문서는 **배포(Render) + 공개 서비스 확장**의 단일 로드맵이다.
> 친구 그룹 가동 → 메이플 커뮤니티 공개로 가는 길에서 **무엇을 어떤 순서로, 어디까지 감당되는가**를
> 코드 근거(파일:라인)와 함께 확정한다. 복잡도: 배포 수정은 작고 외과적(`executor` 표준), 튜닝은
> 병목 1개(전역 스로틀)가 지배적. **단계 0~1은 즉시 착수 가능**, 단계 2는 공개 직전, 단계 3은 인기 후.

## 참조 (중복 금지 — 경로로 참조)

- [work-plan.md](work-plan.md) — 구현 로드맵·진행 현황(Spike 0~Phase 5 완료). 본 문서는 그 **다음 단계**.
- [maple-discord-bot-design.md](../maple-discord-bot-design.md) — 제품/동작 명세(SSOT).
- [adr/0001-nexon-personal-key-model.md](adr/0001-nexon-personal-key-model.md) — 개인키 모델 근거. **본 문서 §2가 그 약관 의존성을 해소**.
- 넥슨 약관/한도(원문): [이용약관](https://openapi.nexon.com/ko/support/terms/) · [API 사용하기](https://openapi.nexon.com/ko/guide/request-api/) · [앱 등록](https://openapi.nexon.com/ko/guide/prepare-in-advance/)
- Render: [Deploy for Free(티어 동작)](https://render.com/docs/free)

## 1. 배포 아키텍처 (확정)

**핵심 정정:** 디스코드 봇은 사용자별로 "탑재"되는 게 아니다. **단일 봇 애플리케이션(토큰 1개)** 이
Render에서 1번 실행되고, 사용자는 **OAuth2 초대링크 클릭**으로 그 봇을 자기 서버에 추가한다(자가 배포 없음).
봇은 게이트웨이로 단일 WebSocket을 열어 추가된 모든 서버의 이벤트를 그 한 연결로 받는다.

```
 디스코드 게이트웨이 ⇄ ┌──────────────────────────────────────────┐ ⇄ Render Postgres
 (봇→디스코드 아웃바운드  │ Render Web Service (단일 프로세스 · 1 인스턴스) │
  WebSocket 1개)        │ discord.py 봇 + FastAPI + APScheduler      │
                       └──────────────────────────────────────────┘
                                         ⇅
                                   넥슨 Open API
```

| 항목 | 결정 | 근거 |
|---|---|---|
| 실행 단위 | 단일 프로세스(봇+FastAPI+스케줄러) | [main.py:42-53](../maple_mate/main.py#L42-L53) 한 이벤트 루프 동시 기동 |
| Render 서비스 형태 | **Web Service (Starter 유료, 상시 가동)** | `$PORT` 바인딩→헬스체크 통과→게이트웨이·스케줄러 상시 유지. `POST /sunday/broadcast` 공개 URL 확보 |
| 무료 티어 | **사용 불가** | 15분 무트래픽 슬립→게이트웨이/스케줄러 사망. 무료 DB 30일 만료·백업 없음 |
| 인스턴스 수 | **정확히 1** | 스케줄러 in-process([bot/core.py:43-44](../maple_mate/bot/core.py#L43-L44))—2개면 알림 중복발송. 오토스케일 끄기 |
| 멀티테넌시 | guild_id 스코핑(이미 구현) | [registration/models.py:16-17](../maple_mate/registration/models.py#L16-L17)·[notification/models.py:20-21](../maple_mate/notification/models.py#L20-L21) |
| DB | Render Postgres(유료) | 같은 리전 Internal URL 사용(SSL 불필요·빠름) |

## 2. 넥슨 약관 검토 (확정 — go)

공개 서비스 의도로 약관 원문 대조 완료. **결론: 출처표시 1건만 남고 나머지는 해소.**

| 조항 | 내용 | 우리 서비스 판정 |
|---|---|---|
| **제5조①②** | API Key 공유·타인키 사용 금지 **(단, 일부 API는 소유자 공개동의 시 제공 가능)** | ✅ 개인키=**공개동의 옵션** 사용 → 단서 충족. 이력류 OK |
| **제5조⑤** | 결과데이터 복제·저장·가공·배포·제3자 재제공은 사전 동의 범위 내 | ✅ 재배포 허용 확인 |
| **제6조⑥** | 데이터 영리 목적 이용은 회사 승낙 필요 | ✅ 디스코드 봇 **수익화 안 함** → 회피 |
| **제6조④** | 결과데이터에 'NEXON Open API' 출처 명시 의무 | 🔴 **미반영 → 작업 0-1** |

**넥슨 호출 한도:** 개발단계 5건/초·1,000건/일 → **서비스단계 500건/초·2,000만건/일**(공개 시 서비스단계 등록 필요).

## 3. 단계별 작업 계획

### 🟢 단계 0 — 약관 컴플라이언스 (즉시)

- **0-1 출처표시** — 모든 데이터 임베드 푸터에 `데이터 출처: NEXON Open API` 추가.
  *→ verify: `/스펙`·`/스타포스`·`/잠재`·`/썬데이`·`/공지알림`·운영요약 임베드 푸터에 문구 노출.*
  대상: [bot/embeds.py:48](../maple_mate/bot/embeds.py#L48) 공통 푸터 + [scheduler.py:214](../maple_mate/notification/scheduler.py#L214) 등 개별 푸터.

### 🔴 단계 1 — Render 배포 (친구 그룹 가동)

**필수 코드 수정**

| # | 작업 | 위치 | verify |
|---|---|---|---|
| 1-1 | `DEV_GUILD_ID` **선택값화** (필수→옵션). 운영 시 빈 값이면 글로벌 동기화 | [config.py:22-25](../maple_mate/config.py#L22-L25) + [bot/core.py:34-41](../maple_mate/bot/core.py#L34-L41) | 빈 값으로 기동 성공 + 글로벌 명령 동기화 로그 |
| 1-2 | **`PORT` 환경변수 읽기** (`os.environ.get("PORT", 8080)`) | [main.py:29](../maple_mate/main.py#L29) | Render 주입 포트로 헬스체크 통과 |
| 1-3 | **DATABASE_URL** `postgresql+asyncpg://` 스킴 정규화 | [config.py:85](../maple_mate/config.py#L85)·[database/core.py:23](../maple_mate/database/core.py#L23) | Render Postgres 연결 성공 |
| 1-4 | **`tzdata`** 의존성 추가 | [pyproject.toml](../pyproject.toml) | 컨테이너에서 `ZoneInfo("Asia/Seoul")` 무오류 |
| 1-5 | **Dockerfile + render.yaml** 스캐폴드(uv 빌드) | 신규 | `render.yaml`로 서비스+DB+env 선언 |

> ⚠️ **1-1이 멀티서버 최대 블로커**: 현재 `DEV_GUILD_ID` 필수라 그 dev 길드에만 명령이 떠
> 다른 사용자 서버에선 슬래시 명령이 안 보인다. 글로벌 동기화는 이 값이 비었을 때만 실행됨.

**Render 인프라 설정 (코드 아님)**

- Web Service(Starter) + Render Postgres(유료, Internal URL) 생성
- 환경변수 6종 등록: `DISCORD_BOT_TOKEN`·`NEXON_APP_KEY`·`FERNET_MASTER_KEY`·`OPERATOR_TOKEN`·`ADMIN_CHANNEL_ID`·`DATABASE_URL`
  *→ `FERNET_MASTER_KEY` 분실 시 등록된 개인키 전부 복호화 불가 — 안전 보관 필수*
- 배포 파이프라인에 `uv run alembic upgrade head`
- 헬스체크 경로 `/health`([api/core.py:23-25](../maple_mate/api/core.py#L23-L25)) · **인스턴스 1개**(오토스케일 off)
- Discord 개발자 포털: **Public Bot** + 초대링크 스코프 `bot`+`applications.commands`(권한 최소: Send Messages·Embed Links). 특권 인텐트 불필요([bot/core.py:23](../maple_mate/bot/core.py#L23))

**라이브 검증 (work-plan 잔여)**

- `/잠재` G1 등업 확정 (`scripts/spike_potential.py` 1콜)
- `/공지알림` baseline 1주기 관찰 · 운영요약 임베드 눈 확인 (`scripts/trigger_ops_summary.py`)

### 🟡 단계 2 — 공개 커뮤니티 대비 튜닝 (홍보 직전)

**지배적 병목 = 전역 4 req/s 스로틀.** [client.py:44](../maple_mate/nexon/client.py#L44) `throttle=0.25` +
단일 `asyncio.Lock`([client.py:73-81](../maple_mate/nexon/client.py#L73-L81))이 **봇 전체의 모든 넥슨 호출(앱키·개인키 공용)을
직렬화**해 초당 4건으로 묶는다. 명령 지연 = (앞에 쌓인 호출 수) × 0.25초.

| 명령 | 넥슨 호출 수 | 4/초 환산 |
|---|---|---|
| `/스펙` 1인(warm) | ~6 ([service.py:272-279](../maple_mate/character/service.py#L272-L279)) | ~1.5초 |
| `/스펙` 5인 비교 | ~30 (cold ~65) | ~7.5초 |
| `/스타포스`·`/잠재` 최근1년 첫조회 | 최대 365 (날짜당 1콜 [service.py:229-235](../maple_mate/history/service.py#L229-L235)) | ~90초 전역 점유 |

| # | 작업 | 위치 | 효과 |
|---|---|---|---|
| 2-1 | **넥슨 서비스단계 등록** | 넥슨 콘솔 | 한도 5→500/초 |
| 2-2 | **전역 스로틀 상향** (0.25→~0.02, 서비스 한도 내) | [client.py:44](../maple_mate/nexon/client.py#L44) | 처리량 12배+ |
| 2-3 | **CPU 작업 `to_thread` 오프로딩** (Pillow·마르코프, 현재 이벤트루프 블로킹·`to_thread` 0건) | [table_image.py](../maple_mate/bot/table_image.py)·[item_card.py](../maple_mate/bot/item_card.py)·[expected_cost.py](../maple_mate/history/expected_cost.py) | 동시성 |
| 2-4 | **사용자별 쿨다운** (어뷰즈 방어 — 현재 백프레셔가 전역 스로틀뿐) | 명령 계층 | 공개 필수 |
| 2-5 | **`history_cache` prune** (무한 증가 — prune는 error_log만 [summary.py:133](../maple_mate/error_log/summary.py#L133)) | summary.py 패턴 답습 | DB 보호 |
| 2-6 | **최신 스펙 단기 캐시** (date=None 호출은 현재 매번 재조회) | [service.py:272-279](../maple_mate/character/service.py#L272-L279) | 반복조회 |
| 2-7 | **인스턴스 등급 상향** (0.5→2 vCPU) | Render | CPU 여유 |

*→ verify: 동시 명령 20건 부하 시 큐 누적 없이 응답 / 어뷰즈 스팸이 전체를 막지 않음 / `history_cache` 행수 상한 유지.*
도달 가능 규모: **활성 수백~낮은 수천**.

### 🔵 단계 3 — 본격 스케일 (수천 서버, 필요 시)

- `discord.Client` → **AutoShardedClient** (디스코드가 ~2,500 길드에서 샤딩 강제 [bot/core.py:21](../maple_mate/bot/core.py#L21))
- 게이트웨이/API/스케줄러 **프로세스 분리** + 스케줄러 단일 리더화
- **Redis 분산 레이트리미터** (현재 스로틀은 프로세스 내 전역)
- 앱키 SPOF 대책 (auth_invalid 시 전체 마비 — 운영요약이 이미 🔴로 감지 [scheduler.py:192-196](../maple_mate/notification/scheduler.py#L192-L196))

→ "단일 서비스 배포"가 아니라 분산 시스템. Render에서 가능(멀티 서비스 + Key Value + 큰 Postgres).

## 4. 수용량 요약

| 구성 | 감당 규모 | 무너지는 지점 |
|---|---|---|
| 단계 1 (배포만) | 친구 그룹~소규모(동시성 낮음) | 짧은 시간 명령 4~8개 몰리면 지연. 광역 이력조회 시 전체 ~90초 정지 |
| 단계 2 (튜닝) | 활성 수백~낮은 수천 | 넥슨 실한도·단일 인스턴스 CPU |
| 단계 3 (분산) | 수천 서버~ | 재설계 범위 |

## 5. 비용 (배포 시점 재확인)

- Web Service Starter ~$7/월 + Render Postgres Basic ~$7/월 ≈ **월 ~$14** (+ 워크스페이스 시트 요금 가능)
- 무료 티어 부적합(봇·DB 둘 다)

## 6. 리스크 / 한계

- **단일 `NEXON_APP_KEY` = SPOF** — 차단/만료 시 전 서버 스펙류 마비. 운영요약 🔴 최우선 감지로 조기 대응.
- **`history_cache` 무한 증가** — 단계 2-5 전까지 누적 주의.
- **discord.py 메모리** — 길드 수 비례. 512MB는 수백 서버대에서 압박 → 단계 2-7로 완화.
- **약관 의존성** — 개인키 공개동의 옵션·재배포 허용·비수익화 전제가 깨지면 §2 재검토.

## 7. 권장 순서

1. **지금**: 단계 0(출처표시) + 단계 1(배포 수정 5건) 한 브랜치 → Render 가동 → 라이브 검증 → 친구 그룹 오픈
2. **홍보 직전**: 단계 2 튜닝 + 넥슨 서비스단계 등록
3. **인기 후**: 단계 3 분산

## 8. 미해결 결정 (착수 시 확정)

1. **render.yaml(IaC) vs 대시보드 수동 설정** — 재현성 위해 render.yaml 권장(기본안).
2. **Dockerfile vs Render 네이티브 Python+uv 빌드** — uv.lock 고정 재현성 위해 Dockerfile 권장(기본안).
3. **커스텀 도메인 / `OPERATOR_TOKEN` 수동 썬데이 엔드포인트 공개 범위** — 운영자 전용이면 그대로, 공개 URL 노출만 주의.
