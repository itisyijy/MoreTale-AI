# MoreTale GCP 데모 배포 제안서

## 1. 목적

MoreTale 프로젝트의 2개월 데모 운영을 위해 비용, 구현 난이도, 안정성, 이후 확장 가능성을 함께 고려한 GCP 배포 구성을 제안한다.

이번 데모의 우선순위는 다음과 같다.

1. 제한된 기간 동안 안정적으로 데모가 동작할 것
2. Spring Boot backend와 FastAPI AI 서버를 억지로 통합하지 않을 것
3. 동화 이미지, TTS, 결과 JSON 파일은 VM에 종속시키지 않을 것
4. 추후 Cloud Run 기반 구조로 이전 가능하도록 설계할 것

---

## 2. 채택안 요약

이번 데모 배포는 **Compute Engine 인스턴스 1대 + Docker Compose + Cloud Storage** 구성을 채택한다.

```text
Vercel Frontend
  |
  | HTTPS
  v
Compute Engine VM
  |
  +-- nginx 컨테이너
  |     - 80/443 외부 공개
  |     - HTTPS 처리
  |     - Spring Boot backend로 reverse proxy
  |
  +-- Spring Boot backend 컨테이너
  |     - 내부 포트 8080
  |     - 프론트엔드 API 요청 처리
  |     - FastAPI AI 서버 호출
  |     - PostgreSQL 접근
  |     - Cloud Storage 파일 URL 저장/반환
  |
  +-- FastAPI AI 컨테이너
  |     - 내부 포트 8000
  |     - 외부 공개하지 않음
  |     - 동화/퀴즈/TTS/일러스트 생성
  |     - 생성 산출물을 Cloud Storage에 업로드
  |
  +-- PostgreSQL 컨테이너
        - 내부 포트 5432
        - VM persistent disk volume 사용

Cloud Storage
  - 동화 이미지
  - TTS 오디오
  - 결과 JSON
  - manifest 파일
```

핵심 결정은 다음과 같다.

| 항목 | 결정 |
|------|------|
| 서버 인프라 | Compute Engine 1대 |
| 프로세스 관리 | Docker Compose |
| 외부 진입점 | nginx |
| 프론트엔드 | Vercel |
| backend | Spring Boot 컨테이너 |
| AI 서버 | FastAPI 컨테이너, 내부 전용 |
| DB | VM 내부 PostgreSQL 컨테이너 |
| 파일 저장 | Cloud Storage |
| 장기 목표 | Cloud Run + Cloud SQL + Cloud Storage |

---

## 3. 이 구성을 선택하는 이유

### 3.1 비용 예측이 쉽다

Compute Engine 1대는 VM이 켜져 있는 시간만큼 고정 비용이 발생한다. 2개월 데모처럼 기간이 명확한 경우 비용을 예측하기 쉽다.

Cloud Run + Cloud SQL 구성도 운영 관점에서는 좋지만, 지금 단계에서는 Cloud SQL 고정비와 초기 연동 작업이 추가된다. 반면 VM 1대 구성은 현재 Spring Boot backend와 FastAPI AI 서버 구조를 크게 바꾸지 않고 배포할 수 있다.

### 3.2 현재 코드 구조와 잘 맞는다

현재 MoreTale 서버는 이미 두 파트로 나뉘어 있다.

```text
MoreTale-backend: Spring Boot
MoreTale-AI: FastAPI
```

두 서비스를 하나의 코드베이스나 하나의 런타임으로 합치는 것은 추천하지 않는다. Java와 Python 런타임을 함수 레벨로 통합하려면 재작성 또는 복잡한 프로세스 연동이 필요하다.

대신 같은 VM 내부 Docker network에서 API로 통신하면 다음 장점이 있다.

- 배포는 단순하게 유지
- 서비스 경계는 유지
- FastAPI는 외부에 노출하지 않음
- 나중에 Cloud Run으로 분리 이전 가능

### 3.3 Cloud Storage를 사용해 파일 종속성을 줄인다

이미지, 오디오, 결과 JSON을 VM 디스크에 저장하면 나중에 서버 이전이나 스케일아웃이 어려워진다.

따라서 이번 데모부터 파일은 Cloud Storage에 저장한다.

```text
stories/{story_id}/cover.png
stories/{story_id}/pages/page_001.png
stories/{story_id}/audio/page_001_primary.wav
stories/{story_id}/audio/page_001_secondary.wav
stories/{story_id}/story.json
stories/{story_id}/quiz.json
stories/{story_id}/manifest.json
```

