# 넥슨 API 실호출 검증 핸드오프 (Spike 0)

> **목적:** [작업계획](./work-plan.md)의 8개 기능 + 알림에 실제로 쓰이는 넥슨 엔드포인트만 골라,
> [docs/api/](./api/) 스펙 문서가 실제 응답과 일치하는지 **실호출로 검증**하고,
> 이력류 키 모델 등 미검증 가정을 확정한다. 이 문서 하나로 다른 세션이 검증을 수행할 수 있도록 작성됨.
>
> **이건 스파이크다.** 검증용 코드는 일회용(`spike/`)이며 Phase 1 본 구현이 아니다. 시크릿은 절대 커밋하지 않는다.

## 검증 범위 (프로젝트 필요 엔드포인트만 — 17개)

길드·랭킹·연무장(battle-practice)·캐시샵공지·`/detail`·미사용 캐릭터 서브엔드포인트는 8개 기능에 안 쓰이므로 **검증 제외**(문서는 참고용으로 유지).

### 그룹 A — 스펙류 (봇 앱 키 + ocid, 공개 D-1)

| # | 엔드포인트 | 봇 명령 | 핵심 검증 포인트 |
|---|---|---|---|
| A1 | `maplestory/v1/id` | (공통) | `character_name`→`ocid`. 없는 닉 → 에러 코드/형태 |
| A2 | `maplestory/v1/character/basic` | /스펙 | D-1 날짜 의미. `date` 생략/오늘/어제 응답 차이 |
| A3 | `maplestory/v1/character/stat` | /스펙 | `final_stat` 배열에 `stat_name="전투력"` 존재·값 타입 |
| A4 | `maplestory/v1/character/ability` | /스펙 | `ability_info` 프리셋 구조 |
| A5 | `maplestory/v1/character/symbol-equipment` | /스펙 | `symbol[]` 필드 |
| A6 | `maplestory/v1/character/hexamatrix` | /스펙 | `character_hexa_core_equipment[].linked_skill` 중첩 |
| A7 | `maplestory/v1/character/hexamatrix-stat` | /스펙 | 코어 배열 필드 |
| A8 | `maplestory/v1/character/item-equipment` | /아이템 | 잠재 1~3·에디셔널·`starforce`·옵션 6종. **"0성 vs 스타포스 불가 부위" 구분 신호 유무** |
| A9 | `maplestory/v1/user/union` | /유니온 | `union_level` 등 |
| A10 | `maplestory/v1/user/union-artifact` | /유니온 | 아티팩트 레벨 |
| A11 | `maplestory/v1/user/union-champion` | /유니온 | `union_champion[].champion_grade` (SSS/SS 분포 카운트용) |

### 그룹 B — 이력류 (개인 키, `ocid` 파라미터 없음) ⚠️ **GO/NO-GO 게이트**

| # | 엔드포인트 | 봇 명령 | 핵심 검증 포인트 |
|---|---|---|---|
| B1 | `maplestory/v1/history/starforce` | /스타포스 | 아래 B-공통 + 비용/레벨 필드 부재 재확인 |
| B2 | `maplestory/v1/history/cube` | /잠재·/잠재합계 | B-공통 + `item_level`/`cube_type` 존재, 메소 필드 부재 |
| B3 | `maplestory/v1/history/potential` | /잠재·/잠재합계 | B-공통 + `potential_type` |

### 그룹 C — 알림 (봇 앱 키, 파라미터 없음)

| # | 엔드포인트 | 봇 명령 | 핵심 검증 포인트 |
|---|---|---|---|
| C1 | `maplestory/v1/notice` | /공지알림 | `notice[]` 의 `title·url·notice_id·date`, 정렬(최신순?) |
| C2 | `maplestory/v1/notice-update` | /공지알림 | 동일 구조 |
| C3 | `maplestory/v1/notice-event` | /썬데이 | `date_event_start/end` 존재. `title`에 "썬데이 메이플" 매칭 가능성 |

## 사전 준비물 (검증 세션 시작 시 사용자에게 요청)

1. **봇 앱 API 키** — 넥슨 Open API 포털 애플리케이션 키 (스펙류·알림용).
2. **개인 API 키 1개** — 본인 넥슨 계정 키 (이력류용, 그룹 B 필수).
3. **테스트 캐릭터 닉네임**
   - 본인 캐릭터 (개인 키 소유 계정 = 이력류 스코프 확인용).
   - 가능하면 **다른 사람 캐릭터 1개** (앱 키로 스펙류만 조회되는지 확인용).
