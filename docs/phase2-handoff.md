# Phase 2 핸드오프 — 읽기전용 스펙류 (`/스펙` · `/유니온` · `/아이템`)

> **목적:** [work-plan.md](./work-plan.md)의 **Phase 2**를 다른 세션이 단독으로 착수·완료하기 위한 단일 지침서.
> Phase 1(기반 + `/등록`)은 **완료·머지**됨([phase1-handoff.md](./phase1-handoff.md), PR #1). 이제 스펙류 비교 명령을 올린다.
>
> **원칙:** 설계는 복사하지 않고 **경로로 참조**(중복 금지). 이 문서는 *Phase 2 범위 + Spike 0 파생 구현 제약 + 합격 기준*만 담는다.
> **실용 테스트** — 순수 변환 로직만 단위테스트, Nexon/Discord는 mock. 과도한 E2E 금지.
> **아키텍처는 이미 확정**([architecture.md](./architecture.md), DDD 도메인 수직 슬라이스) — 그 패턴을 그대로 따른다.

## 0. 먼저 읽을 것 (SSOT)

| 문서 | 역할 |
|---|---|
| [maple-discord-bot-design.md](../maple-discord-bot-design.md) | 제품/동작 명세. **§3.1 `/스펙` · §3.2 `/아이템` · §3.3 `/유니온` · §7 횡단규칙 · §2 범위규칙**이 직접 근거 |
| [CONTEXT.md](../CONTEXT.md) | 도메인 용어(스펙류, 대상, 키 미등록 vs 기록 없음) — **코드 네이밍에 그대로 사용** |
| [docs/architecture.md](./architecture.md) | **DDD 폴더 구조 + "새 도메인/명령 추가법"** — Phase 2 구조의 기준 |
| [docs/api/README.md](./api/README.md) | 넥슨 공통 규약 + 에러코드 매핑 + 봇 명령→엔드포인트 표 |
| [docs/api/character.md](./api/character.md) · [union.md](./api/union.md) | `/스펙`·`/아이템`·`/유니온`이 쓰는 엔드포인트 스펙(실호출 확정 주석 포함) |
| [docs/api-verification-plan.md](./api-verification-plan.md) | Spike 0 결과 — 아래 §3 구현 제약의 출처(그룹 A 스펙류) |
| [docs/phase1-handoff.md](./phase1-handoff.md) | Phase 1에서 확립된 패턴(에러 매핑·푸터·defer·테스트 방침)을 재사용 |

## 1. Phase 2 범위 (5개 빌드 단위)

순서 = 권장 빌드 순서(공유 머신 먼저 → 단순 명령 → 복잡 명령). 각 단위는 합격 기준 충족 후 다음으로.

| # | 빌드 단위 | 합격 기준(검증) |
|---|---|---|
| 1 | **넥슨 스펙류 메서드 + ocid lazy 갱신** | `nexon/client.py`에 `character/basic·stat·ability·symbol-equipment·hexamatrix·hexamatrix-stat·item-equipment`, `user/union·union-artifact·union-champion` 호출 메서드(**date 무지정 기본**). **ocid lazy 갱신**: 캐싱 ocid로 조회 → 실패 시 닉→ocid 1회 재조회 → DB 갱신 → 재시도, 그래도 실패면 "닉 변경 가능성, `/등록`으로 갱신" 안내. 단위테스트: 무지정 호출/`00009` 처리/lazy 갱신 흐름(mock) |
| 2 | **대상(target) 해석 + 부분 성공 수집(공유)** | 인자 없으면 **현재 서버 등록자 전원**, 지정 시 그 유저들 → `registration` 레코드 집합. 일부 유저 조회 실패해도 **성공분 표시 + 실패 사유 행**([design §7](../maple-discord-bot-design.md)). 단위테스트: 대상 해석·부분성공 취합(순수 로직) |
| 3 | **`/유니온`** | `user/union`(유니온 레벨)+`union-artifact`(아티팩트 레벨)+`union-champion`(**챔피언 등급 분포 카운트**, 예: SSS 2/SS 3). 비교/개별 동일 항목. **페이지네이션**. 합격: 등록자 전원 비교 + 단일 대상 모두 동작 |
| 4 | **`/스펙`** | **인자 필수**(없으면 "1~5명 지정" 에러), 1명=단일 상세, **최대 5명** 비교. 항목: **전투력·어빌리티·장착 심볼·HEXA 코어·HEXA 스탯**. 상세 전체 모드 |
| 5 | **`/아이템` + 정적 부위표** | 부위 = **choices 드롭다운**(1부위/1명령). 항목: 스타포스·잠재·에디셔널 잠재·추가옵션·주문서/업그레이드. **0성 vs 스타포스 불가 부위 = 정적 부위표로 구분**(아래 §3.6). **우열 판정 안 함**(수치 나열만) |

> 횡단 규칙(§4)은 모든 명령에 공통 적용 — 빌드 단위마다 따로 적지 않았지만 **defer 의무·임베드 통일·페이지네이션·푸터·error_log 적재**는 합격 기준의 일부다.

## 2. 권장 구조 (DDD — 새 도메인 추가, 새 테이블 없음)

> 스펙류는 **읽기 전용**이라 새 ORM 테이블이 없다(조회만). 도메인은 `service`(넥슨 조회+변환) + `commands`(discord 어댑터)로 구성. [architecture.md](./architecture.md)의 "새 도메인/명령 추가법" 그대로.

```
maple_mate/
  character/                 # ★ /스펙 · /아이템 (둘 다 character/* 엔드포인트)
    __init__.py
    service.py               #   스펙 6종 조합 / 아이템 파싱(전달-무관)
    commands.py              #   /스펙, /아이템 (setup(bot)에서 트리 등록)
    equipment_slots.py       #   정적 부위표(스타포스 불가/잠재 불가 부위) — 데이터 모듈
  union/                     # ★ /유니온
    __init__.py
    service.py               #   union/artifact/champion 조합 + 등급 분포 카운트
    commands.py
```

- **공유 헬퍼 배치(제안):**
  - **대상 해석 + ocid lazy 갱신** → `registration/service.py`에 추가(레코드/ocid 소유 도메인). 예: `get_targets(session_factory, guild_id, user_ids=None)`, `refresh_ocid(...)`.
  - **부분 성공 비교 렌더** → `bot/embeds.py`에 비교 임베드 빌더 추가, 또는 `bot/comparison.py` 신설. `EmbedPaginator`(이미 있음) 재사용.
- **명령 등록:** 각 도메인 `commands.py`에 `setup(bot)` 작성 → `bot/core.py._register_commands`에서 호출 한 줄 추가.
- **재사용 자산(Phase 1):** `nexon/client.py`(`_request`/`get_ocid`/throttle·재시도), `nexon/errors.py`(`classify`/`ErrorClass`/`to_error_log_type`), `bot/embeds.py`(`make_embed`/`format_footer`/`defer`/`EmbedPaginator`), `dependencies.Deps`, `error_log` 모델(재시도 건 적재).

## 3. ⚠️ Spike 0에서 확정된 구현 제약 (그룹 A 스펙류 — 반드시 반영)

출처: [api-verification-plan.md](./api-verification-plan.md) 검증 결과표.

1. **스펙류는 `date` 무지정(최신 ready) 호출**([README §날짜](./api/README.md)): "1AM 이후 D-1" 경계는 **soft**다. **봇은 D-1을 직접 계산해 `date`로 넘기지 말 것.** 무지정 호출 → `200` + 응답 `date:null`(최신 ready 스냅샷). `OPENAPI00009`("data not ready") 수신 시 **에러 아님** → "아직 데이터가 준비되지 않았어요(전일 미생성)"로 안내(해당 유저만). 클라이언트 메서드는 `date: str | None = None` 기본 무지정.
2. **`access_flag` = `"true"/"false"` 문자열**(character/basic, 문서 `"1"/"0"`와 불일치). 비공개 캐릭터 처리 시 문자열 비교.
3. **전투력**(character/stat): `final_stat` 배열에서 `stat_name == "전투력"` 항목, **`stat_value`는 문자열**. (44개 항목 중 존재)
4. **챔피언 등급 분포**(union-champion): `union_champion[].champion_grade` 관측값 = `"SSS"`, `"S"`. 등급 체계 `SSS/SS/S…`. **문서 예시 `"레전드리"`는 오류** — 등급 문자열을 그대로 카운트(하드코딩 매핑 금지, 등장하는 값 집계).
5. **HEXA**: `character/hexamatrix`의 `character_hexa_core_equipment[].linked_skill = [{hexa_skill_id}]` 중첩. `hexamatrix-stat`은 코어 배열 6종.
6. **`/아이템` — 0성 vs 스타포스 불가 신호 없음**(item-equipment): `starforce="0"`이 **0성**과 **스타포스 불가 부위**(훈장·뱃지·포켓·엠블렘·특수 반지 등) **양쪽 공통**. 구분 전용 플래그 부재 → **정적 부위표 필수**(설계 §3.2 하이브리드). `potential_option_grade=null` = 잠재 불가/미설정 부위. → `equipment_slots.py`에 "스타포스 적용 부위 / 잠재 적용 부위" 집합을 정의하고, 불가 부위는 해당 항목을 **강제 숨김**.
7. **ocid lazy 갱신**: 스펙류는 ocid 캐싱 사용 + 조회 실패 시 닉→ocid 1회 재조회([design §7](../maple-discord-bot-design.md)). 없는 닉/잘못된 ocid는 `OPENAPI00004`로 옴(전용 not-found 코드 없음).

## 4. 횡단 규칙 (전 명령 공통 — design §7)

- **모든 비교 명령 `defer` 의무**(`bot/embeds.defer`). 응답 길어질 수 있음.
- **부분 성공 허용**: 되는 유저만 표시 + 실패 유저는 사유 행("닉 변경?", "비공개", "데이터 미준비" 등). 전체 실패 시에만 에러 임베드.
- **"키 미등록" vs "기록 없음"**: 스펙류는 **개인 키 불필요** → 등록만 돼 있으면 전원 조회 가능. (이 구분은 이력류 Phase 3의 핵심; Phase 2에선 "미등록 유저는 대상에서 제외" 정도.)
- **넥슨 장애/타임아웃**: 클라이언트가 1~2회 재시도(이미 구현). 최종 실패는 사용자 안내 + **재시도 발생 건 `error_log` 적재**([design §5⑤](../maple-discord-bot-design.md)).
- **출력**: 디스코드 임베드 통일(`make_embed`). 초과 인원 **버튼 페이지네이션**(`EmbedPaginator`). **`/스펙`만 5명 상한**.
- **푸터**(데이터 기준 시점): `format_footer` 재사용. 무지정 호출은 응답 `date`(또는 null→"최신 기준")를 푸터에 반영.

## 5. 명령별 상세

### 5.1 `/스펙 [유저 1~5명]` (design §3.1)
- **인자 필수**(없으면 명시적 에러 "1~5명 지정"). 1명 = 단일 상세, 2~5명 = 비교. 6명+ 거부.
- 항목: 전투력(stat) · 어빌리티(ability) · 장착 심볼(symbol-equipment) · HEXA 코어(hexamatrix) · HEXA 스탯(hexamatrix-stat). + 기본 정보(basic: 레벨·직업·전투력 맥락).
- 비교/개별 모두 **상세 전체 모드**. (출력량 과다 시 §7 사전결정 — 백로그로 축소/옵션화)

### 5.2 `/유니온 [대상(선택)]` (design §3.3)
- 인자 없으면 현재 서버 등록자 전원 비교, 지정 시 해당 대상.
- 항목(비교/개별 동일): **유니온 레벨 + 아티팩트 레벨 + 챔피언 등급 분포 카운트**(예: SSS 2 / SS 3).
- **페이지네이션** 적용(인원 많을 때).

### 5.3 `/아이템 [부위] [대상(선택)]` (design §3.2)
- 부위 = **choices 드롭다운**(필수, 1부위). 대상 없으면 채널/서버 전체 비교.
- 항목: 스타포스 · 잠재능력 · 에디셔널 잠재 · 추가옵션 · 주문서/업그레이드 (item-equipment에서 파싱).
- **우열 판정 안 함** — 수치 나열만(사용자가 직접 비교).
- **부위별 적용 항목 = 동적 + 정적 보정 하이브리드**: API에 값 있으면 표시 + 구조적으로 불가능한 항목(스타포스 불가 부위의 스타포스, 잠재 불가 부위의 잠재)은 `equipment_slots.py` 기준 **강제 숨김**.

## 6. 테스트 방침 (실용 테스트)

**단위테스트(순수 변환 로직만):**
- 전투력 추출(`final_stat`에서 `stat_name=="전투력"`).
- 챔피언 등급 분포 카운트(등장 grade 집계).
- 아이템 부위별 항목 표시/숨김(정적 부위표 적용 — 0성 vs 불가).
- 대상 해석·부분성공 취합 로직.
- (있으면) ocid lazy 갱신 분기 판정.

**mock:** Nexon httpx 응답·discord 상호작용은 mock(`httpx.MockTransport` 패턴은 `tests/test_nexon_client.py` 참고). **무거운 E2E 금지.** 실호출은 필요 시 `-m live` 1~2건(앱 키, 무지정)로 최소.

## 7. 사전 결정 필요 (착수 전 사용자 확인)

1. **정적 부위표 데이터 소스**: 스타포스 불가 부위 / 잠재 불가 부위 목록을 게임 지식으로 직접 작성할지, 레퍼런스를 차용할지. (훈장·뱃지·포켓·엠블렘·특수 반지 등 Spike 0 관측 외 전체 목록 확정 필요.)
2. **`/아이템` 부위 choices 목록**: 드롭다운에 넣을 부위(모자·상의·하의·신발·장갑·망토·무기·보조무기·엠블렘·반지×4·펜던트×2·…) 확정.
3. **`/스펙` 출력량**: 초기 풀 출력 후 디스코드 렌더 확인 → 축소/옵션화 여부(백로그). 5명 비교 시 임베드 분할/페이지 전략.
4. **부분 성공 표기 형식**: 성공 유저 + 실패 사유 행의 임베드 디자인(한 임베드 내 필드 vs 별도 행).

## 8. 범위 밖 (Phase 2에서 하지 말 것)

- **이력류**(`/스타포스`·`/잠재`·`/잠재합계`) = Phase 3. 기대값 고정 표 = Phase 3.
- 알림(`/공지알림`·`/썬데이`)·스케줄러·운영 요약 = Phase 4~5.
- `/아이템` 우열 판정(수치 나열만). GPT 비교 등 백로그([design §9](../maple-discord-bot-design.md)).
- 추측성 추상화/설정화([CLAUDE.md](../CLAUDE.md) 단순함 우선).

## 9. 산출물 체크리스트

- [ ] 넥슨 스펙류 메서드(date 무지정) + ocid lazy 갱신
- [ ] 대상 해석 + 부분 성공 수집 공유 헬퍼
- [ ] `/유니온`: 레벨+아티팩트+챔피언 등급분포, 페이지네이션
- [ ] `/스펙`: 인자 필수(1~5명), 단일/비교, 5종 항목
- [ ] `/아이템`: 부위 choices, 정적 부위표(0성 vs 불가), 우열판정 없음
- [ ] 횡단: defer·임베드·페이지네이션·푸터·부분성공·error_log 적재
- [ ] 단위테스트 통과(변환 로직·정적표·대상/부분성공), Nexon/Discord mock
- [ ] 라이브 검증: 각 명령 단일/비교 동작, 닉 변경 시 lazy 갱신
- [ ] 시크릿 미커밋 확인(`git status`)

## 참조

- 작업 계획 전체: [work-plan.md](./work-plan.md) (Phase 1~5)
- 검증 결과·잔류: [api-verification-plan.md](./api-verification-plan.md)
- 아키텍처·확장법: [architecture.md](./architecture.md)
- Phase 1 패턴: [phase1-handoff.md](./phase1-handoff.md)
