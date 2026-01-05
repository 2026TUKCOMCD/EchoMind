# 📘 Product Backlog – EchoMind

**Project:** AI 기반 성격 분석 및 소셜 매칭 시스템  
**Project Vision:** 실제 대화 로그(카카오톡 채팅)를 분석하여 Big Five 성격 요인을 추정하고, 이를 기반으로 사용자 간 궁합 매칭 및 소셜 그룹 추천을 제공하는 플랫폼. 설문 기반 테스트의 한계를 극복하여 자연스러운 언어 패턴(자기지시어, 불확실성 표현, 어휘 다양도, 감정 분석 등)을 활용한 과학적 접근.  
**Last Updated:** January 05, 2026  
**Total Estimated Time:** 820–1,180 Hours (Gemini/GPT 버전 통합, 리스크·통합 난이도·추가 테스트 시간 반영)

---

## 📌 Estimation Rules
* **Story Point (SP) Scale:** Fibonacci (1, 2, 3, 5, 8, 13)
* **1 SP ≈ 5.5–7.5 Hours** (순수 개발 시간 기준, QA/디자인/문서화 제외)

---

## 🟦 EPIC 1 — 대화 데이터 전처리 파이프라인
**Purpose:** 비정형 대화 로그를 분석 가능한 정형 데이터로 변환. 카카오톡 특화 파싱, 화자 분리, 텍스트 정제 지원. 지원 파일 포맷: .txt, .csv, .pdf (목표 3종 이상).

### 📝 User Stories

* **D1-1: 다중 포맷 채팅 로그 업로드**  
  **As a user**,
  I want to upload KakaoTalk chat log files (.txt, .csv, .pdf),
  **so that** the system can analyze my real communication behavior instead of surveys.

* **D1-2: 카카오톡 로그 문장 단위 파싱**  
  **As a system**,
  I want to parse raw chat logs into sentence-level structured messages,
  **so that** NLP models can process utterances accurately.

* **D1-3: 화자 자동 분리 및 선택 UI**  
  **As a user**,
  I want the system to automatically identify and separate speakers,
  **so that** I can select the personality to analyze.

* **D1-4: 텍스트 노이즈 제거 및 정규화**  
  **As a system**,
  I want to clean noise (emojis, system messages, special characters) and normalize text,
  **so that** analysis remains unbiased.

* **D1-5: 분석 대상 화자 필터링**  
  **As a user**,
  I want to filter conversations by selected speakers,
  **so that** analysis reflects relevant behavior.

### 📊 Epic 1 Backlog Table
| ID   | User Story                                      | Story Points | 예상 개발 시간 |
|------|-------------------------------------------------|--------------|----------------|
| D1-1 | 대용량 로그 파일 업로드 및 서버 저장 로직 구현 (다중 포맷 지원) | 5            | 30–40h        |
| D1-2 | 카카오톡 특화 대화 포맷 파싱 및 문장 단위 정제 엔진 개발       | 8            | 45–65h        |
| D1-3 | 화자 자동 분리 알고리즘 및 선택 UI 구현                     | 5            | 30–40h        |
| D1-4 | 텍스트 정규화 및 클리닝 파이프라인 구축 (이모지/특수문자 제거)   | 3            | 15–25h        |
| D1-5 | 분석 대상 화자 필터링 로직 구현                            | 5            | 30–40h        |
| **소계** |                                             | **26 SP**    | **150–210h**  |

---

## 🟦 EPIC 2 — AI 기반 성격 분석 엔진
**Purpose:** 텍스트 지표와 감정 패턴을 추출하여 Big Five 성격 요인 추정. Google Perspective API와 Hugging Face API 연동, 정확도 튜닝 포함.

### 📝 User Stories

* **A2-1: 자기지시어(self-reference) 분석**  
  **As a system**,
  I want to calculate self-references (e.g., "나", "I", "me"),
  **so that** I can measure self-focus levels.

* **A2-2: 확실성/불확실성 표현 분석**  
  **As a system**,
  I want to analyze certainty/uncertainty expressions,
  **so that** I can assess confidence.

* **A2-3: 어휘 다양도(TTR) 및 문장 길이 분석**  
  **As a system**,
  I want to measure vocabulary diversity (TTR) and sentence length,
  **so that** I can identify stylistic traits.

