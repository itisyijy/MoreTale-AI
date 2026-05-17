# MoreTale-AI Server

MoreTale-AI의 FastAPI 마이크로서비스입니다.  
동화 생성 요청을 받아 비동기 작업으로 처리하고, 결과(JSON/퀴즈/TTS/표지+내부 일러스트)를 URL 기반으로 제공합니다.

CLI 사용 가이드는 `cli/README.md`를 참고하세요.

## 서버 범위

- `POST /api/stories/`: 스토리 생성 작업 시작 (`202`)
- `GET /api/stories/{story_id}`: 작업 상태 조회
- `GET /api/stories/{story_id}/result`: 결과 조회
- `DELETE /api/stories/{story_id}`: 작업 취소
- `GET /healthz`: 헬스체크
- `/static/outputs/...`: 로컬 산출물 정적 서빙

## 현재 구현 상태

- Phase 1: 서버 스캐폴딩, 비동기 job, 상태/결과 API (라우트 핸들러 전체 async)
- Phase 2: TTS/일러스트/퀴즈 옵션 처리, 부분 실패 표현
- Phase 3-Lite: 운영 하드닝
  - `X-Request-ID` 응답 헤더
  - 인메모리 레이트리밋 (`POST /api/stories/`, API key 단위)
  - 모델/언어 allowlist 검증 (퀴즈 모델 포함)
  - 입력 길이 제한
  - 서버 재시작 시 `running` 상태 Job 자동 복구 (`SERVER_RESTARTED` → `failed`)
- 스토리 32페이지, 선택형 critic 품질 루프, 퀴즈 생성 (`generators/quiz`), 뷰어 자동재생/인쇄/퀴즈 UI 추가

## 프로젝트 구조

```text
app/
  main.py
  api/
    stories.py
  core/
    auth.py
    config.py
  schemas/
    story.py
  services/
  generation_pipeline.py   # 공유 생성 파이프라인 (story → quiz → tts → illustration)
    story_orchestrator.py    # 비동기 job 실행 및 상태 관리
    story_result_builder.py  # 결과 응답 조립
    storage.py               # 저장소 re-export 진입점
    output_paths.py          # 출력 경로 헬퍼
    result_manifests.py      # 산출물 매니페스트
    job_store.py             # 파일 기반 job 상태 저장 (meta.json)
    rate_limiter.py          # API key 단위 레이트리밋
    request_context.py       # X-Request-ID 컨텍스트

generators/
  story/                     # 동화 생성 (Gemini)
  critic/                    # 동화 품질 평가 및 재생성 피드백 (Gemini)
  quiz/                      # 퀴즈 생성 (Gemini)
  tts/                       # TTS 생성 (Gemini TTS)
  illustration/              # 일러스트 생성 (Nano Banana)
```

## 빠른 시작 (서버)

### 1) 가상환경

```bash
source .moretale/bin/activate
```

없다면:

```bash
python3 -m venv .moretale
source .moretale/bin/activate
pip install -r requirements.txt
```

### 2) 환경변수

```env
# 인증 (콤마로 다중 키 지원)
MORETALE_API_KEY=key-a,key-b

# 선택: outputs 경로
# MORETALE_OUTPUTS_DIR=/absolute/path/to/outputs

# 생성기 키
GEMINI_STORY_API_KEY=YOUR_STORY_API_KEY
GEMINI_TTS_API_KEY=YOUR_TTS_API_KEY
NANO_BANANA_KEY=YOUR_ILLUSTRATION_API_KEY

# Phase 3-Lite 하드닝
MORETALE_RATE_LIMIT_POST_STORIES_PER_MIN=5
MORETALE_THEME_MAX_LEN=120
MORETALE_EXTRA_PROMPT_MAX_LEN=2000
MORETALE_CHILD_NAME_MAX_LEN=40
MORETALE_ALLOWED_STORY_MODELS=gemini-2.5-flash
MORETALE_ALLOWED_CRITIC_MODELS=gemini-2.5-flash
MORETALE_ALLOWED_QUIZ_MODELS=gemini-2.5-flash
MORETALE_ALLOWED_TTS_MODELS=gemini-2.5-flash-preview-tts
MORETALE_ALLOWED_ILLUSTRATION_MODELS=gemini-2.5-flash-image
MORETALE_ALLOWED_LANGUAGES=Korean,English,Japanese,Chinese,Spanish,Vietnamese,French,German
```

