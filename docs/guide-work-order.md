# 작업 지시서 — `/가이드` 명령 (봇 기능 안내) · `/핑` 대체

> **상태: 계획 확정 (2026-06-16), 미구현.** `/grill-me` 12문으로 아래를 확정했다.

> 구현된 전체 기능을 한 장의 임베드로 안내하는 **`/가이드`** 슬래시 명령을 추가하고,
> 기존 **`/핑`(헬스체크)을 제거**한다. `/가이드`가 응답하는 것 자체가 봇 생존 증명이라 핑 역할을 흡수한다.
> 가이드 본문은 **정적 손작성**(그룹핑·온보딩 서사)이며, **드리프트 가드 테스트**로 새 명령 추가 시 갱신 누락을 CI가 잡는다.

## 핵심 결론

**`/가이드` = 등록 순서 + 스펙류/이력류 구분 + 권한 전제조건**을 담은 단일 ephemeral 임베드.
Discord는 `/` 입력 시 각 명령의 `description`·인자를 이미 보여준다 — 그래서 가이드는 Discord가 *못* 주는 것(**그룹·등록 순서·키/권한 전제조건**)에만 집중하고, 인자별 풀 문서(Discord UI 중복)는 만들지 않는다.

## 확정 결정 12건 (그릴링)

| # | 결정 | 비고 |
|---|---|---|
| 1 | **`/핑` 삭제 + `/가이드` 추가** | 핑의 생존 프로브 역할은 가이드 응답이 흡수 |
| 2 | **정적 손작성 + 드리프트 가드 테스트** | 자동생성은 Discord `/` UI와 중복·서사 불가 |
| 3 | **내용 깊이 = 중간(B)** | 그룹별 `명령 — 한 줄` + 상단 온보딩(등록 순서·도메인 구분·전제조건) |
| 4 | **단일 임베드** | 그룹당 `add_field` 1개. 한 장에 들어가 `EmbedPaginator` 불필요 |
| 5 | **ephemeral** | 본인만 보임. 채널 도배 방지, `/핑`·설정류와 일관 |
| 6 | **신규 모듈 `maple_mate/guide/commands.py`** + `setup(bot)` | core.py 주석 "새 명령은 도메인 commands.py" 준수 |
| 7 | **쿨다운 없음** | 순수 정적·ephemeral. 도움말을 쿨다운으로 막는 건 나쁜 UX (핑과 동일) |
| 8 | **그룹 구조 = 6그룹(도메인 구분 명시)** | 스펙류/이력류/권한을 그룹 헤더에 노출 (아래 §본문 명세) |
| 9 | **드리프트 가드 = 최상위 명령명 커버리지** | 비틱=1개로 카운트, `가이드` 자신 제외. 풀 리프 검증은 브리틀 |
| 10 | **테스트 세트 전체** | ①등록+핑 미등록 ②ephemeral 임베드 응답 ③드리프트 가드 ④기존 ping 테스트 정리 |
| 11 | **문서 = work-order만** | 결정이 관례적 → ADR·CONTEXT 불필요 ([[adr-usage-preference]]) |
| 12 | **이번 산출물 = 본 work-order 문서까지** | 구현은 별도 |

## 가이드 임베드 본문 명세 (그룹 구조 A · 6그룹)

> 한 줄 설명은 각 명령의 실제 `description=`에서 축약. 그룹 헤더에 **키/권한 전제조건**을 명시.

**title**: `메이플메이트 가이드`

**description (온보딩)**:
```
메이플메이트는 길드원들의 메이플스토리 캐릭터 스펙·이력을 비교하는 봇이에요.
처음이라면 → /캐릭터등록 → (이력 보려면) /키등록 → /대표지정 순으로 등록하세요.
🔓 스펙류는 등록만으로, 📜 이력류는 개인 API 키가 있어야 보입니다.
```

**fields (그룹당 1개, inline=False)**:

| 그룹 헤더 | 명령 — 한 줄 |
|---|---|
| `📝 등록·관리` | `/캐릭터등록` 캐릭터 등록(유저당 여러 개) · `/키등록` 넥슨 개인 API 키 등록(이력류 개방) · `/대표지정` 공개 명령용 대표 캐릭터 지정 · `/캐릭터목록` 내 등록 현황(본인만) |
| `⚔️ 스펙·장비 (스펙류 · 키 불필요)` | `/스펙` 전투력·어빌·심볼·HEXA 비교 · `/아이템` 부위별 스타포스·잠재·옵션 비교 · `/유니온` 유니온·아티팩트·챔피언 등급 비교 |
| `📜 이력 (이력류 · 개인 API 키 필요)` | `/스타포스` 운지수·손익메소 비교 · `/잠재` 재설정·큐브·메소·등업 비교 |
| `🎴 비틱 (자랑 카드)` | `/비틱 스타포스` 스타포스 자랑 카드(본인 키) · `/비틱 잠재` 잠재 자랑 카드(본인 키) · `/비틱 득템` 득템 이미지 자랑 |
| `📈 리더보드` | `/경험치` 등록 캐릭터 최근 7일 레벨 추이 그래프 |
| `🔔 알림 설정 (서버 관리 권한)` | `/경험치알림` 매일 경험치 리더보드 알림 · `/썬데이` 썬데이 메이플 알림 · `/공지알림` 메이플 공지·업데이트 알림 |

