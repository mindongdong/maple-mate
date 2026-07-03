# ADR-0020 — 경험치 스냅샷 소스를 `character/basic` 단일로 전환 (`ranking/overall` 폐기)

- **상태:** 채택 (Accepted) — [ADR-0005](0005-exp-leaderboard-data-source.md)를 대체(Supersedes)
- **일자:** 2026-07-03
- **관련 문서:** [ADR-0005](0005-exp-leaderboard-data-source.md)(폐기 대상 — ranking/overall 단일 채택), [ADR-0011](0011-exp-leaderboard-display.md)(표시 개편 — 순위키 (레벨, exp%)·Δ/전체순위 미표기), [ADR-0018](0018-my-character-solo-comparison.md)(스냅샷 ocid 차원)
- **이력:** 라이브 그래프에서 무기콤보 06/27→06/28 "경험치 하락" 관측 → 실 API 재조회로 원인 확정(2026-07-03).

## 맥락 (Context)

7일 추이 그래프의 각 점은 `progress = character_level + exp_rate/100` 인데, 두 성분의 출처가 달랐다:

- **레벨** ← `ranking/overall?date=D` (ADR-0005 주 소스)
- **exp%** ← `character/basic?date=D` (best-effort 보강)

실 API 재조회(무기콤보, 2026-07-03)로 **두 엔드포인트의 date=D 기준 시점이 하루 어긋남**을 확정했다: `ranking/overall?date=D`의 레벨 = `character/basic?date=D-1`의 레벨(랭킹은 D일 아침 발표 = D-1 마감 집계, basic 은 D일 마감). 즉 그래프 점은 "D-1 마감 레벨 + D 마감 exp%" 합성이라, 레벨업 날 exp% 리셋이 하루 낡은 레벨과 짝지어져 **가짜 하락점**을 만든다(실측: 276.69 → 276.02처럼 보였으나 실제 진행도는 276.69 → 278.02 단조 증가).

한편 ADR-0005 가 ranking/overall 을 채택한 근거(누적 total_exp 정렬·Δ 표시·전체 서버 순위)는 ADR-0011 에서 전부 표시 폐기됐다 — 순위키는 (레벨, exp%)로 통일됐고 Δ·전체순위는 미표기다. 남은 소비자가 그래프·순위판의 **레벨**뿐인데 그 레벨이 하루 뒤처진 값이었다.

## 결정 (Decision)

**경험치 스냅샷의 단일 소스를 `character/basic?ocid=&date=D` 로 전환한다.** `ranking/overall` 호출·클라이언트 메서드·`total_exp`·`world_rank` 컬럼을 제거한다.

1. 스냅샷 값 = basic 의 `character_level` + `character_exp_rate` — **같은 응답의 같은 시점**(D일 마감) 페어라 그래프·순위판 스케일이 정합한다.
2. **실패한 날은 행을 만들지 않는다**(종전: ranking 성공 + basic 실패 → `exp_rate=None` 행 영구 잔존). 행이 없으면 매 실행 멱등 backfill(D-1~D-8)이 빈 날로 보고 재시도 → 일시 실패(429·타임아웃)가 자가복구된다.
3. 기존 행의 레벨은 하루 뒤처진 랭킹 값이므로, 마이그레이션에서 최근 8일(표시 창 포함) 행을 삭제해 backfill 재적재를 유도한다. 8일 초과 과거 행은 표시 소비자가 없어 그대로 둔다.
4. 캐릭터당 일일 넥슨 콜이 2회(ranking+basic) → **1회**(basic)로 준다.

## 검토한 대안 (Alternatives Considered)

- **ranking 유지 + 레벨만 basic 으로 교체** — *기각.* total_exp·world_rank 는 표시 소비자가 없고(ADR-0011), ranking 콜을 남기면 캐릭터당 2콜·죽은 컬럼·"미등재" 개념이 그대로 남는다.
- **DB 스냅샷 폐기, 매 호출 7일 라이브 조회** — *기각.* 서버 리더보드 Top10 기준 매 호출 70콜 ≈ 전역 4req/s 스로틀로 18초+, 매일 잡·구독자 발송까지 곱해진다. DB 캐시(정상 상태 넥슨 0콜)가 옳고, 결손 자가복구는 결정 2(실패 시 행 미생성 + 멱등 backfill)로 달성된다.

## 결과 (Consequences)

**긍정**
- 레벨업 날 가짜 하락점 소멸 — 그래프 progress 의 두 성분이 같은 시점.
- 일시 페치 실패가 영구 결손이 되지 않음(행 미생성 → backfill 재시도).
- 콜 수 절반, "랭킹 미등재" 개념·안내 문구 제거로 단순화.

**부담 / 잔류**
- 전체 서버 순위(#)를 다시 표시하려면 ranking/overall 재도입 필요(현재 표시 계획 없음).
- Δ(어제 하루 획득)를 되살리려면 누적 경험치 소스가 다시 필요(ADR-0005 의 레벨→누적 EXP 테이블 문제로 회귀). 현재 미표기라 무손실.
- 다운그레이드는 컬럼만 복원(total_exp=0 백필)하고 삭제된 최근 8일 행은 구버전 backfill 이 재적재.
