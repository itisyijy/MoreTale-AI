# 스토리 생성 비동기 아키텍처 논의

## 배경

AI 스토리 생성 파이프라인은 다음 단계를 포함하며 **최소 10분 이상** 소요된다.

- 스토리 텍스트 생성 (Gemini) — 약 30초
- 삽화 생성은 `MORETALE_STORY_PAGE_COUNT` 페이지 수에 비례 (Gemini Image)
- TTS 생성은 `MORETALE_STORY_PAGE_COUNT` 페이지 수에 비례 (Gemini TTS)

현재 백엔드 Swagger의 `POST /api/stories/generate`는 완료된 `StoryGenerateResponse`를 직접 반환하는 동기 구조로 명세되어 있어, **AI의 비동기 처리 방식과 불일치**한다.

---

## 결정된 방향

백엔드도 story generation을 비동기 job으로 관리하고, AI 서버에는 internal async job API로 요청한다.
AI 생성 결과는 callback/webhook 또는 backend polling으로 회수한다.

### 적용 흐름

**흐름**
```
Frontend  →  POST /api/stories/generate
                    ↓
          Backend  202 Accepted + { jobId } 반환
                    ↓ (백그라운드)
          Backend  →  POST AI /internal/ai/story/jobs
                           ↓
                      AI  202 Accepted + { aiJobId }
                    ↓ (webhook 또는 백그라운드 폴링)
          Backend  →  GET AI /internal/ai/story/jobs/{aiJobId}/result
                    ↓ 완료 시
          Backend  DB 저장

Frontend  →  GET /api/stories/{jobId}/status  (폴링)
          Backend  →  현재 상태 반환 (queued / running / completed)
```

**결정 이유**
- AI 현재 아키텍처(비동기 잡 패턴)를 그대로 활용 가능
- 긴 생성 시간으로 인한 HTTP timeout 회피
- 스토리 본문, 페이지 이미지, TTS를 하나의 결과물 bundle로 관리 가능
- 백엔드가 사용자-facing job 상태와 DB 반영을 소유하는 구조가 명확함

### 결과물 범위와 실패 정책

- AI internal story job은 텍스트, 페이지 이미지, 양쪽 언어 TTS를 한 번에 생성한다.
- 이미지/TTS URL은 completed result의 `slides[].imageUrl`, `slides[].audioUrlKr`, `slides[].audioUrlNative`에 포함한다.
- 이미지 또는 TTS 중 하나라도 실패하면 partial success로 완료하지 않고 전체 AI job을 `failed` 처리한다.
- Backend는 failed callback/status를 받은 뒤 같은 요청을 새 AI job으로 재시도한다.
- Quiz와 vocabulary는 story bundle의 필수 산출물이 아니며 별도 internal job으로 유지한다.

---

## 보류/대안으로 남긴 흐름

### AI 완료 후 백엔드에 Webhook 콜백

**흐름**
```
Frontend  →  POST /api/stories/generate
                    ↓
          Backend  →  POST AI /api/stories/generate
                           (callback_url 포함)
                      AI  202 Accepted
          Backend  →  Frontend에 즉시 응답 (jobId 등)

          AI 생성 완료
                    ↓
          AI  →  POST /api/stories/callback  (Backend 콜백 엔드포인트)
          Backend  결과 수신 → DB 저장 → Frontend 알림 (SSE / 웹소켓 / 폴링)
```

**장점**
- AI 잡 완료 시 백엔드가 즉시 알 수 있음 (폴링 불필요)
- 결합도 낮음

**단점**
- 백엔드에 콜백 엔드포인트 신규 구현 필요
- AI 서버가 백엔드 URL을 알아야 함 (환경 변수 관리)
- 콜백 실패 시 재시도 로직 필요

---

### 텍스트 생성만 동기, 이미지/TTS는 분리

**흐름**
```
Frontend  →  POST /api/stories/generate
                    ↓
          Backend  →  POST AI /api/stories/generate (텍스트만)
                      AI  약 30초 후 텍스트 + 빈 imageUrl/audioUrl 반환
          Backend  →  DB 저장 (텍스트만)
          Backend  →  Frontend 즉시 응답 (텍스트 포함)

          이후 별도 트리거로:
          Backend  →  POST AI /api/tts/generate  (슬라이드별)
          Backend  →  POST AI /api/illustrations/generate  (페이지별)
          완료 시 DB URL 업데이트
```

**장점**
- 백엔드 현재 동기 스펙 유지 가능 (변경 최소)
- 사용자가 텍스트를 먼저 볼 수 있어 UX 개선 가능
- 이미 백엔드에 `/api/tts/regenerate/*` 엔드포인트 존재 (설계 방향과 일치)

**단점**
- 이미지/오디오가 없는 상태로 먼저 노출되는 UX 처리 필요
- 이미지·TTS 생성 완료 여부를 별도로 추적해야 함

---

## 현재 AI 서버 아키텍처 참고

AI 서버는 현재 **비동기 잡 패턴**으로 구현되어 있다.

| 엔드포인트 | 역할 |
|---|---|
| `POST /api/stories/` | 잡 등록 → 202 + `{ id, status_url, result_url }` |
| `GET /api/stories/{id}` | 잡 상태 조회 |
| `GET /api/stories/{id}/result` | 완료된 결과 조회 |
| `DELETE /api/stories/{id}` | 잡 취소 |

---

## Contract Notes

- Backend-to-AI story generation 기준 endpoint는 `POST /internal/ai/story/jobs`.
- `StoryGenerateRequest`에는 page count를 받지 않는다. AI가 age profile을 기준으로 내부 결정한다.
- AI 내부 page number는 1-based를 유지하고, backend 결과 `slides[].order`는 0-based로 변환한다.
- Completed result의 `slides[]`는 텍스트, 이미지 URL, TTS URL을 모두 포함한다.
- Asset 생성 실패는 전체 AI story job 실패로 처리한다.

---

## 결정 필요 항목 체크리스트

- [x] 백엔드 `POST /api/stories/generate` 동기 유지 vs 비동기 변경: 비동기 변경
- [x] AI → 백엔드 결과 전달 방식: internal async job + callback/webhook 우선, polling fallback 가능
- [x] 이미지·TTS를 스토리 생성과 묶을지 분리할지: story bundle에 포함
- [x] 이미지·TTS 없는 상태의 프론트엔드 UX 처리 방식: 생성 완료 전에는 backend job status 화면 유지, completed에는 asset URL 포함
- [x] 이미지·TTS 실패 정책: 전체 AI story job failed 처리 후 재시도
- [ ] AI 서버 콜백 URL 환경 변수 관리 방식
