# 랭킹 API (공식 문서 id=18)

> 공통 규약(Base URL `https://open.api.nexon.com`, 인증 헤더 `x-nxopen-api-key`, 날짜 KST, 에러코드)은 [README.md](./README.md) 참고.
> 응답 필드는 SpiralMoon/maplestory.openapi KMS DTO로 교차검증. 최종은 실호출로 확정.

## 엔드포인트 요약

| 메서드 | 경로 | 한글명 |
|--------|------|--------|
| GET | `maplestory/v1/ranking/overall` | 종합 랭킹 조회 |
| GET | `maplestory/v1/ranking/union` | 유니온 랭킹 조회 |
| GET | `maplestory/v1/ranking/guild` | 길드 랭킹 조회 |
| GET | `maplestory/v1/ranking/dojang` | 무릉도장 랭킹 조회 |
| GET | `maplestory/v1/ranking/theseed` | 더 시드 랭킹 조회 |
| GET | `maplestory/v1/ranking/achievement` | 업적 랭킹 조회 |

---

## GET `maplestory/v1/ranking/overall` — 종합 랭킹 조회

캐릭터 경험치 기준 종합 랭킹을 조회합니다. 월드, 월드 유형, 직업으로 필터링할 수 있으며 특정 캐릭터(ocid)를 기준으로 해당 캐릭터 주변 순위를 조회할 수 있습니다.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|------|------|------|------|
| date | 아니오 | string | 조회 기준일 (KST, `YYYY-MM-DD`). 미입력 시 전날 데이터 반환 |
| world_name | 아니오 | string | 월드 명 (예: `스카니아`, `베라`). 미입력 시 전체 월드 |
| world_type | 아니오 | integer | 월드 유형. `0` = 일반, `1` = 에오스·헬리오스. 미입력 시 일반 월드 |
| class | 아니오 | string | 직업 명 (예: `히어로`, `아크메이지(불,독)`). 미입력 시 전체 직업 |
| ocid | 아니오 | string | 캐릭터 식별자. 입력 시 해당 캐릭터 기준 순위 반환 |
| page | 아니오 | integer | 페이지 번호 (기본값 `1`, 페이지당 200명) |

**응답 필드**

| 필드 | 타입 | 설명 |
|------|------|------|
| ranking | array | 종합 랭킹 항목 목록 |
| └ date | string | 랭킹 업데이트 일자 (KST, 시·분은 `00:00`) |
| └ ranking | integer | 종합 랭킹 순위 |
| └ character_name | string | 캐릭터 명 |
| └ world_name | string | 월드 명 |
| └ class_name | string | 직업 명 |
| └ sub_class_name | string | 전직 직업 명 |
| └ character_level | integer | 캐릭터 레벨 |
| └ character_exp | integer | 캐릭터 경험치 |
| └ character_popularity | integer | 캐릭터 인기도 |
| └ character_guildname | string \| null | 소속 길드 명 (없으면 `null`) |

**예시 응답**

```json
{
  "ranking": [
    {
      "date": "2024-01-15T00:00:00.000Z",
      "ranking": 1,
      "character_name": "메이플전사",
      "world_name": "스카니아",
      "class_name": "아크메이지(불,독)",
      "sub_class_name": "메이지",
      "character_level": 300,
      "character_exp": 12345678901234,
      "character_popularity": 9999,
      "character_guildname": "최강길드"
    }
  ]
}
```

---

## GET `maplestory/v1/ranking/union` — 유니온 랭킹 조회

유니온 레벨 기준 랭킹을 조회합니다.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|------|------|------|------|
| date | 아니오 | string | 조회 기준일 (KST, `YYYY-MM-DD`). 미입력 시 전날 데이터 반환 |
| world_name | 아니오 | string | 월드 명. 미입력 시 전체 월드 |
| ocid | 아니오 | string | 캐릭터 식별자. 입력 시 해당 캐릭터 기준 순위 반환 |
| page | 아니오 | integer | 페이지 번호 (기본값 `1`, 페이지당 200명) |

**응답 필드**

