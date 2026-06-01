# Generators 구조 안내

`generators/`는 도메인별 하위 디렉토리로 구성됩니다.

## 디렉토리 구성

- `story/`
  - `story_generator.py`: Gemini 텍스트 모델을 호출해 동화 JSON(`Story`)를 생성합니다.
  - `story_model.py`: `Story`, `Page` Pydantic 모델의 canonical 정의입니다.
  - `story_prompts.py`: 스토리 프롬프트 로더/템플릿 처리(`StoryPrompt`)입니다.
  - `module_loader.py`: age, culture, family, gender, interest, language 프롬프트 모듈을 로드합니다.
    - 텍스트 리소스는 루트 `prompts/*.txt`를 읽습니다.

- `critic/`
  - `critic_generator.py`: 생성된 동화를 평가하고 `ok` 또는 `revise` 판정을 반환합니다.
  - `critic_model.py`: critic 결과와 issue 스키마의 canonical 정의입니다.

- `quiz/`
  - `quiz_generator.py`: 동화 JSON을 기반으로 독해 퀴즈를 생성합니다.
  - `quiz_model.py`: 퀴즈, 문항, 선택지, 정답 스키마의 canonical 정의입니다.
  - `quiz_prompts.py`: 퀴즈 시스템/사용자 프롬프트 로더입니다.

- `tts/`
  - `tts_generator.py`: TTS 오케스트레이션 진입점(`TTSGenerator`)
  - `tts_pipeline.py`: 페이지/언어 반복 처리와 상태 집계
  - `tts_runtime.py`: rate limit + retry(backoff)
  - `tts_stream.py`: 스트리밍 응답에서 오디오 바이트 수집
  - `tts_audio.py`: MIME 파싱 및 WAV 변환
  - `tts_text.py`: TTS 프롬프트/언어 슬러그 유틸
  - `tts_manifest.py`: `audio/manifest.json` 저장

- `illustration/`
  - `illustration_generator.py`: 동화 JSON(`cover_illustration_prompt`, `illustration_prompt`, `illustration_scene_prompt`)를 사용해 표지와 페이지별 이미지를 생성합니다.
  - `illustration_cli.py`: 기존 동화 JSON으로 일러스트만 생성하는 CLI 진입점입니다.
  - `illustration_pipeline.py`: 표지와 페이지별 이미지 생성 흐름을 조율합니다.
  - `illustration_cover_prompt.py`: 표지 이미지 프롬프트를 구성합니다.
  - `illustration_prompt_builder.py`: 페이지별 이미지 프롬프트를 구성합니다.
  - `illustration_prompt_utils.py`: 일러스트 prefix/scene 분리 유틸의 canonical 정의입니다.
  - `illustration_image_client.py`: 이미지 생성 API 호출을 담당합니다.
  - `illustration_storage.py`: 생성 이미지 저장을 담당합니다.
  - `illustration_env.py`: 일러스트 생성 환경변수 처리를 담당합니다.
    - 기본 API 키: `.env`의 `NANO_BANANA_KEY`
    - 출력: `illustrations/cover.*`, `illustrations/page_XX.*`, `illustrations/manifest.json`

## Import 호환성

- 내부 구현의 canonical import는 `generators/*`를 사용합니다.
- `prompts/`는 텍스트 리소스(`*.txt`) 전용이며 파이썬 모듈은 제공하지 않습니다.
- 모델 스키마는 `generators.story.story_model` 경로만 지원합니다.

## 호출 흐름 (TTS)

1. `main.py`가 `TTSGenerator.generate_book_audio(...)` 호출
2. `generators/tts/tts_generator.py`가 설정/의존성 준비
3. `generators/tts/tts_pipeline.py`가 페이지와 언어를 순회
4. 요청 단위로 `tts_runtime.py`, `tts_stream.py`, `tts_audio.py`를 조합
5. 완료 후 `tts_manifest.py`가 매니페스트 저장

## 호출 흐름 (Story Pipeline)

1. `main.py` 또는 FastAPI route가 `StoryPipelineRequest`를 구성
2. `app/services/generation_pipeline.py`가 story 생성 실행
3. `enable_critic=true`이면 critic 평가 후 필요 시 재생성
4. `enable_quiz=true`이면 `generators/quiz`로 퀴즈 JSON 생성
5. `enable_tts=true`이면 `generators/tts`로 페이지별 오디오 생성
6. `enable_illustration=true`이면 `generators/illustration`으로 표지/내부 일러스트 생성
7. 결과 파일과 manifest를 `outputs/{run_id}/...`에 저장

## 유지보수 가이드

- 오디오 포맷 확장은 `generators/tts/tts_audio.py`를 먼저 수정합니다.
- 재시도/요청 간격 정책은 `generators/tts/tts_runtime.py`에서 처리합니다.
- 결과 경로/집계 포맷 변경은 `generators/tts/tts_pipeline.py`와 `generators/tts/tts_manifest.py`를 함께 수정합니다.
- 퀴즈 스키마 변경은 `generators/quiz/quiz_model.py`와 backend 연동 응답을 함께 확인합니다.
- critic 판정 기준 변경은 `prompts/critic_system_instruction.txt`와 `generators/critic/critic_model.py`를 함께 확인합니다.
