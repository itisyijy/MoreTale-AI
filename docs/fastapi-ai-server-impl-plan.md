# MoreTale FastAPI 마이크로서비스 구현 계획서

## 0) 목표/범위

### 목표
- **동화 텍스트(이중언어)**, **TTS 오디오 결과물**, **일러스트 결과물**을 **JSON으로 반환**하는 FastAPI 기반 마이크로서비스를 설계/구현한다.
- 오디오/일러스트는 바이너리를 직접 반환하지 않고 **URL(정적 파일 or 오브젝트 스토리지 URL)** 로 제공한다.
- REST 리소스는 `api/stories/`를 기본(prefix)으로 설계한다.

### 비목표(초기)
- 결제/과금, 사용자 계정/권한의 완전한 제품화(단, API Key 수준의 보호는 포함)
- 실시간 스트리밍(웹소켓) 기반 TTS/이미지 스트리밍
- 완전한 멀티테넌시(단, 추후 확장 고려)

## 1) 현 상태(레포 기반) 요약
- 현재는 `main.py` CLI 파이프라인으로 동화 JSON 생성 후(선택) TTS WAV, 일러스트 파일을 `outputs/{run_id}/...`에 저장한다.
- `outputs/viewer/server.py`는 결과 폴더를 스캔해 **오디오/일러스트 URL 포함 JSON**을 반환하는 간단한 HTTP 서버를 제공한다(참고 구현).

### (참조) outputs 최신 산출물 디렉토리 구조
가장 최신 산출물(예: `outputs/20260213_211556_story_/`) 기준 구조는 아래와 같다.

```text
outputs/
  viewer/                               # 결과 뷰어(산출물 아님)
  {run_id}/                             # 예: 20260213_211556_story_
    story_{story_model}.json            # 예: story_gemini-2.5-flash.json
    audio/
      manifest.json                     # TTS 결과 요약/엔트리 목록
      01_{primary_lang_slug}/
        page_01_primary.wav
        ...
        page_24_primary.wav
      02_{secondary_lang_slug}/
        page_01_secondary.wav
        ...
        page_24_secondary.wav
    illustrations/
      manifest.json                     # 일러스트 결과 요약/엔트리 목록
      page_01.png
      ...
      page_24.png
```

추가 관찰(위 최신 run 기준):
- `audio/manifest.json`의 각 엔트리는 `{page_number, language, role, path, status}`를 포함하며 `path`는 `outputs/{run_id}/...` 형태로 기록되어 있다.
- `illustrations/manifest.json`의 각 엔트리는 `{page_number, status, path, prompt_mode}`를 포함하며 `path`는 `outputs/{run_id}/...` 형태로 기록되어 있다.
- 스토리 JSON(`story_*.json`)의 top-level 키는 `title_primary`, `title_secondary`, `author_name`, `primary_language`, `secondary_language`, `image_style`, `main_character_design`, `illustration_prefix`, `pages`이며,
  각 page는 `page_number`, `text_primary`, `text_secondary`, `illustration_prompt`, `illustration_scene_prompt`를 가진다.

## 2) 서비스 설계 개요

### 단일 서비스(초기) → 분리(향후)
초기에는 1개 FastAPI 서비스가 아래 책임을 모두 수행한다.
- 스토리 생성(LLM) → JSON 저장
- TTS 생성 → WAV 저장
- 일러스트 생성 → 이미지 저장
- 정적 결과물 서빙(개발/단일 노드 기준)

향후 트래픽/비용/장애 격리를 위해 분리 가능:
- `story-service`(텍스트 생성), `tts-service`, `illustration-service`, `asset-service`(URL/스토리지)

### 동기 vs 비동기(권장)
생성은 수십 초~수분이 걸릴 수 있으므로 **기본은 비동기 작업(Job) 기반**으로 설계한다.
- `POST /api/stories/`는 즉시 `202 Accepted`로 `story_id`와 `status_url`을 반환
- 클라이언트는 `GET /api/stories/{story_id}`로 폴링하거나, 필요 시 `GET /api/stories/{story_id}/events`(추후 SSE) 확장

## 3) 데이터 모델(REST 리소스)

