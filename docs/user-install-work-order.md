# 작업지시서 — 유저 설치(User Install) 지원: DM 워크스페이스

> **근거 결정:** [ADR-0019](adr/0019-user-install-dm-workspace.md)(본 작업으로 작성). 멀티 캐릭터 키 [ADR-0006](adr/0006-multi-character-data-model.md), 개인 DM 구독 [ADR-0017](adr/0017-notification-unification-and-dm-subscription.md), 솔로 가치 [ADR-0018](adr/0018-my-character-solo-comparison.md).
> **하우스 스타일 레퍼런스:** [my-character-work-order.md](my-character-work-order.md), [prelaunch-qa-work-order.md](prelaunch-qa-work-order.md).
> **그릴링 출처:** `/grill-me` 세션(2026-07-03). 사용자 문제 제기: 봇 초대는 서버 단위인데, 서버에 속하지 않은 개인 유저도 채널 없이 봇을 쓸 수 있게 하고 싶다.
> **상태:** G0 스파이크 1차 시도 **판정 무효**(§7 — 부계정 서버 공유, 재실행 대기). **PR1은 알림 3종을 미개방 상태로 두고 착수 가능**(§7 반영 지침). 구현 미착수.

---

## 0. 한 줄 목표

Discord **유저 설치 앱**을 활성화해, 서버에 속하지 않은 개인 유저가 **봇 DM에서 등록→조회→알림 구독을 완결**할 수 있게 한다. DM 데이터는 센티널 `guild_id=0`으로 키잉하고, **스키마·서비스 함수·기존 서버 동작은 무변경**(회귀 0).

---

## 1. 배경·코드 현황 (다음 세션이 재조사하지 말 것)