* **A2-4: 감정 극성 및 독성 분석 (API 연동)**  
  **As a system**,
  I want to analyze sentiment polarity and toxicity using external APIs,
  **so that** I can quantify emotional stability.

* **A2-5: Big Five 성격 요인 매핑 및 추정**  
  **As a system**,
  I want to map linguistic features to Big Five scores,
  **so that** I can provide an exploratory personality profile.

* **A2-6: 분석 결과 JSON 저장**  
  **As a system**,
  I want to store analysis results as JSON,
  **so that** they can be used for matching and reporting.

### 📊 Epic 2 Backlog Table
| ID   | User Story                                      | Story Points | 예상 개발 시간 |
|------|-------------------------------------------------|--------------|----------------|
| A2-1 | 자기지시어 및 불확실성/확실성 지표 추출 로직 구현              | 8            | 45–65h        |
| A2-2 | 어휘 다양도(TTR) 및 문장 구조 통계 산출 모듈 개발              | 5            | 30–40h        |
| A2-3 | Google Perspective & Hugging Face API 연동 (감정/독성 분석)   | 13           | 70–100h       |
| A2-4 | 지표 통합 기반 Big Five 추정 알고리즘 고도화 및 정확도 튜닝      | 13           | 70–100h       |
| A2-5 | 분석 결과 데이터 모델링 및 JSON 저장 규격화                   | 3            | 15–25h        |
| A2-6 | 주제 다양도 및 추가 패턴 분석 통합                          | 5            | 30–40h        |
| **소계** |                                             | **47 SP**    | **260–370h**  |

---

## 🟦 EPIC 3 — 소셜 매칭 엔진
**Purpose:** Big Five 기반 5대 규칙 적용한 사용자-소셜 그룹 매칭. 가상 소셜 그룹 데이터 20개 이상 구축 및 튜닝.

### 📝 User Stories

* **M3-1: 고독성 사용자 차단**  
  **As a manager**,
  I want to block users with high toxicity scores,
  **so that** the community remains safe.

* **M3-2: Big Five 보완성 기반 매칭**  
  **As a user**,
  I want to be matched with partners/groups whose Big Five traits complement mine,
  **so that** relationship satisfaction is maximized.

* **M3-3: 감정 유사도 가중치 적용**  
  **As a system**,
  I want to award higher scores for emotional similarity,
  **so that** I can connect people with compatible vibes.

* **M3-4: 언어 스타일 최적 중간 지점 계산**  
  **As a system**,
  I want to identify optimal middle ground in language style,
  **so that** communication feels natural.

* **M3-5: 주제 다양도 갭 최적화 매칭**  
  **As a system**,
  I want to optimize matching based on topic diversity gaps,
  **so that** matches remain engaging.

* **M3-6: 소셜 그룹 데이터 관리 및 튜닝**  
  **As a manager**,
  I want to manage social group data (DB),
  **so that** matching can be tuned.

### 📊 Epic 3 Backlog Table
| ID   | User Story                                      | Story Points | 예상 개발 시간 |
|------|-------------------------------------------------|--------------|----------------|
| M3-1 | 독성 필터링 및 감정 유사도 가중치 산출                       | 5            | 30–40h        |
| M3-2 | Big Five 보완성 기반 궁합 알고리즘 구현                      | 8            | 45–65h        |
| M3-3 | 언어 스타일/주제 다양성 최적 편차 계산                       | 8            | 45–65h        |
| M3-4 | 사용자-소셜 그룹 간 최종 매칭 점수 엔진 구축                  | 5            | 30–40h        |
| M3-5 | 가상 소셜 그룹 데이터 20개 이상 구축 및 DB 연동               | 3            | 15–25h        |
| M3-6 | 매칭 알고리즘 가중치 설정 UI/튜닝                           | 3            | 15–25h        |
| **소계** |                                             | **32 SP**    | **180–260h**  |

---

## 🟦 EPIC 4 — 시각화 리포트 및 반응형 UI
**Purpose:** 분석 및 매칭 결과를 직관적으로 전달. Big Five 레이더 차트, 감정 분포, 매칭 리스트, PDF 리포트 지원. PC/Mobile 반응형.

### 📝 User Stories

* **V4-1: Big Five 레이더 차트 시각화**  
  **As a user**,
  I want to see Big Five traits on a radar chart,
  **so that** I can understand my traits at a glance.