### Story 리소스(권장 필드)
- `id`: string (예: `20260218_143701_story_mina-friendship` 같은 run_id)
- `status`: `queued | running | completed | failed | canceled`
- `created_at`, `updated_at`
- `request`: 생성 요청 파라미터(아이 이름/나이/언어/테마/추가 프롬프트/모델/옵션 등)
- `result`:
  - `story_json_url`: 동화 원본 JSON 파일 URL
  - `pages`: 페이지별 결과(텍스트 + 오디오/일러스트 URL)
  - `assets` 요약(오디오/일러스트 생성 여부, 실패 개수 등)
- `error`: 실패 시 `{code, message, detail?}`

### Page 리소스(Story 내부 포함)
- `page_number`: int
- `text_primary`, `text_secondary`
- `audio_primary_url`, `audio_secondary_url` (없으면 `null`)
- `illustration_url` (없으면 `null`)
- `illustration_prompt`, `illustration_scene_prompt`(선택)

## 4) URL/스토리지 전략(오디오/이미지)

### 개발/단일 노드(MVP)
- 결과물을 레포의 `outputs/` 하위에 저장(현 구조 유지)
- FastAPI에서 `outputs/`를 `StaticFiles`로 마운트:
  - 예: `GET /static/outputs/{run_id}/audio/...`
  - API 응답에는 이 경로를 포함한 **절대 URL** 또는 **상대 URL**을 반환

### 운영(권장)
- 결과물을 S3 호환 스토리지(또는 GCS)에 업로드
- API 응답에는:
  - Public URL(권한 필요 없을 때) 또는
  - Presigned URL(만료 포함) 반환
- 이 경우 FastAPI는 파일을 직접 서빙하지 않고 “메타데이터 + URL 발급”만 담당

## 5) REST API 설계 (`/api/stories`)

### 5.1 생성
`POST /api/stories/`
- 동화 생성 + (옵션) TTS + (옵션) 일러스트 작업을 “하나의 Story 생성 작업”으로 시작
- 응답: `202 Accepted`

요청 바디(예시)
```json
{
  "child_name": "Mina",
  "child_age": 5,
  "primary_lang": "Korean",
  "secondary_lang": "English",
  "theme": "Friendship",
  "extra_prompt": "Include a dragon",
  "generation": {
    "story_model": "gemini-2.5-flash",
    "enable_tts": true,
    "tts_model": "gemini-2.5-flash-preview-tts",
    "tts_voice": "Achernar",
    "tts_temperature": 1.0,
    "tts_request_interval_sec": 10.0,
    "enable_illustration": true,
    "illustration_model": "gemini-2.5-flash-image",
    "illustration_aspect_ratio": "16:9",
    "illustration_request_interval_sec": 1.0,
    "illustration_skip_existing": true
  }
}
```

응답 바디(예시)
```json
{
  "id": "20260218_143701_story_mina-friendship",
  "status": "queued",
  "status_url": "/api/stories/20260218_143701_story_mina-friendship",
  "result_url": "/api/stories/20260218_143701_story_mina-friendship/result"
}
```

### 5.2 조회(메타/상태)
`GET /api/stories/{story_id}`
- 상태, 요청 파라미터, 진행률(가능하면) 반환
- 완료 시 `result` 요약 포함(페이지 본문은 크면 분리 권장)

### 5.3 결과(페이지 포함)
`GET /api/stories/{story_id}/result`
- 페이지별 텍스트 + 오디오/일러스트 URL 포함 전체 결과 반환
- `outputs/viewer/server.py`의 `build_book_payload()` 형태를 FastAPI 스키마로 정식화하는 것을 권장

### 5.4 목록/검색
`GET /api/stories/`
- query:
  - `limit`, `cursor`(또는 `offset`)
  - `status`
  - `created_from`, `created_to`
  - `child_name`(옵션), `primary_lang`, `secondary_lang`
- 응답은 페이지 리스트를 제외한 “요약” 중심 권장

### 5.5 취소/삭제
`POST /api/stories/{story_id}/cancel`
- 진행 중 작업 중단(가능한 경우) 및 상태를 `canceled` 처리

`DELETE /api/stories/{story_id}`
- 메타데이터 삭제 + 결과물 정리(운영 정책에 따라 soft delete 권장)

### 5.6 부분 재생성(선택)
`POST /api/stories/{story_id}/tts`
- 기존 스토리 텍스트 기반으로 TTS만 재생성

