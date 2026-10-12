# 작업지시서 — 비교 대상 지정 통일 + 닉네임 직접 입력 (PR1/3)

> **근거 결정:** ADR-0021(본 작업으로 작성 — §6), 무인자 팬아웃 [ADR-0008](adr/0008-unspecified-comparison-fanout-cap.md)(본 작업으로 부분개정), realm [ADR-0009](adr/0009-challengers-realm-model.md), 유저 설치 [ADR-0019](adr/0019-user-install-dm-workspace.md).
> **하우스 스타일 레퍼런스:** [random-fanout-work-order.md](random-fanout-work-order.md), [my-character-work-order.md](my-character-work-order.md).
> **결정 출처:** 2026-10-12 세션. 사용자 판단: 봇의 핵심 가치는 "채널 안에서 여러 캐릭터를 간편 비교"인데, 대상 지정 규칙이 명령마다 다르고 등록자 외 캐릭터는 비교할 수 없다.
> **후속:** [comparison-tabs-work-order.md](comparison-tabs-work-order.md)(PR2) → [account-character-import-work-order.md](account-character-import-work-order.md)(PR3). PR2 는 본 PR 의 대상 해석 결과(Target 목록)를 그대로 재사용한다.
> **상태:** 구현 완료(브랜치 `claude/loving-brahmagupta-tyordi`). §7 as-built 참고.

---

## 0. 한 줄 목표

공개 스펙류 비교 3종(`/스펙`·`/아이템`·`/유니온`)의 **대상 지정 규칙을 하나로 통일**하고, 디스코드 멤버 대신 **메이플 닉네임으로도 대상을 지정**할 수 있게 한다(미등록 캐릭터 포함).

---

## 1. 배경·코드 현황 (재조사하지 말 것)

