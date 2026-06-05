# Phase 2 렌더/UX 이터레이션 핸드오프 — `/유니온` · `/아이템` · `/스펙` 출력 개선

> **목적:** Phase 2 읽기전용 스펙류 명령의 **출력(렌더) UX를 계속 피드백하며 다듬기** 위한 단일 지침서.
> 기능 구현·스코프·합격기준은 [phase2-handoff.md](./phase2-handoff.md)에 있고, **이 문서는 렌더 계층(표/카드/이미지/태그/정렬)** 의
> 현재 상태 + **바꾸는 법(knobs)** + 남은 피드백 항목만 담는다. (중복 금지 — 기능은 phase2-handoff 참조.)
>
> **원칙:** 디스코드는 네이티브 표가 없고 한글 텍스트표 정렬을 보장 못 해서 **수치 비교는 PNG 이미지 표**로 보낸다.
> 이미지는 픽셀 고정이라 안 깨지지만 그 안엔 클릭 태그가 안 들어가므로 **닉↔주인 태그는 이미지 위 '범례'(임베드 설명)** 로 분리한다.

## 0. 먼저 읽을 것 (SSOT)

| 문서 | 역할 |
|---|---|
| [phase2-handoff.md](./phase2-handoff.md) | 기능/스코프/Spike0 제약/합격기준(이 문서의 상위) |
| [maple-discord-bot-design.md](../maple-discord-bot-design.md) | §3.1 `/스펙` · §3.2 `/아이템` · §3.3 `/유니온` · §7 횡단(임베드·부분성공·푸터) |
| [docs/api/character.md](./api/character.md) · [union.md](./api/union.md) | 응답 필드(전투력·HEXA·유니온·챔피언) |
| [architecture.md](./architecture.md) | DDD — service(전달-무관) / commands(discord 어댑터) 경계 |

## 1. 현재 코드 상태 (한눈에)

- **브랜치:** `phase-2-spec-commands`.
- **커밋됨(Phase 2 본구현, 2커밋):** `82cbfdc` 공유 기반 · `ccab9c7` 3개 명령.
- **미커밋(이 렌더/UX 이터레이션, working tree):** `bot/{comparison,core,table_image(신규),item_card(신규)}.py`·`character/{commands,service,item}.py`·`union/commands.py`·`nexon/client.py`(**fetch_image+캐시**)·`pyproject.toml`(**Pillow 추가**)·`uv.lock`·테스트(`test_comparison`·`test_character_{item,spec}`·`test_nexon_client`·`test_item_card`(신규)). **`uv run pytest -q` = 135 통과.**
  - → 만족 시 **"렌더/이미지 표·아이템 카드·태그·랭킹" 한 논리 커밋**으로 정리 예정(아직 안 함).
- ⚠️ **레포 루트에 stray PNG**(`spec*.png`·`union.png`·`스크린샷 *.png`·`아이템{1,2,3}.png`)가 있다 — 사용자가 받은/캡처한 파일. **커밋 금지.** `.gitignore`에 `/*.png`+`스크린샷*.png` 있어 자동 제외됨(확인 완료).
- **봇 실행 중**(Mac Mini). 운영 메모는 §9. **DEV 길드 등록 캐릭:** 손바·네벨루크·라딘라면·점프투파이썬.

## 2. 명령별 현재 렌더 모드

| 명령 | 단일(1명) | 비교(2명+) |
|---|---|---|
| **`/유니온`** | 카드 1필드 + 유저 태그 | **PNG 정렬표** · 행=캐릭터 · **유니온 레벨 내림차순 + `순위` 컬럼** · 컬럼 `순위·캐릭터·유니온·아티팩트·챔피언` |
| **`/스펙`** | 상세 카드(5항목: 전투력·어빌리티·심볼·HEXA코어·HEXA스탯) + 태그 | **PNG 정렬표** · 행=캐릭터 · **전투력 내림차순 + `순위`** · 컬럼 `순위·캐릭터·전투력·스킬·마스터리·강화·공용·스탯 코어 I·II·III`(코어·스탯=칸 그리드, 스탯 첫칸 볼드) · **어빌리티·심볼 제외** |
| **`/아이템`** | **PNG 아이템 카드 1장** + 범례 태그 | **PNG 카드 세로 스택**(`item_card.render_item_cards`, 1인 1카드 위→아래) + 범례 태그 — *수치표가 아니라 게임 툴팁풍 카드(아이콘+이름+뱃지+옵션)* |

