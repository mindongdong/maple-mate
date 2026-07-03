# 작업지시서 — 스케줄러 숙제 PNG 카드 전환

> **근거 결정:** 표시 규칙 [ADR-0013](adr/0013-scheduler-display-redesign.md)(카테고리·todo-first — **표현 매체만 본 작업으로 개정**, 정보 구조는 불변), 카테고리 필터 [ADR-0014](adr/0014-scheduler-category-filter.md), DM 통일 [ADR-0017](adr/0017-notification-unification.md).
> **하우스 스타일 레퍼런스:** [my-character-work-order.md](my-character-work-order.md), [scheduler-category-filter-work-order.md](scheduler-category-filter-work-order.md).
> **그릴링 출처:** `/grill-me` 세션(2026-07-03). 사용자 문제 제기: 스케줄러 숙제 임베드가 "아무리 노력해도 안 예쁘고 텍스트라 한계" — 사이트 목업 수준의 디자인을 원함. PNG 카드 vs Components V2 시안 2종을 실제 렌더링해 비교 후 **PNG 카드(A안) 확정**.
> **상태:** 구현 완료 — 봇 PR1 [#48](https://github.com/mindongdong/maple-mate/pull/48)(squash `d2ccea7`)·사이트 PR2 [#49](https://github.com/mindongdong/maple-mate/pull/49)(squash `c6e4ae9`) 머지. 남은 것: 봇 배포 → 실 디스코드 눈 확인(§7).

---

## 0. 한 줄 목표

`/스케줄러`(온디맨드 ephemeral)와 매시 DM 알림이 보내는 숙제 메시지의 **표현 매체를 임베드 → PIL 렌더링 PNG 카드로 전환**한다. 카테고리 파생·todo-first 정렬·필터(excluded)·상태색·챌린저스 뱃지 등 **표시 규칙과 기능은 전부 그대로 보존**(정보 손실 0). 페치·구독·파싱 로직은 한 줄도 바꾸지 않는다.

---

## 1. 확정 시안 (이 카드가 곧 스펙)

- **시안 파일**: `spike/design_out/scheduler_A_png_card.png` (손바 예시 데이터, 2026-07-03 렌더)
- **시안 생성 스크립트**: [spike/design_scheduler_mockups.py](../spike/design_scheduler_mockups.py) — 레이아웃 수치·팔레트의 출발점. 렌더러 구현 후 참고용 존치.

레이아웃(위→아래):

| 요소 | 내용 |
|---|---|
| 헤더 | 캐릭터명(오렌지 볼드 大) + "의 오늘 숙제" · 우측 `Lv.287 · 크로아`(muted). 챌린저스 캐릭터는 이름 옆 **`챌린저스` pill 뱃지**(현행 🏆 제목 프리픽스의 이관, ADR-0017) |
| 진행 요약 | `남은 숙제 N` 볼드 + 우측 `D/T 완료` + 풀폭 라운드 진행바 |
| 섹션 | 색 액센트 바(小) + 섹션명 볼드 + 우측 카운트(액센트색). 순서·구성은 현행 build_embed 그대로: 일일 퀘스트 → 일일 콘텐츠 → 주간 퀘스트 → 주간 콘텐츠 → 길드 콘텐츠 → 주간 보스(+처치 c/12) → 일간 → 월간 → 기타 보스 |
| 항목 행 | **드로잉 체크박스**(미완=회색 아웃라인 / 완료=그린 채움+체크) + 이름. 완료 항목은 텍스트 흐림(FAINT). 회수형 진행중은 우측 미니 진행바+`n/m`. 길드는 체크박스 없이 이름+점수(골드 볼드 우측) |
| 보스 | **2컬럼 그리드**(높이 절약, 완료 밀도 결정 4). 이름(난이도) 규칙 현행 유지 |
| 푸터 | 구분선 + `HH:00 기준 · NEXON Open API`(현행 format_footer+append_source 문자열 그대로) |

팔레트·폰트는 [bitik_card.py](../maple_mate/bot/bitik_card.py)/[table_image.py](../maple_mate/bot/table_image.py)와 공유(`_load_fonts`, 다크 패널 `#2b2d31`, 오렌지 `(255,156,56)`). **이모지 미사용**(전부 드로잉) — 리눅스 컨테이너에 이모지 폰트 불필요.

---

## 2. 확정 결정 (그릴링)

1. **매체 = PNG 카드.** Components V2(디스코드 Container)와 실렌더 시안 비교 후 선택 — CV2는 구분선·헤딩까지가 한계라 "텍스트라 안 예쁘다"는 근본 불만을 해소 못 함. 하이브리드(CV2+PNG) 기각.
2. **발송 형태 = 파일 단독 + content 한 줄**(임베드 셸 없음). 임베드 테두리 없이 이미지가 곧 메시지. `content`는 푸시 알림 미리보기 담당 — 예: `손바 — 남은 숙제 6개 (16/22 완료)`. 제목·부제·상태색·푸터는 전부 PNG 내부로 이관.
3. **온디맨드 `/스케줄러`·DM 알림 둘 다 PNG.** 산출물 빌더 공유 구조(현행 build_homeworks→build_embed) 유지 — 표현 경로 1개.
4. **완료 항목 밀도 = A안 그대로.** 완료 항목도 전부 나열(기능 보존 — "뭐 깼는지" 확인 가능), 보스만 2컬럼 압축 + 완료 흐림 처리. "완료 N개 한 줄 접기" 기각(정보 손실).
5. **웹사이트 반영 포함, 별도 PR.** 봇 PR 머지 후 `render_demo_shots.py`에 스케줄러 샷 추가 → `SchedulerEmbed` CSS 목업을 진짜 렌더러 PNG로 교체(드리프트 0 — 이번 불만의 원인이었던 "사이트≠실물"을 구조적으로 해소).

**부수 결정(에이전트 판단, 그릴링에서 고지됨):**

- **상태색 이관**: 임베드 컬러바(전부완료 그린/잔여 오렌지, ADR-0013) → PNG 진행바·잔여 카운트 색으로. 전부 완료 시 진행바 그린 + `남은 숙제 0` 자리에 완료 표시.
- **렌더러 위치** = `maple_mate/bot/scheduler_card.py` (이미지 렌더러 관행). 순수 함수(`Homework` + `excluded` + `now` → PNG bytes), 발송부에서 `asyncio.to_thread` 호출(leaderboard_image 규약).
- **입력은 구조화 데이터 직접 소비**: service의 마크다운 문자열 함수(`content_field_value`·`guild_field_value`·`boss_cycle_value`·`section_text`)는 임베드 전용이므로 렌더러가 `ContentItem`/`BossItem`을 직접 받는다. 분류·정렬 순수 함수(`by_category`·`bosses_by_cycle`·`field_counts`·`boss_counts`·`visible_remaining`·`is_empty_filtered`·todo-first 정렬 규칙)는 그대로 재사용.
- **이름 절단**: 현행 `truncate(18자)`는 임베드 모바일 줄바꿈 대응이었음 → PNG에선 **픽셀 폭 기준 말줄임**으로 전환(카드 폭 내 최대 활용).
- **가드·확인 메시지는 임베드 유지**: 미등록·키없음·빈숙제·all-off 안내와 `/스케줄러알림 켜기/끄기` 확인은 현행 텍스트 임베드 그대로(카드화 대상 아님).
- **ADR 신규 작성 없음**(ADR 운용 선호 — 취향 기반 매체 전환). ADR-0013 상단에 "표현 매체 PNG 전환(본 작업지시서 링크)" 추기 한 줄만.

### 비목표

숙제 데이터·페치·파싱·구독 스키마 변경, 카테고리 파라미터·필터 의미 변경, 다른 명령(경험치·비틱 등)의 매체 변경, 숙제 완료 알림 등 신규 기능, CV2 도입.

---

## 3. 배경·코드 현황 (다음 세션이 재조사하지 말 것)

- **표시 진입점 2개, 빌더 공유**: 온디맨드 [scheduler/commands.py:64](../maple_mate/scheduler/commands.py#L64) `handle_scheduler`(캐릭터당 ephemeral followup 1개) · 매시 잡 [scheduler/broadcast.py:203](../maple_mate/scheduler/broadcast.py#L203) `run_scheduler_reminder_job`(캐릭터당 DM 1개). 둘 다 `build_homeworks`(페치, 불변) → `build_embed`([broadcast.py:96](../maple_mate/scheduler/broadcast.py#L96), **교체 대상**).
- **`send_dm`은 이미 `**send_kwargs`** ([bot/dm.py](../maple_mate/bot/dm.py)) — `content=`·`file=` 그대로 지원, 수정 불필요. `interaction.followup.send`도 동일.
- **`discord.File`은 BytesIO 소비 1회용** — 발송마다 fresh 생성([leaderboard/broadcast.py:52](../maple_mate/leaderboard/broadcast.py#L52) `to_files` 전례). 스케줄러는 캐릭터당 PNG가 다르므로 자연 충족.
- **표시 규칙의 현행 소스**: 제목 뱃지 `_embed_title`(챌린저스 분기, [broadcast.py:30](../maple_mate/scheduler/broadcast.py#L30)) · 부제+상태색 `_subtitle`/`_DONE_COLOR` · 필드 구성 `build_embed` 본문 · todo-first 정렬 [service.py:347](../maple_mate/scheduler/service.py#L347)~414(`content_field_value` 등 — 진행중 게이지 내림차순 → 미완 → 완료 순서 규칙을 렌더러로 이식).
- **기존 PNG 렌더러 어휘**: [bitik_card.py](../maple_mate/bot/bitik_card.py)(세로 스택 카드·`_Seg`/`_Line` 모델·동적 높이) · [table_image.py:94](../maple_mate/bot/table_image.py#L94) `_load_fonts`(macOS AppleSDGothic → 리눅스 NanumGothic 폴백).
- **프로덕션 폰트**: Dockerfile에 `fonts-nanum` 설치됨. 단 `_FONT_CANDIDATES`의 Nanum 경로는 reg/bold 같은 index 0 — **볼드가 프로덕션에서 노멀로 렌더**. 카드가 볼드를 많이 쓰므로 `/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf`를 볼드 후보로 추가 권장(기존 렌더러들도 함께 좋아짐, 회귀 없음).
- **테스트 현황**: [tests/test_scheduler_embed.py](../tests/test_scheduler_embed.py)(임베드 조립 — 렌더러 테스트로 대체) · [test_scheduler_command.py](../tests/test_scheduler_command.py)/[test_scheduler_job.py](../tests/test_scheduler_job.py)(가짜 Interaction·DM 캡처 — `embed=` 단언을 `content=`+`file=` 단언으로 갱신) · 이미지 테스트 관행 [test_bitik_card.py](../tests/test_bitik_card.py)(PNG bytes 생성·치수·변형 케이스).
- **QA 하네스**: [spike/qa_harness.py](../spike/qa_harness.py) + `spike/qa_scheduler.py` — 가짜 Interaction+실 Deps로 실호출·PNG 직접 열람 가능(프리런치 QA에서 검증된 경로).
- **사이트**: [site/components/Embeds.tsx:48](../site/components/Embeds.tsx#L48) `SchedulerEmbed`(CSS 목업, 교체 대상) — getting-started·commands MDX에서 사용. 진짜 PNG 파이프라인은 [site/scripts/render_demo_shots.py](../site/scripts/render_demo_shots.py) → `site/public/shots/` 커밋 방식(Vercel 빌드에 파이썬 불필요).

---

## 4. 구현 순서 (봇 PR1)

> 각 단계 끝에 검증. 커밋은 논리 단위 분리(하우스 관행).

**1) 폰트 볼드 후보 추가 (선행 소형 커밋)**
`table_image._FONT_CANDIDATES`에 NanumGothicBold 경로 추가(reg=NanumGothic, bold=NanumGothicBold). → 검증: 기존 이미지 테스트 그린(로컬 macOS는 경로 불변).

**2) 렌더러 신규 `bot/scheduler_card.py` (TDD)**
`render_scheduler_card(hw: Homework, now: datetime, excluded: frozenset[str]) -> bytes` 순수 함수 + `card_summary_line(hw, excluded) -> str`(content 한 줄). §1 레이아웃 구현. excluded 묶음 생략·visible_remaining 재집계·빈 카테고리 생략 규칙은 build_embed와 동일.
→ 검증: `tests/test_scheduler_card.py` — 손바 픽스처(시안 데이터) 렌더 성공·치수, 전부완료(그린)·챌린저스 pill·excluded 생략·진행중 게이지 정렬·빈 필드 생략·긴 이름 말줄임 케이스. 눈 확인용 PNG는 qa 하네스로.

**3) 발송부 교체 `scheduler/broadcast.py`·`commands.py`**
`build_embed` → `build_card_payload(hw, now, excluded) -> (content, bytes)` 어댑터로 교체. `handle_scheduler`는 `followup.send(content=…, file=…, ephemeral=True)`, 잡은 `send_dm(bot, uid, content=…, file=…)`. 렌더는 `asyncio.to_thread`. 가드 메시지는 불변.
→ 검증: test_scheduler_command·test_scheduler_job 갱신 후 그린.

**4) 임베드 전용 코드 정리**
`build_embed`·`_embed_title`·`_subtitle`·`_content_field` 계열 삭제, service의 임베드 문자열 함수(`content_field_value`·`guild_field_value`·`boss_cycle_value`·`section_text`·`truncate` 18자) 중 렌더러가 대체한 것 삭제(본 변경이 만든 orphan만 — 다른 곳 사용 여부 grep 선행). test_scheduler_embed.py 삭제·대체.
→ 검증: 전체 pytest·ruff 그린.

**5) QA·라이브 확인**
qa_scheduler 하네스로 실 데이터 카드 PNG 열람(본서버+챌린저스 캐릭 혼재 케이스). 머지·배포 후 실 디스코드에서 `/스케줄러` 1회 + DM 알림 1회 눈 확인.

## 5. 사이트 반영 (PR2 — 봇 PR 머지 후)

1. `render_demo_shots.py`에 `build_scheduler()` 추가 — 데모 캐스트(홍길동전사) 가짜 Homework 픽스처로 실제 렌더러 호출 → `site/public/shots/scheduler.png`.
2. `Embeds.tsx`의 `SchedulerEmbed` 제거, 사용처(getting-started·commands MDX)를 `<img>` 교체 — 기존 shots 명령들과 동일 프레임. embeds.css의 스케줄러 전용 클래스 정리.
3. 랜딩 Pillars의 스케줄러 미니샷 문구·모양이 새 카드와 어긋나지 않는지 점검(필요 시 카피만 미세조정).
→ 검증: `npm run build`·드리프트 테스트 그린, 라이트/다크 눈 확인.

**As-built (PR #49, 2026-07-03):** 3항목 계획대로 구현. ①`build_scheduler()` — 홍길동전사 픽스처는 사이트 정본값 **Lv.275**·크로아(시안의 287 아님), `shots/scheduler.png` 812×1416, 커밋 PNG=스크립트 출력 byte-identical 검증 ②`SchedulerEmbed`·orphan CSS 제거(`.mm-todo-sub`는 알림·등록 임베드 사용으로 존치), commands 사용처 `shot()` 교체 ③Pillars 카피 2줄 조정 — 길드는 점수제(체크박스 없음)라 `지하수로 ✅ 완료`→`몬스터파크 ✅ 완료`, `주간 보스 5/12`→`8/12 처치`. 빌드·드리프트·ruff·CI 전부 그린, 코드리뷰 승인(블로킹 0).

## 6. 리스크·미결

- **리눅스 폰트 렌더 차이**: 시안은 AppleSDGothic 기준 — 배포 전 qa 하네스 PNG를 도커(리눅스)에서도 1회 뽑아 자간·볼드 확인 권장.
- **항목 수 상한**: 숙제 30개+ 캐릭터도 세로로 늘어날 뿐(동적 높이) — 디스코드 이미지 제한(8MB/최대 변)과는 거리가 큼. 별도 상한 불필요.
- **접근성·복사 트레이드오프**: 숙제 이름 텍스트 복사 불가(그릴링에서 고지·수용). content 한 줄이 검색 가능한 최소 텍스트를 담당.

## 7. 완료 기준

- [x] `/스케줄러`·DM 알림이 §1 시안과 동일한 PNG 카드로 발송(온디맨드 ephemeral 유지) — PR #48
- [x] 카테고리 필터·전부완료 그린·챌린저스 뱃지·todo-first 정렬·빈 카테고리 생략 전부 카드에서 동작(테스트로 고정) — QA 하네스 실데이터 14시나리오 포함
- [x] 전체 pytest·ruff 그린, 임베드 잔재 코드 0 — 800 pass
- [ ] 실 디스코드 DM·온디맨드 각 1회 눈 확인 — **봇 배포 후 운영자 작업**(리눅스 폰트 볼드·자간 포함)
- [x] (PR2) 사이트 스케줄러 예시 = 진짜 렌더러 PNG — PR #49
