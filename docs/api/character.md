# 캐릭터 정보 조회 API (공식 문서 id=14)

> 공통 규약(Base URL `https://open.api.nexon.com`, 인증 헤더 `x-nxopen-api-key`, 날짜 KST/D-1, 에러코드)은 [README.md](./README.md) 참고.
> 응답 필드는 SpiralMoon/maplestory.openapi KMS DTO로 교차검증. 최종은 실호출로 확정.

---

## 엔드포인트 요약

| 한글명 | 경로 | 주요 파라미터 |
|---|---|---|
| 캐릭터 식별자(ocid) 조회 | `maplestory/v1/id` | `character_name` |
| 계정 내 캐릭터 목록 | `maplestory/v1/character/list` | (없음) |
| 업적 정보 | `maplestory/v1/user/achievement` | (없음) |
| 기본 정보 | `maplestory/v1/character/basic` | `ocid`, `date` |
| 인기도 | `maplestory/v1/character/popularity` | `ocid`, `date` |
| 종합 능력치 | `maplestory/v1/character/stat` | `ocid`, `date` |
| 하이퍼스탯 | `maplestory/v1/character/hyper-stat` | `ocid`, `date` |
| 성향 | `maplestory/v1/character/propensity` | `ocid`, `date` |
| 어빌리티 | `maplestory/v1/character/ability` | `ocid`, `date` |
| 장비(캐시 제외) | `maplestory/v1/character/item-equipment` | `ocid`, `date` |
| 캐시장비 | `maplestory/v1/character/cashitem-equipment` | `ocid`, `date` |
| 심볼 | `maplestory/v1/character/symbol-equipment` | `ocid`, `date` |
| 세트효과 | `maplestory/v1/character/set-effect` | `ocid`, `date` |
| 헤어/성형/피부 | `maplestory/v1/character/beauty-equipment` | `ocid`, `date` |
| 안드로이드 | `maplestory/v1/character/android-equipment` | `ocid`, `date` |
| 펫 | `maplestory/v1/character/pet-equipment` | `ocid`, `date` |
| 스킬 | `maplestory/v1/character/skill` | `ocid`, `date`, `character_skill_grade` |
| 링크스킬 | `maplestory/v1/character/link-skill` | `ocid`, `date` |
| V매트릭스 | `maplestory/v1/character/vmatrix` | `ocid`, `date` |
| HEXA매트릭스 | `maplestory/v1/character/hexamatrix` | `ocid`, `date` |
| HEXA스탯 | `maplestory/v1/character/hexamatrix-stat` | `ocid`, `date` |
| 무릉도장 | `maplestory/v1/character/dojang` | `ocid`, `date` |
| 기타 스탯 | `maplestory/v1/character/other-stat` | `ocid`, `date` |
| 반지 교환 스킬 | `maplestory/v1/character/ring-exchange-skill-equipment` | `ocid`, `date` |
| 반지 예약 스킬 | `maplestory/v1/character/ring-reserve-skill-equipment` | `ocid`, `date` |

---

## GET `maplestory/v1/id` — 캐릭터 식별자(ocid) 조회

캐릭터 이름으로 고유 식별자(ocid)를 조회한다. 이후 모든 캐릭터 API 호출에 ocid가 필요하다.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|---|---|---|---|
| `character_name` | Y | string | 캐릭터 명 |

**응답 필드**

| 필드 | 타입 | 설명 |
|---|---|---|
| `ocid` | string | 캐릭터 식별자 |

**예시 응답**
```json
{
  "ocid": "a1b2c3d4e5f6..."
}
```

**봇 활용:** `/스펙`, `/아이템` 등 모든 캐릭터 조회 명령의 첫 단계. `character_name` → `ocid` 변환 후 캐싱.

---

## GET `maplestory/v1/character/list` — 계정 내 캐릭터 목록

인증된 계정에 속한 전체 캐릭터 목록을 반환한다.

**요청 파라미터**

없음 (인증 헤더 필수)

**응답 필드**

| 필드 | 타입 | 설명 |
|---|---|---|
| `account_list` | array | 계정 목록 |
| `└ account_id` | string | Maple Story 계정 식별자 |
| `└ character_list` | array | 해당 계정의 캐릭터 목록 |
| `└─ ocid` | string | 캐릭터 식별자 |
| `└─ character_name` | string | 캐릭터 명 |
| `└─ world_name` | string | 월드 명 |
| `└─ character_class` | string | 직업 |
| `└─ character_level` | integer | 캐릭터 레벨 |

**예시 응답**
```json
{
  "account_list": [
    {
      "account_id": "acc_abc123",
      "character_list": [
        {
          "ocid": "a1b2c3...",
          "character_name": "메이플전사",
          "world_name": "스카니아",
          "character_class": "아크메이지(불,독)",
          "character_level": 285
        }
      ]
    }
  ]
}
```

---

## GET `maplestory/v1/user/achievement` — 업적 정보

인증된 계정의 업적 달성 정보를 반환한다.

**요청 파라미터**

없음 (인증 헤더 필수)

**응답 필드**

| 필드 | 타입 | 설명 |
|---|---|---|
| `account_list` | array | 계정 목록 |
| `└ account_id` | string | Maple Story 계정 식별자 |
| `└ achievement_achieve` | array | 달성한 업적 목록 |
| `└─ achievement_name` | string | 업적 명 |
| `└─ achievement_description` | string | 업적 설명 |

**예시 응답**
```json
{
  "account_list": [
    {
      "account_id": "acc_abc123",
      "achievement_achieve": [
        {
          "achievement_name": "첫 걸음",
          "achievement_description": "처음으로 레벨 10을 달성했습니다."
        }
      ]
    }
  ]
}
```

---

## GET `maplestory/v1/character/basic` — 기본 정보

캐릭터의 기본 정보(레벨, 직업, 월드, 경험치 등)를 반환한다.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|---|---|---|---|
| `ocid` | Y | string | 캐릭터 식별자 |
| `date` | N | string | 조회 기준일 (KST, `YYYY-MM-DD`, 미입력 시 D-1) |

**응답 필드**

| 필드 | 타입 | 설명 |
|---|---|---|
| `date` | datetime \| null | 조회 기준일 (KST) |
| `character_name` | string | 캐릭터 명 |
| `world_name` | string | 월드 명 |
| `character_gender` | string | 캐릭터 성별 |
| `character_class` | string | 직업 |
| `character_class_level` | string | 직업 전직 단계 |
| `character_level` | integer | 캐릭터 레벨 |
| `character_exp` | integer | 현재 레벨 경험치 |
| `character_exp_rate` | string | 현재 레벨 경험치 비율 (%) |
| `character_guild_name` | string \| null | 소속 길드 명 |
| `character_image` | string | 캐릭터 외형 이미지 URL |
| `character_date_create` | datetime \| null | 캐릭터 생성일 |
| `access_flag` | string | 최근 7일 접속 여부. ⚠️ **실호출로 확정: 값은 `"true"` / `"false"` 문자열**(`"1"/"0"` 아님) |
| `liberation_quest_clear` | string | 해방 퀘스트 완료 여부 (`"1"` / `"0"`) — 실측 `"1"` 확인 |

**예시 응답**
```json
{
  "date": "2024-11-15T00:00:00+09:00",
  "character_name": "메이플전사",
  "world_name": "스카니아",
  "character_gender": "남",
  "character_class": "아크메이지(불,독)",
  "character_class_level": "4",
  "character_level": 285,
  "character_exp": 12345678,
  "character_exp_rate": "45.23",
  "character_guild_name": "메이플길드",
  "character_image": "https://open.api.nexon.com/static/maplestory/...",
  "character_date_create": "2015-03-01T00:00:00+09:00",
  "access_flag": "true",
  "liberation_quest_clear": "1"
}
```

**봇 활용:** `/스펙` — `character_name`, `character_class`, `character_level`, `world_name`, `character_guild_name`, `character_image` 사용.

---

## GET `maplestory/v1/character/popularity` — 인기도

