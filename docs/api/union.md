# 유니온 API (공식 문서 id=15)

> 공통 규약(Base URL `https://open.api.nexon.com`, 인증 헤더 `x-nxopen-api-key`, 날짜 KST/D-1, 에러코드)은 [README.md](./README.md) 참고.
> 응답 필드는 SpiralMoon/maplestory.openapi KMS DTO로 교차검증. 최종은 실호출로 확정.

## 엔드포인트 요약

| 메서드 | 경로 | 한글명 | 주요 응답 |
|--------|------|--------|-----------|
| GET | `maplestory/v1/user/union` | 유니온 정보 | 유니온 레벨·등급·아티팩트 요약 |
| GET | `maplestory/v1/user/union-raider` | 유니온 공격대 | 공격대 배치·점령 효과·프리셋 |
| GET | `maplestory/v1/user/union-artifact` | 유니온 아티팩트 | 아티팩트 효과·크리스탈 목록 |
| GET | `maplestory/v1/user/union-champion` | 유니온 챔피언 | 챔피언 등급·휘장 효과 분포 |

---

## GET `maplestory/v1/user/union` — 유니온 정보

캐릭터의 유니온 레벨, 등급, 아티팩트 보유 현황을 조회한다.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|------|------|------|------|
| `ocid` | 필수 | string | 캐릭터 식별자 |
| `date` | 선택 | string | 조회 기준일 (KST, `YYYY-MM-DD`, 미입력 시 전일) |

**응답 필드**

| 필드 | 타입 | 설명 |
|------|------|------|
| `date` | datetime \| null | 조회 기준일 (KST, 시·분은 00으로 표기) |
| `union_level` | int \| null | 유니온 레벨 |
| `union_grade` | string \| null | 유니온 등급 |
| `union_artifact_level` | int \| null | 아티팩트 레벨 |
| `union_artifact_exp` | int \| null | 보유 아티팩트 경험치 |
| `union_artifact_point` | int \| null | 보유 아티팩트 포인트 |

**예시 응답**

```json
{
  "date": "2025-01-01T00:00:00+09:00",
  "union_level": 8750,
  "union_grade": "그랜드 마스터 유니온 1",
  "union_artifact_level": 45,
  "union_artifact_exp": 12500,
  "union_artifact_point": 310
}
```

**봇 활용:** `/유니온` 명령에서 `union_level`과 `union_grade`를 표시하는 핵심 엔드포인트. `union_artifact_level`도 아티팩트 요약에 사용.

---

## GET `maplestory/v1/user/union-raider` — 유니온 공격대

캐릭터의 유니온 공격대 배치 정보, 점령 효과, 내부 스탯, 프리셋 구성을 조회한다.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|------|------|------|------|
| `ocid` | 필수 | string | 캐릭터 식별자 |
| `date` | 선택 | string | 조회 기준일 (KST, `YYYY-MM-DD`, 미입력 시 전일) |

**응답 필드**

| 필드 | 타입 | 설명 |
|------|------|------|
| `date` | datetime \| null | 조회 기준일 (KST) |
| `union_raider_stat` | list[string] | 유니온 공격대원 효과 목록 |
| `union_occupied_stat` | list[string] | 유니온 공격대 점령 효과 목록 |
| `union_inner_stat` | list[UnionRaiderInnerStat] | 유니온 내부 배치 스탯 |
| `└ stat_field_id` | string | 배치 위치 ID (0~7, 11시 방향 기준 시계 방향) |
| `└ stat_field_effect` | string | 해당 위치 효과 |
| `union_block` | list[UnionRaiderBlock] | 유니온 블록 목록 |
| `└ block_type` | string | 블록 기여 효과 타입 |
| `└ block_class` | string \| null | 블록 직업 명 |
| `└ block_level` | string | 블록 캐릭터 레벨 |
| `└ block_control_point` | UnionRaiderBlockControlPoint | 블록 기준점 좌표 |
| `  └ x` | int | X 좌표 (중앙 4칸 우하단 기준 0) |
| `  └ y` | int | Y 좌표 |
| `└ block_position` | list[UnionRaiderBlockPosition] | 블록이 차지하는 칸 좌표 목록 |
| `  └ x` | int | X 좌표 |
| `  └ y` | int | Y 좌표 |
| `use_preset_no` | int | 현재 활성화된 프리셋 번호 |
| `union_raider_preset_1` | UnionRaiderPreset \| null | 프리셋 1 구성 |
| `union_raider_preset_2` | UnionRaiderPreset \| null | 프리셋 2 구성 |
| `union_raider_preset_3` | UnionRaiderPreset \| null | 프리셋 3 구성 |
| `union_raider_preset_4` | UnionRaiderPreset \| null | 프리셋 4 구성 |
| `union_raider_preset_5` | UnionRaiderPreset \| null | 프리셋 5 구성 |

`UnionRaiderPreset` 내부 필드:

| 필드 | 타입 | 설명 |
|------|------|------|
| `union_raider_stat` | list[string] | 프리셋 공격대원 효과 목록 |
| `union_occupied_stat` | list[string] | 프리셋 점령 효과 목록 |
| `union_inner_stat` | list[UnionRaiderInnerStat] | 프리셋 내부 배치 스탯 |
| `union_block` | list[UnionRaiderBlock] | 프리셋 블록 목록 |

**예시 응답**

