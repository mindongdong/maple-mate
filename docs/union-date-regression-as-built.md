# 결과 문서 (as-built) — 유니온 date-무지정 회귀 대응

> `/유니온` 의 **유니온·아티팩트 값이 빈칸(—)** 으로 나오던 버그 수정.
> 넥슨이 `user/union` 의 `date` 무지정(=최신) 호출을 일부 캐릭터에 대해 **200 + 전 필드 null** 로 회귀시킨 것이 원인. 봇이 D-1 을 명시 조회하도록 전환.

- **상태:** 머지 완료 — PR #25, squash `b1d7e69` → `main` (2026-06-19 13:30 KST)
- **검증:** `pytest` 523 passed · `ruff`(E,F,I)+format 클린 · CI 3잡(lint·migrations·test) 그린 · 실 API 라이브 재현/수복 확인
- **관련:** [docs/api/union.md](api/union.md)(회귀 주석) · [ADR-0001](adr/0001-nexon-personal-key-model.md)(넥슨 키/조회 모델) · 동일 "date 사실상 필수" 선례: `ranking/overall`·`history/*`([client.py](../maple_mate/nexon/client.py))

## 무엇이 바뀌었나

넥슨이 2026-06 업데이트 이후 **`maplestory/v1/user/union` 의 `date` 무지정 호출**을 일부 캐릭터에 대해 HTTP 200 + 전 필드 null(`union_level`·`union_grade`·`union_artifact_level` 모두 null)로 회귀시켰다. 봇은 스펙류를 `date` 무지정(=최신)으로 부르므로 해당 캐릭터에서 유니온·아티팩트가 "—" 로 비었다. **`date` 를 명시(D-1)하면 정상 반환**되므로, `/유니온` 만 명시 D-1 호출로 전환했다.

| 구분 | 이전 | 이후 |
|---|---|---|
| `user/union` 호출 | `date` 무지정(=최신) | **명시적 D-1(KST)**, 미준비 시 D-2 1회 폴백 |
| 빈칸 증상 | 일부 캐릭터 유니온·아티팩트 — | 정상 표시 |
| 푸터 | (무지정) `최신 기준` | `YYYY-MM-DD 기준`(어느 스냅샷인지 명시) |
| `union-champion` | 무지정 | **미변경**(date 무지정 정상) |

## 진단 과정 (증거)

실 앱 키로 직접 호출해 원인을 좁혔다. **포맷 변경(union-raider 신규 필드)이 아니라 date-무지정 회귀**임이 핵심.

| 캐릭터 | `date` 무지정(봇 기존) | `date=D-1` 명시 |
|---|---|---|
| 손바 (Lv287) | level=**null**, artifact=**null** ❌ | **9333 / 53** ✅ |
| 라딘라면 | level=**null**, artifact=**null** ❌ | **9353 / 51** ✅ |
| 솝상 (대조군) | 10270 / 60 ✅ | 10270 / 60 ✅ |

- **영향 범위 = `user/union` 단일.** 손바 ocid 로 전 엔드포인트를 무지정 호출 시 `user/union` 만 null, `union-artifact`·`union-champion`·`character/basic`·`character/stat` 은 정상. → 챔피언은 별도 호출이라 데이터가 떠서 "유니온·아티팩트만 빈칸" 증상.
- **date 함정:** 오늘/미래 date → `OPENAPI00004`(거부, 전일 데이터는 익일 02시부터 생성). 무효 ocid → `OPENAPI00003`(INVALID_ID). 봇은 INVALID_PARAM·INVALID_ID 둘 다 stale-ocid 로 분류하므로, date 에러를 바깥으로 흘리면 엉뚱하게 닉 재조회가 돈다 → fetch_union 내부에서 흡수해야 함.

## 구현 (as-built)

