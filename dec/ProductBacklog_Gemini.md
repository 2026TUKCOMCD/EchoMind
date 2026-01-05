# 📘 Product Backlog – EchoMind

**Project:** AI 기반 성격 분석 및 소셜 매칭 시스템  
**Project Vision:** 실제 대화 로그 분석을 통한 Big Five 성격 추정 및 과학적 근거 기반의 소셜 매칭 플랫폼 제공  
**Total Estimated Time:** 1,020 Hours (Range: 800–1,200h)

---

## 📌 Estimation Rules
* **Story Point (SP) Scale:** Fibonacci (1, 2, 3, 5, 8, 13)
* **1 SP ≈ 7 Hours** (순수 개발 시간 기준)
* **Time Range:** 기술적 리스크 및 시스템 통합 난이도 반영

---

## 🟦 EPIC 1 — 대화 데이터 전처리 파이프라인 (155h)
**Purpose:** 비정형 대화 데이터를 분석 가능한 정형 데이터로 변환 및 정제

### 📝 User Stories

* **D1-1: 대용량 로그 파일 업로드 및 서버 저장** - **As a user**, I want to upload my KakaoTalk chat log file, **so that** the system can analyze my real communication behavior.

* **D1-2: 카카오톡 대화 포맷 파싱 및 문장 구조화** - **As a system**, I want to parse raw chat logs into sentence-level structured messages, **so that** NLP models can process each utterance accurately.

* **D1-3: 화자 자동 식별 및 분석 대상 선택** - **As a user**, I want the system to automatically identify and separate speakers, **so that** I can select which person's personality to analyze.

* **D1-4: 텍스트 클리닝 및 정규화** - **As a system**, I want to clean noise (emojis, system messages) and normalize text, **so that** the statistical results remain unbiased.

### 📊 Epic 1 Backlog Table
| ID | User Story | Story Points | 예상 개발 시간 |
|---|---|---|---|
| D1-1 | 대용량 로그 파일 업로드 및 서버 저장 로직 구현 | 5 | 35h |
| D1-2 | 카카오톡 특화 대화 포맷 파싱 및 정제 엔진 개발 | 8 | 55h |
| D1-3 | 화자 분리 알고리즘 및 화자 선택 UI 구현 | 5 | 35h |
| D1-4 | 데이터 정규화 및 클리닝 파이프라인 구축 | 4 | 30h |
| **소계** | | **22 SP** | **155h** |

---

## 🟦 EPIC 2 — AI 기반 성격 지표 분석 엔진 (360h)
**Purpose:** 텍스트 지표와 감정 패턴을 추출하여 Big Five 성격 요인을 추정

### 📝 User Stories

* **A2-1: 자기지시어(Self-reference) 비율 분석** - **As a system**, I want to calculate the ratio of self-references (I, me, my), **so that** I can measure the speaker's self-focus level.

* **A2-2: 확실성 및 불확실성 표현 분석** - **As a system**, I want to analyze certainty and uncertainty expressions, **so that** I can assess the speaker's confidence.

* **A2-3: 어휘 다양도(TTR) 및 문장 스타일 측정** - **As a system**, I want to measure vocabulary diversity (TTR) and sentence length, **so that** I can identify stylistic traits.

* **A2-4: 외부 API 연동 감정 및 독성 점수 산출** - **As a system**, I want to analyze sentiment and toxicity using external APIs, **so that** I can quantify emotional stability.

* **A2-5: 분석 지표 기반 Big Five 성격 매핑** - **As a system**, I want to map all linguistic features to Big Five scores, **so that** I can provide an exploratory personality profile.

### 📊 Epic 2 Backlog Table
| ID | User Story | Story Points | 예상 개발 시간 |
|---|---|---|---|
| A2-1 | 자기지시 및 불확실성 지표 추출 로직 구현 | 13 | 90h |
| A2-2 | 어휘 다양도(TTR) 및 통계 지표 산출 모듈 개발 | 8 | 55h |
| A2-3 | Google Perspective & HuggingFace API 연동 | 13 | 90h |
| A2-4 | 지표 통합 기반 Big Five 추정 알고리즘 고도화 | 15 | 110h |
| A2-5 | 분석 결과 데이터 모델링 및 JSON API 규격화 | 2 | 15h |
| **소계** | | **51 SP** | **360h** |

---

## 🟦 EPIC 3 — 5대 규칙 기반 소셜 매칭 엔진 (250h)
**Purpose:** 정의된 알고리즘 규칙을 적용한 사용자 간 최적 적합도 산출

### 📝 User Stories

* **M3-1: 독성 사용자 필터링 및 환경 안전성 확보** - **As a manager**, I want to block users with high toxicity scores, **so that** the community remains safe.