- 공통: 모두 `defer` → 성공분 렌더 + 실패분 `⚠️ 조회 실패` 묶음 필드(`attach_failures`), 전체 실패 시 에러 임베드, 푸터=`data_footer`(무지정 호출 → "최신 기준").
- **태그(@닉):** 이미지(표·아이템 카드)는 위 범례(`owner_legend`). **핑(알림)은 안 울림**(봇 전역 `allowed_mentions=none`).
- **`/아이템` 카드 구성:** 아이콘(잠재 등급색 프레임·정수배 NEAREST 확대) + 이름 + 뱃지(`★스타포스`·잠재등급·에디등급) + 줄(`잠재`·`에디`=같은 옵션 합산, `추옵`, `작`=주문서 횟수+`item_etc_option` 스탯). 미착용=`미착용` 카드. **환산 점수/우열 판정 없음**(§10).

## 3. 렌더 아키텍처 (어디에 뭐가 있나)

```
maple_mate/bot/
  table_image.py   # ★ PNG 표 렌더(순수). render_table_image(headers, rows, *, aligns)
  item_card.py     # ★ PNG 아이템 카드 렌더(순수). render_item_cards([ItemCard]) — 세로 스택
  comparison.py    #   비교 공유 헬퍼(아래) — discord 어댑터 계층
  core.py          #   allowed_mentions=none(핑 차단) + 명령 setup 등록
  embeds.py        #   make_embed · format_footer · defer · EmbedPaginator
union/{service,commands}.py        # /유니온
character/{service,commands,item,equipment_slots}.py  # /스펙 · /아이템
```

**`bot/comparison.py` 공개 함수:**
- `resolve_targets(session_factory, guild_id, members)` → `(targets, 미등록_outcomes)`
- `image_message(title, png, targets, *, footer, outcomes, filename)` → `(embed, file)` — **렌더된 PNG 공통 메시지 빌더**(범례+이미지+실패필드). 표·아이템 카드 공용.
- `table_image_message(title, headers, rows, targets, *, aligns, footer, outcomes, filename)` → `(embed, file)` — 표 렌더 후 `image_message` 위임
- `owner_legend(targets)` → `"👤 닉 @주인 · …"` · `mention(target)` → `<@id>`
- `truncate_display(text, max_width)` / `_display_width` — 표시 폭(한글=2) 자르기
- `data_footer(raw_date)` · `attach_failures(pages, outcomes)` · `all_failed_embed(...)`
- `field_pages(title, fields, *, per_page, footer)` + `respond_with_pages(...)` — 카드 페이지 헬퍼(현재 미사용 — /아이템이 PNG 카드로 전환. 다인 분할 필요 시 재활용 가능)

**`bot/item_card.py`:** `render_item_cards([ItemCard]) → PNG bytes`. `ItemCard`(label·found·item_name·starforce·icon_png·potential·additional·add_option·upgrade·upgrade_stats) + `CardPotential(grade, options)`. 폰트는 `table_image._load_fonts` 공유, 색/치수/등급색은 모듈 상수(§7). 아이콘 bytes 는 호출부가 `NexonClient.fetch_image`(메모리 캐시)로 받아 주입(전달-무관 유지).

**`bot/table_image.py`:** `render_table_image(headers, rows, *, aligns)` → PNG bytes. aligns ∈ `left/right/center`. 색/폰트/크기는 모듈 상수(§7).

