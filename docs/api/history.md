# 확률 정보 조회 API — 스타포스·큐브·잠재 (공식 문서 id=17)

> ⚠️ **이력류(개인 키 스코프)** — [CONTEXT.md](../../CONTEXT.md) 참고. 키 스코프·동일자 데이터·조회범위는 [작업계획](../work-plan.md) **Spike 0**에서 확정.
> 공통 규약(Base URL, 인증 헤더, 에러코드)은 [README.md](./README.md) 참고.
> 응답 필드는 SpiralMoon/maplestory.openapi KMS DTO로 교차검증. 최종은 실호출로 확정.

---

## Spike 0 실호출 검증 결과 (2026-06-04 확정) — 키 모델 **GO** ✅

| 항목 | 실호출 결과 (2026-06-04) |
|------|--------------------------|
| **키 스코프** ✅ | **확정 GO.** 개인 키 7일 이력(starforce 5 + cube 10 = 15건) **전건 `character_name`=키 소유 캐릭터**, 타 계정 0건, `ocid` 파라미터 없음. → "개인 키 = 그 계정 이력" 모델 성립, **이력류 설계 재그릴 불필요.** ⚠️ 단 검증 시 앱 키=개인 키(동일 값)라 "앱 키로 타인 이력 조회 불가" **음성 대조는 미실험**(메커니즘은 확정). |
| **동일자(오늘) 데이터** ✅ | **수용 확인.** `history/*`는 당일(오늘) 날짜 호출을 **200으로 수용**(스펙류 당일=`OPENAPI00004`와 대비). `/스타포스 오늘` 가능. 단 검증 시 당일 활동 0이라 **반영 지연은 미측정** → 5분 TTL 적정성 후속 확인. |
| **조회 범위** ✅ | **롤링 ~2년 윈도우 확정.** 730일전(2024-06-04) 200 / 760일전(2024-05-05) `OPENAPI00004`. 아래 카테고리별 "절대 시작일"은 현재 2년 초과 시 400이 됨. 봇 30일 상한엔 무관. |
| **starforce 비용/레벨 필드** ✅ | **실측 확정: 메소·레벨 필드 모두 없음**(실제 응답 17키가 DTO와 정확 일치). `target_item` 명칭만 존재 → 기대값 별도 표 계산·이벤트 할인 역산 필요(설계와 일치). |
| **cube 비용 필드** ✅ | **실측 확정: 메소 소모량 필드 없음, `item_level` 있음, `cube_type` 있음**. `cube_type`+레벨 기준 가격 테이블 별도 관리 필요. |
| **potential 필드** ⚠️ | 검증 7일 내 **기록 0건이라 실측 불가(잔류).** cube와 거의 동일 스키마 + `potential_type` 추가 — DTO 교차검증 유지. 기록 있는 키로 후속 확인 권장. |
| **빈값 vs 인증오류** ✅ | **기록 없음=200+빈 배열(`count:0`)** / **키 무효=400 `OPENAPI00005`** "The apikey is not valid." → 명확히 구분 가능. |

전체 결과·잔류 항목: [api-verification-plan.md](../api-verification-plan.md).

---

## 페이지네이션·파라미터 규칙

### `count` — 결과 건수

| 속성 | 값 |
|------|----|
| 타입 | `int` |
| 최솟값 | **10** |
| 최댓값 | **1000** |
| 필수 여부 | 필수 |

### `date` — 조회 기준일

| 속성 | 값 |
|------|----|
| 타입 | `string` (YYYY-MM-DD, KST) |
| 필수 여부 | ⚠️ **실측 정정(2026-06-04): `date`·`cursor` 를 둘 다 빼고 `count` 만 보내면 `OPENAPI00004`(400) 반환** — SDK 문서의 "당일 기본값"과 불일치. 따라서 **첫 페이지 조회 시 `date` 를 명시**해야 한다(봇은 오늘 KST 를 보냄). **당일(오늘) 날짜는 200 수용(실측)** |
| 조회 가능 시작일 | 큐브/잠재/스타포스 공통으로 **롤링 ~2년 윈도우(실측)**. 절대 최초 지원일(큐브 2년·잠재 2024-01-25·스타포스 2023-12-27)은 현재 2년 초과 시 `OPENAPI00004`. 실측: 730일전 200 / 760일전 400 |
| `cursor`와 동시 사용 | SDK는 **둘 중 하나만** 보내도록 강제. ⚠️ **실측: raw API는 둘 다 보내도 에러 없이 200**이며 **`date`가 우선(cursor 무시)**. "동시 불가"는 API 제약이 아니라 SDK 컨벤션 |

