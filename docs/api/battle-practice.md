# 연무장 API (공식 문서 id=55)

> 공통 규약(Base URL `https://open.api.nexon.com`, 인증 헤더 `x-nxopen-api-key`, 날짜 KST/D-1, 에러코드)은 [README.md](./README.md) 참고.
> 응답 필드는 SpiralMoon/maplestory.openapi KMS DTO로 교차검증. 최종은 실호출로 확정.

## 엔드포인트 요약

| 메서드 | 경로 | 한글명 | 주요 응답 |
|--------|------|--------|-----------|
| GET | `maplestory/v1/battle-practice/replay-id` | 리플레이 식별자 목록 | `replay_list` |
| GET | `maplestory/v1/battle-practice/result` | 전투 분석 결과 | DPS·스킬 통계 |
| GET | `maplestory/v1/battle-practice/skill-timeline` | 스킬 타임라인 | 시간별 스킬 사용 내역 (페이지네이션) |
| GET | `maplestory/v1/battle-practice/character-info` | 캐릭터 정보 | 연무장 측정 시점의 전체 캐릭터 스냅샷 |

---

## GET `maplestory/v1/battle-practice/replay-id` — 리플레이 식별자 목록

`ocid`로 해당 캐릭터의 연무장 리플레이 식별자 목록을 조회한다. 이후 세부 엔드포인트의 `replay_id` 파라미터로 사용.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|------|------|------|------|
| `ocid` | 필수 | string | 캐릭터 식별자 |

**응답 필드**

| 필드 | 타입 | 설명 |
|------|------|------|
| `replay_list` | list[BattlePracticeReplayIdInfo] | 리플레이 목록 |
| `└ period_no` | int | 기간 번호 (연무장 초기화마다 1씩 증가) |
| `└ register_date` | datetime | 리플레이 등록 일시 (KST) |
| `└ replay_id` | string | 연무장 리플레이 고유 식별자 |

**예시 응답**

```json
{
  "replay_list": [
    {
      "period_no": 5,
      "register_date": "2025-01-01T14:30:00+09:00",
      "replay_id": "replay_abc123"
    },
    {
      "period_no": 5,
      "register_date": "2025-01-01T12:00:00+09:00",
      "replay_id": "replay_def456"
    }
  ]
}
```

---

## GET `maplestory/v1/battle-practice/result` — 전투 분석 결과

`replay_id`로 해당 연무장 측정의 종합 DPS, 총 데미지, 스킬별 전투 분석을 조회한다.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|------|------|------|------|
| `replay_id` | 필수 | string | 연무장 리플레이 고유 식별자 |

**응답 필드**

| 필드 | 타입 | 설명 |
|------|------|------|
| `register_date` | datetime | 리플레이 등록 일시 (KST) |
| `total_play_time` | int | 총 연무 시간 (ms) |
| `total_damage` | int | 총합 데미지 |
| `total_dps` | int | 초당 평균 데미지 (DPS) |
| `end_type` | string | 종료 타입 (`"1"`: 자동 종료, `"2"`: 수동 종료, `"3"`: 시간 초과, `"9"`: 기타 종료) |
| `like_count` | int | 리플레이 추천 수 |
| `skill_statistic` | list[BattlePracticeSkillStatistic] | 스킬별 전투 분석 목록 |
| `└ skill_name` | string | 스킬 명 |
| `└ damage` | int | 누적 데미지 |
| `└ damage_percent` | string | 데미지 점유율 |
| `└ dps` | int | 초당 평균 데미지 |
| `└ use_count` | int | 사용 횟수 |
| `└ damage_per_use` | int | 1회당 평균 데미지 |
| `└ attack_count` | int | 공격 횟수 |
| `└ max_damage` | int | 최대 데미지 (1타) |
| `└ min_damage` | int | 최소 데미지 (1타) |

**예시 응답**

