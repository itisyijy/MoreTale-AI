# MoreTale-AI CLI

`main.py` 기반 CLI 파이프라인 사용 가이드입니다.

## 개요

CLI는 Gemini API를 사용해 다음을 생성합니다.

- 이중언어 동화 JSON
- (선택) critic agent 품질 평가 및 최대 2회 재생성
- (선택) 페이지 단위 TTS 오디오(WAV)
- (선택) 표지 이미지(`5:4`) + 페이지 단위 일러스트 이미지(`1:1`)

모든 결과물은 `outputs/{run_id}/...`에 저장됩니다.

## 빠른 시작

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
MORETALE_STORY_PAGE_COUNT=32
GEMINI_STORY_API_KEY=YOUR_STORY_API_KEY
GEMINI_TTS_API_KEY=YOUR_TTS_API_KEY
NANO_BANANA_KEY=YOUR_ILLUSTRATION_API_KEY
```

`MORETALE_STORY_PAGE_COUNT`는 필수값이며 `1`부터 `32` 사이의 정수만 허용됩니다.

### 3) 동화 생성

```bash
python main.py \
  --child_name "Mina" \
  --child_age 5 \
  --primary_lang "Korean" \
  --secondary_lang "English" \
  --theme "Friendship" \
  --extra_prompt "Include a dragon" \
  --model_name "gemini-2.5-flash"
```

출력:

```text
outputs/{timestamp}_story_{slug}/story_{model_name}.json
```

### 4) 동화 + 퀴즈 생성

```bash
python main.py \
  --child_name "Mina" \
  --child_age 5 \
  --primary_lang "Korean" \
  --secondary_lang "English" \
  --theme "Friendship" \
  --enable_quiz \
  --quiz_model "gemini-2.5-flash" \
  --quiz_question_count 5
```

퀴즈 출력:

```text
outputs/{timestamp}_story_{slug}/quiz_{quiz_model}.json
```

### 5) 동화 + critic 품질 루프

```bash
python main.py \
  --child_name "Mina" \
  --child_age 5 \
  --primary_lang "Korean" \
  --secondary_lang "English" \
  --theme "Friendship" \
  --enable_critic \
  --critic_model "gemini-2.5-flash" \
  --critic_max_retries 2
```

critic이 `ok`를 반환하면 그대로 저장하고, `revise`를 반환하면 blocker/major issue와 global note를 반영해 최대 `--critic_max_retries`회 다시 생성합니다. critic 실행 실패는 파이프라인 실패로 처리됩니다.

### 6) 동화 + TTS 생성

```bash
python main.py \
  --child_name "Mina" \
  --primary_lang "Korean" \
  --secondary_lang "English" \
  --enable_tts \
  --tts_model "gemini-2.5-flash-preview-tts" \
  --tts_voice "Achernar" \
  --tts_temperature 1.0 \
  --tts_request_interval_sec 10.0
```

TTS 출력:

```text
outputs/{timestamp}_story_{slug}/audio/01_<primary-lang-slug>/page_01_primary.wav
outputs/{timestamp}_story_{slug}/audio/02_<secondary-lang-slug>/page_01_secondary.wav
outputs/{timestamp}_story_{slug}/audio/manifest.json
```

### 7) 동화 + 일러스트 일괄 생성

```bash
python main.py \
  --child_name "Mina" \
  --primary_lang "Korean" \
  --secondary_lang "English" \
  --enable_illustration \
  --illustration_model "gemini-2.5-flash-image" \
  --illustration_aspect_ratio "1:1" \
  --illustration_cover_aspect_ratio "5:4" \
  --illustration_request_interval_sec 1.0 \
  --illustration_skip_existing
```

### 8) 기존 동화 JSON으로 일러스트만 생성

```bash
python generators/illustration/illustration_generator.py \
  --story_json outputs/{timestamp}_story_{slug}/story_gemini-2.5-flash.json \
  --cover_aspect_ratio "5:4" \
  --skip_existing
```

## CLI 옵션

- `--child_name` (필수): 아이 이름
- `--child_age` (선택): 아이 나이
- `--primary_lang` (필수): 주 언어
- `--secondary_lang` (필수): 보조 언어
- `--theme` (선택): 테마
- `--extra_prompt` (선택): 추가 요청사항
- `prompts/style_guide.txt`는 항상 시스템 프롬프트에 포함됨
- `--include_style_guide` (선택): 하위호환용 no-op 옵션
- `--model_name` (선택, 기본 `gemini-2.5-flash`): 스토리 모델
- `MORETALE_STORY_PAGE_COUNT` 환경변수: 생성할 페이지 수
- `--enable_tts` (선택): TTS 생성 활성화
- `--enable_critic` (선택): critic agent 품질 루프 활성화
- `--critic_model` (선택, 기본 `gemini-2.5-flash`)
- `--critic_max_retries` (선택, 기본 `2`): `revise` 판정 시 최대 재생성 횟수
- `--enable_quiz` (선택): 퀴즈 생성 활성화
- `--quiz_model` (선택, 기본 `gemini-2.5-flash`)
- `--quiz_question_count` (선택, 기본 `5`)
- `--tts_model` (선택, 기본 `gemini-2.5-flash-preview-tts`)
- `--tts_voice` (선택, 기본 `Achernar`)
- `--tts_temperature` (선택, 기본 `1.0`)
- `--tts_request_interval_sec` (선택, 기본 `10.0`)
- `--enable_illustration` (선택): 일러스트 생성 활성화
- `--illustration_model` (선택, 기본 `gemini-2.5-flash-image`)
- `--illustration_aspect_ratio` (선택, 기본 `1:1`): 내부 삽화 비율
- `--illustration_cover_aspect_ratio` (선택, 기본 `5:4`): 표지 비율
- `--illustration_request_interval_sec` (선택, 기본 `1.0`)
- `--illustration_skip_existing` (선택): 기존 파일 있으면 스킵
- `--illustration_skip_cover` (선택): 표지 생성 생략

## 출력 JSON 스키마(요약)

- `title_primary`
- `title_secondary`
- `author_name`
- `primary_language`
- `secondary_language`
- `image_style`
- `main_character_design`
- `illustration_prefix` (선택)
- `cover_illustration_prompt` (선택)
- `pages` (`MORETALE_STORY_PAGE_COUNT` 값과 동일)
  - `page_number`
  - `text_primary`
  - `text_secondary`
  - `illustration_prompt`
  - `illustration_scene_prompt` (선택)

## 테스트

```bash
python -m unittest discover -s tests -v
```

## 트러블슈팅

- `GEMINI_STORY_API_KEY environment variable not set.`
- `GEMINI_TTS_API_KEY environment variable not set.`
- `NANO_BANANA_KEY environment variable not set.`
- `ModuleNotFoundError`

위 오류는 대부분 환경변수 누락 또는 가상환경/패키지 미설치에서 발생합니다.