### 3) 실행

```bash
uvicorn app.main:app --reload
```

## API 예시

### 생성

```bash
curl -X POST http://127.0.0.1:8000/api/stories/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: key-a" \
  -d '{
    "child_name": "Mina",
    "child_age": 5,
    "primary_lang": "Korean",
    "secondary_lang": "English",
    "theme": "Friendship",
    "extra_prompt": "Include a dragon",
    "generation": {
      "story_model": "gemini-2.5-flash",
      "enable_quiz": true,
      "quiz_model": "gemini-2.5-flash",
      "quiz_question_count": 5,
      "enable_critic": true,
      "critic_model": "gemini-2.5-flash",
      "critic_max_retries": 2,
      "enable_tts": true,
      "enable_illustration": true,
      "enable_cover_illustration": true,
      "illustration_aspect_ratio": "1:1",
      "illustration_cover_aspect_ratio": "5:4"
    }
  }'
```

### 상태 조회

```bash
curl -H "X-API-Key: key-a" \
  http://127.0.0.1:8000/api/stories/{story_id}
```

### 결과 조회

```bash
curl -H "X-API-Key: key-a" \
  http://127.0.0.1:8000/api/stories/{story_id}/result
```

## 응답/운영 규약

- 스토리 생성 시 `prompts/style_guide.txt`는 항상 시스템 프롬프트에 포함됩니다.
- 요청의 `include_style_guide` 필드는 하위호환용으로만 유지되며, 값과 무관하게 스타일 가이드는 적용됩니다.
- `generation.enable_critic=true`이면 스토리 생성 후 critic agent가 품질을 평가하고, `revise` 판정 시 최대 `critic_max_retries`회까지 스토리를 재생성합니다. critic 실행 실패는 해당 생성 작업 실패로 처리됩니다.
- 결과 응답에는 `critic.enabled`, `critic.attempts`, `critic.final_verdict`, `critic.issue_count`, `critic.results`가 포함됩니다. critic 비활성화 시 `attempts=0`, `final_verdict=null`, `results=[]`입니다.
- Gemini/Google SDK 기반 생성기는 실제 생성 작업 시점에 lazy import됩니다. `/healthz`, 상태 조회, 결과 조회는 생성기 SDK 로드 없이 동작해야 합니다.

- 표준 에러 포맷:

```json
{
  "error": {
    "code": "SOME_CODE",
    "message": "human readable message",
    "detail": {}
  }
}
```

- 공통 응답 헤더:
  - `X-Request-ID`

- 주요 상태 코드:
  - `202`: 비동기 생성 시작
  - `200`: 조회 성공
  - `401`: API key 인증 실패
  - `404`: story_id 없음 (`STORY_NOT_FOUND`)
  - `409`: 결과 준비 전 상태 (`STORY_NOT_READY`)
  - `422`: 입력 검증 실패 (`VALIDATION_ERROR`)
  - `429`: 레이트리밋 초과 (`RATE_LIMIT_EXCEEDED`)

## 테스트

```bash
python -m unittest tests.test_fastapi_phase1 -v
python -m unittest tests.test_fastapi_phase2 -v
python -m unittest tests.test_fastapi_phase3_hardening -v
python -m unittest tests.test_fastapi_phase4_cancel -v
```

전체 테스트:

```bash
python -m unittest discover -s tests -v
```

## 문서 링크

- CLI 사용 가이드: `cli/README.md`
- 생성기 모듈 구조: `generators/README.md`
- FastAPI 구현 계획서: `docs/fastapi-ai-server-impl-plan.md`
- 백엔드 연동 가이드: `docs/backend-integration-guide.md`
- 백엔드 OpenAPI 스냅샷: `docs/moretale-backend-openapi.json`