- `cursor` 미전달 시: SDK가 `date`를 `YYYY-MM-DD` 문자열로 변환하여 쿼리 파라미터로 전달
- 최소 날짜(`min_date`) 미만 날짜를 전달하면 SDK 레벨에서 `ValueError` 발생

### `cursor` — 페이지네이션 토큰

| 속성 | 값 |
|------|----|
| 타입 | `string` |
| 필수 여부 | 선택 (첫 요청 시 미전달) |
| 획득 방법 | 이전 응답의 `next_cursor` 값 |
| 동작 | `cursor` 전달 시 `date` 대신 사용. **실측: `date`와 동시 전달 시 `date` 우선·cursor 무시(에러 아님).** 잘못된 cursor 단독 전달 → `OPENAPI00003` "Please input valid id" |

**페이지네이션 흐름:**
1. 첫 요청: `count=N`, `date=YYYY-MM-DD` → 응답에 `next_cursor` 포함
2. 다음 페이지: `count=N`, `cursor=<next_cursor>` → 다시 `next_cursor` 반환
3. `next_cursor`가 `null`이면 마지막 페이지

> ⚠️ **실측 잔류:** `count`는 **필수**(누락 시 `OPENAPI00004`). `next_cursor` 필드 존재는 확인했으나, 검증 시 일별 기록 <10이라 **`next_cursor`가 항상 `null`** → **cursor 누적 조회는 미실측(잔류).** 고볼륨 일자/키로 후속 확인 필요.

---

## 엔드포인트 요약

| 경로 | 한글명 | 조회 시작일 | 봇 커맨드 |
|------|--------|------------|-----------|
| `GET maplestory/v1/history/cube` | 큐브 사용 결과 | 최근 2년 | `/잠재`, `/잠재합계` |
| `GET maplestory/v1/history/potential` | 잠재능력 재설정(메소) 결과 | 2024-01-25 | `/잠재`, `/잠재합계` |
| `GET maplestory/v1/history/starforce` | 스타포스 강화 결과 | 2023-12-27 | `/스타포스` |

---

## GET `maplestory/v1/history/cube` — 큐브 사용 결과

API 키 소유 계정의 **큐브 사용 이력**을 조회한다. 큐브 종류, 대상 장비, 강화 전후 잠재 옵션, 천장 스택 등을 포함한다. `ocid` 파라미터 없음 (계정 스코프 — Spike 0 미검증).

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|------|------|------|------|
| `count` | 필수 | `int` | 결과 건수. 최소 10, 최대 1000 |
| `date` | 선택 | `string` | 조회 기준일 (YYYY-MM-DD, KST). `cursor` 미전달 시 기본값 = 당일 |
| `cursor` | 선택 | `string` | 페이지네이션 토큰. `date`와 동시 전달 불가 |

**응답 필드 — 래퍼 (`CubeHistory`)**

| 필드 | 타입 | 설명 |
|------|------|------|
| `count` | `int` | 반환된 결과 건수 |
| `next_cursor` | `string \| null` | 다음 페이지 커서. `null`이면 마지막 페이지 |
| `cube_history` | `array[CubeHistoryInfo]` | 큐브 사용 결과 목록. API 응답이 null이면 빈 배열로 정규화 |

**응답 필드 — 항목 (`CubeHistoryInfo`)**

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | `string` | 큐브 히스토리 식별자 |
| `character_name` | `string` | 캐릭터명 |
| `date_create` | `datetime` (KST) | 큐브 사용 일시 |
| `cube_type` | `string` | 사용한 큐브 종류 (예: "수상한 큐브", "장인의 큐브") |
| `item_upgrade_result` | `string` | 강화 결과 (예: "성공", "실패") |
| `miracle_time_flag` | `string` | 미라클 타임 적용 여부 |
| `item_equipment_part` | `string` | 장비 분류 (예: "모자", "무기") |
| `item_level` | `int` | 장비 레벨 ✅ **있음** |
| `target_item` | `string` | 큐브를 사용한 장비 명 |
| `potential_option_grade` | `string` | 잠재능력 등급 (예: "레어", "에픽", "유니크", "레전드리") |
| `additional_potential_option_grade` | `string` | 에디셔널 잠재능력 등급 |
| `upgrade_guarantee` | `bool` | 천장 도달로 확정 등급 상승 여부 |
| `upgrade_guarantee_count` | `int` | 현재까지 쌓인 천장 스택 수 |
| `before_potential_option` | `array[CubePotentialOption]` | 사용 전 잠재능력 옵션 목록 |
| `before_additional_potential_option` | `array[CubePotentialOption]` | 사용 전 에디셔널 잠재능력 옵션 목록 |
| `after_potential_option` | `array[CubePotentialOption]` | 사용 후 잠재능력 옵션 목록 |
| `after_additional_potential_option` | `array[CubePotentialOption]` | 사용 후 에디셔널 잠재능력 옵션 목록 |

