<br>

<div align="center">
    <div>
        <h2><b>MORETALE</b></h2>
        <p><i>More Language, More Tale!</i></p>
    </div>
</div>

<br>

<h1 align="center">MORETALE AI</h1>

아이들의 이야기를 생성하고, 소리와 이미지로 확장하는 AI 이야기 생성 서버.

**MORETALE AI**는 동화 생성 요청을 비동기 작업으로 처리하고, 결과 JSON, 퀴즈, TTS, 표지 및 내부 일러스트를 URL 기반으로 제공합니다.

Backend와 연동하여 다문화 가정 어린이와 부모가 함께 사용할 수 있는 이중언어 동화 생성 흐름을 지원합니다.

<br>

<div align="center">

<a href="https://www.python.org/">
<img src="https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=Python&logoColor=white" alt="Python 3.12"/>
</a>
<a href="https://fastapi.tiangolo.com/">
<img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=FastAPI&logoColor=white" alt="FastAPI"/>
</a>
<a href="https://www.uvicorn.org/">
<img src="https://img.shields.io/badge/Uvicorn-499848?style=flat-square&logo=Gunicorn&logoColor=white" alt="Uvicorn"/>
</a>
<a href="https://docs.pydantic.dev/">
<img src="https://img.shields.io/badge/Pydantic-E92063?style=flat-square&logo=Pydantic&logoColor=white" alt="Pydantic"/>
</a>
<a href="https://ai.google.dev/">
<img src="https://img.shields.io/badge/Google%20GenAI-4285F4?style=flat-square&logo=Google&logoColor=white" alt="Google GenAI"/>
</a>
<a href="https://cloud.google.com/storage">
<img src="https://img.shields.io/badge/Cloud%20Storage-AECBFA?style=flat-square&logo=GoogleCloud&logoColor=black" alt="Google Cloud Storage"/>
</a>
<a href="https://www.docker.com/">
<img src="https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=Docker&logoColor=white" alt="Docker"/>
</a>

</div>

<div align="center">

<h4>Python 3.12 | FastAPI | Uvicorn | Pydantic | Google GenAI | Google Cloud Storage | Docker</h4>

</div>

---

## 👥 Developer

<div align="center">

| <img src="https://github.com/itisyijy.png" width="120"/><br><a href="https://github.com/itisyijy"><b>itisyijy</b></a> |
|:------------------------------------------------------------------------------------------------------------------------:|
|                                           <i>SeoulTech</i>                                           |
|                                                      Member, AI                                                       |

</div>

---

## 📌 Overview

MORETALE AI는 동화 생성 요청을 받아 비동기 Job으로 실행하는 FastAPI 기반 마이크로서비스입니다.

스토리 생성, critic 품질 평가, 퀴즈 생성, TTS 생성, 표지 및 내부 일러스트 생성 흐름을 하나의 파이프라인으로 연결합니다.
생성 결과는 JSON, 퀴즈, TTS, 일러스트 산출물로 구성되며 로컬 정적 경로 또는 Google Cloud Storage URL 기반으로 제공할 수 있습니다.

CLI 사용 가이드는 `cli/README.md`를 참고하세요.

---

## ⚒️ Detailed Tech Stack

