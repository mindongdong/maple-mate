# 작업지시서 — `/캐릭터목록` 관리 허브: 삭제 · 대표 자동 복귀 · 키 삭제 (PR3a)

> **근거 결정:** [ADR-0023](adr/0023-character-management-hub.md)(본 작업으로 작성).
> **결정 출처:** 2026-10-14 세션. 사용자 결정: ① 명령 구조 = `/캐릭터목록`을 허브로 확장(새 명령 없음) ② 전체 등록 해제는 이번 범위에서 제외 ③ 자동(주기) 동기화는 하지 않음.
> **후속:** PR3b = 키 기반 계정 동기화([account-character-import-work-order.md](account-character-import-work-order.md)) — 이 허브에 `🔄 계정 동기화` 버튼으로 추가.
> **상태:** 구현 완료(PR #73, 브랜치 `claude/loving-brahmagupta-tyordi`). PR #74(ADR-0024) 머지·이전 스크립트 실행 후 main 위로 재배치하고 키 삭제 시 계정 이력 캐시 삭제를 추가.

---

## 0. 한 줄 목표

등록 캐릭터·개인 키를 봇 안에서 되돌릴 수 있게 한다. `/캐릭터목록` 결과에 삭제·대표 변경·키 삭제 버튼을 붙인다.

## 1. 확정 결정

ADR-0023 결정 1~8. 요약:
- 버튼 3개: `🗑️ 캐릭터 삭제`(여러 개 선택 → 확인) · `👑 대표 변경`('자동' 포함, 즉시) · `🔑 키 삭제`(확인).
- 캐릭터 삭제는 대표였으면 자동 복귀하고, 경험치 스냅샷은 유지한다. 전부 지우면 스케줄러알림 구독도 해제한다.
- 키 삭제는 그 계정의 이력 캐시(ADR-0024)와 스케줄러알림 구독도 함께 지운다. 캐릭터는 유지한다.
- 캐릭터·키가 모두 없으면 View 없이 기존 안내만 보낸다.

## 2. As-built

- **서비스** ([registration/service.py](../maple_mate/registration/service.py)):
  - `delete_characters(sf, guild_id, uid, ocids) -> (list[닉], 구독 해제됨)` — 본인 것만 삭제하고 대표 포인터를 정리한다. 전부 지우면 스케줄러알림 구독도 해제한다(한 트랜잭션).
  - `reset_representative(sf, guild_id, uid)`
  - `remove_personal_key(sf, cipher, guild_id, uid) -> (키 있었음, 구독 해제됨)` — 그 계정(키 식별자, ADR-0024)의 이력 캐시도 삭제 — `scheduler.models.SchedulerSubscription`을 직접 지운다. scheduler 서비스는 registration을 import 하므로 모델만 import 해 순환을 피한다.
- **전달** ([registration/commands.py](../maple_mate/registration/commands.py)):
  - `character_list_embed(characters, has_key, note)`(순수)
  - `CharacterManageView` — 허브 → 삭제 선택 → 삭제 확인 / 대표 선택 / 키 삭제 확인. 화면 전환은 즉시 교체(`_show`), DB 작업은 `_act`(진행 중 클릭 무시 → 전체 비활성으로 먼저 응답 → 작업·재조회 → 허브로 결과 반영, 오류 시 재시도 안내). Select 값은 `interaction.data["values"]`에서 읽는다.
  - `handle_character_list`가 View를 부착한다(`followup.send(..., wait=True)`로 메시지 핸들을 보관).
- **명령 description**: "등록 캐릭터·대표·키를 보고 삭제·대표 변경·키 삭제를 합니다 (본인만 보임)."
- **사이트**: `site/data/commands.json` 캐릭터목록 summary·tip을 갱신했다(명령 추가 없음 → 드리프트 가드 무영향).
- **문서**: ADR-0023, CONTEXT.md "등록" 항목, PR3b 작업지시서 상태 줄.
- **사이트 개인정보 페이지**: "데이터 철회"에 키·캐릭터 직접 삭제와 남는 데이터(경험치 스냅샷 90일, 이력 캐시 400일)를 추가.
- **리뷰 반영(PR #73)**: 연타·응답 지연 대비(`_act`), 전부 삭제 시 스케줄러알림 구독 해제, Select 값 출처, 개인정보 페이지. 최초 등록 캐릭터 삭제 시 이력 캐시 콜드 재조회는 선행 머지된 PR #74(ADR-0024, 캐시 이름표 = 키 계정 식별자)로 해소. 재배치 후 키 삭제 시 계정 이력 캐시 삭제를 추가. 2차 리뷰 반영: 작업 성공 후 화면 갱신만 실패한 경우 안내 분리, 작업 중 화면 전환 클릭 무시.
- **테스트**: [tests/test_character_manage.py](../tests/test_character_manage.py)(22건) — 서비스 SQL·범위·반환값, View 화면 전환·확인 단계·결과 문구·연타·오류 복구·타임아웃, 핸들러의 View 부착 조건.

## 3. 배포 후 라이브 확인

- [ ] `/캐릭터목록` → `🗑️ 캐릭터 삭제` → 2개 선택 → `2개 삭제` → 목록에서 사라지고 결과 줄 표시
- [ ] 대표 캐릭터 삭제 → 남은 캐릭터 중 최고 레벨이 👑로 표시
- [ ] `👑 대표 변경` → `자동` → 최고 레벨이 대표로 표시
- [ ] `🔑 키 삭제` → 확인 → "개인 키: 미등록", 스케줄러알림을 켜 둔 경우 "구독도 해제" 안내
- [ ] 봇 DM에서도 같은 흐름(DM 워크스페이스 데이터만 영향)