**응답 필드 — 중첩 (`CubePotentialOption`)**

| 필드 | 타입 | 설명 |
|------|------|------|
| `value` | `string` | 옵션 명 (예: "STR : +12%") |
| `grade` | `string` | 옵션 등급 (예: "레어", "에픽") |

**비용 필드 유무:** `CubeHistoryInfo`에 **메소 소모량 필드 없음**. 봇에서 큐브 비용을 계산하려면 `cube_type`을 기준으로 공식 가격 테이블을 별도 관리하고 룩업해야 한다.

**예시 응답**

```json
{
  "count": 2,
  "next_cursor": "eyJhbGciOiJIUzI1NiJ9...",
  "cube_history": [
    {
      "id": "cube-history-id-001",
      "character_name": "메이플전사",
      "date_create": "2024-03-15T14:23:11+09:00",
      "cube_type": "수상한 큐브",
      "item_upgrade_result": "실패",
      "miracle_time_flag": "0",
      "item_equipment_part": "무기",
      "item_level": 160,
      "target_item": "아케인셰이드 소울슈터",
      "potential_option_grade": "에픽",
      "additional_potential_option_grade": "레어",
      "upgrade_guarantee": false,
      "upgrade_guarantee_count": 0,
      "before_potential_option": [
        { "value": "STR : +9%", "grade": "에픽" },
        { "value": "공격력 : +3%", "grade": "레어" },
        { "value": "STR : +6", "grade": "레어" }
      ],
      "before_additional_potential_option": [],
      "after_potential_option": [
        { "value": "STR : +9%", "grade": "에픽" },
        { "value": "공격력 : +3%", "grade": "레어" },
        { "value": "STR : +4", "grade": "레어" }
      ],
      "after_additional_potential_option": []
    }
  ]
}
```

**봇 활용 (`/잠재`, `/잠재합계`)**

| 필드 | 봇 활용 |
|------|---------|
| `cube_type` | 큐브 종류별 사용 횟수 집계, 가격 테이블 룩업 키 |
| `item_level` | 큐브 종류별 실제 비용은 장비 레벨에 따라 다를 수 있어 레벨 참고 가능 |
| `target_item` | `/잠재합계` — 최다 재설정 단일 아이템 집계 |
| `item_upgrade_result` | 등급 상승 성공률 계산 |
| `potential_option_grade` / `additional_potential_option_grade` | 등급 분포 집계 |
| `after_potential_option` | 현재 보유 옵션 확인 |
| `upgrade_guarantee_count` | 천장 스택 현황 |
| **메소 소모량** | ❌ 필드 없음 → `cube_type` 기준 별도 가격 테이블 필요 |

---

## GET `maplestory/v1/history/potential` — 잠재능력 재설정(메소) 결과

API 키 소유 계정의 **메소를 사용한 잠재능력 재설정 이력**을 조회한다. 큐브 엔드포인트와 유사하나 `potential_type` 필드가 추가되어 일반 잠재능력/에디셔널 잠재능력 구분이 가능하다. `ocid` 파라미터 없음 (계정 스코프 — Spike 0 미검증).

> ℹ️ 조회 가능 시작일: **2024-01-25**. 이 날짜 미만을 `date`로 전달하면 SDK에서 `ValueError` 발생.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|------|------|------|------|
| `count` | 필수 | `int` | 결과 건수. 최소 10, 최대 1000 |
| `date` | 선택 | `string` | 조회 기준일 (YYYY-MM-DD, KST). `cursor` 미전달 시 기본값 = 당일 |
| `cursor` | 선택 | `string` | 페이지네이션 토큰. `date`와 동시 전달 불가 |

**응답 필드 — 래퍼 (`PotentialHistory`)**