```json
{
  "register_date": "2025-01-01T14:30:00+09:00",
  "total_play_time": 120000,
  "total_damage": 98500000000,
  "total_dps": 820833333,
  "end_type": "1",
  "like_count": 12,
  "skill_statistic": [
    {
      "skill_name": "파이널 어택: 아크메이지",
      "damage": 15000000000,
      "damage_percent": "15.23",
      "dps": 125000000,
      "use_count": 320,
      "damage_per_use": 46875000,
      "attack_count": 640,
      "max_damage": 95000000,
      "min_damage": 10000000
    }
  ]
}
```

**봇 활용:** `/연무장` 또는 전투 분석 명령에서 `total_dps`, `total_damage`, `skill_statistic`의 상위 스킬 점유율을 요약 카드로 표시.

---

## GET `maplestory/v1/battle-practice/skill-timeline` — 스킬 타임라인

`replay_id`와 `page_no`로 연무장 측정 중 사용된 스킬의 시간 순 타임라인을 조회한다. 결과가 많을 경우 페이지네이션으로 분할 제공.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|------|------|------|------|
| `replay_id` | 필수 | string | 연무장 리플레이 고유 식별자 |
| `page_no` | 필수 | int | 조회할 페이지 번호 (1부터 시작) |

**응답 필드**

| 필드 | 타입 | 설명 |
|------|------|------|
| `page_no` | int | 조회된 페이지 번호 |
| `total_page_no` | int | 전체 페이지 수 |
| `skill_timeline` | list[BattlePracticeSkillTimelineEvent] | 스킬 타임라인 이벤트 목록 |
| `└ elapse_time` | int | 연무 시작 후 경과 시간 (ms) |
| `└ skill_name` | string | 사용한 스킬 명 |
| `└ hexa_skill_specificity_flag` | string | 헥사 스킬 특성 분류 (`"0"`: 그 외 스킬, `"1"`: 오리진 스킬, `"2"`: 어센트 스킬) |
| `└ sequence_name` | string \| null | 시퀀스 명 |
| `└ sequence_key` | string \| null | 시퀀스 키 |

**예시 응답**

```json
{
  "page_no": 1,
  "total_page_no": 3,
  "skill_timeline": [
    {
      "elapse_time": 1200,
      "skill_name": "메테오",
      "hexa_skill_specificity_flag": "0",
      "sequence_name": null,
      "sequence_key": null
    },
    {
      "elapse_time": 2450,
      "skill_name": "오리진 스킬: 아크메이지",
      "hexa_skill_specificity_flag": "1",
      "sequence_name": "시퀀스A",
      "sequence_key": "seq_001"
    }
  ]
}
```

---

## GET `maplestory/v1/battle-practice/character-info` — 캐릭터 정보

`replay_id`로 연무장 측정 시점의 캐릭터 전체 스냅샷(스탯, 장비, 스킬, 유니온, 길드 등)을 조회한다. 응답이 매우 크므로 필요한 서브오브젝트만 사용 권장.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|------|------|------|------|
| `replay_id` | 필수 | string | 연무장 리플레이 고유 식별자 |

**응답 필드 — 최상위**

| 필드 | 타입 | 설명 |
|------|------|------|
| `basic_object` | BattlePracticeCharacterBasic \| null | 캐릭터 기본 정보 |
| `stat_object` | BattlePracticeCharacterStat \| null | 스탯 정보 |
| `hyper_stat_object` | BattlePracticeCharacterHyperStatObject \| null | 하이퍼 스탯 정보 |
| `propensity_object` | BattlePracticeCharacterPropensity \| null | 성향 정보 |
| `ability_object` | BattlePracticeCharacterAbilityObject \| null | 어빌리티 정보 |
| `item_object` | BattlePracticeCharacterItemObject \| null | 장비 및 세트 효과 정보 |
| `cash_item_object` | BattlePracticeCharacterCashItemObject \| null | 캐시 장비 정보 |
| `pet_object` | BattlePracticeCharacterPetObject \| null | 펫 정보 |
| `skill_object` | BattlePracticeCharacterSkillObject \| null | 스킬 정보 |
| `link_skill_object` | BattlePracticeCharacterLinkSkillObject \| null | 링크 스킬 정보 |
| `v_matrix_object` | BattlePracticeCharacterVMatrixObject \| null | V 매트릭스 정보 |
| `hexa_matrix_object` | BattlePracticeCharacterHexaMatrixObject \| null | HEXA 매트릭스 정보 |
| `ring_reserve_skill_object` | BattlePracticeCharacterRingReserveSkillObject \| null | 링 리저브 스킬 정보 |
| `union_raider_object` | BattlePracticeUnionRaiderObject \| null | 유니온 공격대 효과 요약 |
| `union_artifact_object` | BattlePracticeUnionArtifactObject \| null | 유니온 아티팩트 효과 요약 |
| `union_champion_object` | BattlePracticeUnionChampionObject \| null | 유니온 챔피언 휘장 합산 |
| `guild_object` | BattlePracticeGuildObject \| null | 길드·노블레스 스킬 요약 |