`POST /api/stories/{story_id}/illustrations`
- 기존 스토리 텍스트 기반으로 일러스트만 재생성

## 6) 상태/에러/응답 규칙

### 상태 전이(예시)
- `queued` → `running` → `completed`
- `queued/running` → `failed` (에러 저장)
- `queued/running` → `canceled`

### 표준 에러 포맷(예시)
```json
{
  "error": {
    "code": "STORY_NOT_FOUND",
    "message": "story not found",
    "detail": {"id": "..." }
  }
}
```

### HTTP 코드 가이드
- `202`: 비동기 작업 시작
- `200`: 조회 성공
- `400`: 요청 파라미터 검증 실패
- `401/403`: 인증 실패
- `404`: story_id 없음
- `409`: 상태 충돌(이미 완료된 작업에 cancel 등)
- `500`: 내부 오류

## 7) 실행 구조(권장 모듈 구성)

레포 내 새 디렉토리 제안(예시):
```text
app/
  main.py                # FastAPI 앱 엔트리
  api/
    stories.py           # /api/stories 라우터
  schemas/
    story.py             # Pydantic 요청/응답 스키마
  services/
    generation_pipeline.py
    story_orchestrator.py
    story_result_builder.py
    output_paths.py      # 로컬 output 경로/URL 유틸
  workers/
    tasks.py             # 백그라운드 job 실행(선택)
```

## 8) 비동기 작업 처리(선택지)

### 옵션 A: FastAPI BackgroundTasks(MVP)
- 장점: 의존성 최소, 빠른 구현
- 단점: 프로세스 재시작 시 작업 유실, 스케일아웃 어려움

### 옵션 B: 작업 큐(권장)
- 예: RQ/Redis, Celery, arq/Redis 등
- 장점: 재시작/재시도/스케일링 용이
- 단점: Redis 등 인프라 필요

## 9) 메타데이터 저장(권장)

### MVP
- `outputs/{story_id}/meta.json` 같은 파일 기반 메타 저장
- 목록 조회는 디렉토리 스캔(현재 viewer와 유사)

### 운영 권장
- Postgres(또는 SQLite→Postgres 마이그레이션)로 Story 상태/요청/결과 URL 메타데이터 관리
- “파일 스캔” 대신 DB 조회로 목록/검색 성능 확보

## 10) 보안/운영 고려사항(최소)
- 인증: `X-API-Key` 헤더 기반(내부 서비스/초기 운영에 적합)
- 레이트리밋: IP 또는 API key 단위(고비용 생성 요청 보호)
- 요청 검증: 입력 길이 제한(프롬프트 폭주 방지), 허용 언어/모델 allowlist
- 로깅/추적: request_id, story_id, 단계별 소요시간, 외부 API 오류 기록

## 11) 구현 단계(현실적인 로드맵)

### Phase 1 (MVP, 로컬 서빙)
1. FastAPI 프로젝트 스캐폴딩 + `/health`
2. `POST /api/stories/` (story 텍스트만) → `outputs/`에 저장
3. `GET /api/stories/{id}` / `GET /api/stories/{id}/result`
4. `outputs/` StaticFiles 마운트 → `story_json_url` 반환

### Phase 2 (옵션 결과물)
5. TTS 옵션 처리(`enable_tts`) + 페이지별 `audio_*_url` 반환
6. 일러스트 옵션 처리(`enable_illustration`) + `illustration_url` 반환
7. 실패/부분 실패(예: 일부 페이지만 실패)도 결과 JSON에 반영

### Phase 3 (운영화)
8. 작업 큐 도입(재시도/동시성/우선순위)
9. DB 메타데이터 저장 + 목록/검색 강화
10. 오브젝트 스토리지 업로드 + presigned URL

## 12) 기존 코드 재사용 포인트
- 스토리 생성: `generators/story/story_generator.py`의 `StoryGenerator.generate_story()`
- TTS: `generators/tts/tts_generator.py`의 `TTSGenerator.generate_book_audio()`
- 일러스트: `generators/illustration/illustration_pipeline.py`의 `IllustrationGenerator.generate_from_story()`
- 결과 JSON 형태 참고: `outputs/viewer/server.py`의 `build_book_payload()` (페이지별 URL 매핑 로직 포함)