| 필드 | 타입 | 설명 |
|------|------|------|
| `count` | `int` | 반환된 결과 건수 |
| `next_cursor` | `string \| null` | 다음 페이지 커서. `null`이면 마지막 페이지 |
| `potential_history` | `array[PotentialHistoryInfo]` | 잠재능력 재설정 결과 목록. null이면 빈 배열로 정규화 |

**응답 필드 — 항목 (`PotentialHistoryInfo`)**

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | `string` | 잠재능력 재설정 히스토리 식별자 |
| `character_name` | `string` | 캐릭터명 |
| `date_create` | `datetime` (KST) | 재설정 일시 |
| `potential_type` | `string` | 대상 잠재능력 타입 (예: "잠재능력", "에디셔널 잠재능력") |
| `item_upgrade_result` | `string` | 사용 결과 (예: "성공", "실패") |
| `miracle_time_flag` | `string` | 미라클 타임 적용 여부 |
| `item_equipment_part` | `string` | 장비 분류 |
| `item_level` | `int` | 장비 레벨 ✅ **있음** |
| `target_item` | `string` | 잠재능력 재설정 대상 장비 명 |
| `potential_option_grade` | `string` | 잠재능력 등급 |
| `additional_potential_option_grade` | `string` | 에디셔널 잠재능력 등급 |
| `upgrade_guarantee` | `bool` | 천장 도달로 확정 등급 상승 여부 |
| `upgrade_guarantee_count` | `int` | 현재까지 쌓인 천장 스택 수 |
| `before_potential_option` | `array[PotentialOption]` | 사용 전 잠재능력 옵션 목록 |
| `before_additional_potential_option` | `array[PotentialOption]` | 사용 전 에디셔널 잠재능력 옵션 목록 |
| `after_potential_option` | `array[PotentialOption]` | 사용 후 잠재능력 옵션 목록 |
| `after_additional_potential_option` | `array[PotentialOption]` | 사용 후 에디셔널 잠재능력 옵션 목록 |

**응답 필드 — 중첩 (`PotentialOption`)**

| 필드 | 타입 | 설명 |
|------|------|------|
| `value` | `string` | 옵션 명 (예: "보스 몬스터 공격 시 데미지 : +30%") |
| `grade` | `string` | 옵션 등급 |

**비용 필드 유무:** `PotentialHistoryInfo`에 **메소 소모량 필드 없음**. 메소 비용은 잠재능력 재설정 시스템의 메소 차감 단가(장비 레벨·종류 기준)를 별도 테이블로 관리하고 `item_level`, `item_equipment_part`를 키로 룩업해야 한다.

**예시 응답**

```json
{
  "count": 1,
  "next_cursor": null,
  "potential_history": [
    {
      "id": "potential-history-id-001",
      "character_name": "메이플전사",
      "date_create": "2024-04-01T10:05:32+09:00",
      "potential_type": "잠재능력",
      "item_upgrade_result": "성공",
      "miracle_time_flag": "0",
      "item_equipment_part": "모자",
      "item_level": 200,
      "target_item": "아케인셰이드 모자",
      "potential_option_grade": "레전드리",
      "additional_potential_option_grade": "유니크",
      "upgrade_guarantee": true,
      "upgrade_guarantee_count": 0,
      "before_potential_option": [
        { "value": "올스탯 : +9%", "grade": "유니크" },
        { "value": "최대 HP : +9%", "grade": "유니크" },
        { "value": "공격력 : +3%", "grade": "레어" }
      ],
      "before_additional_potential_option": [],
      "after_potential_option": [
        { "value": "보스 몬스터 공격 시 데미지 : +40%", "grade": "레전드리" },
        { "value": "올스탯 : +9%", "grade": "유니크" },
        { "value": "공격력 : +3%", "grade": "레어" }
      ],
      "after_additional_potential_option": []
    }
  ]
}
```

**봇 활용 (`/잠재`, `/잠재합계`)**

| 필드 | 봇 활용 |
|------|---------|
| `potential_type` | 잠재능력 vs 에디셔널 잠재능력 구분 집계 |
| `target_item` | `/잠재합계` — 최다 재설정 단일 아이템 집계 |
| `item_level` + `item_equipment_part` | 메소 비용 테이블 룩업 키 (비용 필드 없으므로 역산 필요) |
| `potential_option_grade` | 등급 상승 성공 집계 |
| `after_potential_option` | 최종 옵션 분포 확인 |
| `upgrade_guarantee` | 천장 소진 여부 통계 |
| **메소 소모량** | ❌ 필드 없음 → `item_level` + `item_equipment_part` 기준 별도 테이블 필요 |