- [union/service.py](../maple_mate/union/service.py) — `_union_latest(nexon, ocid, now)` 신설: `user/union` 을 **명시적 D-1(KST)** 로 호출. 200+null 이거나 미준비(`DATA_NOT_READY`/`INVALID_PARAM`)면 **D-2 로 1회 폴백**(새벽 0~2시 D-1 미생성 구간 흡수). 잘못된 ocid(`INVALID_ID`)·장애는 그대로 raise → 호출자 `registration.service._fetch_one` 의 닉 재조회/실패 처리 보존. `fetch_union` 은 `now` 주입 인자 추가(테스트 결정성). `union_champion` 은 미변경.
- [bot/embeds.py](../maple_mate/bot/embeds.py) — `format_footer` 지난 날짜 분기에 `'기준'` 명시(`'2026-06-18'` → `'2026-06-18 기준'`). 오늘 분기 `'HH:MM 기준'` 과 일관. 명시 D-1 호출로 응답 `date` 가 채워져 유니온 푸터가 `2026-06-18 기준 · NEXON Open API` 로 표시(union 200-null 특수 캐릭은 여전히 `최신 기준`).
- [docs/api/union.md](api/union.md) — `user/union` 섹션에 넥슨 회귀 ⚠️ 주석.
- 테스트: [tests/test_union_service.py](../tests/test_union_service.py) 4케이스 추가(D-1 단일 호출 / D-1 null→D-2 폴백 / D-1 미준비→D-2 폴백 / invalid ocid 전파), [tests/test_footer.py](../tests/test_footer.py) 지난 날짜 기대문자열 2건 갱신.

## 판단 사항

- **수정 위치 = `fetch_union` 내부(`_union_latest`)** — `client._spec`/`union()` 을 전역 변경하지 않음. 영향 범위가 `user/union` 단일이고 다른 스펙 엔드포인트는 무지정 정상이라, 깨진 곳만 수술적으로 손댐. 대가: union 은 `_spec` 의 date=None 캐시를 못 타 캐릭당 호출이 소폭 증가(무시할 수준).
- **D-2 폴백 1회** — 넥슨 "전일 데이터는 익일 02시부터" 규칙상 새벽 0~2시 D-1 미준비 구간만 흡수하면 충분(D-2 는 항상 준비). 둘 다 200+null 이면(특수 직업군 등 유니온 데이터 없음) 마지막 응답을 그대로 돌려 빈칸으로 렌더.
- **`INVALID_PARAM` 내부 흡수** — date 오류(00004)와 stale-ocid(00003)가 봇 분류상 겹쳐, date 폴백 루프 안에서 00004 를 흡수하지 않으면 닉 재조회로 오작동. 00003(INVALID_ID, 잘못된 ocid)만 전파.
- **`format_footer` 전역 변경 채택** — 푸터는 공유 순수함수라 변경이 `/스펙`·`/아이템`에도 닿지만, 그 명령들은 평소 date 무지정(→`최신 기준`)이라 실사용 노출은 `/유니온` 중심. 오늘/지난 분기 모두 "기준" 으로 통일되어 일관성↑.

## 남은 작업 (운영자)

- [ ] **배포**(Render) 반영 — main 머지분 자동/수동 배포.
- [ ] **라이브 검증:** `/유니온` 단일·비교에서 유니온·아티팩트 정상 표시 + 푸터 `YYYY-MM-DD 기준` 노출 확인.

## 한계 / 후속

- **넥슨 측 회귀** — 근본 원인은 벤더 버그라 넥슨이 무지정 동작을 복구할 수 있음. 명시-date 호출은 `ranking`/`history` 와 동일한 정공법이라 복구 후에도 안전(무해).
- **특수 직업군(예: 프렌즈 월드)** — D-1·D-2 모두 유니온 데이터가 없어 빈칸 유지가 정상. 필요 시 "유니온 데이터 미제공" 안내 문구는 후속 UX 개선 사항(이번 범위 밖).
- **`union-champion` 미보호** — 현재 무지정 정상이나 동일 회귀가 번지면 같은 D-1 처리 필요. 발생 시 `_union_latest` 패턴 재사용.