| Role       | Type |
|------------|------|
| Language   | ![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=Python&logoColor=white) |
| Framework  | ![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=FastAPI&logoColor=white) |
| ASGI Server | ![Uvicorn](https://img.shields.io/badge/Uvicorn-499848?style=flat-square&logo=Gunicorn&logoColor=white) |
| Schema     | ![Pydantic](https://img.shields.io/badge/Pydantic-E92063?style=flat-square&logo=Pydantic&logoColor=white) |
| AI SDK     | ![Google GenAI](https://img.shields.io/badge/Google%20GenAI-4285F4?style=flat-square&logo=Google&logoColor=white) |
| Storage    | ![Google Cloud Storage](https://img.shields.io/badge/Cloud%20Storage-AECBFA?style=flat-square&logo=GoogleCloud&logoColor=black) |
| Deployment | ![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=Docker&logoColor=white) |

---

## ✨ Core Features

### 📖 Story Generation

> 사용자 요청을 기반으로 동화 생성 작업을 시작하고 결과를 조회할 수 있습니다.

- `POST /api/stories/`: 스토리 생성 작업 시작 (`202`)
- `GET /api/stories/{story_id}`: 작업 상태 조회
- `GET /api/stories/{story_id}/result`: 결과 조회
- `DELETE /api/stories/{story_id}`: 작업 취소

### 🧠 Quiz

> 생성된 동화를 기반으로 퀴즈 산출물을 생성합니다.

- 퀴즈 생성 옵션 처리
- 퀴즈 모델 allowlist 검증
- 퀴즈 결과를 스토리 결과 응답에 포함

### 🔊 TTS

> 동화 내용을 음성으로 들을 수 있도록 TTS 산출물을 생성합니다.

- Gemini TTS 기반 음성 생성
- TTS 생성 옵션 처리
- 생성된 음성 산출물 URL 제공

### 🎨 Illustration

> 동화 표지와 내부 일러스트 생성 흐름을 지원합니다.

- 표지 일러스트 생성 옵션 처리
- 내부 일러스트 생성 옵션 처리
- 일러스트 aspect ratio 설정 지원

### 🩺 Health & Operation

> 운영 환경에서 필요한 헬스체크와 요청 추적 기능을 제공합니다.

- `GET /health`: 헬스체크 및 필수 의존성 검사
- `/static/outputs/...`: 로컬 산출물 정적 서빙
- `X-Request-ID` 응답 헤더
- API key 단위 인메모리 레이트리밋
- 모델 및 언어 allowlist 검증
- 입력 길이 제한
- 서버 재시작 시 `running` 상태 Job 자동 복구

### 🧩 Current Implementation Status

> GitHub main 기준 현재 구현된 서버 범위입니다.

- Phase 1: 서버 스캐폴딩, 비동기 job, 상태/결과 API (라우트 핸들러 전체 async)
- Phase 2: TTS/일러스트/퀴즈 옵션 처리, 부분 실패 표현
- Phase 3-Lite: 운영 하드닝
- 환경변수 기반 스토리 페이지 수
- 선택형 critic 품질 루프
- 퀴즈 생성 (`generators/quiz`)
- 뷰어 자동재생, 인쇄, 퀴즈 UI

---

## ⚙️ Architecture

> MORETALE AI는 Backend에서 전달받은 동화 생성 요청을 비동기 Job으로 처리합니다.

> 생성 파이프라인은 story, critic, quiz, tts, illustration 모듈을 연결하여 스토리와 부가 산출물을 생성합니다.

> 산출물은 로컬 outputs 경로 또는 Google Cloud Storage에 저장되고, 결과 응답에서는 접근 가능한 URL 형태로 제공됩니다.

```text
Backend
  ↓
FastAPI Story API
  ↓
Async Job Orchestrator
  ↓
Generation Pipeline
  ↓
Story / Critic / Quiz / TTS / Illustration Generators
  ↓
Local Outputs or Google Cloud Storage
```

---

## 🛫 Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/GDGoC-quadS-Team1/MoreTale-AI.git
cd MoreTale-AI
```

### 2. Create Virtual Environment

```bash
source .moretale/bin/activate
```

없다면 아래 명령어로 가상환경을 생성합니다.

```bash
python3 -m venv .moretale
source .moretale/bin/activate
pip install -r requirements.txt
```

### 3. Configure Environment Variables

주요 환경변수는 다음과 같습니다.

```env
# 인증 (콤마로 다중 키 지원)
MORETALE_API_KEY=key-a,key-b

# 선택: outputs 경로
# MORETALE_OUTPUTS_DIR=/absolute/path/to/outputs

# 선택: 산출물 저장소 (Cloud Run 운영 권장)
MORETALE_STORAGE_BACKEND=gcs
MORETALE_GCS_BUCKET=moretale-assets
MORETALE_GCS_KEY_PREFIX=generated

# 생성기 키
GEMINI_STORY_API_KEY=YOUR_STORY_API_KEY
GEMINI_TTS_API_KEY=YOUR_TTS_API_KEY
NANO_BANANA_KEY=YOUR_ILLUSTRATION_API_KEY

# Phase 3-Lite 하드닝
MORETALE_RATE_LIMIT_POST_STORIES_PER_MIN=5
MORETALE_THEME_MAX_LEN=120
MORETALE_EXTRA_PROMPT_MAX_LEN=2000
MORETALE_CHILD_NAME_MAX_LEN=40
MORETALE_STORY_PAGE_COUNT=32
MORETALE_ALLOWED_STORY_MODELS=gemini-2.5-flash
MORETALE_ALLOWED_CRITIC_MODELS=gemini-2.5-flash
MORETALE_ALLOWED_QUIZ_MODELS=gemini-2.5-flash
MORETALE_ALLOWED_TTS_MODELS=gemini-2.5-flash-preview-tts
MORETALE_ALLOWED_ILLUSTRATION_MODELS=gemini-2.5-flash-image
MORETALE_ALLOWED_LANGUAGES=Korean,English,Japanese,Chinese,Spanish,Vietnamese,French,German
MORETALE_HEALTHCHECK_TIMEOUT_SEC=5
```

### 4. Run the Application

```bash
uvicorn app.main:app --reload
```

### 5. Check the Server

서버가 정상적으로 실행되면 아래 주소로 접근할 수 있습니다.

```text
http://127.0.0.1:8000
```

---

## 🐳 Docker

### Build Docker Image

MORETALE AI 애플리케이션을 Docker 이미지로 빌드합니다.

```bash
docker build -t moretale-ai .
```

### Run Docker Container

Cloud Run 컨테이너는 Dockerfile의 기본 CMD로 `$PORT`를 사용합니다.

```bash
docker run --rm -p 8080:8080 -e PORT=8080 --env-file .env moretale-ai
```

---

## 🚀 Deployment

> MORETALE AI는 Docker 기반 컨테이너로 실행되며 Cloud Run 운영 환경을 고려합니다.

### Deployment Flow

```text
GitHub Repository
  ↓
Docker Build
  ↓
Cloud Run Deploy
  ↓
Google Cloud Storage
```

### Storage Backend

`MORETALE_STORAGE_BACKEND=gcs`이면 story, TTS, quiz 산출물을 Google Cloud Storage에 업로드하고 `https://storage.googleapis.com/{bucket}/...` URL을 응답합니다.

---

## 📂 Folder Structure

```text
MoreTale-AI
├── app
│   ├── api
│   │   ├── internal_ai.py
│   │   └── stories.py
│   ├── core
│   │   ├── auth.py
│   │   ├── config.py
│   │   └── languages.py
│   ├── schemas
│   │   ├── internal_ai.py
│   │   └── story.py
│   ├── services
│   │   ├── generation_pipeline.py
│   │   ├── health.py
│   │   ├── internal_ai_jobs.py
│   │   ├── internal_ai_runners.py
│   │   ├── job_store.py
│   │   ├── output_paths.py
│   │   ├── rate_limiter.py
│   │   ├── request_context.py
│   │   ├── result_manifests.py
│   │   ├── storage.py
│   │   ├── storage_backend.py
│   │   ├── story_orchestrator.py
│   │   └── story_result_builder.py
│   └── main.py
│
├── generators
│   ├── critic
│   ├── illustration
│   ├── quiz
│   ├── story
│   └── tts
│
├── prompts
│   └── modules
│
├── outputs
│   └── viewer
│
├── docs
├── cli
├── tests
├── Dockerfile
├── requirements.txt
└── README.md
```

### Application Layer

| Package  | Description |
|----------|-------------|
| api      | Story API, internal AI API 라우터 |
| core     | 인증, 설정, 언어 관련 공통 구성 |
| schemas  | 요청 및 응답 스키마 |
| services | 비동기 Job, 생성 파이프라인, 저장소, 헬스체크, 응답 조립 |

### Generator Layer

| Module       | Description |
|--------------|-------------|
| story        | Gemini 기반 동화 생성 |
| critic       | 동화 품질 평가 및 재생성 피드백 |
| quiz         | Gemini 기반 퀴즈 생성 |
| tts          | Gemini TTS 기반 음성 생성 |
| illustration | Nano Banana 기반 일러스트 생성 |

---

## ✅ Main Contributions

- FastAPI 기반 AI 마이크로서비스 구조 설계
- 비동기 story generation Job API 구현
- story, critic, quiz, tts, illustration 생성 파이프라인 구성
- API key 인증 및 요청별 `X-Request-ID` 처리
- 모델 및 언어 allowlist 검증
- 입력 길이 제한 및 API key 단위 레이트리밋 적용
- 서버 재시작 시 진행 중 Job 복구 처리
- 로컬 outputs 및 Google Cloud Storage 기반 산출물 제공
- Docker 기반 실행 환경 구성

---

## 🧪 API Examples

### Create Story Job

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

### Check Story Status

```bash
curl -H "X-API-Key: key-a" \
  http://127.0.0.1:8000/api/stories/{story_id}
```

### Get Story Result

```bash
curl -H "X-API-Key: key-a" \
  http://127.0.0.1:8000/api/stories/{story_id}/result
```

---

## 📐 Response & Operation Rules

- 스토리 생성 시 `prompts/style_guide.txt`는 항상 시스템 프롬프트에 포함됩니다.
- 요청의 `include_style_guide` 필드는 하위호환용으로만 유지되며, 값과 무관하게 스타일 가이드는 적용됩니다.
- `generation.enable_critic=true`이면 스토리 생성 후 critic agent가 품질을 평가하고, `revise` 판정 시 최대 `critic_max_retries`회까지 스토리를 재생성합니다.
- critic 실행 실패는 해당 생성 작업 실패로 처리됩니다.
- 결과 응답에는 `critic.enabled`, `critic.attempts`, `critic.final_verdict`, `critic.issue_count`, `critic.results`가 포함됩니다.
- critic 비활성화 시 `attempts=0`, `final_verdict=null`, `results=[]`입니다.
- Gemini/Google SDK 기반 생성기는 실제 생성 작업 시점에 lazy import됩니다.
- `/health`는 Cloud Run 배포 전 검증을 위해 필수 API key, outputs 쓰기 권한, Gemini 모델 접근성을 실제로 검사합니다.
- `MORETALE_STORAGE_BACKEND=gcs`일 때 `/health`는 GCS test object 업로드/삭제까지 확인합니다.
- `/health`의 필수 의존성 검사 실패 시 `503`과 `status: "unhealthy"`를 반환합니다.
- Secret 값은 응답에 포함하지 않습니다.
- `MORETALE_STORAGE_BACKEND=gcs`이면 story/TTS/quiz 산출물을 GCS에 업로드하고 `https://storage.googleapis.com/{bucket}/...` URL을 응답합니다.
- Cloud Run 서비스 계정에는 대상 버킷의 object write 권한이 필요합니다.

### Standard Error Format

```json
{
  "error": {
    "code": "SOME_CODE",
    "message": "human readable message",
    "detail": {}
  }
}
```

### Common Response Header

- `X-Request-ID`

### Main Status Codes

| Status | Description |
|--------|-------------|
| `202`  | 비동기 생성 시작 |
| `200`  | 조회 성공 |
| `401`  | API key 인증 실패 |
| `404`  | story_id 없음 (`STORY_NOT_FOUND`) |
| `409`  | 결과 준비 전 상태 (`STORY_NOT_READY`) |
| `422`  | 입력 검증 실패 (`VALIDATION_ERROR`) |
| `429`  | 레이트리밋 초과 (`RATE_LIMIT_EXCEEDED`) |

---

## 🧪 Tests

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

---

## 🔗 Document Links

- CLI 사용 가이드: `cli/README.md`
- 생성기 모듈 구조: `generators/README.md`
- FastAPI 구현 계획서: `docs/fastapi-ai-server-impl-plan.md`
- 백엔드 연동 가이드: `docs/backend-integration-guide.md`
- 백엔드 OpenAPI 스냅샷: `docs/moretale-backend-openapi.json`
