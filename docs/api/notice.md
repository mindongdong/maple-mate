# 공지사항 API (공식 문서 id=24)

> 공통 규약(Base URL `https://open.api.nexon.com`, 인증 헤더 `x-nxopen-api-key`, 날짜 KST, 에러코드)은 [README.md](./README.md) 참고.
> 응답 필드는 SpiralMoon/maplestory.openapi KMS DTO로 교차검증.
>
> **Spike 0 실호출 확정(2026-06-04):** `notice`(20건)·`notice-update`(20건, wrapper `update_notice`)·`notice-event`(19건, wrapper `event_notice`) 모두 200. 래퍼 키·항목 필드는 아래 문서와 일치. **정렬은 `date` 내림차순(최신순)** — 봇 폴링은 마지막 본 `notice_id`/`date` 이후 항목을 신규로 처리. ⚠️ `notice-event`의 **"썬데이 메이플" 제목 매칭은 검증 시점 미진행(0건)이라 라이브 양성확인 잔류** → 라이브 썬데이 또는 Phase 4 수동 엔드포인트로 마감.

## 엔드포인트 요약

| 메서드 | 경로 | 한글명 |
|--------|------|--------|
| GET | `maplestory/v1/notice` | 공지사항 목록 조회 |
| GET | `maplestory/v1/notice/detail` | 공지사항 상세 조회 |
| GET | `maplestory/v1/notice-update` | 업데이트 공지 목록 조회 |
| GET | `maplestory/v1/notice-update/detail` | 업데이트 공지 상세 조회 |
| GET | `maplestory/v1/notice-event` | 진행 중 이벤트 공지 목록 조회 |
| GET | `maplestory/v1/notice-event/detail` | 진행 중 이벤트 공지 상세 조회 |
| GET | `maplestory/v1/notice-cashshop` | 캐시샵 공지 목록 조회 |
| GET | `maplestory/v1/notice-cashshop/detail` | 캐시샵 공지 상세 조회 |

---

## GET `maplestory/v1/notice` — 공지사항 목록 조회

메이플스토리 공지사항 목록을 조회합니다. 파라미터 없이 최신 공지 목록을 반환합니다.

**요청 파라미터**

없음

**응답 필드**

| 필드 | 타입 | 설명 |
|------|------|------|
| notice | array | 공지사항 항목 목록 |
| └ title | string | 공지 제목 |
| └ url | string | 공지 링크 (넥슨 홈페이지 URL) |
| └ notice_id | integer | 공지 식별자 |
| └ date | string (datetime) | 공지 등록일 (KST) |

**예시 응답**

```json
{
  "notice": [
    {
      "title": "[공지] 정기 점검 안내",
      "url": "https://maplestory.nexon.com/News/Notice/View?boardSeq=12345",
      "notice_id": 12345,
      "date": "2024-01-15T10:00:00.000Z"
    }
  ]
}
```

**봇 활용:** `/공지알림` — `notice` 배열을 주기적으로 폴링하여 새 항목(`notice_id` 또는 `date` 기준) 감지 시 `title` + `url` + `date`를 Discord 채널에 전송.

---

## GET `maplestory/v1/notice/detail` — 공지사항 상세 조회

특정 공지사항의 본문 내용을 조회합니다.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|------|------|------|------|
| notice_id | 필수 | integer | 공지 식별자 (`/notice` 목록에서 획득) |

**응답 필드**

| 필드 | 타입 | 설명 |
|------|------|------|
| title | string | 공지 제목 |
| url | string | 공지 링크 |
| contents | string | 공지 본문 (HTML 포함 가능) |
| date | string (datetime) | 공지 등록일 (KST) |

**예시 응답**

```json
{
  "title": "[공지] 정기 점검 안내",
  "url": "https://maplestory.nexon.com/News/Notice/View?boardSeq=12345",
  "contents": "<p>정기 점검이 진행됩니다...</p>",
  "date": "2024-01-15T10:00:00.000Z"
}
```

---

## GET `maplestory/v1/notice-update` — 업데이트 공지 목록 조회