| 필드 | 타입 | 설명 |
|------|------|------|
| ranking | array | 유니온 랭킹 항목 목록 |
| └ date | string | 랭킹 업데이트 일자 (KST, 시·분은 `00:00`) |
| └ ranking | integer | 유니온 랭킹 순위 |
| └ character_name | string | 캐릭터 명 |
| └ world_name | string | 월드 명 |
| └ class_name | string | 직업 명 |
| └ sub_class_name | string | 전직 직업 명 |
| └ union_level | integer | 유니온 레벨 |
| └ union_power | integer | 유니온 파워 |

**예시 응답**

```json
{
  "ranking": [
    {
      "date": "2024-01-15T00:00:00.000Z",
      "ranking": 1,
      "character_name": "유니온왕",
      "world_name": "스카니아",
      "class_name": "패스파인더",
      "sub_class_name": "아처",
      "union_level": 9000,
      "union_power": 999999
    }
  ]
}
```

---

## GET `maplestory/v1/ranking/guild` — 길드 랭킹 조회

길드 랭킹 유형(주간 명성치 / 플래그 레이스 / 지하 수로)별 랭킹을 조회합니다.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|------|------|------|------|
| date | 아니오 | string | 조회 기준일 (KST, `YYYY-MM-DD`). 미입력 시 전날 데이터 반환 |
| ranking_type | 필수 | integer | 랭킹 유형. `0` = 주간 명성치, `1` = 플래그 레이스, `2` = 지하 수로 |
| world_name | 아니오 | string | 월드 명. 미입력 시 전체 월드 |
| guild_name | 아니오 | string | 길드 명. 특정 길드 검색 시 사용 |
| page | 아니오 | integer | 페이지 번호 (기본값 `1`, 페이지당 200개) |

**응답 필드**

| 필드 | 타입 | 설명 |
|------|------|------|
| ranking | array | 길드 랭킹 항목 목록 |
| └ date | string | 랭킹 업데이트 일자 (KST, 시·분은 `00:00`) |
| └ ranking | integer | 길드 랭킹 순위 |
| └ guild_name | string | 길드 명 |
| └ world_name | string | 월드 명 |
| └ guild_level | integer | 길드 레벨 |
| └ guild_master_name | string | 길드 마스터 캐릭터 명 |
| └ guild_mark | string | 길드 마크 |
| └ guild_point | integer | 길드 포인트 (해당 랭킹 유형의 점수) |

**예시 응답**

```json
{
  "ranking": [
    {
      "date": "2024-01-15T00:00:00.000Z",
      "ranking": 1,
      "guild_name": "최강길드",
      "world_name": "스카니아",
      "guild_level": 30,
      "guild_master_name": "길드마스터",
      "guild_mark": "...",
      "guild_point": 9999999
    }
  ]
}
```

---

## GET `maplestory/v1/ranking/dojang` — 무릉도장 랭킹 조회

무릉도장 최고 도달 층수 기준 랭킹을 조회합니다. 난이도(일반/통달)별로 조회할 수 있습니다.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|------|------|------|------|
| date | 아니오 | string | 조회 기준일 (KST, `YYYY-MM-DD`). 미입력 시 전날 데이터 반환 |
| difficulty | 필수 | integer | 난이도. `0` = 일반, `1` = 통달 (기본값 `1`) |
| world_name | 아니오 | string | 월드 명. 미입력 시 전체 월드 |
| class | 아니오 | string | 직업 명. 미입력 시 전체 직업 |
| ocid | 아니오 | string | 캐릭터 식별자. 입력 시 해당 캐릭터 기준 순위 반환 |
| page | 아니오 | integer | 페이지 번호 (기본값 `1`, 페이지당 200명) |

**응답 필드**