- **규칙 불일치**: `/아이템`·`/유니온`은 대상을 안 적으면 본인 포함 랜덤 최대 10명([comparison.select_with_self](../maple_mate/bot/comparison.py#L178)). 반면 `/스펙`은 `member1`이 필수다([character/commands.py:436](../maple_mate/character/commands.py#L436)~, 핸들러 [:214](../maple_mate/character/commands.py#L214)).
- **`/스펙`이 필수였던 이유는 비용**: 1명당 넥슨 호출이 ≈13회(최신 6종 + 7일 최고 전투력용 `character/stat` 7회, [character/service.py:250](../maple_mate/character/service.py#L250)). 전역 4req/s 스로틀(ADR-0004) 기준 10명이면 30초를 넘는다.
- **대상 = 디스코드 멤버만**: `resolve_targets(session_factory, guild_id, members, realm)`([comparison.py:125](../maple_mate/bot/comparison.py#L125))가 `get_targets`([registration/service.py:398](../maple_mate/registration/service.py#L398))로 멤버마다 대표 1명을 해석한다. 미등록 멤버는 "미등록" 부분성공 행이 된다.
- **닉→ocid 헬퍼 있음**: `resolve_ocid(nexon, nickname)`([registration/service.py:76](../maple_mate/registration/service.py#L76))는 실패 시 사용자 메시지를 돌려준다.
- **`Target`은 이미 미등록을 일부 표현함**: `Target(guild_id, discord_user_id, nickname, ocid, world, level)`([registration/service.py:374](../maple_mate/registration/service.py#L374)). `mention()`은 `discord_user_id`가 falsy면 빈 문자열을 돌려준다([comparison.py:36](../maple_mate/bot/comparison.py#L36)). 따라서 `discord_user_id=0`인 대상은 범례에 닉네임만 나온다.
- **조회 머신**: `fetch_each` → `_fetch_one`([registration/service.py:601](../maple_mate/registration/service.py#L601)). 스테일 ocid면 `refresh_ocid`로 닉 재조회 후 DB UPDATE를 한다. `discord_user_id=0`이면 UPDATE 대상 행이 없어 무해하다. 하드 실패는 `error_log.record`(`discord_user_id` nullable)에 남는다.
- **챌린저스**: 시즌 종료로 `모드` 파라미터는 제거됐다(#65). 핸들러의 `realm` 인자는 기본값 `Realm.MAIN`으로만 쓰인다.
- **사이트 카피가 이미 앞서 있음**: `site/data/commands.json` 유니온 tip에 "/유니온 [캐릭터명]으로 특정 캐릭터를 조회"라고 적혀 있다. 지금은 사실이 아니지만 본 PR로 사실이 된다.
- **사이트 드리프트 가드**: [tests/test_website_command_drift.py](../tests/test_website_command_drift.py)는 명령 이름 집합만 비교한다. 이번 PR은 명령 추가가 없어 가드가 깨지지 않지만, 카피 정확성 갱신은 필요하다.

---

## 2. 확정 결정

1. **적용 명령 = `/스펙`·`/아이템`·`/유니온`** (앱 키 + ocid 공개 조회). 아래 명령은 제외한다:
   - `/경험치`: 등록자 DB 스냅샷 기반이라 미등록 캐릭터 이력이 없다.
   - `/스타포스`·`/잠재`: 개인 키 계정 합산이다.
   - `/내캐릭터`: 본인 캐릭터 전용이다.
2. **`/스펙` 무인자 허용 — 상한 K=5.** `member1`을 optional로 바꾼다. 무인자면 본인 포함 랜덤 5명이다(`select_with_self(cap=5)`). 응답 ≈15초(5×13콜÷4). `/아이템`·`/유니온`의 K=10은 그대로 둔다.
3. **닉네임 입력 = 단일 파라미터 `닉네임`(쉼표 구분).** 예: `닉네임: 메이플전사, 아델짱`.
   - 유저 슬롯 + 닉네임을 **합쳐 최대 5명**이다. 초과 시 조회 전에 ephemeral로 거부한다.
   - 공백 제거, 빈 토큰 무시, 대소문자 무시 중복 제거.
4. **닉네임 해석 순서** (호출 절약 + 등록 정보 우선):
   - ① 이 서버 등록 캐릭터(`Character.maple_nickname`, 대표 여부 무관)와 일치하면 그 캐릭터를 쓴다. `discord_user_id`가 소유자로 채워져 태그가 붙는다. 친구의 **비대표 캐릭터**를 지정하는 수단도 된다.
   - ② 일치가 없으면 `resolve_ocid` 1콜로 **게스트 대상**(`discord_user_id=0`)을 만든다.
   - ③ 둘 다 실패하면 부분성공 행 `'X' 닉네임을 찾을 수 없어요.`
5. **혼합 순서·중복**: 유저 슬롯(입력순) → 닉네임(입력순)으로 쌓는다. **ocid 기준 중복을 제거**한다(유저 대표 = 닉 지정 캐릭이면 1회만). 표시 정렬은 명령별 기존 규칙을 유지한다(스펙=전투력, 유니온=유니온 레벨, 아이템=본인 먼저 + 입력순).
6. **게스트 표시**: 범례에는 닉네임만 나온다(태그 없음 — `mention()` 기존 동작). 라벨에 별도 마커는 넣지 않는다(시각 회귀 0).
7. **무인자 푸터**: `/스펙`도 `fanout_note(total, cap=5)`를 쓴다. 문구에 "랜덤 5명"이 나오게 cap을 넘긴다. 본인 미포함 안내 문구는 `/아이템`과 동일하게 쓴다.

### 비목표
- 닉네임 자동완성(외부 캐릭터는 후보가 없고, 등록 캐릭은 PR3 이후 재검토)
- 게스트 캐릭터 DB 저장·캐시
- `/경험치`·이력류 확장
- K값 변경(아이템·유니온 10 유지)
- 결과 메시지 버튼(PR2)

---

## 3. 설계 핵심

### 3-1. 닉네임 파싱 (순수함수, `bot/comparison.py`)

```python
MAX_SPECIFIED_TARGETS = 5

def parse_nicknames(raw: str | None) -> list[str]:
    """'a, b ,A' → ['a', 'b'] — 공백 제거·빈 토큰 무시·대소문자 무시 중복 제거(첫 표기 유지)."""
```

### 3-2. 통합 대상 해석 (`bot/comparison.py`)

```python
async def resolve_mixed_targets(
    deps: Deps, guild_id: int, members: list[discord.Member],
    nicknames: list[str], realm: Realm | None = None,
) -> tuple[list[Target], list[TargetOutcome]]:
    """유저 슬롯 + 닉네임 → (Target 목록, 실패 outcome). 둘 다 비면 무인자 경로(호출자 책임)."""
```

- 유저 쪽은 기존 `resolve_targets`를 그대로 호출한다(회귀 0).
- 닉 쪽은 `registration/service.py`에 신규 `find_guild_character_by_nickname(session_factory, guild_id, nickname, realm) -> Target | None`을 둔다(대소문자 무시 일치, 복수면 첫 행).
  - 미일치 시 `resolve_ocid`로 게스트 `Target(guild_id, 0, nickname, ocid)`를 만든다.
- 마지막에 ocid 중복을 제거하고 입력 순서를 보존한다.
- `Target`에 필드를 추가하지 않는다. 게스트 판별은 `discord_user_id == 0`(헬퍼 `is_guest(target)`)으로 한다.

### 3-3. 명령 시그니처 (3종 공통 패턴)

```python
@app_commands.rename(..., nicknames="닉네임")
@app_commands.describe(nicknames="메이플 닉네임 (쉼표로 여러 명, 유저와 합쳐 최대 5명 · 미등록 캐릭터도 가능)")
async def spec_command(interaction, member1: discord.Member | None = None, ..., nicknames: str | None = None)
```

- **상한 검사는 `defer` 전에** 한다. 공개 defer 후엔 ephemeral 전환이 불가하다(my-character §1-b 교훈). `len(members) + len(parse_nicknames(...)) > 5`면 `interaction.response.send_message(..., ephemeral=True)`.
- 핸들러 시그니처: `handle_spec(deps, interaction, members, nicknames, realm=...)`. `handle_item`·`handle_union`도 같다.
- 무인자 판정 = `not members and not nicknames`.

### 3-4. `/스펙` 무인자 경로

`handle_item`의 무인자 블록([character/commands.py:364](../maple_mate/character/commands.py#L364)~)을 동일 패턴으로 이식한다. 차이는 `cap=SPEC_UNSPECIFIED_CAP(=5)`뿐이다. 1명뿐이면(본인만 등록) 기존 단일 상세 임베드 경로로 간다.

### 3-5. 게스트 대상 안전성 체크리스트

- `_fetch_one` 스테일 분기: 게스트는 방금 `/id`로 받은 ocid라 사실상 진입하지 않는다. 진입해도 `refresh_ocid` UPDATE는 0행이다. 단 실패 문구 "`/캐릭터등록`으로 닉네임을 갱신"은 게스트에게 부적절하므로, 게스트면 `'X' 닉네임을 찾을 수 없어요.`로 분기한다.
- `error_log.record`: 게스트는 `discord_user_id=None`으로 적재한다(0 대신 — 운영 요약이 유저 집계에 쓰지 않는지 확인).
- `_self_first`·`select_with_self`: uid 0은 본인과 같을 수 없다. 무인자 경로엔 게스트가 없다.

---

## 4. 빌드 단위·테스트

| # | 작업 | 검증 |
|---|---|---|
| 1 | `parse_nicknames` + `MAX_SPECIFIED_TARGETS` | 단위: 공백·빈 토큰·중복·대소문자·None |
| 2 | `find_guild_character_by_nickname` | DB 단위: 비대표 캐릭 일치, 대소문자, 미일치 None |
| 3 | `resolve_mixed_targets` | 단위(nexon mock): 등록 일치=0콜, 게스트=1콜, 실패 행, ocid 중복 제거, 순서 보존 |
| 4 | 3종 명령에 `닉네임` 파라미터 + 상한 사전검사(defer 전 ephemeral) | 핸들러 테스트: 6명 → ephemeral 거부·넥슨 0콜 |
| 5 | `/스펙` member1 optional + 무인자 K=5 | 핸들러: 무인자 7명 등록 → 5명 조회, 본인 포함, 푸터 "랜덤 5명" |
| 6 | 게스트 실패 문구·error_log uid None | `_fetch_one` 단위 |
| 7 | 카피: 명령 description 3종, `site/data/commands.json`(스펙 무인자·닉네임 / 아이템·유니온 닉네임), `site/data/tutorial-steps.tsx:189` "/스펙은 지정 필수" 제거 | `uv run pytest tests/test_website_command_drift.py` |
| 8 | 문서: ADR-0021 신규, ADR-0008 개정 노트, CONTEXT.md | 리뷰 |

테스트 관행: [tests/test_fanout_cap.py](../tests/test_fanout_cap.py)(선정), [tests/test_comparison.py](../tests/test_comparison.py)(해석), [tests/test_mychar_commands.py](../tests/test_mychar_commands.py)(가짜 Interaction·monkeypatch 패턴).

공통 게이트: `uv run pytest` · `uv run ruff check . && uv run ruff format --check .`

---

## 5. 수용 기준

- [ ] `/스펙` 무인자 → 본인 포함 랜덤 최대 5명. 등록자 ≤5명이면 전원
- [ ] `/스펙 닉네임:미등록닉` → 게스트 1명 단일 상세(태그 없음)
- [ ] `/아이템 부위:무기 유저1:@A 닉네임:B의부캐` → A 대표 + B 부캐(B 태그). 넥슨 `/id` 호출 0
- [ ] 유저 3 + 닉네임 3 → 조회 없이 ephemeral 거부
- [ ] 없는 닉 포함 → 나머지는 정상 + "조회 실패" 묶음에 그 닉
- [ ] 기존 호출(유저 슬롯만 / 무인자 아이템·유니온) 출력이 바이트 단위로 동일(회귀 0)

---

## 6. 기록·배포

- **ADR-0021 "비교 대상 닉네임 직접 지정(게스트 대상)"**: 결정 3~6, 게스트=`discord_user_id 0` 비저장 모델, 등록 캐릭 우선 해석 근거(호출 절약·태그·비대표 지정)를 담는다.
- **ADR-0008 개정 노트**: `/스펙` 무인자 K=5(비용 근거 13콜/명). "지정 필수" 서술을 삭제한다.
- **CONTEXT.md**: "대상" 정의에 닉네임 지정 추가. 용어 **게스트 대상(Guest target)** 신설(미등록 캐릭터, 비저장, 태그 없음. _Avoid_: 외부 유저, 비회원).
- PR 1개(봇 + 사이트 카피 동시 — 명령 추가가 없어 배포 순서 무관).

---

## 7. As-built (PR2 세션이 재조사하지 말 것)

- **해석**: `comparison.resolve_mixed_targets(session_factory, nexon, guild_id, members, nicknames, realm=None)` — 닉네임이 없으면 `resolve_targets`에 그대로 위임(무인자 포함, 회귀 0). `command=` 라벨은 게스트 `/id` 실패의 error_log 용.
- **상한 거부 = 명령 체크 `comparison.target_limit_check()`**(리뷰 반영 — §3-3 의 "핸들러에서 defer 전 거부"를 대체). `interaction.namespace` 의 Member/User 값 + `닉네임` 을 세어 초과면 `TooManyTargets`(CheckFailure) → 트리 공통 핸들러([bot/core.py](../maple_mate/bot/core.py) `on_app_command_error`)가 ephemeral 안내. 데코레이터를 **쿨다운 아래**에 둬서 쿨다운보다 먼저 실행 → 거부가 10초 쿨다운을 소모하지 않는다. 핸들러는 상한 검사를 하지 않는다.
- **서비스**: `registration/service.py` — `GUEST_USER_ID=0`·`is_guest`·`_match_nicknames`(순수)·`find_guild_characters_by_nicknames`·`resolve_guest_target`·`GUEST_NOT_FOUND`. `_fetch_one` 게스트 분기 2곳(스테일=재조회 없이 `GUEST_NOT_FOUND`, error_log uid None). `resolve_guest_target` 도 가용성 오류(`to_error_log_type` 대상)는 error_log 적재(uid None), 닉 없음은 미적재.
- **§2-4·§3-2와 다른 점 — 실패 문구**: 게스트 해석은 `resolve_ocid` 대신 `nexon.get_ocid` 를 직접 호출하고(등록용 문구 회피), 못 찾으면 `GUEST_NOT_FOUND` = "캐릭터를 찾을 수 없어요. 닉네임을 확인해 주세요."(대상 닉은 실패 행 앞에 이미 표시됨).
- **§3-2와 다른 점**: 닉 일치는 **realm 무필터**(명시적 의도 — ADR-0021 결정 2). `find_…`는 닉 목록 단위 1쿼리(`dict[소문자 닉, Target]`).
- **핸들러**: `handle_spec/handle_item/handle_union(..., *, nicknames=())` keyword-only. 명령 함수가 `comparison.parse_nicknames`로 파싱해 넘긴다. `/스펙` 무인자 상수 `SPEC_UNSPECIFIED_CAP=5`(character/commands.py).
- **유니온 단일 카드**: 게스트(태그 없음)는 첫 줄 빈 줄 없이 본문부터.
- **테스트**: [tests/test_nickname_targets.py](../tests/test_nickname_targets.py)(24건 — 쿼리 컴파일·체크 순서·핸들러 부분성공 포함), [tests/test_cooldowns.py](../tests/test_cooldowns.py)는 쿨다운 체크만 골라 검사하도록 조정.