## 4. 디스코드 렌더 제약 (왜 이렇게 했나 — 바꾸기 전 필독)

1. **네이티브 표 없음 + 한글 텍스트표 깨짐:** 코드블록 monospace도 한글은 숫자 2칸이 *정확히* 아니고, 임베드 너비로 줄바꿈됨 → **정렬 보장 불가**. 그래서 수치 비교는 **PNG 이미지**(픽셀 고정).
2. **이미지 폭:** 디스코드는 임베드 이미지를 폭에 맞춰 **축소 표시**(클릭 시 원본). 컬럼이 많으면 축소돼 작게 보인다 → **컬럼/문자수 줄이면 가독성↑**.
3. **멘션:** `<@id>`는 임베드 본문/필드값에선 클릭 태그, **코드블록/이미지 안에선 불가** → 태그는 항상 텍스트 영역(범례/필드)에. 임베드 멘션은 기본 핑 안 함 + 전역 `none`.
4. **임베드 한도:** 필드값 1024·임베드 총 6000·필드 25개·설명 4096. (이미지는 첨부라 이 한도와 별개.)

## 5. Spike(실호출) 발견 — 렌더에 직접 영향

- **HEXA 코어:** 캐릭터당 **13개** = `스킬 코어`2 + `마스터리 코어`4 + `강화 코어`4 + `공용 코어`3, **API 순서가 직업 무관 동일**(제로·팔라딘·윈드브레이커 실측). → 비교는 **타입별로 레벨만 묶어** 표기(`마스터리 29 / 9 / 17 / 9`). 스킬명은 직업마다 달라 비교 무의미 → 제거.
- **HEXA 스탯:** 코어 3개(`character_hexa_stat_core`/`_2`/`_3`), 각 `main/sub1/sub2` 레벨 합=20. → **숫자만** `4 / 10 / 6`(스탯명 제거).
- **전투력:** `final_stat`의 `stat_name=="전투력"` `stat_value`(문자열). 친구 캐릭 실측 ~1~2억 → `format_eok` 로 `1억 8536만`. ⚠️ **프리셋별 전투력은 API에 없음**(전투력은 활성 세팅 기준 D-1 단일값) → "최고 전투력 프리셋 선택" 불가(검토 완료, 2026-06-04).
- **챔피언 등급:** `SSS/SS/S/A…` 등장값 그대로 집계(하드코딩 매핑 없음).
- ⚠️ **닉↔ocid는 DB(`registration`)가 정답.** 로컬 미리보기 스크립트에서 닉을 손으로 매핑하면 라벨이 어긋날 수 있다(버그 아님).

## 6. 확정된 결정 (지금까지)