**`basic_object` 내부 필드**

| 필드 | 타입 | 설명 |
|------|------|------|
| `character_name` | string | 캐릭터 명 |
| `character_level` | int | 캐릭터 레벨 |
| `character_class` | string | 직업 명 |
| `character_class_level` | string | 직업 레벨 |
| `character_image` | string | 캐릭터 이미지 URL |

**`stat_object` 내부 필드**

| 필드 | 타입 | 설명 |
|------|------|------|
| `basic_stat_object` | BattlePracticeCharacterBasicStat | 기본 스탯 |
| `└ final_stat` | list[BattlePracticeCharacterFinalStat] | 최종 스탯 목록 |
| `  └ stat_name` | string | 스탯 명 |
| `  └ stat_value` | string | 스탯 값 |
| `symbol_stat_object` | BattlePracticeCharacterSymbolStat | 심볼 스탯 |
| `└ symbol` | list[BattlePracticeCharacterSymbol] | 심볼 목록 |
| `  └ symbol_name` | string | 심볼 명 |
| `  └ symbol_force` | string | 심볼 포스 |
| `  └ symbol_level` | int | 심볼 레벨 |
| `  └ symbol_str` | string | STR 증가량 |
| `  └ symbol_dex` | string | DEX 증가량 |
| `  └ symbol_int` | string | INT 증가량 |
| `  └ symbol_luk` | string | LUK 증가량 |
| `  └ symbol_hp` | string | HP 증가량 |
| `  └ symbol_drop_rate` | string | 아이템 드롭률 증가 |
| `  └ symbol_meso_rate` | string | 메소 획득량 증가 |
| `  └ symbol_exp_rate` | string | 경험치 획득량 증가 |
| `  └ symbol_growth_count` | int | 현재 성장치 |
| `  └ symbol_require_growth_count` | int | 다음 레벨업 필요 성장치 |
| `other_stat_object` | BattlePracticeCharacterOtherStat | 기타 스탯 |
| `└ other_stat` | list[BattlePracticeCharacterOtherStatDetail] | 기타 스탯 상세 목록 |
| `  └ other_stat_type` | string | 스탯 타입 |
| `  └ stat_info` | list[BattlePracticeCharacterOtherStatInfo] | 스탯 세부 항목 |
| `    └ stat_name` | string | 스탯 명 |
| `    └ stat_value` | string | 스탯 값 |

**`hyper_stat_object` 내부 필드**

| 필드 | 타입 | 설명 |
|------|------|------|
| `hyper_stat` | list[BattlePracticeCharacterHyperStat] | 하이퍼 스탯 목록 |
| `└ stat_type` | string | 스탯 타입 |
| `└ stat_level` | int | 스탯 레벨 |
| `└ stat_increase` | string | 스탯 증가량 |

**`propensity_object` 내부 필드**

| 필드 | 타입 | 설명 |
|------|------|------|
| `charisma_level` | int | 카리스마 레벨 |
| `sensibility_level` | int | 감성 레벨 |
| `insight_level` | int | 통찰력 레벨 |
| `willingness_level` | int | 의지 레벨 |
| `handicraft_level` | int | 손재주 레벨 |
| `charm_level` | int | 매력 레벨 |