캐릭터의 인기도 수치를 반환한다.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|---|---|---|---|
| `ocid` | Y | string | 캐릭터 식별자 |
| `date` | N | string | 조회 기준일 (KST, `YYYY-MM-DD`) |

**응답 필드**

| 필드 | 타입 | 설명 |
|---|---|---|
| `date` | datetime \| null | 조회 기준일 (KST) |
| `popularity` | integer | 인기도 |

**예시 응답**
```json
{
  "date": "2024-11-15T00:00:00+09:00",
  "popularity": 9999
}
```

---

## GET `maplestory/v1/character/stat` — 종합 능력치

캐릭터의 현재 스탯 전체 목록과 잔여 AP를 반환한다. **전투력**은 `final_stat` 배열에서 `stat_name == "전투력"`인 항목의 `stat_value`로 확인한다.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|---|---|---|---|
| `ocid` | Y | string | 캐릭터 식별자 |
| `date` | N | string | 조회 기준일 (KST, `YYYY-MM-DD`) |

**응답 필드**

| 필드 | 타입 | 설명 |
|---|---|---|
| `date` | datetime \| null | 조회 기준일 (KST) |
| `character_class` | string | 직업 |
| `final_stat` | array | 현재 스탯 정보 목록 |
| `└ stat_name` | string | 스탯 명 (예: `"전투력"`, `"최대 HP"`, `"공격력"` 등) |
| `└ stat_value` | string | 스탯 값 |
| `remain_ap` | integer | 잔여 AP |

> **전투력 추출:** `next(s["stat_value"] for s in data["final_stat"] if s["stat_name"] == "전투력")`

**예시 응답**
```json
{
  "date": "2024-11-15T00:00:00+09:00",
  "character_class": "아크메이지(불,독)",
  "final_stat": [
    { "stat_name": "전투력", "stat_value": "12345678901" },
    { "stat_name": "최대 HP", "stat_value": "99999" },
    { "stat_name": "최대 MP", "stat_value": "30000" },
    { "stat_name": "공격력", "stat_value": "5000" },
    { "stat_name": "마력", "stat_value": "12000" },
    { "stat_name": "보스 몬스터 데미지", "stat_value": "280" }
  ],
  "remain_ap": 0
}
```

**봇 활용:** `/스펙` — `final_stat` 중 전투력, 보스 데미지, 방어율 무시, 마력/공격력 표시.

---

## GET `maplestory/v1/character/hyper-stat` — 하이퍼스탯

캐릭터의 하이퍼스탯 3개 프리셋 정보를 반환한다.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|---|---|---|---|
| `ocid` | Y | string | 캐릭터 식별자 |
| `date` | N | string | 조회 기준일 (KST, `YYYY-MM-DD`) |

**응답 필드**

| 필드 | 타입 | 설명 |
|---|---|---|
| `date` | datetime \| null | 조회 기준일 (KST) |
| `character_class` | string | 직업 |
| `use_preset_no` | string | 현재 사용 중인 프리셋 번호 |
| `use_available_hyper_stat` | integer | 사용 가능한 최대 하이퍼스탯 포인트 |
| `hyper_stat_preset_1` | array | 프리셋 1 스탯 목록 |
| `└ stat_type` | string | 스탯 종류 |
| `└ stat_point` | integer \| null | 투자 포인트 |
| `└ stat_level` | integer | 스탯 레벨 |
| `└ stat_increase` | string \| null | 스탯 증가량 |
| `hyper_stat_preset_1_remain_point` | integer | 프리셋 1 잔여 포인트 |
| `hyper_stat_preset_2` | array | 프리셋 2 스탯 목록 (구조 동일) |
| `hyper_stat_preset_2_remain_point` | integer | 프리셋 2 잔여 포인트 |
| `hyper_stat_preset_3` | array | 프리셋 3 스탯 목록 (구조 동일) |
| `hyper_stat_preset_3_remain_point` | integer | 프리셋 3 잔여 포인트 |

**예시 응답**
```json
{
  "date": "2024-11-15T00:00:00+09:00",
  "character_class": "아크메이지(불,독)",
  "use_preset_no": "1",
  "use_available_hyper_stat": 5000,
  "hyper_stat_preset_1": [
    { "stat_type": "STR", "stat_point": 0, "stat_level": 0, "stat_increase": null },
    { "stat_type": "데미지", "stat_point": 45, "stat_level": 9, "stat_increase": "+9%" }
  ],
  "hyper_stat_preset_1_remain_point": 10
}
```

---

## GET `maplestory/v1/character/propensity` — 성향

캐릭터의 6가지 성향 레벨을 반환한다.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|---|---|---|---|
| `ocid` | Y | string | 캐릭터 식별자 |
| `date` | N | string | 조회 기준일 (KST, `YYYY-MM-DD`) |

**응답 필드**

| 필드 | 타입 | 설명 |
|---|---|---|
| `date` | datetime \| null | 조회 기준일 (KST) |
| `charisma_level` | integer | 카리스마 레벨 |
| `sensibility_level` | integer | 감성 레벨 |
| `insight_level` | integer | 통찰력 레벨 |
| `willingness_level` | integer | 의지 레벨 |
| `handicraft_level` | integer | 손재주 레벨 |
| `charm_level` | integer | 매력 레벨 |

**예시 응답**
```json
{
  "date": "2024-11-15T00:00:00+09:00",
  "charisma_level": 100,
  "sensibility_level": 100,
  "insight_level": 100,
  "willingness_level": 100,
  "handicraft_level": 100,
  "charm_level": 100
}
```

---

## GET `maplestory/v1/character/ability` — 어빌리티

캐릭터의 어빌리티 등급·정보 및 3개 프리셋을 반환한다.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|---|---|---|---|
| `ocid` | Y | string | 캐릭터 식별자 |
| `date` | N | string | 조회 기준일 (KST, `YYYY-MM-DD`) |

**응답 필드**

| 필드 | 타입 | 설명 |
|---|---|---|
| `date` | datetime \| null | 조회 기준일 (KST) |
| `ability_grade` | string | 현재 어빌리티 등급 |
| `ability_info` | array | 현재 어빌리티 목록 |
| `└ ability_no` | string | 어빌리티 번호 |
| `└ ability_grade` | string | 어빌리티 등급 |
| `└ ability_value` | string | 어빌리티 값 |
| `remain_fame` | integer | 누적 명성치 |
| `preset_no` | integer \| null | 현재 활성 프리셋 번호 |
| `ability_preset_1` | object \| null | 프리셋 1 |
| `└ ability_preset_grade` | string | 프리셋 어빌리티 등급 |
| `└ ability_info` | array | 프리셋 어빌리티 목록 (구조: ability_no, ability_grade, ability_value) |
| `ability_preset_2` | object \| null | 프리셋 2 (구조 동일) |
| `ability_preset_3` | object \| null | 프리셋 3 (구조 동일) |

**예시 응답**
```json
{
  "date": "2024-11-15T00:00:00+09:00",
  "ability_grade": "레전드리",
  "ability_info": [
    { "ability_no": "1", "ability_grade": "레전드리", "ability_value": "버프 스킬의 지속 시간 +50%" },
    { "ability_no": "2", "ability_grade": "유니크", "ability_value": "공격 시 20%의 확률로 2초 동안 적을 상태 이상에 걸리게 함" },
    { "ability_no": "3", "ability_grade": "에픽", "ability_value": "STR, DEX, INT, LUK +12" }
  ],
  "remain_fame": 2500000,
  "preset_no": 1,
  "ability_preset_1": {
    "ability_preset_grade": "레전드리",
    "ability_info": [
      { "ability_no": "1", "ability_grade": "레전드리", "ability_value": "버프 스킬의 지속 시간 +50%" }
    ]
  },
  "ability_preset_2": null,
  "ability_preset_3": null
}
```

**봇 활용:** `/스펙` — `ability_grade`, `ability_info[].ability_value` 표시.

---

## GET `maplestory/v1/character/item-equipment` — 장비(캐시 제외)

