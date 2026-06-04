# 길드 API (공식 문서 id=16)

> 공통 규약(Base URL `https://open.api.nexon.com`, 인증 헤더 `x-nxopen-api-key`, 날짜 KST/D-1, 에러코드)은 [README.md](./README.md) 참고.
> 응답 필드는 SpiralMoon/maplestory.openapi KMS DTO로 교차검증. 최종은 실호출로 확정.

## 엔드포인트 요약

| 메서드 | 경로 | 한글명 | 주요 응답 |
|--------|------|--------|-----------|
| GET | `maplestory/v1/guild/id` | 길드 식별자 조회 | `oguild_id` |
| GET | `maplestory/v1/guild/basic` | 길드 기본 정보 | 레벨·명성·길드원 목록·스킬 |

---

## GET `maplestory/v1/guild/id` — 길드 식별자 조회

길드명과 월드명으로 고유 길드 식별자(`oguild_id`)를 조회한다. 이후 `guild/basic` 호출에 사용.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|------|------|------|------|
| `guild_name` | 필수 | string | 길드 명 |
| `world_name` | 필수 | string | 월드 명 (예: `스카니아`, `베라`) |

**응답 필드**

| 필드 | 타입 | 설명 |
|------|------|------|
| `oguild_id` | string | 길드 고유 식별자 |

**예시 응답**

```json
{
  "oguild_id": "a1b2c3d4e5f6"
}
```

---

## GET `maplestory/v1/guild/basic` — 길드 기본 정보

`oguild_id`로 길드의 레벨, 명성치, 포인트, 마스터, 길드원 목록, 스킬 목록을 조회한다.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|------|------|------|------|
| `oguild_id` | 필수 | string | 길드 고유 식별자 (`guild/id`로 취득) |
| `date` | 선택 | string | 조회 기준일 (KST, `YYYY-MM-DD`, 미입력 시 전일) |

**응답 필드**

| 필드 | 타입 | 설명 |
|------|------|------|
| `date` | datetime \| null | 조회 기준일 (KST, 시·분은 00으로 표기) |
| `world_name` | string | 월드 명 |
| `guild_name` | string | 길드 명 |
| `guild_level` | int | 길드 레벨 |
| `guild_fame` | int | 길드 명성치 |
| `guild_point` | int | 길드 포인트(GP) |
| `guild_master_name` | string | 길드 마스터 캐릭터 명 |
| `guild_member_count` | int | 길드원 수 |
| `guild_member` | list[string] | 길드원 캐릭터 명 목록 |
| `guild_skill` | list[GuildSkill] | 길드 스킬 목록 |
| `└ skill_name` | string | 스킬 명 |
| `└ skill_description` | string | 스킬 설명 |
| `└ skill_level` | int | 스킬 레벨 |
| `└ skill_effect` | string | 스킬 레벨 별 효과 |
| `└ skill_icon` | string | 스킬 아이콘 URL |
| `guild_noblesse_skill` | list[GuildSkill] | 노블레스 스킬 목록 (필드 구조는 `guild_skill`과 동일) |

**예시 응답**

```json
{
  "date": "2025-01-01T00:00:00+09:00",
  "world_name": "스카니아",
  "guild_name": "메이플길드",
  "guild_level": 30,
  "guild_fame": 125000,
  "guild_point": 9500,
  "guild_master_name": "마스터캐릭",
  "guild_member_count": 180,
  "guild_member": ["캐릭A", "캐릭B", "캐릭C"],
  "guild_skill": [
    {
      "skill_name": "길드 기도",
      "skill_description": "EXP를 증가시킵니다.",
      "skill_level": 3,
      "skill_effect": "EXP 획득량 3% 증가",
      "skill_icon": "https://open.api.nexon.com/static/skill/icon/guild_prayer.png"
    }
  ],
  "guild_noblesse_skill": [
    {
      "skill_name": "노블레스 기도",
      "skill_description": "노블레스 전용 EXP 증가.",
      "skill_level": 2,
      "skill_effect": "EXP 획득량 2% 증가",
      "skill_icon": "https://open.api.nexon.com/static/skill/icon/noblesse_prayer.png"
    }
  ]
}
```

**봇 활용:** 길드 검색 기능 구현 시 `guild/id` → `guild/basic` 두 단계 호출이 필요. `guild_member_count`·`guild_level`·`guild_fame`은 길드 요약 카드에 사용.