* **V4-2: 감정 및 독성 인사이트 상세 보기**  
  **As a user**,
  I want to view detailed sentiment and toxicity insights,
  **so that** I can reflect on communication patterns.

* **V4-3: 추천 소셜 그룹 랭킹 리스트**  
  **As a user**,
  I want a ranked list of recommended social groups,
  **so that** I can find fitting communities.

* **V4-4: 반응형 웹 인터페이스**  
  **As a mobile user**,
  I want a responsive web interface,
  **so that** I can access reports on any device.

* **V4-5: PDF 리포트 생성 및 다운로드**  
  **As a user**,
  I want to generate PDF reports,
  **so that** I can share or save results.

### 📊 Epic 4 Backlog Table
| ID   | User Story                                      | Story Points | 예상 개발 시간 |
|------|-------------------------------------------------|--------------|----------------|
| V4-1 | Big Five 레이더 차트 및 감정 분석 대시보드 구현               | 5            | 30–40h        |
| V4-2 | 맞춤형 성격 리포트 및 매칭 결과 리스트 페이지 개발             | 8            | 45–65h        |
| V4-3 | PC/Mobile 반응형 웹 프론트엔드 최적화                       | 5            | 30–40h        |
| V4-4 | PDF 리포트 생성 기능 구현                                | 3            | 15–25h        |
| V4-5 | UI Flow: 업로드 → 분석 대기 → 결과 확인                     | 5            | 30–40h        |
| **소계** |                                             | **26 SP**    | **150–210h**  |

---

## 🟦 EPIC 5 — 시스템 인프라 및 백엔드 안정화
**Purpose:** 안정적 처리 환경 구축. 비동기 큐, DB 저장, AWS 배포, 동시 접속 100명 지원.

### 📝 User Stories

* **B5-1: 비동기 처리 큐 구현**  
  **As a developer**,
  I want an asynchronous processing queue,
  **so that** heavy AI tasks don't block the server.

* **B5-2: MySQL 데이터베이스 연동**  
  **As a developer**,
  I want to store data in MySQL,
  **so that** user history is preserved.

* **B5-3: AWS 고동시 접속 지원 및 성능 튜닝**  
  **As a system**,
  I want to handle 100 concurrent users on AWS,
  **so that** loading speed is maintained.

* **B5-4: 모듈화된 AI 모델 교체 구조**  
  **As a developer**,
  I want modular AI model swapping,
  **so that** future updates are easy.

### 📊 Epic 5 Backlog Table
| ID   | User Story                                      | Story Points | 예상 개발 시간 |
|------|-------------------------------------------------|--------------|----------------|
| B5-1 | Flask/FastAPI 및 Celery 기반 비동기 파이프라인 구축           | 8            | 45–65h        |
| B5-2 | DB 스키마 설계 및 RDS(MySQL) 연동                         | 5            | 30–40h        |
| B5-3 | AWS EC2 서버 구성 및 성능 튜닝 (트래픽·보안 처리)            | 5            | 30–40h        |
| B5-4 | AI 모델 교체 구조 및 API 기반 처리 모듈화                    | 3            | 15–25h        |
| **소계** |                                             | **21 SP**    | **120–170h**  |

---

## 🔢 Overall Development Summary

| 영역 (Epics)                  | 총 Story Points | 총 예상 개발 시간 | 비중  |
|-------------------------------|-----------------|-------------------|-------|
| Data Processing (Epic 1)      | 26              | 150–210h          | 16%   |
| AI Analysis Engine (Epic 2)   | 47              | 260–370h          | 32%   |
| Matching Engine (Epic 3)      | 32              | 180–260h          | 20%   |
| UI & Reporting (Epic 4)       | 26              | 150–210h          | 16%   |
| Infra & Backend (Epic 5)      | 21              | 120–170h          | 13%   |
| **합계 (TOTAL)**              | **152 SP**      | **860–1,220h**    | **100%** |

**Notes:**  
- 목표 성능: 성격 분석 정확도 80% 이상, 매칭 만족도 4.0/5.0, 페이지 로딩 2초 이내, 동시 접속 100명 지원  
- 추후 확장 가능: 스터디·비즈니스 등 추가 소셜 그룹 매칭