4. (선택) **오늘 KST에 스타포스/큐브를 사용한 기록** — B의 "동일자 데이터" 확인에 필요. 없으면 해당 항목만 보류.

## 핵심 검증 항목 — 그룹 B 상세 (이 게이트가 설계 전체를 좌우)

| 항목 | 확인 방법 | 합격 기준 | 실패 시 |
|---|---|---|---|
| **B-키스코프** | 개인 키로 `history/starforce` 호출 → 이벤트의 `character_name`이 그 계정 캐릭터들인지 확인. 같은 호출을 **앱 키**로도 시도 | 개인 키 = 해당 계정 이력 반환 / 앱 키 = 임의 유저 이력 **불가**(에러 또는 봇소유주 이력) | **설계 재그릴** — "개인 키로 이력류 해제" 모델 붕괴 |
| **B-동일자** | `date`=오늘(KST) 호출 → 오늘 친 강화가 보이는지 + 반영 지연 측정 | 오늘 데이터 조회 가능 | `/스타포스 오늘` 프리셋 제거 또는 "최신 가용일"로 재정의 + 5분 TTL 재검토 |
| **B-페이지네이션** | `count=10` → `next_cursor`로 다음 페이지. `date`+`cursor` 동시 전달 시도 | cursor 누적 조회 동작, 끝에서 `next_cursor=null`, date↔cursor 상호배타 | 기간 조회 로직 수정 |
| **B-비용/레벨 부재** | 응답 필드 실측 | starforce: 메소·레벨 필드 없음 / cube·potential: 메소 없음(`item_level`은 있음) | 기대값·가격 테이블 별도 구축 범위 확정(Phase 3) |
| **B-조회범위** | starforce `2023-12-27`·잠재 `2024-01-25` 경계 및 그 이전 날짜 호출 | 경계 내 정상, 이전은 에러/빈값 | 상한 30일 설계 영향 없음(참고만) |
| **B-빈값 vs 인증오류** | 활동 없는 날짜 호출 vs 잘못된 키 호출 | 빈 배열="기록 없음" / 인증 에러="키 무효" 구분 가능 | "키 미등록 vs 기록 없음" 처리 로직 확정 |

## 검증 방법 — 일회용 스파이크 스크립트

본 프로젝트(Python)와 맞추되 **Phase 1 본 구현과 분리**한다. 권장 위치 `spike/verify_nexon_api.py`.

- `.env`에서 키 로드 (`python-dotenv` 또는 `os.environ`), **`.env`·`spike/`는 `.gitignore`에 추가**(없으면 생성).
- 의존성: `httpx`, `python-dotenv` (일회용이므로 `uv run --with httpx --with python-dotenv` 같은 경량 실행 권장).
- 각 엔드포인트 호출 → 원본 JSON 출력 → 문서 필드와 대조.

```python
# spike/verify_nexon_api.py  (일회용 검증 스크립트 — 시크릿 커밋 금지)
import os, json, httpx
from datetime import date, timedelta

BASE = "https://open.api.nexon.com"
APP_KEY = os.environ["NEXON_APP_KEY"]            # 스펙류·알림
PERSONAL_KEY = os.environ["NEXON_PERSONAL_KEY"]  # 이력류(개인)
CHAR = os.environ["TEST_CHARACTER_NAME"]
YDAY = (date.today() - timedelta(days=1)).isoformat()

def call(path, key, **params):
    q = {k: v for k, v in params.items() if v is not None}
    r = httpx.get(f"{BASE}/{path}", headers={"x-nxopen-api-key": key}, params=q, timeout=10)
    print(f"\n=== {path} {q} -> {r.status_code} ===")
    print(json.dumps(r.json(), ensure_ascii=False, indent=2)[:4000])
    return r

# A1: ocid
ocid = call("maplestory/v1/id", APP_KEY, character_name=CHAR).json().get("ocid")
# A2~A11 스펙류
for p in ["character/basic","character/stat","character/ability","character/symbol-equipment",
          "character/hexamatrix","character/hexamatrix-stat","character/item-equipment",
          "user/union","user/union-artifact","user/union-champion"]:
    call(f"maplestory/v1/{p}", APP_KEY, ocid=ocid, date=YDAY)
# B1~B3 이력류 (개인 키, ocid 없음)
for p in ["history/starforce","history/cube","history/potential"]:
    call(f"maplestory/v1/{p}", PERSONAL_KEY, count=10, date=YDAY)
    call(f"maplestory/v1/{p}", PERSONAL_KEY, count=10, date=date.today().isoformat())  # B-동일자
call("maplestory/v1/history/starforce", APP_KEY, count=10, date=YDAY)  # B-키스코프 대조
# C1~C3 알림
for p in ["notice","notice-update","notice-event"]:
    call(f"maplestory/v1/{p}", APP_KEY)
```