캐릭터의 착용 장비 전체 정보를 반환한다. `/아이템` 명령의 핵심 엔드포인트.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|---|---|---|---|
| `ocid` | Y | string | 캐릭터 식별자 |
| `date` | N | string | 조회 기준일 (KST, `YYYY-MM-DD`) |

**응답 최상위 필드**

| 필드 | 타입 | 설명 |
|---|---|---|
| `date` | datetime \| null | 조회 기준일 (KST) |
| `character_gender` | string | 캐릭터 성별 |
| `character_class` | string | 직업 |
| `preset_no` | integer \| null | 현재 활성 프리셋 번호 |
| `item_equipment` | array | 현재 착용 장비 목록 |
| `item_equipment_preset_1` | array | 프리셋 1 장비 목록 |
| `item_equipment_preset_2` | array | 프리셋 2 장비 목록 |
| `item_equipment_preset_3` | array | 프리셋 3 장비 목록 |
| `title` | object \| null | 칭호 정보 |
| `medal_shape` | object \| null | 메달 외형 정보 |
| `dragon_equipment` | array | 에반 드래곤 장비 목록 |
| `mechanic_equipment` | array | 메카닉 장비 목록 |

**장비 아이템 스키마 (`CharacterItemEquipmentInfo`)**

| 필드 | 타입 | 설명 |
|---|---|---|
| `item_equipment_part` | string | 장비 파츠 명 |
| `item_equipment_slot` | string | 장비 슬롯 위치 |
| `item_name` | string | 장비 명 |
| `item_icon` | string | 장비 아이콘 이미지 URL |
| `item_description` | string \| null | 장비 설명 |
| `item_gender` | string \| null | 장비 성별 제한 |
| `item_shape_name` | string | 외형 장비 명 |
| `item_shape_icon` | string | 외형 장비 아이콘 URL |
| `item_total_option` | object | 장비 최종 옵션 |
| `item_base_option` | object | 장비 기본 옵션 |
| `item_exceptional_option` | object | 익셉셔널 강화 옵션 |
| `item_add_option` | object | 추가 옵션 |
| `item_etc_option` | object | 기타 옵션 |
| `item_starforce_option` | object | 스타포스 옵션 |
| `starforce` | string | 스타포스 강화 단계 |
| `starforce_scroll_flag` | string | 놀라운 장비 강화 주문서 사용 여부 |
| `potential_option_flag` | string \| null | 잠재능력 설정 여부 |
| `potential_option_grade` | string \| null | 잠재능력 등급 |
| `potential_option_1` | string \| null | 잠재능력 첫 번째 옵션 |
| `potential_option_2` | string \| null | 잠재능력 두 번째 옵션 |
| `potential_option_3` | string \| null | 잠재능력 세 번째 옵션 |
| `additional_potential_option_flag` | string \| null | 에디셔널 잠재능력 설정 여부 |
| `additional_potential_option_grade` | string \| null | 에디셔널 잠재능력 등급 |
| `additional_potential_option_1` | string \| null | 에디셔널 잠재능력 첫 번째 옵션 |
| `additional_potential_option_2` | string \| null | 에디셔널 잠재능력 두 번째 옵션 |
| `additional_potential_option_3` | string \| null | 에디셔널 잠재능력 세 번째 옵션 |
| `equipment_level_increase` | integer | 장비 레벨 증가 |
| `growth_exp` | integer | 성장 경험치 |
| `growth_level` | integer | 성장 레벨 |
| `scroll_upgrade` | string | 업그레이드 횟수 |
| `golden_hammer_flag` | string | 황금 망치 제련 적용 여부 |
| `scroll_resilience_count` | string | 복구 가능한 횟수 |
| `scroll_upgradeable_count` | string | 업그레이드 가능한 횟수 |
| `soul_name` | string \| null | 소울 명 |
| `soul_option` | string \| null | 소울 옵션 |
| `special_ring_level` | integer | 특수 반지 레벨 |
| `date_expire` | datetime \| null | 유효 기간 만료일 |
| `is_expired` | boolean \| null | 만료 여부 |
| `cuttable_count` | integer | 가위 사용 가능 횟수 (255 = 무제한) |
| `freestyle_flag` | string \| null | 자유 장착 여부 (`"1"` = 자유) |

**옵션 객체 공통 필드**

아래 표는 `item_total_option`, `item_base_option`, `item_etc_option`, `item_add_option`, `item_starforce_option` 각각에 포함될 수 있는 필드다. 오브젝트 종류에 따라 일부 필드가 없을 수 있다.

| 필드 | 타입 | 포함 옵션 타입 | 설명 |
|---|---|---|---|
| `str` | string | 전체 | STR |
| `dex` | string | 전체 | DEX |
| `int` | string | 전체 | INT |
| `luk` | string | 전체 | LUK |
| `max_hp` | string | 전체(except starforce) | 최대 HP |
| `max_mp` | string | 전체(except starforce) | 최대 MP |
| `attack_power` | string | 전체 | 공격력 |
| `magic_power` | string | 전체 | 마력 |
| `armor` | string | 전체 | 방어력 |
| `speed` | string | 전체 | 이동 속도 |
| `jump` | string | 전체 | 점프력 |
| `boss_damage` | string | total, base, add | 보스 몬스터 데미지 (%) |
| `ignore_monster_armor` | string | total, base | 몬스터 방어율 무시 (%) |
| `all_stat` | string | total, base, add | 올스탯 (%) |
| `damage` | string | total, add | 데미지 (%) |
| `max_hp_rate` | string | total, base | 최대 HP (%) |
| `max_mp_rate` | string | total, base | 최대 MP (%) |
| `equipment_level_decrease` | integer | total, add | 장비 레벨 감소 |
| `base_equipment_level` | integer | base 전용 | 기본 장비 레벨 |
| `exceptional_upgrade` | integer | exceptional 전용 | 익셉셔널 강화 횟수 (기본값 0) |

**칭호 스키마 (`title`)**

| 필드 | 타입 | 설명 |
|---|---|---|
| `title_name` | string \| null | 칭호 명 |
| `title_icon` | string \| null | 칭호 아이콘 URL |
| `title_description` | string \| null | 칭호 설명 |
| `date_expire` | datetime \| null | 칭호 유효 기간 만료일 |
| `date_option_expire` | datetime \| null | 칭호 옵션 유효 기간 만료일 |
| `is_expired` | boolean \| null | 칭호 만료 여부 |
| `is_option_expired` | boolean \| null | 칭호 옵션 만료 여부 |
| `title_shape_name` | string \| null | 외형 칭호 명 |
| `title_shape_icon` | string \| null | 외형 칭호 아이콘 URL |
| `title_shape_description` | string \| null | 외형 칭호 설명 |

**메달 외형 스키마 (`medal_shape`)**

| 필드 | 타입 | 설명 |
|---|---|---|
| `medal_shape_name` | string | 메달 외형 명 |
| `medal_shape_icon` | string | 메달 외형 아이콘 URL |
| `medal_shape_description` | string | 메달 외형 설명 |
| `medal_shape_changed_name` | string | 변경된 메달 외형 명 |
| `medal_shape_changed_icon` | string | 변경된 메달 외형 아이콘 URL |
| `medal_shape_changed_description` | string | 변경된 메달 외형 설명 |

**드래곤/메카닉 장비 스키마 (`dragon_equipment`, `mechanic_equipment`)**

`CharacterItemEquipmentDragonInfo` / `CharacterItemEquipmentMechanicInfo` — `item_equipment_part`, `item_equipment_slot`, `item_name`, `item_icon`, `item_description`, `item_gender`, `item_shape_name`, `item_shape_icon`, `item_total_option`, `item_base_option`, `item_exceptional_option`, `item_add_option`, `item_etc_option`, `item_starforce_option`, `starforce`, `starforce_scroll_flag`, `equipment_level_increase`, `growth_exp`, `growth_level`, `scroll_upgrade`, `golden_hammer_flag`, `scroll_resilience_count`, `scroll_upgradeable_count`, `soul_name`, `soul_option`, `special_ring_level`, `date_expire`, `is_expired`, `cuttable_count` (잠재능력 관련 필드 및 `freestyle_flag` 없음)

