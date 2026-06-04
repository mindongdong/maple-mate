# 넥슨 메이플스토리 Open API 레퍼런스

maple-mate 봇이 사용하는 넥슨 메이플스토리 Open API의 엔드포인트·스키마 레퍼런스.
봇은 Python `httpx`로 이 API를 호출하고, 디스코드용 API 서버는 FastAPI로 구성한다.

> **출처/검증:** 공식 문서(<https://openapi.nexon.com/game/maplestory/>)의 엔드포인트 경로·파라미터,
> 그리고 [SpiralMoon/maplestory.openapi](https://github.com/SpiralMoon/maplestory.openapi)
> KMS 클라이언트의 DTO 정의로 응답 필드명을 교차검증함.
> **Spike 0 완료(2026-06-04):** 프로젝트가 쓰는 17개 엔드포인트는 실호출로 검증됨(이력류 키 모델 = **GO**). 결과·잔류 항목은 [api-verification-plan.md](../api-verification-plan.md) 참고. 이하 문서의 "실호출로 확정" 표기는 그 검증 결과.

## 공통 규약

### Base URL
```
https://open.api.nexon.com
```
모든 엔드포인트는 이 호스트 + `maplestory/v1/...` 경로. HTTPS GET, 응답 `application/json`.

### 인증
```
x-nxopen-api-key: {API_KEY}
```
- **스펙류**(캐릭터·유니온·길드·연무장·랭킹·공지) → 봇 **앱 키** + `ocid`로 임의 캐릭터 공개 데이터 조회.
- **이력류**(`history/*` — 스타포스·큐브·잠재) → 데이터가 **API 키 소유 계정에 스코프**됨(아래 참고).

스펙류/이력류 구분은 [CONTEXT.md](../../CONTEXT.md) 용어 사전 참고.

### 날짜 · 시간 (KST 기준)
- `date` 파라미터 형식: **`YYYY-MM-DD`** (KST).
- 조회 가능 시작일: **2023-12-21** (이전 데이터 없음).
- 캐릭터/유니온/길드 등 **스펙류는 전일(D-1) 기준** — 전일 데이터는 다음날 **오전 1시(KST) 이후** 조회 가능. `date` 미지정 시 최신.
  - ⚠️ **실호출로 확정(2026-06-04 01:10 KST):** "1시 이후 D-1" 경계는 **soft**다. 01:10 시점에 D-1 호출은 **`OPENAPI00009` "data not ready"** 였고 실제 최신 ready 일자는 **D-2**였다. 미래/당일 날짜는 **`OPENAPI00004`**. **`date` 미지정 시 200 + 응답 `date:null`로 "최신 ready 스냅샷"을 반환** → 봇은 D-1을 직접 계산해 넘기기보다 **무지정(최신) 호출** 또는 **`OPENAPI00009` 폴백**을 써야 한다.
- 이력류 동일자(오늘) 데이터: **실호출로 확정** — 이력류 `history/*`는 **당일(오늘) 날짜 호출을 200으로 수용**한다(스펙류 당일=`OPENAPI00004`와 대비). 따라서 봇 `/스타포스 오늘` 프리셋은 가능. 단 검증 시 당일 활동이 0이라 **반영 지연(딜레이)은 미측정** — 5분 TTL 적정성은 활동 있는 키로 후속 확인 권장.
- 이력류 **조회 범위는 롤링 ~2년 윈도우**(실측: 730일전 200 / 760일전 `OPENAPI00004`). 카테고리별 절대 시작일(아래 history.md)은 현재 2년 초과 시 우선순위에서 밀려 400. 봇 30일 상한 설계엔 무관.

### ocid 조회 흐름
1. `GET maplestory/v1/id?character_name={닉네임}` → `{ "ocid": "..." }`
2. 이후 모든 스펙류 조회는 `ocid`로. 봇은 ocid를 캐싱하고, 조회 실패 시 1회 재조회(lazy 갱신).

### 에러 응답
```json
{ "error": { "name": "OPENAPI00004", "message": "Please input valid parameter" } }
```
*실호출로 확정(2026-06-04):* 위 `{ "error": { name, message } }` 구조가 표준이며 HTTP 4xx와 함께 온다. 실측 메시지 예 — `OPENAPI00004`="Please input valid parameter", `OPENAPI00005`="The apikey is not valid.", `OPENAPI00009`="Please wait until the data is ready", `OPENAPI00003`="Please input valid id", `OPENAPI00007`="Please try again later".

> **Rate limit (실측):** 검증에 쓴 `test_` 프리픽스 키는 `x-ratelimit-limit: 5`(짧은 창, 약 5/sec)로 초과 시 **429 `OPENAPI00007`**. 운영 클라이언트는 스로틀·재시도 필요. live(서비스) 키 한도는 별도 확인 대상.

| 코드 | HTTP | 의미 |
|---|---|---|
| OPENAPI00001 | 500 | 서버 내부 오류 |
| OPENAPI00002 | 403 | 권한 없음 |
| OPENAPI00003 | 400 | 유효하지 않은 식별자 |
| OPENAPI00004 | 400 | 파라미터 누락/오류 |
| OPENAPI00005 | 400 | 유효하지 않은 API 키 |
| OPENAPI00006 | 400 | 유효하지 않은 게임/경로 |
| OPENAPI00007 | 429 | 호출 한도 초과(rate limit) |
| OPENAPI00009 | 400 | 데이터 준비 중 |
| OPENAPI00010 | 400 | 서비스 점검 중 |
| OPENAPI00011 | 503 | API 점검 중 |

봇 매핑: `nexon_api`(00001/00006/00011) · `auth_invalid`(00002/00005) · `rate_limit`(00007) · 데이터 미준비(00009)는 "기록 없음/전일 미생성"으로 처리. ([error_log error_type](../../maple-discord-bot-design.md) §5⑤)

### httpx 클라이언트 패턴 (참고)
```python
import httpx

class NexonClient:
    BASE = "https://open.api.nexon.com"

    def __init__(self, api_key: str):
        self._client = httpx.AsyncClient(
            base_url=self.BASE,
            headers={"x-nxopen-api-key": api_key},
            timeout=10.0,
        )

    async def get(self, path: str, **params) -> dict:
        # None 값 파라미터 제거 후 GET
        q = {k: v for k, v in params.items() if v is not None}
        r = await self._client.get(path, params=q)
        r.raise_for_status()
        return r.json()
```

## 카테고리 문서

| 공식 id | 문서 | 포함 엔드포인트 |
|---|---|---|
| 14 | [character.md](./character.md) | `id` · `character/*` · `character/list` · `user/achievement` |
| 15 | [union.md](./union.md) | `user/union` · `union-raider` · `union-artifact` · `union-champion` |
| 16 | [guild.md](./guild.md) | `guild/id` · `guild/basic` |
| 55 | [battle-practice.md](./battle-practice.md) | `battle-practice/*` (연무장/전투분석) |
| 17 | [history.md](./history.md) | `history/cube` · `history/potential` · `history/starforce` **(이력류, 개인 키)** |
| 18 | [ranking.md](./ranking.md) | `ranking/overall·union·guild·dojang·theseed·achievement` |
| 24 | [notice.md](./notice.md) | `notice` · `notice-update` · `notice-event` · `notice-cashshop` (+`/detail`) |

## 봇 명령 → 엔드포인트 매핑

| 봇 명령 | 사용 엔드포인트 | 비고 |
|---|---|---|
| (공통) | `id` | 닉네임→ocid |
| `/스펙` | `character/basic`, `character/stat`(전투력), `character/ability`, `character/symbol-equipment`, `character/hexamatrix`, `character/hexamatrix-stat` | 스펙류 |
| `/아이템` | `character/item-equipment` | 스타포스·잠재·에디셔널·추가옵션·주문서 |
| `/유니온` | `user/union`, `user/union-artifact`, `user/union-champion` | 유니온레벨·아티팩트·챔피언 등급분포 |
| `/스타포스` | `history/starforce` | **이력류(개인 키)** |
| `/잠재`·`/잠재합계` | `history/cube`, `history/potential` | **이력류(개인 키)**, 두 엔드포인트 합산 |
| `/공지알림` | `notice`, `notice-update` | 이벤트 제외 |
| `/썬데이` | `notice-event` | title에 "썬데이 메이플" 매칭 |