1. 수치 비교 = **PNG 이미지 표**(깨짐 방지). [[phase2-decisions]]의 "코드블록 정렬표"는 한글 깨짐으로 **이미지로 대체됨**.
2. **행=캐릭터(세로), 순위 위→아래.** (전치 버전은 폐기 — 랭킹 가독성 위해 세로 정렬.)
3. **정렬:** 유니온=`union_level` desc / 스펙=`전투력` desc, 각 `순위` 컬럼. *(스펙을 캐릭터 레벨로 바꿀지 미확정 — §8)*
4. **HEXA:** 코어=타입별 레벨 묶음(스킬·마스터리·강화·공용), 스탯=메인/서브/서브 레벨. 스킬명·스탯명 제거. *(service 는 정수 튜플로 반환 — 렌더가 칸 그리드로 §6.9.)*
5. **스펙 비교에서 어빌리티·심볼 제외**(단일 상세엔 유지).
6. **`/아이템` = PNG 아이템 카드 이미지**(2026-06-05 사용자 피드백 — 게임 툴팁풍). 단일=카드 1장, 비교=카드 세로 스택. 텍스트 카드(`field_pages`/`_render_item`)에서 전환. **결정 반영:** ① 환산 점수(📜/💎) 제외(API 부재+§10), ② 같은 옵션 합산(`재사용 -2초+-1초→-3초`, `공격력 +11+10→+21`), ③ 에디 등급 `+` 미표기, ④ 작 = `주문서 N회 + item_etc_option 주스탯/공마`(HP/MP/방어력 제외).
7. 태그=범례/필드, 핑 차단.
8. **스탯 코어 = `스탯 코어 I·II·III` 3개 컬럼**(로마숫자 라벨). 기존 1컬럼 묶음(`·` 결합)에서 분리 — 가로폭↑ 감수, 정렬·가독성 우선(2026-06-04 사용자 선택).
9. **수치 = 칸 그리드**(`table_image.NumGrid`, 2026-06-05 피드백 "칩 유치"). 세로줄로 **고정 칸**(스킬2·마스터리4·강화4·공용3·스탯3)을 나눠 두 자릿수 폭에 **가운데 정렬**, **빈 칸·없는 코어는 0**. 스탯 코어는 `bold_first=True` 로 **첫 칸(메인 스탯)만 볼드**. **전투력 좌측 정렬.** 표 테두리·주 컬럼 경계(`_GRID`)+내부 칸 구분선(`_GRID_SUB`). *(폐기 이력: 2자리 패딩+mono → 색칩 Chips → 누적막대 StackedBar → 칸 그리드.)*

## 7. 바꾸는 법 (knobs) — 피드백 반영 지점

| 바꾸고 싶은 것 | 위치 |
|---|---|
| **/스펙 컬럼 집합·순서·라벨** | `character/commands.py` `handle_spec` 비교 블록 — `core_cols`(이름,칸수)·`stat_cols` 튜플 + `headers`/`rows` |
| **코어/스탯 칸 그리드 셀** | `character/commands.py` 에서 `table_image.NumGrid(값튜플, 칸수[, bold_first])` 생성 |
| **코어 타입별 칸 수** | `character/commands.py` `core_cols`(스킬2·마스터리4·강화4·공용3) + 스탯 3 |
| **칸 폭·세로줄 색** | `bot/table_image.py` `_SUB_W` · `_GRID`(주경계) · `_GRID_SUB`(내부 구분선) |
| **임베드 설명(범례)** | `bot/comparison.py` `owner_legend`(닉↔태그). 안내 문구는 제거됨 — 표 자체로 자명 |
| **/유니온 컬럼·정렬** | `union/commands.py` `handle_union` 비교 블록 — `headers`/`rows` + `sorted(... key=union_level)` |
| **정렬 기준(전투력↔캐릭터 레벨 등)** | 각 명령의 `sorted(..., key=...)` (스펙은 `_power`) |
| **HEXA 코어 타입 묶음/순서** | `character/service.py` `hexa_core_levels_by_type` + `_CORE_TYPE_SHORT` (정수 튜플 반환) |
| **HEXA 스탯 트리플(정수)** | `character/service.py` `hexa_stat_triples` ((메인,서브1,서브2)) |
| **전투력 숫자 포맷(억/만)** | `character/service.py` `format_eok` |
| **닉/직업 잘림 길이** | 명령의 `comparison.truncate_display(..., N)` |
| **이미지 색·폰트·글자크기·여백** | `bot/table_image.py` 상수: `_BG`·`_ROW_ALT`·`_TEXT`·`_HEADER_TEXT`·`_UNDERLINE`·`_SIZE`·`_PAD_X/Y`·`_MARGIN`, 폰트=`_FONT_CANDIDATES` |
| **셀 정렬(좌/우/가운데)** | 명령의 `aligns=[...]` (render_table_image가 해석) |
| **범례 형식(👤 …)** | `bot/comparison.py` `owner_legend` |
| **실패 묶음 필드 문구** | `bot/comparison.py` `attach_failures` |
| **핑 on/off** | `bot/core.py` `allowed_mentions` |
| **/아이템 카드 → 표시 항목·헤더 라벨** | `character/commands.py` `_to_item_card`(ItemResult→ItemCard 매핑) |
| **/아이템 카드 색·등급색·치수·여백·뱃지** | `bot/item_card.py` 상수: `_PANEL`·`_ICON_BG`·`_STAR`·`_GRADE`(등급→색·라벨)·`_NAME/_BODY/_PILL_SIZE`·`_ICON_BOX`·`_PAD`·`_GAP`·`_CARD_GAP` |
| **같은 옵션 합산 규칙** | `character/item.py` `combine_options`(이름+단위 키로 합산) |
| **작 표시 스탯(주스탯/공마, HP·MP 제외)** | `character/item.py` `_UPGRADE_STAT_LABELS` + `summarize_upgrade_stats` |
| **아이콘 다운로드·캐시** | `nexon/client.py` `fetch_image`(메모리 캐시) · `character/commands.py` `_fetch_icon`(실패 시 None) |