**예시 응답**
```json
{
  "date": "2024-11-15T00:00:00+09:00",
  "character_gender": "남",
  "character_class": "아크메이지(불,독)",
  "preset_no": 1,
  "item_equipment": [
    {
      "item_equipment_part": "모자",
      "item_equipment_slot": "모자",
      "item_name": "앱솔랩스 마법사모자",
      "item_icon": "https://open.api.nexon.com/static/maplestory/...",
      "item_description": null,
      "item_gender": null,
      "item_shape_name": "앱솔랩스 마법사모자",
      "item_shape_icon": "https://open.api.nexon.com/static/maplestory/...",
      "item_total_option": {
        "str": "0", "dex": "0", "int": "280", "luk": "0",
        "max_hp": "600", "max_mp": "600",
        "attack_power": "0", "magic_power": "120",
        "armor": "500", "speed": "0", "jump": "0",
        "boss_damage": "30", "ignore_monster_armor": "10",
        "all_stat": "0", "damage": "0",
        "max_hp_rate": "0", "max_mp_rate": "0",
        "equipment_level_decrease": 0
      },
      "item_base_option": {
        "str": "0", "dex": "0", "int": "75", "luk": "0",
        "max_hp": "255", "max_mp": "255",
        "attack_power": "0", "magic_power": "75",
        "armor": "300", "speed": "0", "jump": "0",
        "boss_damage": "0", "ignore_monster_armor": "0",
        "all_stat": "0", "max_hp_rate": "0", "max_mp_rate": "0",
        "base_equipment_level": 160
      },
      "item_exceptional_option": {
        "str": "0", "dex": "0", "int": "0", "luk": "0",
        "max_hp": "0", "max_mp": "0",
        "attack_power": "0", "magic_power": "0",
        "exceptional_upgrade": 0
      },
      "item_add_option": {
        "str": "0", "dex": "0", "int": "60", "luk": "0",
        "max_hp": "0", "max_mp": "0",
        "attack_power": "0", "magic_power": "0",
        "armor": "0", "speed": "0", "jump": "0",
        "boss_damage": "30", "damage": "0",
        "all_stat": "0", "equipment_level_decrease": 0
      },
      "item_etc_option": {
        "str": "0", "dex": "0", "int": "100", "luk": "0",
        "max_hp": "255", "max_mp": "255",
        "attack_power": "0", "magic_power": "35",
        "armor": "130", "speed": "0", "jump": "0"
      },
      "item_starforce_option": {
        "str": "0", "dex": "0", "int": "45", "luk": "0",
        "max_hp": "90", "max_mp": "90",
        "attack_power": "0", "magic_power": "10",
        "armor": "70", "speed": "0", "jump": "0"
      },
      "starforce": "22",
      "starforce_scroll_flag": "사용",
      "potential_option_flag": "해제",
      "potential_option_grade": "레전드리",
      "potential_option_1": "INT : +12%",
      "potential_option_2": "INT : +9%",
      "potential_option_3": "마력 : +9",
      "additional_potential_option_flag": "해제",
      "additional_potential_option_grade": "에픽",
      "additional_potential_option_1": "INT : +6%",
      "additional_potential_option_2": "INT : +6%",
      "additional_potential_option_3": "마력 : +6",
      "equipment_level_increase": 0,
      "growth_exp": 0,
      "growth_level": 0,
      "scroll_upgrade": "8",
      "golden_hammer_flag": "미적용",
      "scroll_resilience_count": "2",
      "scroll_upgradeable_count": "0",
      "soul_name": "위대한 카리스의 소울",
      "soul_option": "마력 +20",
      "special_ring_level": 0,
      "date_expire": null,
      "is_expired": false,
      "cuttable_count": 255,
      "freestyle_flag": null
    }
  ],
  "title": null,
  "medal_shape": null,
  "dragon_equipment": [],
  "mechanic_equipment": []
}
```

**봇 활용:** `/아이템` — 슬롯별 장비 표시, 잠재능력, 에디셔널 잠재능력, 스타포스, 옵션 수치 전체 활용.

> ⚠️ **실호출로 확정(2026-06-04) — "0성 vs 스타포스 불가 부위" 구분 신호 없음:** 25개 부위 실측 결과 `starforce` 값이 **`"0"`인 경우가 ① 실제 0성 강화 장비와 ② 스타포스 불가 부위(훈장/뱃지/포켓 아이템/엠블렘/특수 반지 등)에 공통**으로 나타난다. 두 경우를 구분하는 전용 불리언 필드는 **응답에 존재하지 않는다.** → 봇은 `item_equipment_part`(부위명) 기반 **정적 "스타포스 가능 부위" 표**로 보정해야 한다(설계의 동적+정적 하이브리드 정당화). 참고: 잠재능력 미설정/불가 부위는 `potential_option_grade`/`potential_option_flag`가 `null`.

---

## GET `maplestory/v1/character/cashitem-equipment` — 캐시장비

캐릭터의 캐시 아이템 착용 정보를 반환한다.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|---|---|---|---|
| `ocid` | Y | string | 캐릭터 식별자 |
| `date` | N | string | 조회 기준일 (KST, `YYYY-MM-DD`) |

**응답 필드**

| 필드 | 타입 | 설명 |
|---|---|---|
| `date` | datetime \| null | 조회 기준일 (KST) |
| `character_gender` | string | 캐릭터 성별 |
| `character_class` | string | 직업 |
| `character_look_mode` | string \| null | 외형 모드 |
| `preset_no` | integer | 현재 활성 프리셋 번호 |
| `cash_item_equipment_base` | array | 기본 캐시장비 목록 |
| `cash_item_equipment_preset_1` | array | 프리셋 1 캐시장비 목록 |
| `cash_item_equipment_preset_2` | array | 프리셋 2 캐시장비 목록 |
| `cash_item_equipment_preset_3` | array | 프리셋 3 캐시장비 목록 |
| `additional_cash_item_equipment_base` | array | 기본 추가 캐시장비 목록 |
| `additional_cash_item_equipment_preset_1` | array | 프리셋 1 추가 캐시장비 목록 |
| `additional_cash_item_equipment_preset_2` | array | 프리셋 2 추가 캐시장비 목록 |
| `additional_cash_item_equipment_preset_3` | array | 프리셋 3 추가 캐시장비 목록 |

**캐시장비 아이템 스키마**

| 필드 | 타입 | 설명 |
|---|---|---|
| `cash_item_equipment_part` | string | 캐시장비 파츠 명 |
| `cash_item_equipment_slot` | string | 캐시장비 슬롯 위치 |
| `cash_item_name` | string | 캐시장비 명 |
| `cash_item_icon` | string | 캐시장비 아이콘 URL |
| `cash_item_description` | string \| null | 캐시장비 설명 |
| `cash_item_option` | array | 캐시장비 옵션 목록 |
| `└ option_type` | string | 옵션 종류 |
| `└ option_value` | string | 옵션 값 |
| `date_expire` | datetime \| null | 유효 기간 만료일 |
| `is_expired` | boolean \| null | 만료 여부 |
| `date_option_expire` | datetime \| null | 옵션 유효 기간 만료일 |
| `is_option_expired` | boolean \| null | 옵션 만료 여부 |
| `cash_item_label` | string \| null | 캐시장비 라벨 |
| `cash_item_coloring_prism` | object \| null | 컬러링프리즘 정보 |
| `└ color_range` | string | 색상 범위 |
| `└ hue` | integer | 색조 |
| `└ saturation` | integer | 채도 |
| `└ value` | integer | 명도 |
| `cash_item_effect_prism` | object \| null | 이펙트프리즘 정보 (구조 동일) |
| `item_gender` | string \| null | 장비 성별 제한 |
| `skills` | array | 스킬 목록 (string 배열) |
| `freestyle_flag` | string \| null | 자유 장착 여부 |
| `emotion_name` | string \| null | 감정 표현 명 |

