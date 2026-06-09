# 작업 지시서 — Phase 5 운영 요약 (운영 오류 대응 보고)

> 설계 §6 "일일 운영 요약". 매일 09:00 KST, 전날 `error_log`를 **운영자가 대응 가능한 오류만 선별**해
> `ADMIN_CHANNEL_ID`로 보낸다 + 90일 경과 로그 prune. **왜 선별이고 무엇을 빼는가**는
> [CONTEXT.md](../CONTEXT.md) `운영 요약` 항목과 아래 [확정 결정](#확정-결정-grill-결과) 표가 진실 소스.
> 복잡도 낮음 → `executor`(표준)로 충분. 테스트는 순수 집계·임베드 단위테스트(실용 테스트 합의).

## 참조 (중복 금지 — 경로로 참조)

- [maple-discord-bot-design.md](../maple-discord-bot-design.md) §6·§5⑤ — 운영 요약·`error_log` 명세(SSOT). **단, "타입별 건수(전체)"는 아래 grill로 "선별 보고"로 진화** — 본 문서가 우선.
- [CONTEXT.md](../CONTEXT.md) — `운영 요약`·`운영자`(이 세션 추가). 포함/제외 정책의 도메인 근거.
- [sunday-work-order.md](sunday-work-order.md)·[scheduler.py](../maple_mate/notification/scheduler.py) — 잡 등록·임베드 빌더·채널 해석 패턴(답습 대상).

## 확정 결정 (grill 결과)

| # | 결정 | 선택 |
|---|---|---|
| Q1 | 목적 | "오류 대응" 보고 — **운영자가 실제 대응 가능한 오류만**(평면 건수 덤프 ✗) |
| Q2 | `auth_invalid` 분기 | `discord_user_id IS NULL`(봇 **앱 키** 실패)=유지·최우선 / 채워짐(친구 **개인 키**)=**제외**(자가 발견) |
| Q3 | 트리거 | 매일 **09:00 KST 배치**, **세 섹션 모두 비면 발송 생략**(0건 노이즈 차단). 실시간 ✗ |
| Q4 | 미상 장비 | `unmatched_equipment` → **distinct 장비명 + 발생 횟수**, 빈도 내림차순, **상위 10종**(초과 "외 N종") |
| Q5 | 헬스 신호 | `nexon_api`/`timeout`/`rate_limit` → 임계 없음, **타입별 + command 분해 + 대표 detail 1줄** |
| Q6 | 레이아웃 | 임베드 1개, 섹션 순서 **앱키 → 미상 장비 → 헬스**, 있는 섹션만 렌더. 앱키 실패 ≥1 → **🔴 빨강**, 아니면 BRAND_COLOR |
| Q7 | 윈도우·채널 | "전날" = 전날 KST 00:00~24:00. `ADMIN_CHANNEL_ID` 단일·글로벌(`guild_id` 무시) |
| Q8 | retention | **90일** 경과 삭제, **같은 09:00 잡 안에서 발송 직후** 단일 DELETE. 삭제 건수는 앱로그만 |

**섹션 ↔ error_type 매핑**

| 섹션 | 필터 |
|---|---|
| 🚨 앱키 실패 | `error_type='auth_invalid' AND discord_user_id IS NULL` |
| 🔧 미상 장비 | `error_type='unmatched_equipment'` (detail=장비명) |
| ⚠️ 헬스 | `error_type IN ('nexon_api','timeout','rate_limit')` + 예상 밖 타입 방어 포함 |
| (제외) | `error_type='auth_invalid' AND discord_user_id IS NOT NULL` (친구 개인 키) |

`resolved`·`internal` 컬럼은 미사용 — 무시(외과적 변경, 손대지 않음).

## 현황 진단

**재사용 (import만):**
- [scheduler.py:267](../maple_mate/notification/scheduler.py#L267) `start_scheduler(bot, deps)` — 09:00 잡 1개 추가할 자리.
- [bot/embeds.py:16-17](../maple_mate/bot/embeds.py#L16) `KST`·`BRAND_COLOR`.
- [scheduler.py:30](../maple_mate/notification/scheduler.py#L30) `KST_ZONE`(`ZoneInfo("Asia/Seoul")`) — CronTrigger용.
- [config.py:49](../maple_mate/config.py#L49) `Config.admin_channel_id` (← `deps.config.admin_channel_id`). 이미 fail-fast 로딩, **현재 미배선** — 본 작업이 첫 소비자.
- [error_log/models.py:16](../maple_mate/error_log/models.py#L16) `ErrorLog` ORM.

**마이그레이션:** 불필요(`error_log` 기존). **신규 .env 키:** 없음.

## 빌드 단위 (의존 순서)

### 1. `maple_mate/error_log/summary.py` — 순수 집계 + DB (신규, discord 無)
`notice_service.py`의 "전달-무관 순수 도메인" 역할. discord import 금지.

```python
from __future__ import annotations
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..bot.embeds import KST          # timezone(+9)
from .models import ErrorLog

RETENTION_DAYS = 90
UNMATCHED_TOP_N = 10
_HEALTH_TYPES = ("nexon_api", "timeout", "rate_limit")

@dataclass(frozen=True)
class HealthEntry:
    error_type: str
    count: int
    by_command: tuple[tuple[str, int], ...]   # (command, count) 내림차순
    recent_detail: str | None                 # 가장 최근 행 detail

@dataclass(frozen=True)
class OpsSummary:
    app_key_failures: int                     # auth_invalid AND discord_user_id IS NULL
    app_key_recent_detail: str | None
    unmatched: tuple[tuple[str, int], ...]    # (장비명, 횟수) 빈도 내림차순, 상위 N
    unmatched_kinds: int                      # distinct 종 수(상위 N 초과분 "외" 계산용)
    health: tuple[HealthEntry, ...]           # 타입별, count 내림차순

    @property
    def is_empty(self) -> bool:
        return not (self.app_key_failures or self.unmatched or self.health)

def aggregate(rows: Sequence[ErrorLog]) -> OpsSummary:
    """전날 error_log 행 → 선별 집계(순수). 친구 개인 키 auth_invalid 는 버린다.

    분류: app_key = auth_invalid & discord_user_id None / unmatched = unmatched_equipment
    / health = 그 외(헬스 3종 + 예상 밖 타입 방어). detail/command None 가드.
    """
    ...   # 카운트·정렬만. 외부 의존 없음 → 단위테스트 1급 대상.

async def fetch_yesterday_errors(
    session_factory: async_sessionmaker[AsyncSession], now: datetime
) -> list[ErrorLog]:
    """전날(KST 00:00~24:00) 행 조회. timestamp 는 timestamptz → KST 경계로 비교."""
    now_kst = now.astimezone(KST)
    today0 = now_kst.replace(hour=0, minute=0, second=0, microsecond=0)
    start, end = today0 - timedelta(days=1), today0
    async with session_factory() as session:
        stmt = select(ErrorLog).where(
            ErrorLog.timestamp >= start, ErrorLog.timestamp < end
        )
        return list((await session.execute(stmt)).scalars().all())

async def prune_old_errors(
    session_factory: async_sessionmaker[AsyncSession], now: datetime
) -> int:
    """RETENTION_DAYS 경과 행 단일 DELETE. 삭제 행수 반환(앱로그용)."""
    cutoff = now.astimezone(KST) - timedelta(days=RETENTION_DAYS)
    async with session_factory() as session:
        result = await session.execute(delete(ErrorLog).where(ErrorLog.timestamp < cutoff))
        await session.commit()
        return result.rowcount or 0
```
- *검증(aggregate 순수 단위테스트): ① 개인 키 auth_invalid 제외·앱키 auth_invalid 포함 ② unmatched distinct+횟수+빈도내림+상위10("외 N종" 계산) ③ health 타입별·command 분해·recent_detail=최신 ④ 빈 입력→is_empty.*

### 2. `maple_mate/notification/scheduler.py` — 임베드 빌더 + 잡 (기존 수정)
`build_notice_embeds` 옆에 임베드 빌더, `run_notice_job` 옆에 잡 본체.

```python
from ..error_log import summary as ops_summary

def build_ops_summary_embed(s: ops_summary.OpsSummary, ref_date) -> discord.Embed | None:
    """OpsSummary → 운영 요약 임베드. 비면 None(순수 — 단위테스트 대상).

    색: 앱키 실패 ≥1 → 빨강 / 아니면 BRAND_COLOR. 섹션 순서 앱키→미상→헬스, 있는 것만.
    """
    if s.is_empty:
        return None
    color = discord.Color.red() if s.app_key_failures else BRAND_COLOR
    embed = discord.Embed(title=f"🛠 운영 요약 · {ref_date:%Y-%m-%d}", color=color)
    # 🚨 앱키 / 🔧 미상 장비(상위 N + "외 N종") / ⚠️ 헬스(타입 + command 분해 + 최근 detail)
    ...
    embed.set_footer(text=f"데이터 기준: {ref_date:%Y-%m-%d} KST")
    return embed

async def run_ops_summary_job(bot: discord.Client, deps: Deps) -> None:
    """09:00 잡: 집계 → (비어있지 않으면)ADMIN_CHANNEL 발송 → prune. 발송과 prune 독립."""
    now = datetime.now(KST)
    rows = await ops_summary.fetch_yesterday_errors(deps.session_factory, now)
    s = ops_summary.aggregate(rows)
    embed = build_ops_summary_embed(s, (now.astimezone(KST) - timedelta(days=1)).date())
    if embed is not None:                                   # 0건이면 발송 생략(Q3)
        channel = bot.get_channel(deps.config.admin_channel_id) or \
            await _fetch_admin_channel(bot, deps.config.admin_channel_id)
        if channel is not None:
            try:
                await channel.send(embed=embed)
            except discord.HTTPException as exc:             # 발송 실패는 앱로그만(자기참조 차단)
                log.warning("운영 요약 발송 실패: %s", exc)
    pruned = await ops_summary.prune_old_errors(deps.session_factory, now)  # 발송 여부와 독립
    log.info("운영 요약: 발송=%s, prune=%d행", embed is not None, pruned)
```
- `_fetch_admin_channel`: `bot.fetch_channel(id)` 폴백 + `discord.HTTPException` 가드(`_resolve_channel`와 동형, 단 guild 인자 없음). 인라인 작은 헬퍼로 충분.
- `start_scheduler`에 등록(09:00 KST):
```python
OPS_SUMMARY_HOUR, OPS_SUMMARY_MINUTE = 9, 0
scheduler.add_job(
    run_ops_summary_job,
    trigger=CronTrigger(hour=OPS_SUMMARY_HOUR, minute=OPS_SUMMARY_MINUTE, timezone=KST_ZONE),
    args=[bot, deps], id="ops_summary", name="운영 요약", coalesce=True, max_instances=1,
)
```
- *검증(build_ops_summary_embed 순수 단위테스트): is_empty→None / 앱키 있으면 red·없으면 BRAND_COLOR / 섹션 순서·"외 N종"·command 분해 문자열. run_ops_summary_job 은 mock(fetch/aggregate/send/prune)으로 "빈 요약→미발송·prune 호출" "비빈 요약→발송·prune 호출" 2케이스.*

### 3. `scripts/trigger_ops_summary.py` — 라이브 검증 도구 (신규, `trigger_notice.py` 패턴)
- `run_ops_summary_job`(또는 fetch+aggregate+build)를 1회 수동 실행해 `ADMIN_CHANNEL_ID`로 즉시 발송. 봇 가동 중 실제 임베드 눈 확인용. prune은 `--no-prune`로 끌 수 있게(검증 중 데이터 보존).

### 4. 테스트 — `tests/` (신규)
- `test_ops_summary_aggregate.py`: 빌드 #1 검증 항목(순수, ErrorLog 인스턴스 직접 구성).
- `test_ops_summary_embed.py`: `build_ops_summary_embed` 색·섹션·None(discord.Embed 구성만, DB 무).
- DB(fetch/prune)·discord 발송은 mock 또는 생략(실용 테스트). E2E 생략.

## 영향 파일 요약
```
신규:  maple_mate/error_log/summary.py
       scripts/trigger_ops_summary.py
       tests/test_ops_summary_{aggregate,embed}.py
수정:  maple_mate/notification/scheduler.py  (build_ops_summary_embed·run_ops_summary_job·add_job)
```
마이그레이션·.env·config 변경 없음(`admin_channel_id` 기존).

## 산출물
- 위 코드 + 단위테스트 통과 + `uv run pytest` 그린 + `uvx ruff check maple_mate/`.
- 봇 가동 시 `scripts/trigger_ops_summary.py`로 라이브 발송 1회 눈 확인(앱키 빨강·미상 장비 "외 N종"·헬스 command 분해).
- 문서 갱신: [work-plan.md](work-plan.md) Phase 5 ⬜→✅·진행 현황 표.

## 리스크 / 미실측
- ⚠️ `ADMIN_CHANNEL_ID` 해석 실패(봇이 길드 밖·권한 없음) → 발송 조용히 누락(앱로그만). 첫 가동 시 채널 ID·봇 권한 1회 확인 필요.
- ⚠️ 09:00 잡 발화 시 봇이 꺼져 있었으면 그날 요약 누락(`misfire_grace` 미설정 — 운영 요약은 따라잡기 가치 낮아 의도적). 필요 시 추후 grace 추가(가역적).
- `timestamp` timestamptz ↔ KST 경계 비교는 tz-aware 양변이라 안전하나, 첫 라이브에서 "전날" 행 수 1회 대조 권장.

## 스코프 밖
- 실시간/임계 알림·헬스 baseline·길드별 분해 — 불필요(친구봇 저볼륨). 거슬리면 추후.
- 친구 개인 키 실패 알림 — 제외(자가 발견). prune 주기 조정·`resolved` 워크플로 — 백로그.