| 필드 | 타입 | 설명 |
|------|------|------|
| ranking | array | 무릉도장 랭킹 항목 목록 |
| └ date | string | 랭킹 업데이트 일자 (KST, 시·분은 `00:00`) |
| └ ranking | integer | 무릉도장 랭킹 순위 |
| └ character_name | string | 캐릭터 명 |
| └ world_name | string | 월드 명 |
| └ class_name | string | 직업 명 |
| └ sub_class_name | string | 전직 직업 명 |
| └ character_level | integer | 캐릭터 레벨 |
| └ dojang_floor | integer | 무릉도장 최고 도달 층수 |
| └ dojang_time_record | integer | 무릉도장 클리어 시간 기록 (초 단위) |

**예시 응답**

```json
{
  "ranking": [
    {
      "date": "2024-01-15T00:00:00.000Z",
      "ranking": 1,
      "character_name": "무릉고수",
      "world_name": "스카니아",
      "class_name": "히어로",
      "sub_class_name": "전사",
      "character_level": 280,
      "dojang_floor": 350,
      "dojang_time_record": 600
    }
  ]
}
```

---

## GET `maplestory/v1/ranking/theseed` — 더 시드 랭킹 조회

더 시드 최고 도달 층수 기준 랭킹을 조회합니다.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|------|------|------|------|
| date | 아니오 | string | 조회 기준일 (KST, `YYYY-MM-DD`). 미입력 시 전날 데이터 반환 |
| world_name | 아니오 | string | 월드 명. 미입력 시 전체 월드 |
| ocid | 아니오 | string | 캐릭터 식별자. 입력 시 해당 캐릭터 기준 순위 반환 |
| page | 아니오 | integer | 페이지 번호 (기본값 `1`, 페이지당 200명) |

**응답 필드**

| 필드 | 타입 | 설명 |
|------|------|------|
| ranking | array | 더 시드 랭킹 항목 목록 |
| └ date | string | 랭킹 업데이트 일자 (KST, 시·분은 `00:00`) |
| └ ranking | integer | 더 시드 랭킹 순위 |
| └ character_name | string | 캐릭터 명 |
| └ world_name | string | 월드 명 |
| └ class_name | string | 직업 명 |
| └ sub_class_name | string | 전직 직업 명 |
| └ character_level | integer | 캐릭터 레벨 |
| └ theseed_floor | integer | 더 시드 최고 도달 층수 |
| └ theseed_time_record | integer | 더 시드 클리어 시간 기록 (초 단위) |

**예시 응답**

```json
{
  "ranking": [
    {
      "date": "2024-01-15T00:00:00.000Z",
      "ranking": 1,
      "character_name": "시드마스터",
      "world_name": "스카니아",
      "class_name": "나이트로드",
      "sub_class_name": "도적",
      "character_level": 285,
      "theseed_floor": 200,
      "theseed_time_record": 1800
    }
  ]
}
```

---

## GET `maplestory/v1/ranking/achievement` — 업적 랭킹 조회

업적 점수 기준 랭킹을 조회합니다.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|------|------|------|------|
| date | 아니오 | string | 조회 기준일 (KST, `YYYY-MM-DD`). 미입력 시 전날 데이터 반환 |
| ocid | 아니오 | string | 캐릭터 식별자. 입력 시 해당 캐릭터 기준 순위 반환 |
| page | 아니오 | integer | 페이지 번호 (기본값 `1`, 페이지당 200명) |

**응답 필드**

| 필드 | 타입 | 설명 |
|------|------|------|
| ranking | array | 업적 랭킹 항목 목록 |
| └ date | string | 랭킹 업데이트 일자 (KST, 시·분은 `00:00`) |
| └ ranking | integer | 업적 랭킹 순위 |
| └ character_name | string | 캐릭터 명 |
| └ world_name | string | 월드 명 |
| └ class_name | string | 직업 명 |
| └ sub_class_name | string | 전직 직업 명 |
| └ trophy_grade | string | 업적 등급 |
| └ trophy_score | integer | 업적 점수 |

**예시 응답**

```json
{
  "ranking": [
    {
      "date": "2024-01-15T00:00:00.000Z",
      "ranking": 1,
      "character_name": "업적달인",
      "world_name": "스카니아",
      "class_name": "팔라딘",
      "sub_class_name": "전사",
      "trophy_grade": "마스터",
      "trophy_score": 99999
    }
  ]
}
```