**예시 응답**
```json
{
  "date": "2024-11-15T00:00:00+09:00",
  "character_gender": "남",
  "character_class": "아크메이지(불,독)",
  "character_look_mode": null,
  "preset_no": 1,
  "cash_item_equipment_base": [
    {
      "cash_item_equipment_part": "전체 코스튬",
      "cash_item_equipment_slot": "전체 코스튬",
      "cash_item_name": "로얄 스타일 코스튬",
      "cash_item_icon": "https://open.api.nexon.com/static/maplestory/...",
      "cash_item_description": null,
      "cash_item_option": [],
      "date_expire": null,
      "is_expired": false,
      "date_option_expire": null,
      "is_option_expired": null,
      "cash_item_label": null,
      "cash_item_coloring_prism": null,
      "cash_item_effect_prism": null,
      "item_gender": null,
      "skills": [],
      "freestyle_flag": null,
      "emotion_name": null
    }
  ]
}
```

---

## GET `maplestory/v1/character/symbol-equipment` — 심볼 장비

캐릭터의 아케인/사크레드 심볼 착용 정보를 반환한다.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|---|---|---|---|
| `ocid` | Y | string | 캐릭터 식별자 |
| `date` | N | string | 조회 기준일 (KST, `YYYY-MM-DD`) |

**응답 필드**

| 필드 | 타입 | 설명 |
|---|---|---|
| `date` | datetime \| null | 조회 기준일 (KST) |
| `character_class` | string | 직업 |
| `symbol` | array | 심볼 목록 |
| `└ symbol_name` | string | 심볼 명 |
| `└ symbol_icon` | string | 심볼 아이콘 URL |
| `└ symbol_description` | string | 심볼 설명 |
| `└ symbol_other_effect_description` | string \| null | 기타 효과 설명 |
| `└ symbol_force` | string | 심볼 포스 수치 |
| `└ symbol_level` | integer | 심볼 레벨 |
| `└ symbol_str` | string | STR 증가량 |
| `└ symbol_dex` | string | DEX 증가량 |
| `└ symbol_int` | string | INT 증가량 |
| `└ symbol_luk` | string | LUK 증가량 |
| `└ symbol_hp` | string | HP 증가량 |
| `└ symbol_drop_rate` | string \| null | 아이템 드롭률 증가 |
| `└ symbol_meso_rate` | string \| null | 메소 획득량 증가 |
| `└ symbol_exp_rate` | string \| null | 경험치 획득량 증가 |
| `└ symbol_growth_count` | integer | 현재 성장치 |
| `└ symbol_require_growth_count` | integer | 다음 레벨 업 필요 성장치 |

**예시 응답**
```json
{
  "date": "2024-11-15T00:00:00+09:00",
  "character_class": "아크메이지(불,독)",
  "symbol": [
    {
      "symbol_name": "아케인심볼 : 소멸의 여로",
      "symbol_icon": "https://open.api.nexon.com/static/maplestory/...",
      "symbol_description": "아케인의 힘이 깃든 심볼",
      "symbol_other_effect_description": null,
      "symbol_force": "165",
      "symbol_level": 20,
      "symbol_str": "0",
      "symbol_dex": "0",
      "symbol_int": "2700",
      "symbol_luk": "0",
      "symbol_hp": "0",
      "symbol_drop_rate": null,
      "symbol_meso_rate": null,
      "symbol_exp_rate": null,
      "symbol_growth_count": 2679,
      "symbol_require_growth_count": 0
    }
  ]
}
```

**봇 활용:** `/스펙` — 심볼 레벨, 포스 합계, 스탯 합계 표시.

---

## GET `maplestory/v1/character/set-effect` — 세트효과

캐릭터의 착용 장비에 적용된 세트효과 정보를 반환한다.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|---|---|---|---|
| `ocid` | Y | string | 캐릭터 식별자 |
| `date` | N | string | 조회 기준일 (KST, `YYYY-MM-DD`) |

**응답 필드**

| 필드 | 타입 | 설명 |
|---|---|---|
| `date` | datetime \| null | 조회 기준일 (KST) |
| `set_effect` | array | 세트효과 목록 |
| `└ set_name` | string | 세트효과 명 |
| `└ total_set_count` | integer | 럭키 아이템 포함 세트 개수 |
| `└ set_effect_info` | array | 현재 활성화된 세트효과 정보 |
| `└─ set_count` | integer | 세트효과 단계 |
| `└─ set_option` | string | 세트효과 설명 |
| `└ set_option_full` | array | 모든 세트효과 단계 정보 (구조 동일) |

**예시 응답**
```json
{
  "date": "2024-11-15T00:00:00+09:00",
  "set_effect": [
    {
      "set_name": "앱솔랩스 마법사",
      "total_set_count": 6,
      "set_effect_info": [
        { "set_count": 2, "set_option": "INT : +15, 마력 : +5" },
        { "set_count": 4, "set_option": "마력 : +5, 보스 몬스터 공격 시 데미지 : +10%" },
        { "set_count": 6, "set_option": "마력 : +5, 보스 몬스터 공격 시 데미지 : +10%" }
      ],
      "set_option_full": [
        { "set_count": 2, "set_option": "INT : +15, 마력 : +5" },
        { "set_count": 4, "set_option": "마력 : +5, 보스 몬스터 공격 시 데미지 : +10%" },
        { "set_count": 6, "set_option": "마력 : +5, 보스 몬스터 공격 시 데미지 : +10%" }
      ]
    }
  ]
}
```

---

## GET `maplestory/v1/character/beauty-equipment` — 헤어/성형/피부

캐릭터의 헤어, 성형, 피부 정보를 반환한다. 기본/추가 두 세트 제공.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|---|---|---|---|
| `ocid` | Y | string | 캐릭터 식별자 |
| `date` | N | string | 조회 기준일 (KST, `YYYY-MM-DD`) |

**응답 필드**

| 필드 | 타입 | 설명 |
|---|---|---|
| `date` | datetime \| null | 조회 기준일 (KST) |
| `character_gender` | string \| null | 캐릭터 성별 |
| `character_class` | string \| null | 직업 |
| `character_hair` | object \| null | 기본 헤어 정보 |
| `└ hair_name` | string | 헤어 명 |
| `└ base_color` | string | 기본 색상 |
| `└ mix_color` | string \| null | 믹스 색상 |
| `└ mix_rate` | string | 믹스 색상 비율 (%) |
| `└ freestyle_flag` | string \| null | 자유 장착 여부 |
| `character_face` | object \| null | 기본 성형 정보 |
| `└ face_name` | string | 성형 명 |
| `└ base_color` | string | 기본 색상 |
| `└ mix_color` | string \| null | 믹스 색상 |
| `└ mix_rate` | string | 믹스 색상 비율 (%) |
| `└ freestyle_flag` | string \| null | 자유 장착 여부 |
| `character_skin` | object \| null | 기본 피부 정보 |
| `└ skin_name` | string | 피부 종류 명 |
| `└ color_style` | string \| null | 색상 계열 |
| `└ hue` | integer \| null | 색조 |
| `└ saturation` | integer \| null | 채도 |
| `└ brightness` | integer \| null | 밝기 |
| `additional_character_hair` | object \| null | 추가 헤어 정보 (구조 동일) |
| `additional_character_face` | object \| null | 추가 성형 정보 (구조 동일) |
| `additional_character_skin` | object \| null | 추가 피부 정보 (구조 동일) |

**예시 응답**
```json
{
  "date": "2024-11-15T00:00:00+09:00",
  "character_gender": "남",
  "character_class": "아크메이지(불,독)",
  "character_hair": { "hair_name": "클래식 단발", "base_color": "검정", "mix_color": null, "mix_rate": "0", "freestyle_flag": null },
  "character_face": { "face_name": "냉정한 눈빛", "base_color": "검정", "mix_color": null, "mix_rate": "0", "freestyle_flag": null },
  "character_skin": { "skin_name": "보통", "color_style": null, "hue": null, "saturation": null, "brightness": null },
  "additional_character_hair": null,
  "additional_character_face": null,
  "additional_character_skin": null
}
```