DB에는 파일 자체가 아니라 object key 또는 URL만 저장한다.

```text
story_id
title
status
cover_image_key
story_json_key
quiz_json_key
created_at
```

이렇게 하면 VM이 교체되어도 생성된 동화 파일은 유지된다.

---

## 4. 네트워크 구조

외부에 공개하는 포트는 nginx의 `80`, `443`만 허용한다.

```text
외부 공개:
  80  HTTP, HTTPS redirect
  443 HTTPS

외부 비공개:
  8080 Spring Boot
  8000 FastAPI
  5432 PostgreSQL
```

권장 요청 흐름은 다음과 같다.

```text
Vercel
  -> https://api.moretale.site
  -> nginx
  -> Spring Boot backend
  -> FastAPI AI
  -> Cloud Storage
```

프론트엔드는 FastAPI를 직접 호출하지 않는다.

```text
좋은 구조:
  Vercel -> Spring Boot -> FastAPI

피해야 할 구조:
  Vercel -> FastAPI 직접 호출
```

---

## 5. 컨테이너 구성

권장 Docker Compose 서비스는 다음과 같다.

```yaml
services:
  nginx:
    image: nginx
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - backend

  backend:
    image: moretale-backend
    environment:
      DB_HOST: postgres
      DB_PORT: 5432
      AI_BASE_URL: http://ai:8000
      FILE_STORAGE_BACKEND: gcs
    depends_on:
      - postgres
      - ai

  ai:
    image: moretale-ai
    environment:
      MORETALE_STORAGE_BACKEND: gcs
      MORETALE_GCS_BUCKET: moretale-demo-assets
      MORETALE_GCS_KEY_PREFIX: demo

  postgres:
    image: postgres
    volumes:
      - /opt/moretale/data/postgres:/var/lib/postgresql/data
```

실제 파일은 각 repo의 Dockerfile, 환경변수 이름, Spring 설정 키에 맞춰 조정한다.

---

## 6. 권장 GCP 리소스

### 6.1 Compute Engine

권장 시작 사양:

```text
Machine type: e2-medium
vCPU: 2
Memory: 4GB
Disk: 50GB balanced persistent disk
OS: Debian 또는 Ubuntu
```

여유를 더 두고 싶다면:

```text
Machine type: e2-standard-2
vCPU: 2
Memory: 8GB
Disk: 50GB~100GB
```

`e2-micro`는 무료 tier 대상일 수 있지만, Spring Boot + FastAPI + PostgreSQL + AI 생성 작업을 함께 돌리기에는 메모리가 부족하다.

### 6.2 Cloud Storage

권장 설정:

```text
Bucket name: moretale-demo-assets
Region: VM과 같은 region
Storage class: Standard
Public access: private 권장
Object versioning: off
Lifecycle rule: 90일 후 삭제
```

데모 편의상 public object를 사용할 수도 있지만, 아동 개인화 콘텐츠를 다루는 서비스 특성상 private bucket + signed URL 방식을 우선 검토한다.

### 6.3 IAM

VM service account에 필요한 최소 권한만 부여한다.

```text
Cloud Storage object read/write
Secret Manager secret accessor, 선택
Logging writer
Monitoring metric writer
```

서비스 계정 키 JSON 파일을 VM에 직접 올리는 방식은 가능하면 피하고, Compute Engine service account 기반 인증을 사용한다.

### 6.4 DB 관리 정책

이번 데모에서는 **Cloud SQL을 사용하지 않고, Compute Engine VM 내부 PostgreSQL 컨테이너**를 운영 DB로 사용한다.

```text
운영 DB:
  VM 내부 PostgreSQL 컨테이너

DB 데이터 위치:
  /opt/moretale/data/postgres
  - VM persistent disk에 mount

DB 백업 위치:
  Cloud Storage
  - gs://moretale-demo-assets/backups/postgres/...

장기 목표:
  Cloud SQL PostgreSQL로 이전
```

Cloud Storage는 파일 저장소이며 DB를 대체하지 않는다.

```text
PostgreSQL:
  - 사용자
  - OAuth 사용자 정보
  - 프로필
  - 스토리 메타데이터
  - 슬라이드 목록
  - 퀴즈 결과
  - 생성 job 상태

Cloud Storage:
  - 동화 이미지
  - TTS 오디오
  - story.json
  - quiz.json
  - manifest.json
```