## 8. 남은 피드백 / 백로그 (다음 이터레이션 후보)

- [x] **스펙 `스탯` 칸 분리** — 3코어 트리플 묶음을 `스탯 코어 I·II·III` 3컬럼으로 분리(결정 §6.8). ⚠️ 대신 표가 **총 10컬럼**으로 가로로 넓어짐 → 디스코드 축소가 과하면 폰트/패딩 축소나 컬럼 추리기 재검토.
- [x] **수치 표기 = 칸 그리드** — 세로줄 고정 칸·가운데정렬·빈칸 0·스탯 첫 칸 볼드, 전투력 좌측(결정 §6.9). 칩/누적막대는 "유치" 피드백으로 폐기.
- [ ] **스펙 정렬 기준 확정** — 전투력 vs 캐릭터 레벨.
- [ ] **코어 타입 순서 확정** — 현재 `스킬·마스터리·강화·공용`(API 순). 마스터리 먼저 등 원하면.
- [ ] **레벨 1 슬롯 노이즈** — 미투자(=1) 코어가 많음. 그대로 vs 추리기.
- [x] **`/아이템` 이미지화** — 텍스트 카드 → PNG 아이템 카드(아이콘+뱃지+옵션), 비교는 세로 스택(결정 §6.6). 환산 점수 제외·같은 옵션 합산·작 스탯 표기 반영.
- [ ] **`/아이템` 작 스탯 범위** — 현재 주스탯+공/마력만(HP·MP·방어력 제외). 전부 표기로 바꿀지.
- [ ] **`/아이템` 등급 뱃지 표기** — 현재 한글 단어(`레전드리`). 참조 카드식 글자 약자(L/U/E/R)로 바꿀지.
- [ ] **단일 상세 일관성** — 단일 `/스펙`은 아직 어빌리티·심볼·스킬명 포함(카드). 비교와 표기 통일할지.
- [ ] **다인 페이지네이션** — 이미지 표는 현재 한 장(전 인원). 대형 길드면 세로로 길어짐 → 분할/상한 검토(친구 규모엔 무관).
- [ ] **이미지 스타일** — 헤더 강조·행 음영·폰트 굵기 등 디테일.

## 9. 미리보기 · 실행 · 검증

**봇 기동/재기동**(`.env`·DB 준비됨):
```bash
docker compose up -d db                       # 이미 떠 있으면 생략
caffeinate -i uv run python -m maple_mate      # macOS 슬립 시 10062 방지
# 코드 수정 후: pkill -f maple_mate ; (다시 위 명령)
```