**`ability_object` 내부 필드**

| 필드 | 타입 | 설명 |
|------|------|------|
| `ability_info` | list[BattlePracticeCharacterAbilityInfo] | 어빌리티 목록 |
| `└ ability_no` | string | 어빌리티 번호 |
| `└ ability_grade` | string | 어빌리티 등급 |
| `└ ability_value` | string | 어빌리티 효과 |

**`item_object` — 장비 정보** (`item_equipment_object` 내부)

| 필드 | 타입 | 설명 |
|------|------|------|
| `item_equipment` | list[BattlePracticeCharacterItemEquipment] | 일반 장비 목록 |
| `└ item_equipment_part` | string | 장비 부위 |
| `└ item_equipment_slot` | string | 장비 슬롯 |
| `└ item_name` | string | 아이템 명 |
| `└ item_icon` | string | 아이템 아이콘 URL |
| `└ item_description` | string \| null | 아이템 설명 |
| `└ item_shape_name` | string | 외형 아이템 명 |
| `└ item_shape_icon` | string | 외형 아이템 아이콘 |
| `└ item_gender` | string \| null | 아이템 성별 제한 |
| `└ item_total_option` | object | 장비 합산 옵션 (str, dex, int, luk, max_hp, max_mp, attack_power, magic_power, armor, speed, jump, boss_damage, ignore_monster_armor, all_stat, damage, equipment_level_decrease, max_hp_rate, max_mp_rate) |
| `└ item_base_option` | object | 장비 기본 옵션 (동일 구조, `base_equipment_level` 포함) |
| `└ item_exceptional_option` | object | 익셉셔널 옵션 (str, dex, int, luk, max_hp, max_mp, attack_power, magic_power, exceptional_upgrade) |
| `└ item_add_option` | object | 추가 옵션 (str, dex, int, luk, max_hp, max_mp, attack_power, magic_power, armor, speed, jump, boss_damage, damage, all_stat, equipment_level_decrease) |
| `└ item_etc_option` | object | 기타 옵션 (str, dex, int, luk, max_hp, max_mp, attack_power, magic_power, armor, speed, jump) |
| `└ item_starforce_option` | object | 스타포스 옵션 (동일 구조) |
| `└ potential_option_flag` | string \| null | 잠재 능력 설정 여부 |
| `└ potential_option_grade` | string \| null | 잠재 능력 등급 |
| `└ potential_option_1` | string \| null | 잠재 능력 1 |
| `└ potential_option_2` | string \| null | 잠재 능력 2 |
| `└ potential_option_3` | string \| null | 잠재 능력 3 |
| `└ additional_potential_option_flag` | string \| null | 에디셔널 잠재 능력 설정 여부 |
| `└ additional_potential_option_grade` | string \| null | 에디셔널 잠재 능력 등급 |
| `└ additional_potential_option_1` | string \| null | 에디셔널 잠재 능력 1 |
| `└ additional_potential_option_2` | string \| null | 에디셔널 잠재 능력 2 |
| `└ additional_potential_option_3` | string \| null | 에디셔널 잠재 능력 3 |
| `└ equipment_level_increase` | int | 장비 레벨 증가치 |
| `└ growth_exp` | int | 성장 경험치 |
| `└ growth_level` | int | 성장 레벨 |
| `└ scroll_upgrade` | string | 스크롤 업그레이드 횟수 |
| `└ cuttable_count` | string | 가위 사용 가능 횟수 |
| `└ golden_hammer_flag` | string | 황금 망치 강화 여부 |
| `└ scroll_resilience_count` | string | 복구 가능 횟수 |
| `└ scroll_upgrade_able_count` | string | 업그레이드 가능 횟수 |
| `└ soul_name` | string \| null | 소울 명 |
| `└ soul_option` | string \| null | 소울 옵션 |
| `└ starforce` | string | 스타포스 강화 단계 |
| `└ starforce_scroll_flag` | string | 놀라운 장비 강화 스크롤 사용 여부 |
| `└ special_ring_level` | int | 특수 반지 레벨 |
| `└ date_expire` | datetime \| null | 아이템 만료 일시 |
| `└ freestyle_flag` | string \| null | 자유 장착 여부 |
| `title` | BattlePracticeCharacterItemTitle \| null | 칭호 정보 |
| `└ title_name` | string | 칭호 명 |
| `└ title_icon` | string | 칭호 아이콘 URL |
| `└ title_description` | string | 칭호 설명 |
| `└ date_expire` | datetime \| null | 칭호 만료 일시 |
| `└ date_option_expire` | datetime \| null | 칭호 옵션 만료 일시 |
| `└ title_shape_name` | string \| null | 외형 칭호 명 |
| `└ title_shape_icon` | string \| null | 외형 칭호 아이콘 |
| `└ title_shape_description` | string \| null | 외형 칭호 설명 |
| `dragon_equipment` | list[BattlePracticeCharacterItemDragonEquipment] | 에반 드래곤 장비 목록 (구조는 일반 장비와 동일) |
| `mechanic_equipment` | list[BattlePracticeCharacterItemMechanicEquipment] | 메카닉 장비 목록 (구조는 일반 장비와 동일) |