DB에는 가능하면 Cloud Storage의 공개 URL 전체가 아니라 object key를 저장한다.

```text
권장:
  stories/{story_id}/pages/page_001.png

비권장:
  https://storage.googleapis.com/moretale-demo-assets/demo/stories/{story_id}/pages/page_001.png
```

object key를 저장하면 bucket 공개 정책, signed URL, CDN, 도메인 변경에 더 유연하게 대응할 수 있다.

### 6.5 Firebase/Firestore 판단

이번 데모에서는 Firebase 또는 Firestore를 메인 DB로 채택하지 않는다.

이유는 다음과 같다.

- 현재 Spring Boot backend는 JPA/PostgreSQL 기반이다.
- 사용자, 프로필, 스토리, 슬라이드, 퀴즈, 단어장처럼 관계형 데이터가 많다.
- Firestore로 전환하려면 entity/repository/query/transaction 설계를 크게 바꿔야 한다.
- 2개월 데모 목표에 비해 전환 비용이 크다.

따라서 이번 데모의 저장소 역할은 다음처럼 나눈다.

```text
PostgreSQL:
  서비스의 기준 데이터 저장

Cloud Storage:
  이미지, 오디오, JSON 파일 저장

Firebase/Firestore:
  이번 데모에서는 사용하지 않음
```

예외적으로, 추후 프론트에서 AI 생성 상태를 realtime으로 구독해야 하는 요구가 강해지면 Firestore를 보조 저장소로 검토할 수 있다. 단, 이 경우에도 메인 DB는 PostgreSQL을 유지한다.

---

## 7. 환경변수 계획

### 7.1 Spring Boot backend

```env
SPRING_PROFILES_ACTIVE=prod
DB_HOST=postgres
DB_PORT=5432
DB_NAME=moretale
DB_USER=moretale
DB_PASSWORD=...
JWT_SECRET=...
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
AI_BASE_URL=http://ai:8000
GCS_BUCKET=moretale-demo-assets
GCS_KEY_PREFIX=demo
```

현재 backend 설정이 기능별 URL을 나눠 쓰는 경우 다음 값은 모두 FastAPI 컨테이너를 바라보게 둘 수 있다.

```env
STORY_GENERATION_URL=http://ai:8000
IMAGE_GENERATION_URL=http://ai:8000
TTS_URL=http://ai:8000
QUIZ_GENERATION_URL=http://ai:8000
```

### 7.2 FastAPI AI

```env
MORETALE_API_KEY=...
MORETALE_STORAGE_BACKEND=gcs
MORETALE_GCS_BUCKET=moretale-demo-assets
MORETALE_GCS_KEY_PREFIX=demo
GEMINI_STORY_API_KEY=...
GEMINI_TTS_API_KEY=...
NANO_BANANA_KEY=...
MORETALE_RATE_LIMIT_POST_STORIES_PER_MIN=5
```

---

## 8. 운영 정책

### 8.1 생성 제한

AI 생성 비용과 API quota 보호를 위해 제한을 둔다.

```text
사용자당 하루 생성 권수 제한
전체 하루 생성 권수 제한
동시 생성 작업 수 제한
실패 재시도 횟수 제한
```

데모 초기 권장값:

```text
전체 동시 생성: 1~2개
사용자당 하루 생성: 1~3권
전체 하루 생성: 10권 이하
```

### 8.2 백업

Cloud Storage를 사용하므로 파일 백업 부담은 줄어든다. 대신 PostgreSQL 백업은 필수다.

권장 백업:

```text
매일 1회 pg_dump
백업 파일을 Cloud Storage backup prefix에 업로드
최근 7~14일치 보관
```

예시 경로:

```text
gs://moretale-demo-assets/backups/postgres/2026-05-05.sql.gz
```

### 8.3 모니터링

최소한 다음 항목은 확인한다.

```text
VM CPU/RAM/Disk 사용량
Docker container restart count
Spring Boot error log
FastAPI error log
PostgreSQL disk usage
Cloud Storage object count/size
AI API 실패율
```

### 8.4 비용 알림

Billing budget alert를 설정한다.

권장 알림 구간:

```text
50%
75%
90%
100%
```

---

## 9. 구현 체크리스트

### 인프라

- [ ] GCP 프로젝트 생성
- [ ] Billing budget alert 설정
- [ ] Compute Engine VM 생성
- [ ] VM firewall에서 80/443만 공개
- [ ] Docker, Docker Compose 설치
- [ ] Cloud Storage bucket 생성
- [ ] VM service account에 Cloud Storage 권한 부여
- [ ] 도메인 DNS를 VM external IP로 연결
- [ ] nginx HTTPS 설정

