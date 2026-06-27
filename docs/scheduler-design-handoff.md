# 핸드오프 — 스케줄러 알리미 임베드 디자인 개선 (이어서)

> **⚠️ 갱신(2026-06-27):** 아래 §2~§4의 **요약형은 폐기됨**. `/grill-with-docs` 그릴링 + 라이브 9캐릭 실 API 조사로 **필드 파생 카테고리 세분화**(퀘스트=완료/미완료·몬파=회수·길드=점수·보스=cycle별)로 **재설계·구현·라이브검증 완료**. 단일 출처 = **[ADR-0013](adr/0013-scheduler-field-derived-categories.md)** + [work-order §3](scheduler-work-order.md). 아래 §2~§4·§8(요약형/이미지카드 후보)는 **역사적 맥락**으로만 남긴다(현행 아님).
>
> **이전 상태(요약형, 폐기):** 기능 구현 완료 + 임베드 1차 디자인 개선(요약형) 완료. 기능 자체의 설계 근거는 [ADR-0012](adr/0012-scheduler-reminder-per-user-dm.md), 빌드 단위는 [scheduler-work-order.md](scheduler-work-order.md), API는 [docs/api/scheduler.md](api/scheduler.md).

## 0. 한 줄 목표

`/스케줄러`·스케줄러 알림 DM의 **임베드 가독성**을 계속 다듬는다. 데이터·전달 로직은 건드리지 않고 **표시(렌더)만** 손본다.

## 1. 지금 상태 (어디까지 됐나)

- **기능 전체 구현 완료**(브랜치 `feat/scheduler-reminder`, **미커밋**). 신규 `maple_mate/scheduler/` 패키지 + 마이그레이션 `b9e1d4c20f7a`(실 DB 가역성 검증). **617 테스트 그린**, ruff E/F/I+format clean, code-reviewer APPROVE.
- **임베드 1차 디자인 개선 완료(요약형).** 최초 안("완료·미완료 모두 한 줄씩 체크리스트")이 라이브 스크린샷에서 일일 점수형(수로/조사) `0/100` 도배로 **텍스트 벽 → 가독성 붕괴**라, 요약형으로 바꿨다(ADR-0012 결정5 as-built 개정).
- **⚠️ 아직 실제 디스코드에서 눈으로 못 봤다.** 개선은 **오프라인 렌더 + 단위테스트**로만 검증함. 다음 세션 첫 할 일 = **라이브로 띄워 실제 가독성 확인**(§3).

## 2. 현재 디자인 스펙 (as-built 요약형)

실데이터 렌더 결과:
```
🏆 챌린저스 칠한하약알 의 스케줄러 숙제        (본서버는 🗓, 라벨 없음)
Lv.276 · 챌린저스2                            (부제 = 레벨·월드)

📅 일일 · 1/11 완료  ▰▱▱▱▱▱▱▱
  🟡 스올미 추윤 조사 `64/100`                (진행 중만 게이지 개별 — 달성률 내림차순)
  ⚪ 남은 9개 · 레멜라트 최고의 조사 · 아콘카니 점령 작전 …   (미시작=now0 → 이름만 한 줄 접기)
  ✅ 완료 1개                                  (완료는 수만)
📆 주간 · 0/1 완료  ▱▱▱▱▱▱▱▱
  🟡 길드 콘텐츠 `3/7`
⚔️ 보스 · 8/14 처치  ▰▰▰▰▱▱▱▱
  ⬜ 스우(노말)                                (미처치=남은 보스 개별 — '뭘 잡아야 하나')
  ✅ 처치 1개
푸터: 21:00 기준 · NEXON Open API
```

**렌더 코드 위치(순수함수는 전부 service.py — 테스트 용이):**
- 임베드 조립: [broadcast.py](../maple_mate/scheduler/broadcast.py) `build_embed`(+`_subtitle`, `_content_field`, `_embed_title`).
- 순수 렌더 헬퍼: [service.py](../maple_mate/scheduler/service.py) — `content_section_value`(일일/주간 버킷), `boss_section_value`(보스), `content_counts`(완료/총), `progress_bar`(▰▱), `join_clamp`(미시작 한 줄), `strip_prefix`(앞 `[..]` 제거), `truncate`(18자 말줄임), `section_text`(줄-리스트 1024 클램프).
- 튜닝 상수(service.py 상단): `_NAME_MAX=18`, `_BAR_WIDTH=8`, `_NOT_STARTED_BUDGET=800`, `FIELD_LIMIT=1024`.
- 버킷 규칙: 진행중 `0<now<max`(또는 max0인데 now>0) / 미시작 `now==0` / 완료 `now>=max and max>0`. 보스 완료 = `complete_flag=="true"`.

## 3. 빠른 반복 루프 (디자인 만질 때 이걸로)