```json
{
  "date": "2025-01-01T00:00:00+09:00",
  "union_raider_stat": ["STR 40 증가", "DEX 40 증가"],
  "union_occupied_stat": ["마력 25 증가", "공격력 25 증가"],
  "union_inner_stat": [
    { "stat_field_id": "0", "stat_field_effect": "마력 25 증가" }
  ],
  "union_block": [
    {
      "block_type": "마력",
      "block_class": "불/독 아크메이지",
      "block_level": "250",
      "block_control_point": { "x": 0, "y": 0 },
      "block_position": [{ "x": 0, "y": 0 }, { "x": 1, "y": 0 }]
    }
  ],
  "use_preset_no": 1,
  "union_raider_preset_1": null,
  "union_raider_preset_2": null,
  "union_raider_preset_3": null,
  "union_raider_preset_4": null,
  "union_raider_preset_5": null
}
```

---

## GET `maplestory/v1/user/union-artifact` — 유니온 아티팩트

캐릭터의 유니온 아티팩트 효과 목록, 크리스탈 정보, 잔여 AP를 조회한다.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|------|------|------|------|
| `ocid` | 필수 | string | 캐릭터 식별자 |
| `date` | 선택 | string | 조회 기준일 (KST, `YYYY-MM-DD`, 미입력 시 전일) |

**응답 필드**

| 필드 | 타입 | 설명 |
|------|------|------|
| `date` | datetime \| null | 조회 기준일 (KST) |
| `union_artifact_effect` | list[UnionArtifactEffect] | 아티팩트 효과 목록 |
| `└ name` | string | 아티팩트 효과 명 |
| `└ level` | int | 아티팩트 효과 레벨 |
| `union_artifact_crystal` | list[UnionArtifactCrystal] | 아티팩트 크리스탈 목록 |
| `└ name` | string | 아티팩트 크리스탈 명 |
| `└ validity_flag` | string | 유효 여부 (`"0"`: 유효, `"1"`: 무효) |
| `└ date_expire` | datetime \| null | 크리스탈 만료 일시 (KST, 만료 시 null) |
| `└ is_expired` | bool | 만료 여부 |
| `└ level` | int | 크리스탈 레벨 |
| `└ crystal_option_name_1` | string | 크리스탈 옵션 명 1 |
| `└ crystal_option_name_2` | string | 크리스탈 옵션 명 2 |
| `└ crystal_option_name_3` | string | 크리스탈 옵션 명 3 |
| `union_artifact_remain_ap` | int | 잔여 아티팩트 AP |

**예시 응답**

```json
{
  "date": "2025-01-01T00:00:00+09:00",
  "union_artifact_effect": [
    { "name": "올스탯 증가", "level": 10 }
  ],
  "union_artifact_crystal": [
    {
      "name": "크리스탈 of 공격",
      "validity_flag": "0",
      "date_expire": "2025-03-01T00:00:00+09:00",
      "is_expired": false,
      "level": 5,
      "crystal_option_name_1": "공격력 증가",
      "crystal_option_name_2": "마력 증가",
      "crystal_option_name_3": "올스탯 증가"
    }
  ],
  "union_artifact_remain_ap": 50
}
```

**봇 활용:** `/유니온` 명령의 아티팩트 섹션에서 `union_artifact_effect` 목록과 `union_artifact_remain_ap`를 표시.

---

## GET `maplestory/v1/user/union-champion` — 유니온 챔피언

캐릭터의 유니온 챔피언 등급·직업 분포와 휘장 효과 합산을 조회한다. 봇 `/유니온` 명령의 핵심 서브섹션.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|------|------|------|------|
| `ocid` | 필수 | string | 캐릭터 식별자 |
| `date` | 선택 | string | 조회 기준일 (KST, `YYYY-MM-DD`, 미입력 시 전일) |

**응답 필드**

| 필드 | 타입 | 설명 |
|------|------|------|
| `date` | datetime \| null | 조회 기준일 (KST) |
| `union_champion` | list[UnionChampionInfo] | 유니온 챔피언 상세 목록 |
| `└ champion_name` | string | 챔피언 캐릭터 명 |
| `└ champion_slot` | int | 챔피언 슬롯 번호 |
| `└ champion_grade` | string | 챔피언 등급. ⚠️ **실호출 관측값: `"SSS"`, `"S"`**(2개 챔피언 계정에서). 등급 체계는 `SSS/SS/S/A/B…` (`"SS"` 등은 이 계정 미관측). 아래 예시의 `"레전드리"`는 오류(잠재 등급과 혼동). 분포 카운트 동작 확인 |
| `└ champion_class` | string | 챔피언 직업 명 |
| `└ champion_badge_info` | list[UnionChampionBadgeInfo] | 챔피언 휘장 효과 목록 |
| `  └ stat` | string | 휘장 효과 설명 |
| `champion_badge_total_info` | list[UnionChampionBadgeInfo] | 전체 챔피언 휘장 합산 효과 목록 |
| `└ stat` | string | 휘장 효과 설명 |

**예시 응답**

```json
{
  "date": "2025-01-01T00:00:00+09:00",
  "union_champion": [
    {
      "champion_name": "내캐릭터",
      "champion_slot": 1,
      "champion_grade": "SSS",
      "champion_class": "아크메이지(불,독)",
      "champion_badge_info": [
        { "stat": "보스 몬스터 공격 시 데미지 +1%" }
      ]
    }
  ],
  "champion_badge_total_info": [
    { "stat": "보스 몬스터 공격 시 데미지 +5%" },
    { "stat": "일반 몬스터 공격 시 데미지 +3%" }
  ]
}
```

**봇 활용:** `/유니온` 명령에서 챔피언 등급 분포(**SSS/SS/S…** 카운트, 실측 관측값 SSS·S)와 `champion_badge_total_info`로 휘장 효과 합산을 표시. 유니온 시스템의 핵심 지표 중 하나.