## 산출물 (검증 세션이 남길 것)

1. **이 문서의 "검증 결과" 섹션 채우기** (아래 체크리스트).
2. **`docs/api/*.md` 갱신**: 확정된 값으로 "실호출로 확정" 캐비엇 제거, `history.md` 상단 **미검증 표** 갱신, 필드 불일치 발견 시 수정.
3. **GO/NO-GO 판정** 명시. B-키스코프 실패 시 여기서 멈추고 사용자에게 재그릴 요청.
4. 시크릿/원본 덤프는 커밋 금지(개인 이력 = 민감). 샘플 인용 시 캐릭터명 등 마스킹.

## 검증 결과 (실호출로 확정 — 2026-06-04)

- 검증일: **2026-06-04 (KST 01:10경)**  / 봇 앱 키: ☑ / 개인 키: ☑ / 테스트 캐릭터: **손\*** (+ 타인 대조 **라\*\*면**, 마스킹)
- 호출 도구: `spike/verify_nexon_api.py` (httpx, 일회용·gitignore). 원본 JSON은 `spike/raw/*.json`(미커밋).

> ### 🎯 종합 판정: **GO** ✅
> 이력류 키 모델(**개인 키 = 그 계정 이력만, `ocid` 없음**)이 실호출로 성립함. **이력류 설계 재그릴 불필요.**
> 단, 검증 환경의 한계·실측 잔류 2건은 아래 표와 "검증 한계/잔류" 절에 분리 명시.