* **M3-2: Big Five 성격 보완성 기반 궁합 계산** - **As a user**, I want to be matched with partners whose Big Five traits complement mine, **so that** relationship satisfaction is maximized.

* **M3-3: 감정 유사도 가중치 기반 매칭 점수 산출** - **As a system**, I want to award higher scores for emotional similarity, **so that** I can connect people with compatible vibes.

* **M3-4: 언어 스타일 최적 편차(Middle Ground) 식별** - **As a system**, I want to identify the "optimal middle ground" in language style, **so that** communication feels natural.

* **M3-5: 주제 다양성 차이 기반 매칭 최적화** - **As a system**, I want to optimize matching based on topic diversity gaps, **so that** matches remain engaging.

### 📊 Epic 3 Backlog Table
| ID | User Story | Story Points | 예상 개발 시간 |
|---|---|---|---|
| M3-1 | 독성 필터링 및 감정 유사도 가중치 산출 | 8 | 55h |
| M3-2 | Big Five 보완성 기반 궁합 알고리즘 구현 | 13 | 90h |
| M3-3 | 언어 스타일/주제 다양성 최적 편차 계산 | 11 | 75h |
| M3-4 | 사용자-소셜 그룹 간 최종 매칭 점수 산출 엔진 구축 | 4 | 30h |
| **소계** | | **36 SP** | **250h** |

---

## 🟦 EPIC 4 — 시각화 리포트 및 반응형 UI (150h)
**Purpose:** 분석 및 매칭 결과를 사용자에게 직관적으로 전달

### 📝 User Stories

* **V4-1: Big Five 성격 시각화 레이더 차트** - **As a user**, I want to see my Big Five traits on a radar chart, **so that** I can understand my traits at a glance.

* **V4-2: 상세 성격 및 커뮤니케이션 인사이트 제공** - **As a user**, I want to view detailed sentiment and toxicity insights, **so that** I can reflect on my communication patterns.

* **V4-3: 맞춤형 소셜 그룹 추천 리스트** - **As a user**, I want a ranked list of recommended social groups, **so that** I can find communities that fit me.

* **V4-4: 멀티 디바이스 대응 반응형 웹 구현** - **As a mobile user**, I want a responsive web interface, **so that** I can check my reports on my smartphone.

### 📊 Epic 4 Backlog Table
| ID | User Story | Story Points | 예상 개발 시간 |
|---|---|---|---|
| V4-1 | Big Five 레이더 차트 및 감정 분석 대시보드 구현 | 8 | 55h |
| V4-2 | 맞춤형 성격 리포트 및 매칭 결과 리스트 페이지 개발 | 8 | 55h |
| V4-3 | PC/Mobile 대응 반응형 웹 프론트엔드 최적화 | 6 | 40h |
| **소계** | | **22 SP** | **150h** |

---

## 🟦 EPIC 5 — 시스템 인프라 및 백엔드 안정화 (105h)
**Purpose:** 안정적이고 빠른 분석 환경 구축 및 동시 접속 처리

### 📝 User Stories

* **B5-1: 비동기 처리 큐(Asynchronous Queue) 구축** - **As a developer**, I want to use an asynchronous processing pipeline, **so that** heavy AI tasks do not block the web server.

* **B5-2: 영속적 데이터 저장 및 이력 관리** - **As a developer**, I want to store all analysis data in MySQL, **so that** user history is preserved for future matching.

* **B5-3: 고가용성 클라우드 인프라 배포** - **As a system**, I want to handle 100 concurrent users on AWS, **so that** target loading speed은 유지된다.

### 📊 Epic 5 Backlog Table
| ID | User Story | Story Points | 예상 개발 시간 |
|---|---|---|---|
| B5-1 | Flask/FastAPI 및 Celery 기반 비동기 파이프라인 구축 | 8 | 55h |
| B5-2 | 데이터베이스 스키마 설계 및 RDS(MySQL) 연동 | 4 | 30h |
| B5-3 | AWS EC2 서버 환경 구성 및 성능 튜닝 | 3 | 20h |
| **소계** | | **15 SP** | **105h** |

---

## 🔢 Overall Development Summary

| 영역 (Epics) | 총 Story Points | 총 예상 개발 시간 | 비중 |
|---|---|---|---|
| **Data Processing (Epic 1)** | 22 | 155h | 15.2% |
| **AI Analysis Engine (Epic 2)** | 51 | 360h | 35.3% |
| **Matching Engine (Epic 3)** | 36 | 250h | 24.5% |
| **UI & Reporting (Epic 4)** | 22 | 150h | 14.7% |
| **Infra & Backend (Epic 5)** | 15 | 105h | 10.3% |
| **합계 (TOTAL)** | **146 SP** | **1,020h** | **100.0%** |