**디스코드 없이 PNG 미리보기**(레이아웃 빠른 반복용 — 실데이터로 표 이미지만 뽑아 확인):
```python
import asyncio
from maple_mate.config import load_config
from maple_mate.nexon.client import NexonClient
from maple_mate.character import service
from maple_mate.character.service import format_eok
from maple_mate.bot import table_image
# ocid는 DB registration 에서. (닉 손매핑 주의 — §5)
async def m():
    nx = NexonClient(load_config().nexon_app_key)
    info = await service.fetch_spec(nx, "<ocid>"); await nx.aclose()
    by_type = dict(info.hexa_core_by_type); tr = info.hexa_stat_triples
    core_slots = [("스킬",2),("마스터리",4),("강화",4),("공용",3)]
    headers = ["순위","캐릭터","전투력",*(n for n,_ in core_slots),
               "스탯 코어 I","스탯 코어 II","스탯 코어 III"]
    rows = [["1", "닉", format_eok(info.combat_power),
             *(table_image.NumGrid(by_type.get(n, ()), s) for n,s in core_slots),
             *(table_image.NumGrid(tr[i] if i < len(tr) else (), 3, bold_first=True)
               for i in range(3))]]
    png = table_image.render_table_image(
        headers, rows,
        aligns=["center","left","left",*(["center"]*7)])  # 전투력 좌측·코어/스탯=NumGrid
    open("/tmp/preview.png","wb").write(png)
asyncio.run(m())
```
→ 생성된 `/tmp/preview.png`를 열어 확인. (실호출이라 앱 키 필요.)

**`/아이템` 카드 PNG 미리보기**(아이콘 다운로드 포함 통합 경로):
```python
import asyncio
from maple_mate.config import load_config
from maple_mate.nexon.client import NexonClient
from maple_mate.character import item
from maple_mate.character.commands import _to_item_card, _fetch_icon
from maple_mate.bot import item_card
async def m():
    nx = NexonClient(load_config().nexon_app_key)
    cards = []
    for nick in ("손바", "네벨루크"):           # 닉→ocid (DB 정답이나 미리보기는 닉 조회)
        ocid = await nx.get_ocid(nick)
        result = await item.fetch_item(nx, ocid, "모자")
        icon = await _fetch_icon(nx, result)     # NexonClient.fetch_image(캐시)
        cards.append(_to_item_card(f"{nick} · 모자", result, icon))
    open("/tmp/item.png","wb").write(item_card.render_item_cards(cards))
    await nx.aclose()
asyncio.run(m())
```
→ `/tmp/item.png` 확인. 부위는 `SLOT_CHOICES`(예: `모자`·`무기`·`반지1`).

**테스트:** `uv run pytest -q` (Nexon/Discord mock, 실호출 없음).
관련: `tests/test_comparison.py`(이미지·범례·태그·페이지·푸터·`image_message`), `tests/test_item_card.py`(카드 PNG·뱃지·작 합산·브리지), `tests/test_character_item.py`(파싱·`combine_options`·작 스탯·아이콘 URL), `tests/test_character_spec.py`(전투력·HEXA), `tests/test_nexon_client.py`(`fetch_image` 캐시), `tests/test_union_service.py`.

## 10. 범위 밖 / 주의 (계속 지킬 것)

- **Phase 3~5 금지:** 이력류(`/스타포스`·`/잠재`·`/잠재합계`)·알림·스케줄러·운영요약·기대값표.
- **`/아이템` 우열 판정 금지**(수치 나열만).
- **시크릿·stray PNG 커밋 금지** — `git status`로 확인, 명시 경로만 스테이징.
- service(`*.py`)는 **전달-무관**(discord 임포트 금지). 렌더는 commands/`bot/*` 에만.
- 작성과 리뷰는 **별도 패스**(code-reviewer/verifier) — 같은 컨텍스트 self-approve 금지.

## 참조

- 기능 핸드오프: [phase2-handoff.md](./phase2-handoff.md) · Phase 1: [phase1-handoff.md](./phase1-handoff.md)
- 아키텍처: [architecture.md](./architecture.md) · API: [api/README.md](./api/README.md)
- 결정 기록(메모리): `phase2-decisions`(§7 사전결정 4건)