**`item_object` — 세트 효과** (`set_effect_object` 내부)

| 필드 | 타입 | 설명 |
|------|------|------|
| `set_effect` | list[BattlePracticeCharacterSetEffect] | 세트 효과 목록 |
| `└ set_name` | string | 세트 명 |
| `└ total_set_count` | int | 세트 아이템 장착 수 |
| `└ set_effect_info` | list[BattlePracticeCharacterSetEffectInfo] | 세트 효과 상세 |
| `  └ set_count` | int | 세트 효과 발동 조건 수 |
| `  └ set_option` | string | 세트 효과 옵션 |

**`cash_item_object` 내부 필드**

| 필드 | 타입 | 설명 |
|------|------|------|
| `cash_item_equipment_base` | list[BattlePracticeCharacterCashItemEquipment] | 기본 캐시 장비 목록 |
| `additional_cash_item_equipment_base` | list[BattlePracticeCharacterCashItemEquipment] | 추가 캐시 장비 목록 |
| `└ cash_item_equipment_part` | string | 캐시 장비 부위 |
| `└ cash_item_equipment_slot` | string | 캐시 장비 슬롯 |
| `└ cash_item_name` | string | 캐시 아이템 명 |
| `└ cash_item_icon` | string | 캐시 아이템 아이콘 URL |
| `└ cash_item_description` | string \| null | 캐시 아이템 설명 |
| `└ cash_item_option` | list[BattlePracticeCharacterCashItemOption] | 캐시 아이템 옵션 목록 |
| `  └ option_type` | string | 옵션 타입 |
| `  └ option_value` | string | 옵션 값 |
| `└ date_expire` | datetime \| null | 만료 일시 |
| `└ date_option_expire` | datetime \| null | 옵션 만료 일시 |

**`pet_object` 내부 필드**

각 펫(1~3)에 대해 동일 구조:

| 필드 | 타입 | 설명 |
|------|------|------|
| `pet_N_name` | string \| null | 펫 명 |
| `pet_N_nickname` | string \| null | 펫 닉네임 |
| `pet_N_icon` | string \| null | 펫 아이콘 URL |
| `pet_N_description` | string \| null | 펫 설명 |
| `pet_N_equipment` | BattlePracticeCharacterPetEquipment \| null | 펫 장비 |
| `└ item_name` | string | 펫 장비 명 |
| `└ item_icon` | string | 펫 장비 아이콘 URL |
| `└ item_description` | string \| null | 펫 장비 설명 |
| `└ item_option` | list[BattlePracticeCharacterPetEquipmentItemOption] | 펫 장비 옵션 목록 |
| `  └ option_type` | string | 옵션 타입 |
| `  └ option_value` | string | 옵션 값 |
| `└ scroll_upgrade` | int | 업그레이드 횟수 |
| `└ scroll_upgradable` | int | 업그레이드 가능 횟수 |
| `└ item_shape` | string \| null | 외형 아이템 명 |
| `└ item_shape_icon` | string \| null | 외형 아이템 아이콘 |
| `└ item_date_expire` | datetime \| null | 펫 장비 만료 일시 |
| `pet_N_auto_skill` | BattlePracticeCharacterPetAutoSkill \| null | 펫 자동 스킬 |
| `└ skill_1` | string \| null | 자동 스킬 1 명 |
| `└ skill_1_icon` | string \| null | 자동 스킬 1 아이콘 |
| `└ skill_2` | string \| null | 자동 스킬 2 명 |
| `└ skill_2_icon` | string \| null | 자동 스킬 2 아이콘 |
| `pet_N_pet_type` | string \| null | 펫 타입 |
| `pet_N_skill` | list[string] | 펫 스킬 목록 |
| `pet_N_date_expire` | datetime \| null | 펫 만료 일시 |

**`skill_object` 내부 필드**

| 필드 | 타입 | 설명 |
|------|------|------|
| `character_skill` | list[BattlePracticeCharacterSkillInfo] | 캐릭터 스킬 목록 |
| `└ skill_name` | string | 스킬 명 |
| `└ skill_description` | string | 스킬 설명 |
| `└ skill_level` | int | 스킬 레벨 |
| `└ skill_effect` | string \| null | 스킬 효과 |
| `└ skill_icon` | string | 스킬 아이콘 URL |

**`link_skill_object` 내부 필드**

| 필드 | 타입 | 설명 |
|------|------|------|
| `character_link_skill` | list[BattlePracticeCharacterSkillInfo] | 링크 스킬 목록 (필드 구조는 `character_skill`과 동일) |
| `character_owned_link_skill` | BattlePracticeCharacterSkillInfo \| null | 자신이 보유한 링크 스킬 |

**`v_matrix_object` 내부 필드**

| 필드 | 타입 | 설명 |
|------|------|------|
| `character_v_core_equipment` | list[BattlePracticeCharacterVCore] | V코어 장착 목록 |
| `└ slot_id` | string | 슬롯 ID |
| `└ slot_level` | int | 슬롯 레벨 |
| `└ v_core_name` | string | V코어 명 |
| `└ v_core_type` | string | V코어 타입 |
| `└ v_core_level` | int | V코어 레벨 |
| `└ v_core_skill_1` | string \| null | 관련 스킬 1 |
| `└ v_core_skill_2` | string \| null | 관련 스킬 2 |
| `└ v_core_skill_3` | string \| null | 관련 스킬 3 |

**`hexa_matrix_object` — HEXA 코어** (`hexa_core_object` 내부)

| 필드 | 타입 | 설명 |
|------|------|------|
| `character_hexa_core_equipment` | list[BattlePracticeCharacterHexaCoreEquipment] | HEXA 코어 장착 목록 |
| `└ hexa_core_name` | string | HEXA 코어 명 |
| `└ hexa_core_level` | int | HEXA 코어 레벨 |
| `└ hexa_core_type` | string | HEXA 코어 타입 |
| `└ linked_skill` | list[BattlePracticeCharacterHexaLinkedSkill] | 연결 스킬 목록 |
| `  └ hexa_skill_id` | string | 헥사 스킬 ID |

**`hexa_matrix_object` — HEXA 스탯** (`hexa_matrix_stat_object` 내부)

| 필드 | 타입 | 설명 |
|------|------|------|
| `character_hexa_stat_core` | list[BattlePracticeCharacterHexaStatCore] | HEXA 스탯 코어 목록 (프리셋 1) |
| `character_hexa_stat_core_2` | list[BattlePracticeCharacterHexaStatCore] | HEXA 스탯 코어 목록 (프리셋 2) |
| `character_hexa_stat_core_3` | list[BattlePracticeCharacterHexaStatCore] | HEXA 스탯 코어 목록 (프리셋 3) |
| `└ slot_id` | string | 슬롯 ID |
| `└ main_stat_name` | string | 메인 스탯 명 |
| `└ sub_stat_name_1` | string | 서브 스탯 명 1 |
| `└ sub_stat_name_2` | string | 서브 스탯 명 2 |
| `└ main_stat_level` | int | 메인 스탯 레벨 |
| `└ sub_stat_level_1` | int | 서브 스탯 레벨 1 |
| `└ sub_stat_level_2` | int | 서브 스탯 레벨 2 |
| `└ stat_grade` | int | 스탯 등급 |