---

## GET `maplestory/v1/history/starforce` — 스타포스 강화 결과

API 키 소유 계정의 **스타포스 강화 이력**을 조회한다. 강화 시도 결과(성공/실패/파괴), 강화 전후 스타포스 수치, 이벤트 정보 등을 포함한다. `ocid` 파라미터 없음 (계정 스코프 — Spike 0 미검증).

> ℹ️ 조회 가능 시작일: **2023-12-27**. 이 날짜 미만을 `date`로 전달하면 SDK에서 `ValueError` 발생.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|------|------|------|------|
| `count` | 필수 | `int` | 결과 건수. 최소 10, 최대 1000 |
| `date` | 선택 | `string` | 조회 기준일 (YYYY-MM-DD, KST). `cursor` 미전달 시 기본값 = 당일 |
| `cursor` | 선택 | `string` | 페이지네이션 토큰. `date`와 동시 전달 불가 |

**응답 필드 — 래퍼 (`StarforceHistory`)**

| 필드 | 타입 | 설명 |
|------|------|------|
| `count` | `int` | 반환된 결과 건수 |
| `next_cursor` | `string \| null` | 다음 페이지 커서. `null`이면 마지막 페이지 |
| `starforce_history` | `array[StarforceHistoryInfo]` | 스타포스 강화 결과 목록. null이면 빈 배열로 정규화 |

**응답 필드 — 항목 (`StarforceHistoryInfo`)**

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | `string` | 스타포스 히스토리 식별자 |
| `item_upgrade_result` | `string` | 강화 시도 결과. ⚠️ **실측: 접미사 포함 — `"성공"`, `"실패(유지)"`, `"실패(하락)"`, `"파괴"` 형태.** 봇의 성공/실패/파괴 집계는 `"실패(*)"` 접두 매칭으로 파싱해야 함 |
| `before_starforce_count` | `int` | 강화 시도 전 스타포스 수치 |
| `after_starforce_count` | `int` | 강화 시도 후 스타포스 수치 (파괴 시 0 또는 이전값) |
| `starcatch_result` | `string \| null` | 스타 캐치 결과. 미적용 시 null (실측 null 확인) |
| `superior_item_flag` | `string` | 슈페리얼 장비 여부. ⚠️ **실측: 서술형 한글 문자열** (예: `"슈페리얼 장비 미해당"`) — `"0"/"1"` 아님 |
| `destroy_defence` | `string` | 파괴 방지 사용 여부. ⚠️ **실측: `"파괴 방지 미적용"` 등 서술형 한글 문자열** |
| `chance_time` | `string` | 찬스 타임 적용 여부. ⚠️ **실측: `"찬스타임 미적용"` 등 서술형 한글 문자열** |
| `event_field_flag` | `string` | 파괴 방지 필드 이벤트 여부 |
| `upgrade_item` | `string` | 사용 주문서 명 |
| `protect_shield` | `string` | 프로텍트 실드 사용 여부 |
| `bonus_stat_upgrade` | `string` | 보너스 스탯 부여 아이템 사용 여부 |
| `character_name` | `string` | 캐릭터 명 |
| `world_name` | `string` | 월드 명 |
| `target_item` | `string` | 대상 장비 아이템 명 |
| `date_create` | `datetime` (KST) | 강화 일시 |
| `starforce_event_list` | `array[StarforceHistoryEvent]` | 진행 중인 스타포스 강화 이벤트 목록. null이면 빈 배열로 정규화 |

**응답 필드 — 중첩 (`StarforceHistoryEvent`)**

| 필드 | 타입 | 설명 |
|------|------|------|
| `success_rate` | `string \| null` | 이벤트 성공 확률 |
| `destroy_decrease_rate` | `string \| null` | 이벤트 파괴 확률 감소율. ⚠️ **실측: `"30"`(% 기호 없음)** |
| `cost_discount_rate` | `string \| null` | 이벤트 비용 할인율. ⚠️ **실측: `"30"`(% 기호 없음)** |
| `plus_value` | `string \| null` | 이벤트 강화 수치 가중값 |
| `starforce_event_range` | `string \| null` | 이벤트 적용 스타포스 범위. ⚠️ **실측: `"0~29"` 범위형 또는 `"15,16,17,18,19,20,21"` 콤마 목록형 둘 다 가능** |
| `recovery_cost_discount_rate` | `string \| null` | ⚠️ **실측으로 발견(문서 누락 필드): 복구 비용 할인율** (예: `"20"`) |