---

## GET `maplestory/v1/character/android-equipment` — 안드로이드

캐릭터의 안드로이드 착용 정보 및 프리셋을 반환한다.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|---|---|---|---|
| `ocid` | Y | string | 캐릭터 식별자 |
| `date` | N | string | 조회 기준일 (KST, `YYYY-MM-DD`) |

**응답 필드**

| 필드 | 타입 | 설명 |
|---|---|---|
| `date` | datetime \| null | 조회 기준일 (KST) |
| `android_name` | string \| null | 안드로이드 명 |
| `android_nickname` | string \| null | 안드로이드 닉네임 |
| `android_icon` | string \| null | 안드로이드 아이콘 URL |
| `android_description` | string \| null | 안드로이드 설명 |
| `android_hair` | object \| null | 안드로이드 헤어 (hair_name, base_color, mix_color, mix_rate, freestyle_flag) |
| `android_face` | object \| null | 안드로이드 성형 (face_name, base_color, mix_color, mix_rate, freestyle_flag) |
| `android_skin` | object \| null | 안드로이드 피부 (skin_name, color_style, hue, saturation, brightness) |
| `android_cash_item_equipment` | array | 안드로이드 캐시장비 목록 |
| `└ cash_item_equipment_part` | string | 파츠 명 |
| `└ cash_item_equipment_slot` | string | 슬롯 위치 |
| `└ cash_item_name` | string | 캐시장비 명 |
| `└ cash_item_icon` | string | 아이콘 URL |
| `└ cash_item_description` | string \| null | 설명 |
| `└ cash_item_option` | array | 옵션 목록 (option_type, option_value) |
| `└ date_expire` | datetime \| null | 만료일 |
| `└ is_expired` | boolean \| null | 만료 여부 |
| `└ date_option_expire` | datetime \| null | 옵션 만료일 |
| `└ is_option_expired` | boolean \| null | 옵션 만료 여부 |
| `└ cash_item_label` | string \| null | 라벨 |
| `└ cash_item_coloring_prism` | object \| null | 컬러링프리즘 (color_range, hue, saturation, value) |
| `└ android_item_gender` | string \| null | 장비 성별 제한 |
| `└ freestyle_flag` | string \| null | 자유 장착 여부 |
| `android_ear_sensor_clip_flag` | string \| null | 이어센서 클립 적용 여부 |
| `android_gender` | string \| null | 안드로이드 성별 |
| `android_grade` | string \| null | 안드로이드 등급 |
| `android_non_humanoid_flag` | string \| null | 비인간형 안드로이드 여부 |
| `android_shop_usable_flag` | string \| null | 상점 이용 가능 여부 |
| `preset_no` | integer \| null | 현재 활성 프리셋 번호 |
| `android_preset_1` | object \| null | 프리셋 1 안드로이드 정보 |
| `android_preset_2` | object \| null | 프리셋 2 안드로이드 정보 |
| `android_preset_3` | object \| null | 프리셋 3 안드로이드 정보 |

**프리셋 안드로이드 스키마 (`android_preset_1/2/3`)**

| 필드 | 타입 | 설명 |
|---|---|---|
| `android_name` | string | 안드로이드 명 |
| `android_nickname` | string | 닉네임 |
| `android_icon` | string | 아이콘 URL |
| `android_description` | string | 설명 |
| `android_gender` | string \| null | 성별 |
| `android_grade` | string | 등급 |
| `android_hair` | object | 헤어 정보 |
| `android_face` | object | 성형 정보 |
| `android_skin` | object \| null | 피부 정보 |
| `android_ear_sensor_clip_flag` | string | 이어센서 클립 적용 여부 |
| `android_non_humanoid_flag` | string | 비인간형 여부 |
| `android_shop_usable_flag` | string | 상점 이용 가능 여부 |

**예시 응답**
```json
{
  "date": "2024-11-15T00:00:00+09:00",
  "android_name": "엔젤릭버스터 안드로이드",
  "android_nickname": "버스터",
  "android_icon": "https://open.api.nexon.com/static/maplestory/...",
  "android_description": "...",
  "android_hair": { "hair_name": "웨이브 헤어", "base_color": "금발", "mix_color": null, "mix_rate": "0", "freestyle_flag": null },
  "android_face": { "face_name": "큰 눈", "base_color": "갈색", "mix_color": null, "mix_rate": "0", "freestyle_flag": null },
  "android_skin": null,
  "android_cash_item_equipment": [],
  "android_ear_sensor_clip_flag": "미적용",
  "android_gender": "여",
  "android_grade": "헤이로",
  "android_non_humanoid_flag": "미적용",
  "android_shop_usable_flag": "가능",
  "preset_no": null,
  "android_preset_1": null,
  "android_preset_2": null,
  "android_preset_3": null
}
```

---

## GET `maplestory/v1/character/pet-equipment` — 펫

캐릭터의 펫 3마리(슬롯 1~3) 착용 정보를 반환한다.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|---|---|---|---|
| `ocid` | Y | string | 캐릭터 식별자 |
| `date` | N | string | 조회 기준일 (KST, `YYYY-MM-DD`) |

**응답 필드**

각 펫 슬롯(`pet_1`, `pet_2`, `pet_3`)은 동일한 구조이다.

| 필드 | 타입 | 설명 |
|---|---|---|
| `date` | datetime \| null | 조회 기준일 (KST) |
| `pet_1_name` | string \| null | 펫 1 명 |
| `pet_1_nickname` | string \| null | 펫 1 닉네임 |
| `pet_1_icon` | string \| null | 펫 1 아이콘 URL |
| `pet_1_description` | string \| null | 펫 1 설명 |
| `pet_1_equipment` | object \| null | 펫 1 장착 아이템 정보 |
| `└ item_name` | string \| null | 아이템 명 |
| `└ item_icon` | string \| null | 아이템 아이콘 URL |
| `└ item_description` | string \| null | 아이템 설명 |
| `└ item_option` | array | 아이템 옵션 목록 (option_type, option_value) |
| `└ scroll_upgrade` | integer | 업그레이드 횟수 |
| `└ scroll_upgradable` | integer | 업그레이드 가능 횟수 |
| `└ item_shape` | string \| null | 외형 아이템 명 |
| `└ item_shape_icon` | string \| null | 외형 아이콘 URL |
| `└ item_date_expire` | datetime \| null | 아이템 만료일 |
| `pet_1_auto_skill` | object \| null | 펫 1 자동 스킬 |
| `└ skill_1` | string \| null | 자동 스킬 1 명 |
| `└ skill_1_icon` | string \| null | 자동 스킬 1 아이콘 URL |
| `└ skill_2` | string \| null | 자동 스킬 2 명 |
| `└ skill_2_icon` | string \| null | 자동 스킬 2 아이콘 URL |
| `pet_1_pet_type` | string \| null | 펫 1 종류 |
| `pet_1_skill` | array | 펫 1 보유 스킬 목록 (string 배열) |
| `pet_1_date_expire` | datetime \| null | 펫 1 만료일 |
| `pet_1_expired` | boolean \| null | 펫 1 만료 여부 |
| `pet_1_appearance` | string \| null | 펫 1 외형 명 |
| `pet_1_appearance_icon` | string \| null | 펫 1 외형 아이콘 URL |
| `pet_2_name` ... `pet_2_appearance_icon` | (동일 구조) | 펫 2 |
| `pet_3_name` ... `pet_3_appearance_icon` | (동일 구조) | 펫 3 |