| # | 엔드포인트 | 200 | 필드 일치 | 비고/수정사항 |
|---|---|---|---|---|
| A1 | id | ☑ | ☑ | 없는 닉 → **400 `OPENAPI00004`** (전용 not-found 코드 없음, 파라미터 오류로 처리) |
| A2 | character/basic | ☑ | △ | **D-1 동작:** no-date→200(응답 `date:null`) · **D-1(어제 06-03)→`OPENAPI00009` "data not ready"** · today→`OPENAPI00004` · **D-2(06-02) 이하→200**+date echo. "1AM 이후 D-1" 경계는 soft(01:10 시점 D-1 미생성, 최신 ready=D-2). **`access_flag` 실측=`"true"/"false"` 문자열(문서 `"1"/"0"`와 불일치)** |
| A3 | character/stat | ☑ | ☑ | **전투력 stat_name:** `"전투력"` 존재(final_stat 44개 중), `stat_value`=**string** |
| A4 | character/ability | ☑ | ☑ | top_keys 문서 일치 |
| A5 | symbol-equipment | ☑ | ☑ | `symbol[]` 일치 |
| A6 | hexamatrix | ☑ | ☑ | `linked_skill=[{hexa_skill_id}]` 중첩 일치 |
| A7 | hexamatrix-stat | ☑ | ☑ | 코어 배열 6종 일치 |
| A8 | item-equipment | ☑ | ☑ | **스타포스불가 부위 신호: 없음** — `starforce="0"`이 0성·스타포스불가(훈장/뱃지/포켓/엠블렘/특수반지) **양쪽에 공통**. 구분 전용 플래그 부재 → **정적 부위표 필요**(설계 하이브리드 정당화). `potential_option_grade=null`=잠재 불가/미설정 부위 |
| A9 | user/union | ☑ | ☑ | `union_level` 등 일치 |
| A10 | union-artifact | ☑ | ☑ | 아티팩트 레벨 일치 |
| A11 | union-champion | ☑ | △ | **등급 분포 필드:** `champion_grade` 관측값 = **`"SSS"`, `"S"`**(챔피언 2개 계정; 분포 카운트 동작 확인). 등급 체계 `SSS/SS/S…`(`"SS"` 등 이 계정 미관측). 문서 예시 `"레전드리"`는 오류 → 정정 |
| **B-키스코프** | history/* | ☑ | — | **GO/NO-GO: GO** ✅ — 개인 키 7일 이력(starforce 5건 + cube 8건@05-31·2건@06-03 = 15건) **전건 `character_name`=키 소유 캐릭(손\*)**, 타 계정 0건, `ocid` 파라미터 없음. ⚠️ 앱 키=개인 키(동일 값)라 **2계정 음성 대조는 미실험**(메커니즘은 확정) |
| **B-동일자** | history/* | ☑ | — | **오늘 데이터:** 이력류는 today(06-04) 호출 **200 수용**(스펙류 today=`00004`와 대비) → `/스타포스 오늘` 가능. 단 오늘 활동 0이라 **반영 지연은 미측정** |
| B-페이지네이션 | history/* | ☑ | △ | `next_cursor` 필드 존재(일별 ≤count라 항상 `null` 관측). **date+cursor 동시→200(에러 아님, date 우선·cursor 무시)** → 문서 "동시 불가"는 **SDK 컨벤션이지 API 제약 아님**. cursor만(가짜)→`OPENAPI00003`. **count 필수**(누락→`OPENAPI00004`). cursor 누적 조회는 **미실측(잔류)** |
| B-비용/레벨 | history/* | ☑ | ☑ | starforce: **메소·레벨 필드 없음(실측 확인, 17키 DTO 일치)** / cube: 메소 없음·**`item_level` 있음**. potential: 7일 0건이라 **실측 불가(잔류, DTO 유지)** |
| B-조회범위 | history/* | ☑ | — | **롤링 ~2년 윈도우**: 730일전(2024-06-04)→200 / 760일전(2024-05-05)→`OPENAPI00004`. 문서의 절대 시작일(sf 2023-12-27 등)은 현재 2년 초과로 400. **봇 30일 상한엔 무관** |
| B-빈값/인증 | history/* | ☑ | — | **기록 없음=200+빈 배열(`count:0`)** / **키 무효=400 `OPENAPI00005`** "The apikey is not valid." → 명확히 구분 가능 |
| C1 | notice | ☑ | ☑ | **정렬: `date` 내림차순(최신순)**. wrapper=`notice`, 20건, `{title,url,notice_id,date}` |
| C2 | notice-update | ☑ | ☑ | wrapper=`update_notice`, 20건, 동일 필드, 최신순 |
| C3 | notice-event | ☑ | ☑ | **`date_event_start/end`: 존재**. wrapper=`event_notice`, 19건. "썬데이 메이플" 제목 **0건(현재 미진행)** → 제목 매칭 라이브 양성확인 **미실시(잔류)** |

### 검증 한계 / 잔류 항목 (GO 판정과 별개로 후속 확인)

1. **앱 키 = 개인 키 동일 값** — B-키스코프의 "앱 키로 타인 이력 조회 불가" 음성 대조는 미실험. (단일 키가 그 계정 이력만 반환하는 양성 증거는 확보.) 실제 운영 시 봇 앱 키 ≠ 유저 개인 키이므로 설계상 문제 없음.
2. **이력류 `test_` 키 — rate limit `x-ratelimit-limit: 5`** (짧은 창, 약 5/sec). 검증 스크립트는 throttle 0.8s + 429 재시도로 우회. **운영(live) 키 한도는 별도 확인 필요**(Phase 1 클라이언트 재시도/스로틀 설계 입력).
3. **potential 이력 실측 0건** — 조회 가능 7일 내 메소 잠재 재설정 기록 없음. 필드는 cube와 거의 동일 + DTO 교차검증 유지. 기록 있는 키로 후속 확인 권장.
4. **cursor 누적 페이지네이션 미실측** — 일별 기록 <count(10)라 `next_cursor` 비-null 미발생. 고볼륨 일자/키로 후속 확인.
5. **"썬데이 메이플" 제목 매칭** — 검증 시점 미진행(0건). 라이브 썬데이 또는 Phase 4 수동 HTTP 엔드포인트로 마감(work-plan §82 미니 스파이크와 합치).

## 참조

- 스펙 문서: [docs/api/](./api/) (README + 카테고리 7개)
- 봇 명령→엔드포인트 매핑: [docs/api/README.md](./api/README.md)
- 작업 계획: [docs/work-plan.md](./work-plan.md) (Spike 0 게이트)
- 용어 사전: [CONTEXT.md](../CONTEXT.md) (스펙류/이력류, 키미등록 vs 기록없음)