### (a) 오프라인 렌더 미리보기 — 디스코드 없이 즉시 (가장 빠름)
service/broadcast만 고치고 아래로 바로 눈 확인. 실 넥슨/DB/디스코드 불필요:
```bash
uv run python - <<'PY'
from datetime import datetime
from maple_mate.nexon.client import KST
from maple_mate.registration.realm import Realm
from maple_mate.scheduler.service import parse_homework
from maple_mate.scheduler.broadcast import build_embed
data = {  # 스크린샷 모사: 일일 점수형 다수(0/100) + 진행1 + 완료1
  'character_name':'칠한하약알','world_name':'챌린저스2','character_level':276,
  'daily_contents':[{'content_name':'무릉도장','registration_flag':'true','now_count':1,'max_count':1},
    {'content_name':'[일일/웨스트] 스올미 추윤 조사','registration_flag':'true','now_count':64,'max_count':100},
    *[{'content_name':f'[일일/웨스트] 조사{i}','registration_flag':'true','now_count':0,'max_count':100} for i in range(9)]],
  'weekly_contents':[{'content_name':'길드 콘텐츠','registration_flag':'true','now_count':3,'max_count':7}],
  'boss_contents':[{'content_name':'스우','difficulty':'노말','list_order_no':1,'registration_flag':'true','complete_flag':'false'},
    {'content_name':'검은 마법사','difficulty':'하드','list_order_no':2,'registration_flag':'true','complete_flag':'true'}],
  'weekly_boss_clear_count':8,'weekly_boss_clear_limit_count':14}  # ⚠️ 키는 _limit_count
e = build_embed(parse_homework(data), Realm.CHALLENGERS, datetime(2026,6,27,21,0,tzinfo=KST))
print('TITLE   :', e.title); print('SUB     :', e.description)
for f in e.fields:
    print('─'*54); print(f.name)
    for ln in f.value.split(chr(10)): print('  ', ln)
print('FOOTER  :', e.footer.text)
PY
```
> 한계: 모바일 줄바꿈·실제 폰트 폭·이모지 색은 디스코드에서만 보임 → 결국 (b)로 1회 확인.

### (b) 실제 디스코드에서 보기 (라이브)
컨테이너 코드는 **이미지에 구워짐**(볼륨 마운트 아님)이라 새 코드 = **재빌드** 필요. 시작 시 `alembic upgrade head` 자동 실행, `DEV_GUILD_ID` 설정돼 있어 슬래시 명령은 **dev 길드 즉시 동기화**.
```bash
docker compose up -d --build app
docker compose logs -f app   # "스케줄러 시작: …스케줄러 알리미(매시 :00)" + "슬래시 커맨드 길드 동기화" 확인
```
디스코드에서 (개인 키 등록된 계정으로) `/스케줄러`, `/스케줄러 모드:챌린저스`. DM은 `/스케줄러알림 켜기 시각:<다음 시>` 후 정각(:00) 발사.
- ⚠️ **재빌드는 작업트리 전체를 굽는다** — 무관한 이전 세션 미커밋 변경도 들어감. 스케줄러만 깨끗이 보려면 그것들 `git stash` 후 빌드.
- ⚠️ 한번 올리면 테이블 생성됨 → **구 코드로 되돌릴 땐 먼저** `docker exec maple-mate-app uv run --no-sync alembic downgrade c3d4e5f6a7b8`.
- DB DSN: 컨테이너=compose override, 호스트 실행 시 `.env`의 `localhost:5433`. live DB에 개인 키 보유 등록 5계정·캐릭터 9개 있음(테스트 가능).

## 4. 열린 디자인 개선 후보 (다음 세션 검토 대상)

라이브로 본 뒤 우선순위 정할 것. 모두 **표시 규칙만** 손대는 범위(ADR-0012 결정5 영역).

1. **`남은 N개 · …` 줄이 여전히 길다.** 미시작이 많으면(수로 9~12개) 한 줄이지만 모바일에서 3~4줄 래핑. 후보: 앞 K개만 + `…외 M개`(이름 budget 축소), 또는 이름 더 짧게.
2. **보스 미처치가 많으면** 개별 줄이 다시 벽이 될 수 있다. 후보: 난이도별/주차별 묶기, 또는 일정 수 넘으면 접기.
3. **점수형 vs 횟수형 구분.** 수로 `64/100`(점수)와 무릉 `1/1`(횟수)이 같은 게이지. 후보: 점수형은 `%`, 횟수형은 `n/m`.
4. **완료 항목 노출 정책.** 지금은 `완료 N개`(수만). 일부 유저는 ✅ 이름 확인을 원할 수 있음 → 소수면 이름 표기 옵션.
5. **색/강조.** 임베드 단색(브랜드 오렌지). 후보: 전부 완료 시 초록, 남은 게 있으면 오렌지 등 상태색.
6. **진행바 문자/폭.** `▰▱` 8칸 — 모바일 폭 확인 후 6칸/다른 글리프 검토.
7. **부제 정보량.** 현재 `Lv·월드`. 전체 진척(예: `오늘 12개 중 3개 완료`) 한 줄 추가 검토.
8. **(큰 결정) PIL 이미지 카드(Option C).** 임베드 텍스트의 한계(열 정렬 불가)를 넘으려면 leaderboard/bitik처럼 PNG 표 렌더. 가독성 최상이나 노력 큼 + ADR-0012 결정5 재개정 + 모바일 글자 작아짐 트레이드오프. **임베드 한계가 명확해지면** 그때 검토.

