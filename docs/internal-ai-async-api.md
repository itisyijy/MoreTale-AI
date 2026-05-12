# Internal AI Async API

This document defines the AI-side contract that the Spring backend can call before
backend integration is implemented. Public user-facing Swagger APIs remain owned
by the backend.

## Common Contract

- Base path: `/internal/ai`
- Auth: `X-API-Key`
- Job creation response status: `202 Accepted`
- Job statuses: `queued`, `running`, `completed`, `failed`, `canceled`
- Completion callback body includes only job metadata and `resultUrl`; callers fetch
  the result separately.

### Job Create Response

```json
{
  "jobId": "20260512_120000_story_friendship",
  "type": "story",
  "status": "queued",
  "statusUrl": "/internal/ai/jobs/20260512_120000_story_friendship",
  "resultUrl": "/internal/ai/story/jobs/20260512_120000_story_friendship/result",
  "callbackUrl": "https://backend.example.com/internal/ai/callback"
}
```

### Completion Webhook

```json
{
  "jobId": "20260512_120000_story_friendship",
  "type": "story",
  "status": "completed",
  "resultUrl": "/internal/ai/story/jobs/20260512_120000_story_friendship/result",
  "error": null,
  "requestId": "optional-request-id"
}
```

## Endpoints

### Story

`POST /internal/ai/story/jobs`

Request is the backend `StoryGenerateRequest` payload plus:

```json
{
  "callbackUrl": "https://backend.example.com/internal/ai/callback",
  "requestId": "optional-request-id"
}
```

Result `data` matches backend `StoryGenerateResponse`:

```json
{
  "title": "Mina's Adventure",
  "childName": "Mina",
  "primaryLanguage": "ko",
  "secondaryLanguage": "en",
  "slides": [
    {
      "order": 1,
      "imageUrl": null,
      "textKr": "...",
      "textNative": "...",
      "audioUrlKr": null,
      "audioUrlNative": null
    }
  ]
}
```

### TTS

`POST /internal/ai/tts/jobs`

Single text:

```json
{
  "callbackUrl": "https://backend.example.com/internal/ai/callback",
  "text": "Hello",
  "language": "en-US"
}
```

Batch:

```json
{
  "callbackUrl": "https://backend.example.com/internal/ai/callback",
  "inputs": [
    { "id": "slide-1-kr", "text": "안녕", "language": "ko-KR" }
  ]
}
```

Result `data` includes `items`; single-text jobs also mirror the first item as
`audioUrl`, `language`, `duration`, and `message`.

### Quiz

`POST /internal/ai/quiz/jobs`

Provide either `story` or `storyJsonUrl`:

```json
{
  "callbackUrl": "https://backend.example.com/internal/ai/callback",
  "storyId": "story-1",
  "storyJsonUrl": "/static/outputs/story-1/story_gemini-2.5-flash.json",
  "questionCount": 5
}
```

Result `data` is camelCase and includes `questions`, `choices`, `answer`, source
page numbers, and `quizJsonUrl`.

### Vocabulary

`POST /internal/ai/vocab/jobs`

```json
{
  "callbackUrl": "https://backend.example.com/internal/ai/callback",
  "storyId": "story-1",
  "primaryLanguage": "ko",
  "secondaryLanguage": "en",
  "slides": [
    {
      "order": 1,
      "textKr": "안녕 친구",
      "textNative": "hello friend",
      "vocabulary": []
    }
  ]
}
```

Result `data.entries[]` uses `slideOrder`, `entryId`, `primaryWord`,
`secondaryWord`, `primaryDefinition`, and `secondaryDefinition`.
