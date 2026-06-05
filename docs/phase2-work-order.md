# Phase 2 작업 지시문 (다음 세션 킥오프용)

> 아래 블록을 그대로 다음 세션에 붙여넣어 착수한다. 상세 스펙·합격 기준·구현 제약은 [phase2-handoff.md](./phase2-handoff.md)가 단일 진실 소스.

---

maple-mate 레포에서 work-plan의 **Phase 2 — 읽기전용 스펙류(`/스펙`·`/유니온`·`/아이템`)**를 구현해줘.

## 먼저 읽을 것
1. @docs/phase2-handoff.md ← 이번 작업의 단일 지침서. 범위·빌드순서·합격기준·Spike0 구현제약·구조·산출물 체크리스트가 다 들어있음.
2. @docs/architecture.md ← DDD 폴더 구조 + "새 도메인/명령 추가법". 이 패턴 그대로 따를 것.
3. @maple-discord-bot-design.md (§3.1 `/스펙`·§3.2 `/아이템`·§3.3 `/유니온`·§7 횡단규칙·§2 범위) , @CONTEXT.md (용어: 스펙류·대상·키미등록vs기록없음)
4. @docs/api/README.md , @docs/api/character.md , @docs/api/union.md , @docs/api-verification-plan.md (그룹 A 스펙류 실측)
5. (배경) @docs/phase1-handoff.md ← Phase 1에서 확립된 패턴(에러매핑·푸터·defer·테스트 방침·mock)을 재사용

## 시작 전 나에게 받을 것 (착수 전 먼저 물어봐줘 — handoff §7)
- **정적 부위표 데이터 소스**: 스타포스 불가/잠재 불가 부위 목록을 게임 지식으로 직접 작성할지, 레퍼런스 차용할지.
- **`/아이템` 부위 choices 목록**: 드롭다운에 넣을 부위 확정(모자·상의·…·무기·보조무기·엠블렘·반지·펜던트 등).
- **`/스펙` 출력량/5명 비교 렌더 전략**, **부분성공 표기 임베드 형식**.

## 작업 규칙
- **확정 스택·구조 불변**: Python/discord.py + FastAPI + SQLAlchemy 2.0 + asyncpg + httpx + pytest. **DDD 도메인 수직 슬라이스**(architecture.md). 새 도메인은 `character/`(스펙·아이템) + `union/`. **스펙류는 읽기 전용 → 새 테이블 없음**(조회만).
- **재사용 필수**: `nexon/client._request`·`get_ocid`·throttle/재시도, `nexon/errors.classify`, `bot/embeds`(`make_embed`·`format_footer`·`defer`·`EmbedPaginator`), `dependencies.Deps`, `error_log` 모델. 바퀴 재발명 금지.
- **Spike 0 구현 제약 반영(handoff §3)**: 스펙류 **date 무지정(최신 ready) 호출**(D-1 직접 계산 금지, `00009`는 "데이터 미준비"로 안내), `access_flag`="true"/"false" 문자열, 전투력 `stat_value` 문자열, 챔피언 `champion_grade`=SSS/SS/S 등장값 집계, **`/아이템` 0성 vs 스타포스불가 = 정적 부위표로 구분**.
- **횡단 규칙 의무(handoff §4)**: 모든 비교 명령 **defer**, 임베드 통일, **부분 성공**(되는 유저 + 실패 사유 행), 버튼 페이지네이션, 푸터, **ocid lazy 갱신**(실패 시 닉 재조회 1회→DB 갱신→재시도), 재시도 발생 건 `error_log` 적재.
- **실용 테스트만**: 순수 변환 로직(전투력 추출·등급 분포·정적표 적용·대상/부분성공)만 단위테스트, Nexon/Discord는 mock. 무거운 E2E 금지.
- **단순함·외과적 변경**(CLAUDE.md): 추측성 추상화·설정화 금지. **Phase 3~5 절대 손대지 마**(이력류=`/스타포스`·`/잠재`·`/잠재합계`, 기대값표, 알림, 스케줄러, 운영요약 = 범위 밖). `/아이템` 우열 판정 금지(수치 나열만).

## 빌드 순서 (각 단위 합격 기준 통과 후 다음 — handoff §1 표)
넥슨 스펙류 메서드+ocid lazy 갱신 → 대상해석+부분성공 공유헬퍼 → `/유니온`(가장 단순) → `/스펙` → `/아이템`+정적 부위표.

## 진행 방식
- 권장 스킬: /oh-my-claudecode:autopilot 또는 ultrawork(병렬), 코드 작성은 executor 에이전트(복잡 작업 model=opus).
- API/SDK 불확실 시 document-specialist(discord.py choices·SQLAlchemy·넥슨 API).
- **검증/리뷰는 별도 패스**(code-reviewer/verifier) — 작성과 같은 컨텍스트에서 self-approve 금지.
- 커밋: 논리 단위로 레포 컨벤션(`<type>: <한글 요약>` + 불릿, **attribution 없음**). **push·PR은 내 승인 후.**

## 끝나고
- handoff §9 산출물 체크리스트 전부 충족 + 단위테스트 통과 + 라이브 검증(각 명령 단일/비교, 닉 변경 lazy 갱신) + 시크릿 미커밋(`git status`).
- 변경 요약 보고 후, 승인 시 브랜치 push + PR(일반 컨벤션) 생성.

---

## 운영 메모 (라이브 검증 시)
- 봇 기동: `docker compose up -d db` → `uv sync` → `uv run python -m maple_mate`. (Phase 1 `.env` 그대로 사용.)
- macOS에서 유휴 중 슬립 시 디스코드 상호작용 `10062` 발생 가능 → `caffeinate -i uv run python -m maple_mate` 권장.
- 테스트: `uv run pytest` (실호출은 `set -a; source spike/.env; set +a; uv run pytest -m live`).