> 직전 세션에서 사용자 선택지 3안(요약형/정돈형/이미지카드) 중 **요약형** 채택. 8번(이미지카드)은 보류였음.

## 5. 지켜야 할 제약 (건드리지 말 것 / 만져도 되는 것)

- **잠금(ADR-0012 결정 1~4,6,7):** per-user DM 구독 모델, `/스케줄러`+`/스케줄러알림` 분리, realm별 독립, 매시 정각 cron, 온디맨드·DM **빌더 공유**(`build_homework`/`build_embed`), 조용한 스킵+fail-fast 가드. → 디자인 작업이 이걸 깨면 안 됨.
- **잠금(결정 5 중 불변):** `registration_flag=="true"` 필터, 일일/주간/보스 3섹션, **콘텐츠명 하드코딩 금지**(자유 문자열). `strip_prefix`는 일반 `[..]` 제거라 무위반.
- **유연(결정 5 표시 규칙):** 버킷·게이지·진행바·접기·색·부제 등 **렌더 디테일은 자유롭게** 개선 가능. 바꾸면 ADR-0012 결정5 as-built 절 + work-order §3 동기화.
- 데이터 계약: 오늘=`date` 무지정(명시 시 400), `registration_flag`/`complete_flag`는 **문자열** `"true"`, 정수는 `weekly_boss_clear_limit_count`(끝 `_count` 주의). 4xx 흡수.

## 6. 파일 맵

| 역할 | 경로 |
|---|---|
| 임베드 조립(여기서 디자인) | [broadcast.py](../maple_mate/scheduler/broadcast.py) `build_embed` |
| 순수 렌더 헬퍼(여기서 디자인) | [service.py](../maple_mate/scheduler/service.py) 렌더링 섹션 |
| 명령(온디맨드/구독) | [commands.py](../maple_mate/scheduler/commands.py) |
| 파싱·DTO·DB·키해석(건들 일 적음) | [service.py](../maple_mate/scheduler/service.py) 파싱/구독 섹션 |
| cron 등록 | [notification/scheduler.py](../maple_mate/notification/scheduler.py) |
| 모델·마이그레이션 | [models.py](../maple_mate/scheduler/models.py), `alembic/versions/b9e1d4c20f7a_*.py` |
| 테스트 | tests/test_scheduler_{service,embed,command,job}.py |
| 디자인 단위테스트(주로 여기 갱신) | [test_scheduler_service.py](../tests/test_scheduler_service.py)(렌더 헬퍼)·[test_scheduler_embed.py](../tests/test_scheduler_embed.py)(필드 구조) |

## 7. 품질 게이트 (커밋/머지 전)

```bash
uv run pytest -q -m "not live"                       # 전체(현재 617 그린)
uv run ruff check maple_mate/scheduler/ tests/test_scheduler_*.py
uv run ruff format --check maple_mate/scheduler/ tests/test_scheduler_*.py
```
디자인 바꾸면 `test_scheduler_embed.py`(필드 name/value 단언)·`test_scheduler_service.py`(렌더 헬퍼)도 같이 갱신. CI는 `ruff format --check .` 전체 적용이니 만진 파일 포맷 필수.

## 8. 주의

- **미커밋 더미:** `main`/이 브랜치 작업트리에 이전 세션의 무관한 미커밋 변경(leaderboard·CONTEXT·railway 등) 잔존 — 손대지 말 것. 커밋 시 **스케줄러 관련 파일만** 골라 담기.
- 스케줄러 기능 자체의 **남은 운영 작업**: 커밋·PR·CI·배포·라이브 확인(실 넥슨 DM 1회). 디자인 확정 후 함께 처리.

## 9. 참조

- [ADR-0012](adr/0012-scheduler-reminder-per-user-dm.md) — 결정 9건 + 결정5 as-built(요약형) 개정.
- [scheduler-work-order.md](scheduler-work-order.md) §3 — 표시 규약(요약형).
- [docs/api/scheduler.md](api/scheduler.md) — API 필드·실호출 회귀(오늘=무지정 등).
- 하우스 스타일 렌더 레퍼런스: [bot/leaderboard_image.py](../maple_mate/bot/leaderboard_image.py)·[bot/bitik_card.py](../maple_mate/bot/bitik_card.py)(PIL 카드 갈 경우).
