# 스케줄러 API (공식 문서 id=57)

> 공통 규약(Base URL `https://open.api.nexon.com`, 인증 헤더 `x-nxopen-api-key`, 에러코드)은 [README.md](./README.md) 참고.
> **출처/검증:** 넥슨 공식 OpenAPI 3.0.3 스펙 YAML(`?id=57` 문서 탭이 로드하는 원본,
> `https://openapi.nexon.com/static/api/maplestory/62_ko_script20260624052642.yaml`, 생성 2026-06-24)을
> 직접 받아 필드를 1:1 확인. 가용성 규칙은 공지 [3482567](https://openapi.nexon.com/ko/support/notice/3482567/)
> ("메이플스토리 Open API 업데이트 안내", 2026-06-25 적용)에서 확인.
> **신규(2026-06-25 적용)** — **2026-06-26 DB 저장 개인 키 8캐릭터로 실호출 검증 완료**(아래 "실호출 검증" 참고).

> ### ✅ 실호출 검증 (2026-06-26, DB 개인 키 5계정/8등록캐릭터)
> - **봇 실사용 경로 동작 확인:** 개인 키 + 등록 대표 ocid + `date` 미지정 → **전원 200 OK**. 챌린저스 캐릭터 포함(무기콤보 daily=18/weekly=22/boss=77, 중망레테 `weekly_boss_clear_count`=4/12).
> - **⚠️ `date` 명시 = 오늘 → 400 `OPENAPI00004` (거부).** 오늘 실시간 데이터는 **`date` 무지정으로만** 받는다(스펙류와 동일한 "오늘 거부" 회귀). 과거일(`date=어제` 등, −14일 내)은 명시 호출 200.
> - **응답 `date`는 `YYYY-MM-DD`가 아니라 datetime 문자열**(`"2026-06-26T00:00+09:00"`, KST·시·분 00). YAML 설명의 `YYYY-MM-DD`는 부정확.
> - **이 계정 캐릭터인데도 미접속/비대상 캐릭터는 빈 200이 아니라 에러**로 관측: `date` 무지정 시 `OPENAPI00003`(invalid id), `date` 명시 시 `OPENAPI00004`. (저활동·신규 캐릭터 2건에서 재현, 표본 작음)
> - 검증 스크립트는 컨테이너 내 일회성 실행(`docker exec -i maple-mate-app uv run python -`), 키는 `KeyCipher`로 복호화. 레포 미커밋.

## ⚠️ 핵심: 스펙류 아님 — **계정 스코프(이력류 친척)**

다른 `character/*` 엔드포인트와 달리, 스케줄러는 **API 키 소유 계정의 캐릭터만** 조회된다
(스펙 원문: "자신의 계정에 속한 캐릭터만 조회가 가능합니다"). 따라서:

- **봇 앱 키 + 임의 ocid** ⟶ ❌ 동작 안 함(봇 계정 캐릭터가 아니므로 `403 Forbidden` 예상).
- 임의 유저의 스케줄러를 보려면 **그 유저의 개인 넥슨 키**가 필요하다 — 즉
  **이력류 모델**(개인 키, [ADR-0001](../adr/0001-nexon-personal-key-model.md))을 그대로 따른다.
  단 `history/*`와 달리 **`ocid`로 계정 내 어느 캐릭터인지 지정**한다(개인 키 = 계정, ocid = 그 안의 캐릭터).
- 날짜 규칙도 스펙류와 반대다: **무지정 = 오늘(실시간)**, D-1 아님. 과거일도 조회 가능(최대 14일).
  단 실호출상 **`date`에 오늘을 명시하면 400** — 오늘은 무지정으로만 받는다(아래 실호출 검증).

| 분류축 | 스펙류 | 이력류(`history/*`) | **스케줄러** |
|---|---|---|---|
| 키 | 봇 앱 키 | 개인 키 | **개인 키** |
| 캐릭터 지정 | `ocid`(임의 공개) | 없음(키=계정 전체) | **`ocid`(자기 계정 한정)** |
| 기본 날짜 | 전일 D-1 | 당일 수용 | **오늘(무지정만)·명시 today 거부** |
| 조회 범위 | 롤링 ~2년 | 롤링 ~2년 | **최대 14일** |

## 엔드포인트 요약

| 메서드 | 경로 | 한글명 | 주요 응답 |
|--------|------|--------|-----------|
| GET | `maplestory/v1/scheduler/character-state` | 캐릭터 스케줄러 정보 | 일일·주간 콘텐츠/퀘스트·보스 수행 현황 |

> 그룹 내 서브엔드포인트는 이 **1개뿐**(스펙 YAML `paths` 블록 전수 확인).

---

## GET `maplestory/v1/scheduler/character-state` — 캐릭터 스케줄러 정보

인게임 "메이플 스케줄러"에 등록된 콘텐츠·퀘스트·보스의 수행 현황을 조회한다.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|------|------|------|------|
| `ocid` | 필수 | string | 캐릭터 식별자. **자신의(=키 소유) 계정에 속한 캐릭터만** 조회 가능 |
| `date` | 선택 | string | 조회 기준일 (KST, `YYYY-MM-DD`). **미입력 시 오늘(실시간)**. ⚠️ **실호출: 오늘을 명시하면 400 `OPENAPI00004`** — 오늘은 무지정으로만. 과거일은 명시 200(−14일 내). 해당 기준일 미접속이면 응답 없을 수 있음 |

**응답 필드** (`CharacterStateResponse`)

| 필드 | 타입 | 설명 |
|------|------|------|
| `date` | string | 조회 기준일. ⚠️ 실측은 **datetime 문자열** `"2026-06-26T00:00+09:00"`(KST). YAML의 `YYYY-MM-DD` 표기는 부정확 |
| `character_name` | string | 캐릭터 명 |
| `world_name` | string | 월드 명 |
| `character_level` | int | 캐릭터 레벨 |
| `character_class` | string | 캐릭터 직업 |
| `daily_contents` | list[DailyContent] | 일일 콘텐츠 정보 |
| `└ content_name` | string | 콘텐츠/퀘스트 명 |
| `└ type` | string | 타입 — `"contents"` 또는 `"quest"` |
| `└ registration_flag` | string | 인게임 스케줄러 등록 여부 — `"true"`/`"false"` (⚠️ 불리언 아닌 **문자열**) |
| `└ now_count` | int | 현재 완료 횟수/점수 |
| `└ max_count` | int | 최대 완료 가능 횟수/점수 |
| `└ quest_state` | string | 퀘스트일 때 진행 상태 — `"0"`:기타, `"1"`:진행 중, `"2"`:완료 |
| `weekly_contents` | list[WeeklyContent] | 주간 콘텐츠 정보 (필드 구조는 `daily_contents`와 동일) |
| `boss_contents` | list[BossContent] | 보스 콘텐츠 정보 |
| `└ content_name` | string | 보스 명 |
| `└ difficulty` | string | 보스 난이도 (자유 문자열, enum 미정의) |
| `└ cycle` | string | 보스 초기화 주기 (자유 문자열) |
| `└ list_order_no` | int | 리스트 순서 |
| `└ registration_flag` | string | 인게임 스케줄러 등록 여부 — `"true"`/`"false"` |
| `└ complete_flag` | string | 완료 여부 — `"true"`/`"false"` |
| `weekly_boss_clear_count` | int | 주간 보스 처치 완료 횟수 |
| `weekly_boss_clear_limit_count` | int | 주간 보스 처치 제한 횟수 |

> **타입 주의:** `registration_flag`·`complete_flag`·`quest_state`는 모두 **문자열**(`"true"`/`"0"` 등)로 온다.
> 봇에서 쓸 땐 `flag == "true"`처럼 문자열 비교하거나 파싱 헬퍼로 bool/enum 변환할 것.
> `now_count`/`max_count`/`*_level`/`*_count`는 정수(`int64`).
> 보스에는 카운트 필드가 없고(완료는 `complete_flag`), 일/주간 콘텐츠에는 `difficulty`/`cycle`/`complete_flag`가 없다.

**예시 응답** (스키마 기반 구성 예시 — 필드/값 형태는 실호출과 일치, 콘텐츠 명은 가공)

```json
{
  "date": "2026-06-26T00:00+09:00",
  "character_name": "내캐릭터",
  "world_name": "스카니아",
  "character_level": 285,
  "character_class": "아크메이지(불,독)",
  "daily_contents": [
    {
      "content_name": "일일 보스 무릉도장",
      "type": "contents",
      "registration_flag": "true",
      "now_count": 1,
      "max_count": 1,
      "quest_state": "0"
    },
    {
      "content_name": "유로파 일일 퀘스트",
      "type": "quest",
      "registration_flag": "true",
      "now_count": 0,
      "max_count": 1,
      "quest_state": "1"
    }
  ],
  "weekly_contents": [
    {
      "content_name": "길드 콘텐츠",
      "type": "contents",
      "registration_flag": "true",
      "now_count": 3,
      "max_count": 7,
      "quest_state": "0"
    }
  ],
  "boss_contents": [
    {
      "content_name": "검은 마법사",
      "difficulty": "하드",
      "cycle": "주간",
      "list_order_no": 1,
      "registration_flag": "true",
      "complete_flag": "false"
    }
  ],
  "weekly_boss_clear_count": 8,
  "weekly_boss_clear_limit_count": 14
}
```

**에러 응답:** 표준 `{ "error": { name, message } }`. 정의된 상태코드 — `400`·`403`·`429`·`500`.
- `403 Forbidden`: ocid가 키 소유 계정의 캐릭터가 아닐 때 발생 **예상**(스펙의 "자신의 계정만" 제약). 단 실호출에서는 계정 외/오늘명시/비대상 케이스가 주로 **`400`**(`OPENAPI00004`/`OPENAPI00003`)으로 떨어졌고 403은 미관측 — 봇은 4xx 전반을 "조회 불가"로 처리하는 게 안전.
- `400 OPENAPI00004`: `date`에 **오늘 명시**, 또는 잘못된 파라미터(실측 다발).
- `400 OPENAPI00003`: 비대상/저활동 캐릭터를 `date` 무지정으로 조회 시 관측(invalid id).

### 데이터 가용성·갱신 규칙 (공지 3482567 원문)

- **범위:** 실시간 조회 + 이전 일자 조회. **조회 요청일 기준 최대 14일 전까지**.
- **과거일 의미:** 이전 일자 조회 시 **그 날의 가장 마지막 스케줄러 상태**가 반환된다(스냅샷 아님, 그날 최종값).
- **실시간 갱신 시점:**
  - 길드 콘텐츠·에픽던전·무릉도장·보스 콘텐츠 ⟶ **각 콘텐츠 완료 시** 갱신.
  - 그 외 콘텐츠·퀘스트 ⟶ **캐릭터 접속 중 및 접속 종료 시** 갱신.
- **적용일:** 2026-06-25(목) 10:00. **그 이후의 스케줄러 정보부터** 조회 가능.
- **⚠️ 조회 자격:** **2026-06-25 이후 최초 1회 이상 접속한 캐릭터만** 조회 가능. 비대상 캐릭터는 (공지는 "빈 응답"이라 하나) 실측상 **`OPENAPI00003`/`OPENAPI00004` 에러**로 떨어졌다.

### 봇 통합 메모

현재 봇에 스케줄러 명령은 없다. 도입한다면:

1. **키 모델:** 이력류(`history/*`)와 같은 **개인 키 경로**로 붙인다 — 봇 앱 키로는 못 쓴다(403).
   `NexonClient._request(..., api_key=개인키)` 오버라이드 패턴 재사용([client.py](../../maple_mate/nexon/client.py) 이력류 메서드 참조).
   단 `history/*`와 달리 **`ocid` 파라미터를 함께 보낸다**(계정 내 캐릭터 지정).
2. **캐릭터 선택:** 한 개인 키(계정)에 N개 캐릭터가 묶이므로, 대표 캐릭터 ocid 또는 사용자가 고른 ocid로 호출
   (멀티 캐릭터 등록 모델 [ADR-0006](../adr/0006-multi-character-data-model.md)와 정합).
3. **날짜:** **오늘은 반드시 `date` 무지정**으로 호출(오늘 명시 시 400, 실호출 확정). 과거는 `date` 명시(−14일 내). 스펙류의 D-1 계산 로직과 **무관**.
4. **realm:** 응답에 `world_name`이 있어 본서버/챌린저스 구분 가능([ADR-0009](../adr/0009-challengers-realm-model.md)). 실호출에서 챌린저스 캐릭터(무기콤보·중망레테)도 정상 200.
5. **렌더:** 일일/주간은 `now_count/max_count` 진행도 게이지, 보스는 `complete_flag` 체크리스트로 표현 적합.
6. **에러 처리:** 비대상/저활동 캐릭터는 빈 응답이 아니라 4xx로 떨어지므로(`OPENAPI00003`/`00004`), 이력류처럼 "조회 불가/기록 없음"으로 흡수.

**제안 클라이언트 메서드(미구현, 참고용 — 실호출 규약 반영):**

```python
async def scheduler_character_state(
    self, api_key: str, ocid: str, date_iso: str | None = None
) -> dict:
    """개인 키 + ocid 로 그 캐릭터의 스케줄러 수행 현황.

    ⚠️ 오늘 데이터는 date_iso=None(무지정)으로만 — 오늘을 명시하면 OPENAPI00004.
    과거(−14일)는 date_iso 명시. 계정 외/비대상 ocid 는 4xx(403 예상이나 실측 400 다발).
    """
    return await self._request(
        "maplestory/v1/scheduler/character-state",
        api_key=api_key,
        ocid=ocid,
        date=date_iso,
    )
```