- **모든 명령이 수동 DM 거부**: 11개 명령 전부 `if interaction.guild_id is None: ... _DM_ONLY` 패턴(예: [registration/commands.py:62](../maple_mate/registration/commands.py#L62), [scheduler/commands.py:75](../maple_mate/scheduler/commands.py#L75), [bitik/commands.py:319](../maple_mate/bitik/commands.py#L319)). `allowed_installs`/`allowed_contexts`/`guild_only`는 코드 어디에도 없음. 유일한 예외 `/가이드`([guide/commands.py:46](../maple_mate/guide/commands.py#L46))는 체크 자체가 없어 이미 DM 동작 가능.
- **데이터 키**: Registration PK `(guild_id, discord_user_id)`, Character PK `(guild_id, discord_user_id, ocid)`([registration/models.py](../maple_mate/registration/models.py)). 구독류도 `(guild_id, discord_user_id, ...)`. **guild_id 0을 넣으면 전 경로가 무수정 동작**하는 구조.
- **DM 발송 경로는 이미 있음**: `send_dm(bot, user_id, ...)` — 스케줄러 리마인더·개인 알림 구독이 사용([notification/scheduler.py:101](../maple_mate/notification/scheduler.py#L101)~125). 단 지금까지는 전원 서버 공유 유저였음.
- **members 인텐트 의존은 /스타포스·/잠재뿐**([history/commands.py:302](../maple_mate/history/commands.py#L302) `guild.get_member`) — 미개방 명령이라 본 작업과 무관.
- **discord.py 2.4 API**: `@app_commands.allowed_installs(guilds=, users=)` · `@app_commands.allowed_contexts(guilds=, dms=, private_channels=)` 데코레이터(그룹에도 지정 가능), `interaction.is_user_integration()` / `interaction.is_guild_integration()`.
- **명령 노출 변경 = 사이트 문서 동반**: 드리프트 가드([tests/test_website_command_drift.py](../tests/test_website_command_drift.py))는 명령 이름 집합만 비교하므로 본 작업으론 안 깨지지만, 시작하기·명령어 페이지의 "서버 초대" 전제 카피는 PR2에서 갱신.
- **초대 링크 현황**: `scope=bot applications.commands`, `permissions` 파라미터 없음(권한 0 초대). 길드 설치 권장 권한 = View Channels+Send Messages+Embed Links+Attach Files = **52224**(스케줄러 채널 발송용).

---

## 2. 확정 결정 (그릴링 6)

1. **목표 유저 = 서버 미소속 개인 유저.** 등록부터 알림까지 DM에서 완결. 기존 서버 유저의 DM 편의는 비목표(DM 등록은 별개 데이터, 재등록 필요).
2. **데이터 키 = 센티널 `guild_id=0`** ("DM 워크스페이스"). 스노우플레이크에 0 없음 → 충돌 불가. 스키마 무변경·마이그레이션 0건.
3. **명령 분류:**
   - **개방**: `/가이드`, `/캐릭터등록`·`/키등록`·`/대표지정`·`/캐릭터목록`, `/내캐릭터`(3서브), `/스케줄러`, `/스케줄러알림`, `/공지알림`·`/썬데이알림`(개인 DM 대상만 — 채널 대상 선택 시 거부 문구).
   - **미개방**(유저 설치 목록에서 숨김): `/스펙`·`/아이템`·`/유니온`·`/스타포스`·`/잠재`·`/경험치`·`/비틱`.
4. **컨텍스트 = 봇 DM 전용.** 그룹 DM·타서버(봇 미초대) 호출 불허. `allowed_contexts`가 설치 경로별 분리를 못 하므로 **런타임 가드**로 구현(§3-2).
5. **G0 스파이크 선행**: "유저 설치만(서버 미공유)" 상태 유저에게 크론성 DM 발송이 되는지 실검증. **실패 시 `/스케줄러알림`·`/공지알림`·`/썬데이알림`은 개방 목록에서 제외**하고, `/스케줄러`(온디맨드)만 유지.
6. **패키징 = ADR-0019 + 2 PR.** PR1 = 봇, PR2 = 사이트·문서. 운영자 작업 별도(§6).

**부수 결정(에이전트 판단, 그릴링에서 고지됨):**
- 미개방 명령 = `allowed_installs(guilds=True, users=False)` → 유저 설치 유저에게 아예 안 보임(거부 문구안 기각).
- realm은 world_name 유도(ADR-0009)라 DM 등록에도 무변경.
- 기존 서버 유저가 DM에서 개방 명령 사용 시: guild 0 스코프로 동작(빈 등록이면 "등록된 캐릭터가 없어요" — 기존 0캐릭 에러 재사용). 서버 데이터 승계 없음을 문구로 안내하지 않는다(1차 목표 유저에겐 해당 없음, 혼란 보고 들어오면 후속).

### 비목표

글로벌 계정 테이블·계정 통합, 서버↔DM 데이터 승계, 비교류·리더보드의 DM 변형(솔로는 `/내캐릭터`가 담당), 그룹 DM·타서버 컨텍스트 개방, 길드 설치 경로의 어떤 동작 변경, 팬아웃 경계(이슈0001).

---

## 3. 설계 핵심

### 3-1. 스코프 해석 헬퍼 (신규, 개방 명령 전용)

```python
DM_WORKSPACE_ID = 0  # 센티널 — Discord 스노우플레이크에 0 없음 (ADR-0019)

def resolve_scope(interaction: discord.Interaction) -> int | None:
    """개방 명령의 데이터 스코프. None = 사용 불가 컨텍스트(호출부가 안내 후 종료)."""
    if interaction.guild_id is not None:
        # 봇 미초대 서버에서 유저 설치로 호출 → 거부 (결정 4)
        if interaction.is_user_integration() and not interaction.is_guild_integration():
            return None
        return interaction.guild_id
    return DM_WORKSPACE_ID  # 봇 DM
```

- 개방 명령의 기존 `if interaction.guild_id is None: 거부`를 `scope = resolve_scope(...)` + `None`이면 "이 명령은 서버 채널 또는 봇 DM에서 사용할 수 있어요" ephemeral 거부로 교체. 이후 `guild_id` 자리에 `scope` 전달 — **서비스층 무변경**.
- 미개방 명령은 기존 수동 체크 그대로(이중 방어). 데코레이터만 추가.

### 3-2. 데코레이터 배선

- 개방 명령/그룹: `@allowed_installs(guilds=True, users=True)` + `@allowed_contexts(guilds=True, dms=True, private_channels=False)`.
- 미개방 명령/그룹: `@allowed_installs(guilds=True, users=False)` + `@allowed_contexts(guilds=True, dms=False, private_channels=False)` — 명시해서 기본값 드리프트 방지.
- `/공지알림`·`/썬데이알림`: DM 컨텍스트(`scope == DM_WORKSPACE_ID`)에서 대상=채널 선택 시 "DM에서는 개인 알림만 켤 수 있어요" ephemeral 거부.

### 3-3. 크론 포섭 체크포인트 (구현 시 검증 필수)

- **스케줄러 리마인더·개인 알림 구독**: 구독 테이블 전역 조회라 guild 0 행이 자연 포함되는지 확인 — 포함되면 무변경.
- **exp_snapshot 수집**: 수집 트리거가 "exp_alert 채널이 설정된 길드" 순회라면 **guild 0은 영원히 미수집** → `/내캐릭터 경험치`가 DM에서 빈 그래프. 수집 대상 열거를 "등록 존재 스코프"로 넓히거나, 온디맨드 백필(매실행 멱등)이 커버하는지 실측으로 판정. **이 검증 결과를 PR1 본문에 기록할 것.**
- **경험치 서버 리더보드 방송**: guild 0에는 채널 설정이 없어 자연 배제 — 확인만.

### 3-4. G0 스파이크 (구현 착수 전, 코드 머지 없음)

1. Developer Portal(테스트 앱 또는 본 앱)에서 User Install 활성화.
2. 부계정으로 **유저 설치만** 수행 — 봇과 공유 서버가 없어야 함(필요 시 부계정을 모든 공유 서버에서 탈퇴).
3. 테스트 봇 프로세스에서 `bot.fetch_user(uid)` → `user.send(...)` 시도 — **인터랙션 직후가 아니라 별도 프로세스/시점에서**(크론 상황 재현).
4. 판정: 성공 → 알림 3종 개방 확정. 실패(Forbidden 등) → 알림 3종 미개방으로 §2 결정 3 목록 축소, `/스케줄러알림`을 DM에서 켜려 하면 안내 문구.
5. 결과를 본 문서 §7에 기록.

---

## 4. 빌드 단위

### PR1 — 봇 (스키마 무변경)

1. `resolve_scope` 헬퍼 + 단위 테스트(길드/DM/유저설치-타서버/양통합 4분기).
2. 개방 명령 전환: 등록 4종 → `/내캐릭터` → `/스케줄러`·`/스케줄러알림` → 알림 2종(G0 통과 시) 순. 각각 데코레이터 + `resolve_scope` 교체 + 기존 테스트 회귀 확인.
3. 미개방 명령: 데코레이터만 추가(동작 무변경).
4. 크론 포섭 체크(§3-3) — 필요 시 exp_snapshot 수집 열거 보정(이 경우에만 코드 변경).
5. 테스트: 가짜 Interaction에 `guild_id=None`·`is_user_integration` 스텁 — [tests/test_mychar_commands.py](../tests/test_mychar_commands.py)의 `_Response`/`_Followup` 패턴 재사용.

### PR2 — 사이트·문서

1. 시작하기: "서버에 초대" 옆에 "내 계정에 추가(개인으로 쓰기)" 경로 추가 — 유저 설치 링크, DM 사용 흐름, 서버 등록과 별개 데이터임을 한 줄 고지.
2. 명령어 페이지: 개방 명령에 "개인 DM 가능" 표시(전제조건 funnel 배지 체계와 정합하게).
3. 초대 CTA: 길드 설치 링크에 `&permissions=52224` 반영(§1 마지막 항목), `NEXT_PUBLIC_INVITE_URL` 계열 env 문서 갱신([website-deploy-runbook.md](website-deploy-runbook.md)).

---

## 5. 검증 게이트

- [ ] G0 스파이크 판정 기록(§7) — **이후 작업의 전제**
- [ ] `resolve_scope` 4분기 단위 테스트
- [ ] 전체 pytest 그린(기존 테스트 무수정 통과 = 길드 경로 회귀 0)
- [ ] ruff clean
- [ ] 라이브: 부계정(서버 미공유)으로 설치→`/키등록`→`/캐릭터등록`→`/내캐릭터 스펙`→`/스케줄러알림 켜기`→익일 DM 수신 확인
- [ ] 라이브: 봇 미초대 서버에서 유저 설치 호출 → 거부 문구 확인
- [ ] 사이트 빌드·드리프트 테스트 그린

---

## 6. 운영자 수동 작업

1. Developer Portal → Installation: **User Install 활성화**, Default Install Settings에 Guild = `bot`+`applications.commands`+권한 52224 / User = `applications.commands`.
2. Developer Portal 기본 설치 링크 확인(유저 설치 시 "내 계정에 추가" 노출).
3. Vercel env `NEXT_PUBLIC_INVITE_URL` 갱신(permissions 포함), 유저 설치용 링크 env 추가 여부는 PR2에서 결정.

---

## 6.5 PR1 as-built (구현 완료 — 다음 세션 재조사 금지)

- **신규 헬퍼**: [maple_mate/bot/scope.py](../maple_mate/bot/scope.py) — `DM_WORKSPACE_ID(0)`·`resolve_scope`·`MSG_UNAVAILABLE`("이 명령은 서버 채널 또는 봇 DM에서 사용할 수 있어요.") + 그룹 생성자용 배선 상수 4개(`OPEN_INSTALLS`/`OPEN_CONTEXTS`/`GUILD_INSTALLS`/`GUILD_CONTEXTS`).
- **§3-1 스케치와 다른 점 1(의도적)**: DM 컨텍스트는 `is_user_integration()`일 때만 워크스페이스 0. 길드 설치 전용 봇 DM(서버 공유 유저, `_integration_owners={0:0}`)은 기존대로 거부 — ① 기존 DM 거부 테스트 3곳(test_scheduler_command·test_notification_toggle·test_mychar_commands)이 무수정 통과(회귀 0 제약), ② 서버 등록과 별개인 guild 0 데이터 오인 방지(결정 1과 정합). 판별 메서드 없는 가짜 Interaction 은 길드 설치로 간주(레거시 테스트 호환).
- **다른 점 2(부수 판단)**: `/경험치알림`도 미개방(길드 전용 명시) — 서버 리더보드 산출물이라 결정 3의 "리더보드 = 서버 개념 전제"에 포함시킴.
- **알림 게이트(§7 반영)**: `/스케줄러알림`·`/공지알림`·`/썬데이알림` = `GUILD_INSTALLS`(users=False) + `OPEN_CONTEXTS`(dms=True) — G0 통과 시 각 그룹의 `allowed_installs=GUILD_INSTALLS → OPEN_INSTALLS` 플립 한 줄씩만 남음(scope·거부 배선 완료). 위치: [scheduler/commands.py](../maple_mate/scheduler/commands.py) `setup`, [notification/commands.py](../maple_mate/notification/commands.py) `_alert_group`.
- **DM 채널대상 배선**: [notification/toggle.py](../maple_mate/notification/toggle.py) `handle_toggle` — DM 스코프에서 `대상:채널` 명시 = 거부 문구, `대상` 미지정 = **개인 구독으로 라우팅**(guild 0 채널행 생성 금지 — DM 채널을 공용 채널로 오발송 방지).
- **크론 포섭 판정(§3-3)**: ① 리마인더 — `subscriptions_at_hour`(scheduler/service.py, hour 만 필터)가 guild 0 자연 포함, 발송은 `send_dm(user_id)` → **무변경**. ② 공지·썬데이 — `dm_subscriber_users`(notification/service.py, kind 만 필터) distinct user → **무변경**. ③ exp_snapshot — `run_leaderboard_job`(leaderboard/broadcast.py)의 길드 열거 = exp 채널 ∪ exp DM 구독 길드라 guild 0 **크론 미포섭이 맞으나 보정 불필요**: `/내캐릭터 경험치`가 매 실행 멱등 `backfill`(D-1~D-8 빈 날만)로 자가 복구 — exp 채널 없는 일반 길드와 동일 경로. ④ 리더보드 방송 — guild 0 에 채널·구독 없음 → 자연 배제 확인.
- **테스트**: [tests/test_user_install.py](../tests/test_user_install.py) 18케이스 — resolve_scope 분기 6(4분기+길드설치DM+레거시가짜), 트리 배선 분류 4(개방 7·게이트 3·미개방 7 전수), DM 스코프 전달 배선 8. 전체 807 pass(기존 789 무수정)·ruff clean·사이트 드리프트 그린.
- **남은 것**: G0 스파이크 재실행(§3-4) → 통과 시 installs 플립 3줄 + §7 기록, PR2(사이트·문서), 운영자 포털 작업(§6).

---

## 7. G0 스파이크 결과 (기록란)

- **2026-07-03 1차 시도 — 판정 무효.** 스크립트 [spike/user_install_dm_spike.py](../spike/user_install_dm_spike.py) 작성·실행(메이트#9844, 앱 ID 1511936543013732452 = 부계정이 설치한 앱과 동일 확인). 부계정(457115703816880129)에게 DM **발송은 성공**했으나, 부계정이 봇과 '메이플 테스트' 서버를 **공유 중**이어서 유저 설치 효과와 구분 불가. 부계정의 해당 서버 탈퇴 후 재실행 필요(유저 설치 상태는 탈퇴와 무관하게 유지됨).
- **PR1 반영 지침(미판정 시)**: 알림 3종(`/스케줄러알림`·`/공지알림`·`/썬데이알림`)은 `allowed_installs(users=False)`로 두고 나머지를 개방한다 — G0 통과 시 데코레이터 플립 한 줄이 후속. DM 채널대상 거부 등 내부 배선은 PR1에서 미리 해둔다.