메이플스토리 업데이트 공지 목록을 조회합니다. 패치 노트, 신규 콘텐츠 업데이트 공지가 해당됩니다.

**요청 파라미터**

없음

**응답 필드**

| 필드 | 타입 | 설명 |
|------|------|------|
| update_notice | array | 업데이트 공지 항목 목록 |
| └ title | string | 공지 제목 |
| └ url | string | 공지 링크 |
| └ notice_id | integer | 공지 식별자 |
| └ date | string (datetime) | 공지 등록일 (KST) |

**예시 응답**

```json
{
  "update_notice": [
    {
      "title": "[업데이트] 1월 정기 업데이트 안내",
      "url": "https://maplestory.nexon.com/News/Update/View?boardSeq=67890",
      "notice_id": 67890,
      "date": "2024-01-10T09:00:00.000Z"
    }
  ]
}
```

**봇 활용:** `/공지알림` — `update_notice` 배열을 주기적으로 폴링하여 새 항목 감지 시 `title` + `url` + `date`를 Discord 채널에 전송.

---

## GET `maplestory/v1/notice-update/detail` — 업데이트 공지 상세 조회

특정 업데이트 공지의 본문 내용을 조회합니다.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|------|------|------|------|
| notice_id | 필수 | integer | 공지 식별자 (`/notice-update` 목록에서 획득) |

**응답 필드**

| 필드 | 타입 | 설명 |
|------|------|------|
| title | string | 공지 제목 |
| url | string | 공지 링크 |
| contents | string | 공지 본문 (HTML 포함 가능) |
| date | string (datetime) | 공지 등록일 (KST) |

**예시 응답**

```json
{
  "title": "[업데이트] 1월 정기 업데이트 안내",
  "url": "https://maplestory.nexon.com/News/Update/View?boardSeq=67890",
  "contents": "<p>이번 업데이트에서는...</p>",
  "date": "2024-01-10T09:00:00.000Z"
}
```

---

## GET `maplestory/v1/notice-event` — 진행 중 이벤트 공지 목록 조회

현재 진행 중인 이벤트 공지 목록을 조회합니다. 이벤트 시작일·종료일이 포함되어 기간 필터링에 활용할 수 있습니다.

**요청 파라미터**

없음

**응답 필드**

| 필드 | 타입 | 설명 |
|------|------|------|
| event_notice | array | 이벤트 공지 항목 목록 |
| └ title | string | 공지 제목 |
| └ url | string | 공지 링크 |
| └ thumbnail_url | string | 썸네일 이미지 링크 |
| └ notice_id | integer | 공지 식별자 |
| └ date | string (datetime) | 공지 등록일 (KST) |
| └ date_event_start | string (datetime) | 이벤트 시작일 (KST) |
| └ date_event_end | string (datetime) | 이벤트 종료일 (KST) |

**예시 응답**

```json
{
  "event_notice": [
    {
      "title": "썬데이 메이플 이벤트",
      "url": "https://maplestory.nexon.com/News/Event/View?boardSeq=11111",
      "thumbnail_url": "https://ssl.nexon.com/S2/Game/maplestory/thumbnail/11111.jpg",
      "notice_id": 11111,
      "date": "2024-01-12T00:00:00.000Z",
      "date_event_start": "2024-01-14T00:00:00.000Z",
      "date_event_end": "2024-01-21T23:59:59.000Z"
    }
  ]
}
```

**봇 활용:** `/썬데이` — `event_notice` 목록에서 `title`에 `"썬데이 메이플"` 포함 여부를 검사. 매칭된 항목의 `date_event_start` ~ `date_event_end` 기간을 임박 알림 또는 현재 진행 여부 판단에 사용.

---

## GET `maplestory/v1/notice-event/detail` — 진행 중 이벤트 공지 상세 조회

특정 이벤트 공지의 본문 내용과 이벤트 기간을 조회합니다.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|------|------|------|------|
| notice_id | 필수 | integer | 공지 식별자 (`/notice-event` 목록에서 획득) |

**응답 필드**