**예시 응답**
```json
{
  "date": "2024-11-15T00:00:00+09:00",
  "pet_1_name": "메이플 모험대",
  "pet_1_nickname": "솜뭉치",
  "pet_1_icon": "https://open.api.nexon.com/static/maplestory/...",
  "pet_1_description": null,
  "pet_1_equipment": {
    "item_name": "메이플 모험대 갑옷",
    "item_icon": "https://...",
    "item_description": null,
    "item_option": [{ "option_type": "공격력", "option_value": "5" }],
    "scroll_upgrade": 0,
    "scroll_upgradable": 5,
    "item_shape": null,
    "item_shape_icon": null,
    "item_date_expire": null
  },
  "pet_1_auto_skill": { "skill_1": "아이템 줍기", "skill_1_icon": "...", "skill_2": null, "skill_2_icon": null },
  "pet_1_pet_type": "일반",
  "pet_1_skill": ["아이템 줍기"],
  "pet_1_date_expire": null,
  "pet_1_expired": false,
  "pet_1_appearance": null,
  "pet_1_appearance_icon": null,
  "pet_2_name": null,
  "pet_3_name": null
}
```

---

## GET `maplestory/v1/character/skill` — 스킬

캐릭터의 특정 차수 스킬 목록을 반환한다.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|---|---|---|---|
| `ocid` | Y | string | 캐릭터 식별자 |
| `date` | N | string | 조회 기준일 (KST, `YYYY-MM-DD`) |
| `character_skill_grade` | Y | string | 조회 차수 (`"0"` = 0차, `"1"` = 1차, `"1.5"` = 1.5차, `"2"` = 2차, `"2.5"` = 2.5차, `"3"` = 3차, `"4"` = 4차, `"hyperpassive"` = 하이퍼 패시브, `"hyperactive"` = 하이퍼 액티브, `"5"` = 5차, `"6"` = 6차) |

**응답 필드**

| 필드 | 타입 | 설명 |
|---|---|---|
| `date` | datetime \| null | 조회 기준일 (KST) |
| `character_class` | string | 직업 |
| `character_skill_grade` | string \| null | 조회 차수 |
| `character_skill` | array | 스킬 목록 |
| `└ skill_name` | string | 스킬 명 |
| `└ skill_description` | string | 스킬 설명 |
| `└ skill_level` | integer | 스킬 레벨 |
| `└ skill_effect` | string \| null | 스킬 효과 (현재 레벨) |
| `└ skill_effect_next` | string \| null | 다음 레벨 스킬 효과 |
| `└ skill_icon` | string | 스킬 아이콘 URL |

**예시 응답**
```json
{
  "date": "2024-11-15T00:00:00+09:00",
  "character_class": "아크메이지(불,독)",
  "character_skill_grade": "6",
  "character_skill": [
    {
      "skill_name": "인페르노",
      "skill_description": "불꽃을 쏟아부어 주변을 불바다로 만든다.",
      "skill_level": 30,
      "skill_effect": "최종 데미지: 1000%",
      "skill_effect_next": null,
      "skill_icon": "https://open.api.nexon.com/static/maplestory/..."
    }
  ]
}
```

---

## GET `maplestory/v1/character/link-skill` — 링크스킬

캐릭터에 장착된 링크스킬 및 3개 프리셋과 자신의 링크스킬을 반환한다.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|---|---|---|---|
| `ocid` | Y | string | 캐릭터 식별자 |
| `date` | N | string | 조회 기준일 (KST, `YYYY-MM-DD`) |

**응답 필드**

| 필드 | 타입 | 설명 |
|---|---|---|
| `date` | datetime \| null | 조회 기준일 (KST) |
| `character_class` | string | 직업 |
| `character_link_skill` | array | 현재 장착 링크스킬 목록 |
| `└ skill_name` | string | 스킬 명 |
| `└ skill_description` | string | 스킬 설명 |
| `└ skill_level` | integer | 스킬 레벨 |
| `└ skill_effect` | string | 스킬 효과 |
| `└ skill_effect_next` | string \| null | 다음 레벨 효과 |
| `└ skill_icon` | string | 스킬 아이콘 URL |
| `character_link_skill_preset_1` | array | 프리셋 1 링크스킬 (구조 동일) |
| `character_link_skill_preset_2` | array | 프리셋 2 링크스킬 (구조 동일) |
| `character_link_skill_preset_3` | array | 프리셋 3 링크스킬 (구조 동일) |
| `character_owned_link_skill` | object \| null | 본인 링크스킬 (구조 동일) |
| `character_owned_link_skill_preset_1` | object \| null | 본인 링크스킬 프리셋 1 (구조 동일) |
| `character_owned_link_skill_preset_2` | object \| null | 본인 링크스킬 프리셋 2 (구조 동일) |
| `character_owned_link_skill_preset_3` | object \| null | 본인 링크스킬 프리셋 3 (구조 동일) |

**예시 응답**
```json
{
  "date": "2024-11-15T00:00:00+09:00",
  "character_class": "아크메이지(불,독)",
  "character_link_skill": [
    { "skill_name": "파이어브레스", "skill_description": "...", "skill_level": 3, "skill_effect": "마력 +15", "skill_effect_next": null, "skill_icon": "..." }
  ],
  "character_link_skill_preset_1": [],
  "character_link_skill_preset_2": [],
  "character_link_skill_preset_3": [],
  "character_owned_link_skill": { "skill_name": "이그니션", "skill_description": "...", "skill_level": 2, "skill_effect": "불 속성 데미지 +10%", "skill_effect_next": null, "skill_icon": "..." },
  "character_owned_link_skill_preset_1": null,
  "character_owned_link_skill_preset_2": null,
  "character_owned_link_skill_preset_3": null
}
```

---

## GET `maplestory/v1/character/vmatrix` — V매트릭스

캐릭터의 V코어 장착 정보를 반환한다.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|---|---|---|---|
| `ocid` | Y | string | 캐릭터 식별자 |
| `date` | N | string | 조회 기준일 (KST, `YYYY-MM-DD`) |

**응답 필드**

| 필드 | 타입 | 설명 |
|---|---|---|
| `date` | datetime \| null | 조회 기준일 (KST) |
| `character_class` | string | 직업 |
| `character_v_core_equipment` | array | V코어 장착 목록 |
| `└ slot_id` | string | 슬롯 인덱스 |
| `└ slot_level` | integer | 슬롯 레벨 (2025-12-18 이후 지원 종료) |
| `└ v_core_name` | string \| null | V코어 명 |
| `└ v_core_type` | string \| null | V코어 종류 |
| `└ v_core_level` | integer | V코어 레벨 |
| `└ v_core_skill_1` | string \| null | 연결 스킬 1 (2025-12-18 이후 지원 종료) |
| `└ v_core_skill_2` | string \| null | 연결 스킬 2 (2025-12-18 이후 지원 종료) |
| `└ v_core_skill_3` | string \| null | 연결 스킬 3 (2025-12-18 이후 지원 종료) |
| `character_v_matrix_remain_slot_upgrade_point` | integer | 잔여 슬롯 강화 포인트 |

**예시 응답**
```json
{
  "date": "2024-11-15T00:00:00+09:00",
  "character_class": "아크메이지(불,독)",
  "character_v_core_equipment": [
    { "slot_id": "0", "slot_level": 30, "v_core_name": "플레임 헤이즈 강화", "v_core_type": "스킬 강화", "v_core_level": 60, "v_core_skill_1": "플레임 헤이즈", "v_core_skill_2": null, "v_core_skill_3": null }
  ],
  "character_v_matrix_remain_slot_upgrade_point": 0
}
```

---

## GET `maplestory/v1/character/hexamatrix` — HEXA매트릭스

캐릭터의 HEXA코어 장착 정보를 반환한다.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|---|---|---|---|
| `ocid` | Y | string | 캐릭터 식별자 |
| `date` | N | string | 조회 기준일 (KST, `YYYY-MM-DD`) |

**응답 필드**

| 필드 | 타입 | 설명 |
|---|---|---|
| `date` | datetime \| null | 조회 기준일 (KST) |
| `character_hexa_core_equipment` | array | HEXA코어 장착 목록 |
| `└ hexa_core_name` | string | 코어 명 |
| `└ hexa_core_level` | integer | 코어 레벨 |
| `└ hexa_core_type` | string | 코어 종류 |
| `└ linked_skill` | array | 연결 스킬 목록 |
| `└─ hexa_skill_id` | string | HEXA 스킬 명 |