**`ring_reserve_skill_object` 내부 필드**

| 필드 | 타입 | 설명 |
|------|------|------|
| `special_ring_reserve_name` | string \| null | 링 리저브 스킬 명 |
| `special_ring_reserve_level` | int \| null | 링 리저브 스킬 레벨 |
| `special_ring_reserve_icon` | string \| null | 링 리저브 스킬 아이콘 URL |
| `special_ring_reserve_description` | string \| null | 링 리저브 스킬 설명 |

**`union_raider_object` 내부 필드**

| 필드 | 타입 | 설명 |
|------|------|------|
| `union_raider_stat` | list[string] | 유니온 공격대원 효과 목록 |
| `union_occupied_stat` | list[string] | 유니온 점령 효과 목록 |

**`union_artifact_object` 내부 필드**

| 필드 | 타입 | 설명 |
|------|------|------|
| `union_artifact_effect` | list[BattlePracticeUnionArtifactEffect] | 아티팩트 효과 목록 |
| `└ name` | string | 아티팩트 효과 명 |
| `└ level` | int | 아티팩트 효과 레벨 |

**`union_champion_object` 내부 필드**

| 필드 | 타입 | 설명 |
|------|------|------|
| `champion_badge_total_info` | list[BattlePracticeUnionChampionBadge] | 챔피언 휘장 합산 효과 목록 |
| `└ stat` | string | 휘장 효과 설명 |

**`guild_object` 내부 필드**

| 필드 | 타입 | 설명 |
|------|------|------|
| `guild_skill` | list[BattlePracticeGuildSkill] | 길드 스킬 목록 |
| `guild_noblesse_skill` | list[BattlePracticeGuildSkill] | 노블레스 스킬 목록 |
| `└ skill_name` | string | 스킬 명 |
| `└ skill_description` | string | 스킬 설명 |
| `└ skill_level` | int | 스킬 레벨 |
| `└ skill_effect` | string | 스킬 레벨 별 효과 |
| `└ skill_icon` | string | 스킬 아이콘 URL |

**예시 응답**

```json
{
  "basic_object": {
    "character_name": "내캐릭터",
    "character_level": 285,
    "character_class": "아크메이지(불,독)",
    "character_class_level": "6",
    "character_image": "https://open.api.nexon.com/..."
  },
  "stat_object": { "...": "..." },
  "hyper_stat_object": null,
  "propensity_object": null,
  "ability_object": null,
  "item_object": null,
  "cash_item_object": null,
  "pet_object": null,
  "skill_object": null,
  "link_skill_object": null,
  "v_matrix_object": null,
  "hexa_matrix_object": null,
  "ring_reserve_skill_object": null,
  "union_raider_object": {
    "union_raider_stat": ["STR 40 증가"],
    "union_occupied_stat": ["마력 25 증가"]
  },
  "union_artifact_object": {
    "union_artifact_effect": [
      { "name": "올스탯 증가", "level": 10 }
    ]
  },
  "union_champion_object": {
    "champion_badge_total_info": [
      { "stat": "보스 몬스터 공격 시 데미지 +5%" }
    ]
  },
  "guild_object": {
    "guild_skill": [],
    "guild_noblesse_skill": []
  }
}
```

**봇 활용:** 전투 분석 결과와 함께 캐릭터 상태를 검증하거나 상세 리포트를 생성할 때 사용. 응답 크기가 매우 크므로 필요한 서브오브젝트(`basic_object`, `stat_object` 등)만 파싱하는 것을 권장.