> ⚠️ **실측 정정:** 한 강화 시도의 `starforce_event_list`에 여러 이벤트 객체가 동시에 올 수 있으며(성공률/파괴감소/비용할인이 각각 별 객체로 분리), 비율 값은 **`%` 기호 없는 숫자 문자열**이다. `recovery_cost_discount_rate`는 기존 문서에 없던 필드.

**비용·레벨 필드 유무 (봇 설계 핵심 확인사항):**

| 항목 | 결과 |
|------|------|
| **강화 비용(메소) 필드** | ❌ `StarforceHistoryInfo`에 **없음** |
| **장비 레벨 필드** | ❌ `StarforceHistoryInfo`에 **없음** (`target_item` 명칭만 있음) |
| **이벤트 할인율** | ✅ `StarforceHistoryEvent.cost_discount_rate`로 제공 |

→ 봇 설계 가정 **"스타포스 이력에 장비 레벨 미제공 → 기대값 별도 표 계산"** 이 **실호출로 확정됨**(메소·레벨 필드 모두 없음). `/스타포스` 커맨드에서 기대 소모 메소를 계산하려면 `target_item` 명에서 장비 정보를 파싱하거나 별도 장비 조회 API를 호출해야 하며, 강화 구간별 공식 비용 테이블을 내부 관리해야 한다.

**예시 응답** *(아래는 설명용 예시 — 실제 값 형식은 위 표의 "실측" 주석을 따른다: 플래그는 서술형 한글 문자열, 할인율은 `%` 없는 숫자, `item_upgrade_result`는 `"실패(유지)"` 등)*

```json
{
  "count": 3,
  "next_cursor": "eyJhbGciOiJIUzI1NiJ9...",
  "starforce_history": [
    {
      "id": "starforce-history-id-001",
      "item_upgrade_result": "성공",
      "before_starforce_count": 20,
      "after_starforce_count": 21,
      "starcatch_result": null,
      "superior_item_flag": "0",
      "destroy_defence": "0",
      "chance_time": "0",
      "event_field_flag": "0",
      "upgrade_item": "",
      "protect_shield": "0",
      "bonus_stat_upgrade": "0",
      "character_name": "메이플전사",
      "world_name": "크로아",
      "target_item": "아케인셰이드 소울슈터",
      "date_create": "2024-03-10T22:14:05+09:00",
      "starforce_event_list": [
        {
          "success_rate": null,
          "destroy_decrease_rate": null,
          "cost_discount_rate": "30%",
          "plus_value": null,
          "starforce_event_range": "0~24"
        }
      ]
    },
    {
      "id": "starforce-history-id-002",
      "item_upgrade_result": "파괴",
      "before_starforce_count": 22,
      "after_starforce_count": 12,
      "starcatch_result": null,
      "superior_item_flag": "0",
      "destroy_defence": "0",
      "chance_time": "0",
      "event_field_flag": "0",
      "upgrade_item": "",
      "protect_shield": "0",
      "bonus_stat_upgrade": "0",
      "character_name": "메이플전사",
      "world_name": "크로아",
      "target_item": "아케인셰이드 소울슈터",
      "date_create": "2024-03-10T22:15:41+09:00",
      "starforce_event_list": []
    }
  ]
}
```

**봇 활용 (`/스타포스`)**

| 필드 | 봇 활용 |
|------|---------|
| `item_upgrade_result` | 성공/실패/파괴 카운트 집계 → 실제 성공률 계산 |
| `before_starforce_count` + `after_starforce_count` | 강화 구간 파악 → 구간별 성공률 비교 |
| `target_item` | 아이템별 강화 이력 필터링 |
| `date_create` | 기간 필터 (`/스타포스 오늘` 등 프리셋) |
| `starforce_event_list[].cost_discount_rate` | 이벤트 할인 적용 시 비용 역산 |
| `destroy_defence` / `chance_time` / `protect_shield` | 소모 옵션 통계 |
| **강화 비용(메소)** | ❌ 필드 없음 → 공식 강화 비용 테이블(별도 관리) × 이벤트 할인율로 역산 |
| **장비 레벨** | ❌ 필드 없음 → `target_item` 파싱 또는 별도 장비 조회 API 필요. 기대값 표 계산 시 레벨 가정 필요 |
| `starcatch_result` | 스타 캐치 사용 통계 |
| `character_name` + `world_name` | 다중 캐릭터 소유 계정 필터링 |