### backend

- [ ] Dockerfile 작성
- [ ] prod profile 분리
- [ ] DB 연결을 env 기반으로 변경
- [ ] FastAPI base URL을 env 기반으로 변경
- [ ] Cloud Storage 파일 업로드 구현 또는 설정
- [ ] CORS에 Vercel 도메인 허용
- [ ] `/health` 또는 actuator health endpoint 준비

### AI

- [x] Dockerfile 작성
- [x] GCS storage backend 구현 완료
- [x] `google-cloud-storage` 의존성 추가
- [ ] local `/static/outputs` 의존 제거 또는 fallback으로만 유지
- [ ] job 상태 저장 정책 확정
- [ ] `/health` endpoint 확인

### 운영

- [ ] PostgreSQL volume persistent disk 경로 사용
- [ ] 매일 pg_dump 백업 스크립트
- [ ] Cloud Storage lifecycle rule 설정
- [ ] AI 생성 횟수 제한
- [ ] 재시작 정책 설정
- [ ] 배포/롤백 절차 문서화

---

## 10. Cloud Run 전환 로드맵

이번 데모는 Compute Engine으로 시작하지만, 장기적으로는 Cloud Run 기반 구조가 더 적합하다.

최종 목표 구조:

```text
Vercel Frontend
  -> Cloud Run: moretale-backend
      -> Cloud Run: moretale-ai
      -> Cloud SQL PostgreSQL
      -> Cloud Storage
      -> Secret Manager
```

전환 순서:

1. **파일 저장 외부화**
   - 이번 데모에서 이미 Cloud Storage를 사용하므로 완료 목표

2. **DB 외부화**
   - VM 내부 PostgreSQL을 Cloud SQL PostgreSQL로 이전

3. **AI job 상태 외부화**
   - 인메모리 job store를 PostgreSQL 또는 Firestore로 이전

4. **서비스 분리 배포**
   - Spring Boot와 FastAPI를 각각 Cloud Run service로 배포

5. **내부 인증**
   - backend service account에만 AI Cloud Run Invoker 권한 부여

6. **비동기 작업 큐 도입**
   - 생성 시간이 길거나 동시 요청이 늘면 Cloud Tasks 또는 Pub/Sub 도입

---

## 11. 리스크와 대응

| 리스크 | 영향 | 대응 |
|------|------|------|
| VM 장애 | 전체 서비스 중단 | PostgreSQL 백업, 빠른 재생성 절차 준비 |
| PostgreSQL 데이터 손실 | 사용자/스토리 메타데이터 손실 | 매일 pg_dump 후 Cloud Storage 업로드 |
| AI 생성 비용 증가 | 크레딧 소진 | 생성 횟수 제한, quota 확인 |
| VM 메모리 부족 | 컨테이너 재시작 또는 느려짐 | e2-medium 이상 사용, JVM heap 제한 |
| Cloud Storage 권한 오류 | 파일 업로드 실패 | VM service account IAM 사전 검증 |
| FastAPI 외부 노출 | 보안 위험 | nginx만 public, Docker network 내부 통신 |

---

## 12. 결론

MoreTale의 2개월 데모 배포에는 다음 구성을 채택한다.

```text
Compute Engine 1대
+ Docker Compose
+ nginx
+ Spring Boot backend
+ FastAPI AI
+ PostgreSQL
+ Cloud Storage
+ Vercel frontend
```

이 구성은 현재 코드 구조를 크게 바꾸지 않으면서도, 파일 저장을 Cloud Storage로 외부화해 이후 Cloud Run 전환 가능성을 확보한다.

즉, 이번 데모에서는 **Compute Engine으로 빠르고 안정적으로 운영**하고, 장기적으로는 **Cloud Run + Cloud SQL + Cloud Storage** 구조로 이전한다.

---

## 참고 문서

- Google Cloud Free Program: https://cloud.google.com/free/docs/free-cloud-features
- Compute Engine machine types: https://cloud.google.com/compute/docs/general-purpose-machines
- Cloud Storage signed URLs: https://cloud.google.com/storage/docs/access-control/signed-urls
- Cloud Run service-to-service authentication: https://cloud.google.com/run/docs/authenticating/service-to-service
- Cloud SQL PostgreSQL from Cloud Run: https://cloud.google.com/sql/docs/postgres/connect-run