**예시 응답**
```json
{
  "date": "2024-11-15T00:00:00+09:00",
  "character_hexa_core_equipment": [
    {
      "hexa_core_name": "인페르노 마스터리",
      "hexa_core_level": 30,
      "hexa_core_type": "마스터리",
      "linked_skill": [
        { "hexa_skill_id": "인페르노" }
      ]
    },
    {
      "hexa_core_name": "인페르노 강화",
      "hexa_core_level": 10,
      "hexa_core_type": "강화",
      "linked_skill": [
        { "hexa_skill_id": "인페르노" }
      ]
    }
  ]
}
```

**봇 활용:** `/스펙` — HEXA코어 레벨, 종류, 연결 스킬 표시.

---

## GET `maplestory/v1/character/hexamatrix-stat` — HEXA스탯

캐릭터의 HEXA 스탯 코어 정보를 반환한다.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|---|---|---|---|
| `ocid` | Y | string | 캐릭터 식별자 |
| `date` | N | string | 조회 기준일 (KST, `YYYY-MM-DD`) |

**응답 필드**

| 필드 | 타입 | 설명 |
|---|---|---|
| `date` | datetime \| null | 조회 기준일 (KST) |
| `character_class` | string | 직업 |
| `character_hexa_stat_core` | array | HEXA 스탯 I 코어 목록 |
| `└ slot_id` | string | 슬롯 인덱스 |
| `└ main_stat_name` | string | 메인 스탯 명 |
| `└ sub_stat_name_1` | string | 서브 스탯 1 명 |
| `└ sub_stat_name_2` | string | 서브 스탯 2 명 |
| `└ main_stat_level` | integer | 메인 스탯 레벨 |
| `└ sub_stat_level_1` | integer | 서브 스탯 1 레벨 |
| `└ sub_stat_level_2` | integer | 서브 스탯 2 레벨 |
| `└ stat_grade` | integer | 스탯 코어 등급 |
| `character_hexa_stat_core_2` | array | HEXA 스탯 II 코어 목록 (구조 동일) |
| `character_hexa_stat_core_3` | array | HEXA 스탯 III 코어 목록 (구조 동일) |
| `preset_hexa_stat_core` | array | 프리셋 HEXA 스탯 I 코어 목록 (구조 동일) |
| `preset_hexa_stat_core_2` | array | 프리셋 HEXA 스탯 II 코어 목록 (구조 동일) |
| `preset_hexa_stat_core_3` | array | 프리셋 HEXA 스탯 III 코어 목록 (구조 동일) |

**예시 응답**
```json
{
  "date": "2024-11-15T00:00:00+09:00",
  "character_class": "아크메이지(불,독)",
  "character_hexa_stat_core": [
    {
      "slot_id": "0",
      "main_stat_name": "마력",
      "sub_stat_name_1": "보스 몬스터 데미지",
      "sub_stat_name_2": "방어율 무시",
      "main_stat_level": 10,
      "sub_stat_level_1": 5,
      "sub_stat_level_2": 5,
      "stat_grade": 0
    }
  ],
  "character_hexa_stat_core_2": [],
  "character_hexa_stat_core_3": [],
  "preset_hexa_stat_core": [],
  "preset_hexa_stat_core_2": [],
  "preset_hexa_stat_core_3": []
}
```

**봇 활용:** `/스펙` — HEXA 스탯 메인/서브 명, 레벨 표시.

---

## GET `maplestory/v1/character/dojang` — 무릉도장

캐릭터의 무릉도장 최고 기록을 반환한다.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|---|---|---|---|
| `ocid` | Y | string | 캐릭터 식별자 |
| `date` | N | string | 조회 기준일 (KST, `YYYY-MM-DD`) |

**응답 필드**

| 필드 | 타입 | 설명 |
|---|---|---|
| `date` | datetime \| null | 조회 기준일 (KST) |
| `character_class` | string | 직업 |
| `world_name` | string | 월드 명 |
| `dojang_best_floor` | integer | 무릉도장 최고 층수 |
| `date_dojang_record` | datetime \| null | 무릉도장 최고 기록 달성 날짜 |
| `dojang_best_time` | integer | 무릉도장 최고 기록 (초) |

**예시 응답**
```json
{
  "date": "2024-11-15T00:00:00+09:00",
  "character_class": "아크메이지(불,독)",
  "world_name": "스카니아",
  "dojang_best_floor": 90,
  "date_dojang_record": "2024-10-31T00:00:00+09:00",
  "dojang_best_time": 543
}
```

**봇 활용:** `/스펙` — `dojang_best_floor`, `dojang_best_time` 표시.

---

## GET `maplestory/v1/character/other-stat` — 기타 스탯

캐릭터의 기타 능력치 영향 요소 정보를 반환한다.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|---|---|---|---|
| `ocid` | Y | string | 캐릭터 식별자 |
| `date` | N | string | 조회 기준일 (KST, `YYYY-MM-DD`) |

**응답 필드**

| 필드 | 타입 | 설명 |
|---|---|---|
| `date` | datetime \| null | 조회 기준일 (KST) |
| `other_stat` | array | 기타 스탯 요소 목록 |
| `└ other_stat_type` | string | 능력치 영향 요소 종류 |
| `└ stat_info` | array | 해당 요소의 스탯 정보 목록 |
| `└─ stat_name` | string | 스탯 명 |
| `└─ stat_value` | string | 스탯 값 |

**예시 응답**
```json
{
  "date": "2024-11-15T00:00:00+09:00",
  "other_stat": [
    {
      "other_stat_type": "링크스킬",
      "stat_info": [
        { "stat_name": "마력", "stat_value": "120" }
      ]
    }
  ]
}
```

---

## GET `maplestory/v1/character/ring-exchange-skill-equipment` — 반지 교환 스킬

캐릭터의 반지 교환 특수 스킬 장착 정보를 반환한다.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|---|---|---|---|
| `ocid` | Y | string | 캐릭터 식별자 |
| `date` | N | string | 조회 기준일 (KST, `YYYY-MM-DD`) |

**응답 필드**

| 필드 | 타입 | 설명 |
|---|---|---|
| `date` | datetime \| null | 조회 기준일 (KST) |
| `character_class` | string \| null | 직업 |
| `special_ring_exchange_name` | string \| null | 교환 특수 반지 명 |
| `special_ring_exchange_level` | integer \| null | 교환 특수 반지 레벨 |
| `special_ring_exchange_icon` | string \| null | 교환 특수 반지 아이콘 URL |
| `special_ring_exchange_description` | string \| null | 교환 특수 반지 설명 |

**예시 응답**
```json
{
  "date": "2024-11-15T00:00:00+09:00",
  "character_class": "아크메이지(불,독)",
  "special_ring_exchange_name": null,
  "special_ring_exchange_level": null,
  "special_ring_exchange_icon": null,
  "special_ring_exchange_description": null
}
```

---

## GET `maplestory/v1/character/ring-reserve-skill-equipment` — 반지 예약 스킬

캐릭터의 반지 예약 특수 스킬 장착 정보를 반환한다.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|---|---|---|---|
| `ocid` | Y | string | 캐릭터 식별자 |
| `date` | N | string | 조회 기준일 (KST, `YYYY-MM-DD`) |

**응답 필드**

| 필드 | 타입 | 설명 |
|---|---|---|
| `date` | datetime \| null | 조회 기준일 (KST) |
| `character_class` | string | 직업 |
| `special_ring_reserve_name` | string \| null | 예약 특수 반지 명 |
| `special_ring_reserve_level` | integer \| null | 예약 특수 반지 레벨 |
| `special_ring_reserve_icon` | string \| null | 예약 특수 반지 아이콘 URL |
| `special_ring_reserve_description` | string \| null | 예약 특수 반지 설명 |

**예시 응답**
```json
{
  "date": "2024-11-15T00:00:00+09:00",
  "character_class": "아크메이지(불,독)",
  "special_ring_reserve_name": null,
  "special_ring_reserve_level": null,
  "special_ring_reserve_icon": null,
  "special_ring_reserve_description": null
}
```
