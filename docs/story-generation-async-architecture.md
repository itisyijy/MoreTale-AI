# 스토리 생성 비동기 아키텍처 논의

## 배경

AI 스토리 생성 파이프라인은 다음 단계를 포함하며 **최소 10분 이상** 소요된다.

- 스토리 텍스트 생성 (Gemini) — 약 30초
- 삽화 생성 32페이지 (Gemini Image) — 약 5~10분
- TTS 생성 32페이지 (Gemini TTS) — 약 3~5분

현재 백엔드 Swagger의 `POST /api/stories/generate`는 완료된 `StoryGenerateResponse`를 직접 반환하는 동기 구조로 명세되어 있어, **AI의 비동기 처리 방식과 불일치**한다.

---

## 논의가 필요한 결정 사항

### 방향 1: 백엔드도 비동기로 변경

**흐름**
```
Frontend  →  POST /api/stories/generate
                    ↓
          Backend  202 Accepted + { jobId } 반환
                    ↓ (백그라운드)
          Backend  →  POST AI /api/stories/generate
                           ↓
                      AI  202 Accepted + { aiJobId }
                    ↓ (백그라운드 폴링)
          Backend  →  GET AI /api/stories/{aiJobId}/result
                    ↓ 완료 시
          Backend  DB 저장

Frontend  →  GET /api/stories/{jobId}/status  (폴링)
          Backend  →  현재 상태 반환 (queued / running / completed)
```

**장점**
- AI 현재 아키텍처(비동기 잡 패턴)를 그대로 활용 가능
- 타임아웃 문제 없음

**단점**
- 백엔드 API 스펙 변경 필요 (현재 동기 → 비동기)
- 프론트엔드도 폴링 로직 구현 필요
- 백엔드가 AI 잡 상태를 별도 관리해야 함

---

### 방향 2: AI 완료 후 백엔드에 Webhook 콜백

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

### 방향 3: 텍스트 생성만 동기, 이미지/TTS는 분리

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

## 권고 사항

**방향 3 (텍스트 동기 + 이미지/TTS 분리)** 을 우선 검토 권장.

이유:
- 백엔드 스펙 변경 최소화
- 백엔드 Swagger에 이미 `/api/tts/regenerate/*` 가 분리되어 있어 설계 의도와 일치
- 사용자 체감 속도 개선 (텍스트 먼저 노출)
- GCS 스토리지 연동 후 이미지/TTS URL을 순차적으로 채우는 구조와 자연스럽게 연결됨

단, 이미지·TTS 없는 상태에서 프론트엔드가 어떻게 UX를 처리할지 **프론트엔드팀과도 함께 논의** 필요.

---

## 결정 필요 항목 체크리스트

- [ ] 백엔드 `POST /api/stories/generate` 동기 유지 vs 비동기 변경
- [ ] AI → 백엔드 결과 전달 방식 (폴링 / 콜백 / 직접 반환)
- [ ] 이미지·TTS를 스토리 생성과 묶을지 분리할지
- [ ] 이미지·TTS 없는 상태의 프론트엔드 UX 처리 방식
- [ ] AI 서버 콜백 URL 환경 변수 관리 방식 (방향 2 선택 시)