**footer**: `각 명령 사용법은 / 입력 시 표시돼요 · 도움말 재호출: /가이드`

> 본문 문구는 구현 시 다듬을 수 있으나, **그룹 헤더의 (키 불필요/개인 API 키 필요/서버 관리 권한) 라벨은 유지** — 가이드의 핵심 가치.

## 변경 파일 명세

### 신규 — `maple_mate/guide/__init__.py`
빈 패키지 초기화.

### 신규 — `maple_mate/guide/commands.py`
- `build_guide_embed() -> discord.Embed` — **순수 함수**(인자 없음). `make_embed()` + `add_field` 6회. 테스트에서 직접 호출 가능하도록 분리.
- `setup(bot: discord.Client) -> None` — `@bot.tree.command(name="가이드", description="봇의 명령 목록과 사용법을 안내합니다.")` 등록. 쿨다운 데코레이터 **없음**. 콜백은 `await interaction.response.send_message(embed=build_guide_embed(), ephemeral=True)`.

### 수정 — `maple_mate/bot/core.py`
- [core.py:101-103](../maple_mate/bot/core.py#L101-L103) `ping` 정의 **삭제**.
- 도메인 import 블록에 `from ..guide.commands import setup as setup_guide` 추가.
- `_register_commands()` 본문에 `setup_guide(self)` 호출 추가.

### 수정 — `tests/test_cooldowns.py`
- [test_cooldowns.py:74-77](../tests/test_cooldowns.py#L74-L77) `test_ping_has_no_cooldown` → `test_guide_has_no_cooldown`으로 교체(`get_command("핑")`이 핑 제거로 None 반환해 깨짐). `/가이드` 체크 0개 검증으로 대체.

### 신규 — `tests/test_guide.py`
기존 오프라인 봇 패턴([test_cooldowns.py](../tests/test_cooldowns.py) 참조: `MapleMateBot(deps=object(), dev_guild_id=None)` + `_register_commands()`) 재사용.
- `test_guide_registered_and_ping_removed` — `tree.get_command("가이드")` is not None, `tree.get_command("핑")` is None.
- `test_guide_responds_ephemeral_embed` — 가짜 Interaction으로 콜백 호출 → `response.send_message`가 `ephemeral=True` + `embed` 인자로 1회 호출.
- `test_guide_covers_all_top_level_commands` (**드리프트 가드**) — `build_guide_embed()`의 전체 텍스트(`description` + 모든 field `name`·`value`) 결합 → `tree.get_commands()` 최상위 명령명에서 `"가이드"` 제외한 전부가 부분문자열로 등장하는지 `assert`. 누락 명령을 메시지에 노출.

> 검증 대상 최상위 명령(14개): 캐릭터등록·키등록·대표지정·캐릭터목록·스펙·아이템·유니온·스타포스·잠재·비틱·경험치·경험치알림·썬데이·공지알림.

## 구현 단계 + 검증

```
1. guide/__init__.py + guide/commands.py 작성
   → verify: python -c "from maple_mate.guide.commands import build_guide_embed; print(build_guide_embed().title)"
2. core.py 핑 제거 + setup_guide 배선
   → verify: ruff check . && ruff format --check .
3. test_cooldowns.py 핑 테스트 교체 + test_guide.py 작성
   → verify: pytest tests/test_guide.py tests/test_cooldowns.py -q
4. 전체 회귀
   → verify: pytest -q  (기존 516개 + 신규 그린)
```

## 참조 (중복 금지 — 경로로 참조)

- [maple_mate/bot/core.py:90-113](../maple_mate/bot/core.py#L90-L113) — `_register_commands()`(핑 정의·도메인 setup 배선). 변경 지점
- [maple_mate/bot/embeds.py:49-60](../maple_mate/bot/embeds.py#L49-L60) — `make_embed(title, description, color, footer)`. 가이드 임베드 빌더 기반
- [maple_mate/bot/cooldowns.py:5](../maple_mate/bot/cooldowns.py#L5) — "핑은 쿨다운 제외" 주석. 가이드도 동일
- [tests/test_cooldowns.py:31-43](../tests/test_cooldowns.py#L31-L43) — 오프라인 봇 픽스처 + `get_command` 패턴. 신규 테스트가 재사용
- [CONTEXT.md](../CONTEXT.md) — 스펙류/이력류 도메인 구분(가이드 그룹 헤더 라벨의 근거). 변경 없음

## 비목표 (이번 범위 아님)

- 인자별 풀 문서·예시 (Discord `/` UI와 중복)
- 페이지네이션·버튼 상호작용
- 공개(non-ephemeral) 브로드캐스트 옵션 (필요 시 차후 `공개:true` 인자로 확장)
- 명령 트리 자동생성
- ADR·CONTEXT.md 갱신
