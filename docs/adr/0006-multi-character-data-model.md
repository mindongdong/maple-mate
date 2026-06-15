# ADR-0006 — 멀티 캐릭터 데이터 모델: `registration`(키+대표 포인터) + `character`(N) 2테이블

- **상태:** 채택 (Accepted)
- **일자:** 2026-06-15
- **관련 문서:** [n-characters-work-order.md](../n-characters-work-order.md)(그릴링 12결정·빌드 단위), [n-characters-as-built.md](../n-characters-as-built.md)(as-built), [CONTEXT.md](../../CONTEXT.md)(등록·캐릭터·대표 용어), [ADR-0001](0001-nexon-personal-key-model.md)(앱키 vs 개인키), [ADR-0007](0007-history-account-wide.md)(이력류 계정 전체화)
- **이력:** 멀티 캐릭터 등록 그릴링(2026-06-15) 결정 1·2·5·6·9·11. PR #22.

## 맥락 (Context)

기존 `registration` 1테이블이 (guild_id, discord_user_id) 1레코드에 **닉·ocid·개인 키를 융합**해, 디스코드 유저당 메이플 캐릭터 **딱 1개**만 묶을 수 있었다. 요구는 유저당 **N개 캐릭터** 등록이며, 그릴링에서 다음이 확정됐다.

- 공개 ocid 명령(`/스펙`·`/아이템`·`/유니온`·`/경험치`)은 유저를 **대표 캐릭터 1명**으로 표시한다(결정 11 — `exp_snapshot` PK `(guild,user,date)` 불변 유지).
- 개인 키는 **유저당 1개**, 같은 넥슨 계정의 전 캐릭터가 공유한다(결정 1 — 키는 계정 스코프).
- 레벨은 **등록 시 스냅샷**만 두고, 자동 대표 = 저장 레벨 최고값(결정 5).

## 결정 (Decision)

**2테이블 + 포인터로 정규화한다.**

```
registration  (계정/유저 레벨, PK (guild_id, discord_user_id))
  api_key_encrypted    nullable   ← 유저당 1개 키(계정 공유)
  representative_ocid  nullable   ← NULL=자동(최고레벨) / 값=수동 지정

character     (캐릭터 N개, PK (guild_id, discord_user_id, ocid))
  maple_nickname, level(nullable), created_at, updated_at
  (논리적 FK → registration; 부모 행은 캐릭터/키 등록 시 자동 upsert)
```

1. **대표 해석 `pick_representative`(순수함수):** ① `representative_ocid` set & 해당 캐릭터 존재 → 그 캐릭터, ② NULL/부재 → 레벨 최고(동률·NULL은 `created_at`→`ocid` 결정적 타이브레이크), ③ 0개 → None.
2. **상한 = 유저당 10개**(모듈 상수). 같은 ocid 재등록은 닉/레벨 갱신(upsert)이라 상한 무관.
3. **마이그레이션 = 단일 리비전, 비파괴 제자리 변환** — `character` 생성 → 기존 1행 백필(`created_at` 보존) → `representative_ocid` 추가(NULL) → 융합 컬럼 제거. 다운그레이드는 역방향(N→1은 대표 우선 `DISTINCT ON`, 손실 허용).
4. `/등록`(닉+키 한 방)을 **`/캐릭터등록`·`/키등록`·`/대표지정`·`/캐릭터목록`** 으로 분리.

## 검토한 대안 (Alternatives Considered)

- **캐릭터별 키 (1 character = 1 key)** — *기각.* 넥슨 개인 키는 **계정 전체**를 반환하므로 한 친구의 모든 캐릭터가 키 1개로 조회된다. 캐릭터마다 키를 요구하면 같은 키 중복 입력 + UX 부담, 이력류 계정 전체화(ADR-0007)와도 상충.
- **단일 테이블 비정규화 (캐릭터 행마다 key 컬럼 반복)** — *기각.* 키·대표 상태가 행마다 중복돼 정합성 부담. 대표를 "행 1개"로 표현하기 어렵고 키 갱신이 N행 UPDATE가 된다.
- **대표를 `character.is_representative` 불리언 플래그로** — *기각.* 유저당 정확히 1개 True 강제가 어렵고(0개·2개 정합성), "자동(최고레벨)" 상태를 표현하려면 별도 NULL 의미가 필요. nullable 포인터가 자동/수동을 한 컬럼으로 자연 표현한다.

## 결과 (Consequences)

**긍정**
- `get_targets`(스펙류 단일 출처)에 **대표 해석만 추가**하면 `/스펙`·`/아이템`·`/유니온`·`/경험치`가 자동 배선된다(`Target` DTO 모양 불변). `exp_snapshot` PK도 유저당 대표 1명이라 무변경.
- 키가 `registration`에 1개라 계정 전체 이력(ADR-0007)과 자연 정합. 캐시 앵커(`min(created_at)` 캐릭터 ocid)가 안정적 키를 제공.
- 마이그레이션 비파괴 — 기존 등록은 캐릭터 1개 + 대표 NULL로 백필돼 day-1 동작 동일(로컬 DB·CI에서 upgrade/downgrade 가역성 실증).

**부담 / 잔류**
- **`/캐릭터삭제` 없음**(결정 8 보조 명령 최소화) — 잘못 등록한 캐릭터 제거 불가, 같은 ocid 재등록=갱신뿐.
- **레벨 스냅샷 고정** — 레벨업해도 자동 대표 불변 → `/대표지정` 수동 보정(결정 5).
- **테이블명 `character`는 SQL 예약어** — 마이그레이션 raw SQL에서 `"character"` 인용 필수(SQLAlchemy ORM/DDL은 자동 인용).
- 키만 등록하고 캐릭터 0개인 등록은 공개/이력 명령에서 제외(표시 불가) — 정상 플로(`/캐릭터등록`→`/키등록`)에선 발생하지 않음.