| 필드 | 타입 | 설명 |
|------|------|------|
| title | string | 공지 제목 |
| url | string | 공지 링크 |
| contents | string | 공지 본문 (HTML 포함 가능) |
| date | string (datetime) | 공지 등록일 (KST) |
| date_event_start | string (datetime) | 이벤트 시작일 (KST) |
| date_event_end | string (datetime) | 이벤트 종료일 (KST) |

**예시 응답**

```json
{
  "title": "썬데이 메이플 이벤트",
  "url": "https://maplestory.nexon.com/News/Event/View?boardSeq=11111",
  "contents": "<p>썬데이 메이플 이벤트가 진행됩니다...</p>",
  "date": "2024-01-12T00:00:00.000Z",
  "date_event_start": "2024-01-14T00:00:00.000Z",
  "date_event_end": "2024-01-21T23:59:59.000Z"
}
```

---

## GET `maplestory/v1/notice-cashshop` — 캐시샵 공지 목록 조회

캐시샵 신규·이벤트 판매 공지 목록을 조회합니다. 판매 시작일·종료일 및 상시 판매 여부가 포함됩니다.

**요청 파라미터**

없음

**응답 필드**

| 필드 | 타입 | 설명 |
|------|------|------|
| cashshop_notice | array | 캐시샵 공지 항목 목록 |
| └ title | string | 공지 제목 |
| └ url | string | 공지 링크 |
| └ thumbnail_url | string | 썸네일 이미지 링크 |
| └ notice_id | integer | 공지 식별자 |
| └ date | string (datetime) | 공지 등록일 (KST) |
| └ date_sale_start | string (datetime) \| null | 판매 시작일 (KST). 상시 판매 시 `null` 가능 |
| └ date_sale_end | string (datetime) \| null | 판매 종료일 (KST). 상시 판매 시 `null` 가능 |
| └ ongoing_flag | string | 상시 판매 여부. `"true"` = 상시 판매, `"false"` = 기간 한정 |

**예시 응답**

```json
{
  "cashshop_notice": [
    {
      "title": "[캐시샵] 1월 신규 패키지 출시",
      "url": "https://maplestory.nexon.com/News/Cashshop/View?boardSeq=22222",
      "thumbnail_url": "https://ssl.nexon.com/S2/Game/maplestory/thumbnail/22222.jpg",
      "notice_id": 22222,
      "date": "2024-01-15T00:00:00.000Z",
      "date_sale_start": "2024-01-15T00:00:00.000Z",
      "date_sale_end": "2024-01-31T23:59:59.000Z",
      "ongoing_flag": "false"
    }
  ]
}
```

---

## GET `maplestory/v1/notice-cashshop/detail` — 캐시샵 공지 상세 조회

특정 캐시샵 공지의 본문 내용과 판매 기간을 조회합니다.

**요청 파라미터**

| 이름 | 필수 | 타입 | 설명 |
|------|------|------|------|
| notice_id | 필수 | integer | 공지 식별자 (`/notice-cashshop` 목록에서 획득) |

**응답 필드**

| 필드 | 타입 | 설명 |
|------|------|------|
| title | string | 공지 제목 |
| url | string | 공지 링크 |
| contents | string | 공지 본문 (HTML 포함 가능) |
| date | string (datetime) | 공지 등록일 (KST) |
| date_sale_start | string (datetime) \| null | 판매 시작일 (KST). 상시 판매 시 `null` 가능 |
| date_sale_end | string (datetime) \| null | 판매 종료일 (KST). 상시 판매 시 `null` 가능 |
| ongoing_flag | string | 상시 판매 여부. `"true"` = 상시 판매, `"false"` = 기간 한정 |

**예시 응답**

```json
{
  "title": "[캐시샵] 1월 신규 패키지 출시",
  "url": "https://maplestory.nexon.com/News/Cashshop/View?boardSeq=22222",
  "contents": "<p>신규 패키지가 출시되었습니다...</p>",
  "date": "2024-01-15T00:00:00.000Z",
  "date_sale_start": "2024-01-15T00:00:00.000Z",
  "date_sale_end": "2024-01-31T23:59:59.000Z",
  "ongoing_flag": "false"
}
```
