# 📘 Product Backlog – EchoMind

**Project:** OpenAI GPT 기반 대화 분석 및 소셜 매칭 플랫폼  
**Last Updated:** 2026-01  
**Project Vision:** 실제 카카오톡 대화 로그를 GPT 모델로 분석하여
사용자의 고유한 성격 특성, 대화 스타일, 개선점을 도출하고 이를 기반으로 최적의 관계 인사이트와 소셜 매칭을 제공하는 웹 서비스.

---

## 📌 Estimation Rules

* **Story Point (SP) Scale:** Fibonacci (1, 2, 3, 5, 8, 13)
* **1 SP ≈ 7 Hours** (순수 개발 시간 기준)
* **Time Range:** 기술적 리스크, 프롬프트 최적화 및 시스템 통합 난이도 반영

---

## 🟦 EPIC 1 — 웹 기반 대화 데이터 처리 파이프라인 (161h)
**Purpose:** 사용자가 웹에서 업로드한 비정형 대화 파일을 구조화된 데이터로 정제

### 📝 User Stories

* **D1-1: 웹 UI를 통한 대용량 로그 파일 업로드**
    * **As a user**,
    I want to upload my KakaoTalk `.txt` file via a web interface,
    **so that** the system can process my data without local console interaction.

* **D1-2: 대화 데이터 구조화 및 문장 파싱 엔진**
    * **As a system**,
    I want to parse raw text into structured objects (Timestamp, Speaker, Message),
    **so that** context is preserved for the GPT model.

* **D1-3: 화자 식별 및 분석 대상 커스텀 선택**
    * **As a user**,
    I want to see a list of chat participants and select a specific person,
    **so that** the analysis is accurately focused on the intended individual.

* **D1-4: 개인정보 식별 및 데이터 마스킹**
    * **As a system**,
    I want to detect and mask sensitive information (phone numbers, addresses) before sending data to the API,
    **so that** user privacy is protected.

### 📊 Epic 1 Backlog Table
| ID | User Story | SP | 예상 개발 시간 |
|---|---|---|---|
| D1-1 | 웹 파일 업로드 컴포넌트 및 멀티파트 개발 | 5 | 35h |
| D1-2 | 카카오톡 특화 대화 포맷 파싱 및 데이터 정규화 로직 | 8 | 56h |
| D1-3 | 화자 추출 UI 및 선택 필터링 기능 구현 | 5 | 35h |
| D1-4 | 보안을 위한 데이터 프리프로세싱 및 마스킹 모듈 | 5 | 35h |
| **소계** | | **23 SP** | **161h** |

---

## 🟦 EPIC 2 — GPT 기반 성격 및 대화 스타일 분석 엔진 (357h)
**Purpose:** OpenAI GPT-4를 활용하여 심층적인 성격 지표 및 피드백 도출

### 📝 User Stories

* **A2-1: OpenAI GPT API 연동 및 보안 환경 구축**
    * **As a developer**,
    I want to securely integrate the OpenAI API,
    **so that** I can leverage high-performance LLMs for text analysis.

* **A2-2: 성격 특성 및 페르소나 추출 프롬프트 엔지니어링**
    * **As a system**,
    I want to derive qualitative personality traits from conversation patterns,
    **so that** I can build a comprehensive user profile.

* **A2-3: 대화 스타일 및 언어 습관 수치화**
    * **As a system**,
    I want to analyze communication styles (active, passive, assertive, etc.),
    **so that** I can provide objective linguistic insights.

* **A2-4: 맞춤형 대화 개선점 및 피드백 생성**
    * **As a user**,
    I want to receive specific advice on how to improve my social interactions based on my logs,
    **so that** I can grow socially.

* **A2-5: 분석 프로세스 비동기 처리 및 상태 알림**
    * **As a user**,
    I want to see the progress of the analysis in real-time,
    **so that** I am informed during the GPT processing time.

### 📊 Epic 2 Backlog Table
| ID | User Story | SP | 예상 개발 시간 |
|---|---|---|---|
| A2-1 | API 연동 환경 구축 및 비용 최적화 로직 | 8 | 56h |
| A2-2 | 성격/스타일 분석용 페르소나 프롬프트 엔지니어링 | 13 | 91h |
| A2-3 | 대화 개선점 제안 알고리즘 및 결과 파싱 로직 | 13 | 91h |
| A2-4 | JSON 구조화 및 데이터 모델링 | 5 | 35h |
| A2-5 | Celery/Redis 기반 비동기 작업 큐 및 상태 전송 API | 12 | 84h |
| **소계** | | **51 SP** | **357h** |

---

## 🟦 EPIC 3 — 알고리즘 기반 소셜 매칭 엔진 (210h)
**Purpose:** 분석된 성격 지표 간의 보완성을 계산하여 최적의 관계 추천

### 📝 User Stories

* **M3-1: 성격 키워드 유사도 및 보완성 계산**
    * **As a system**,
    I want to calculate compatibility scores between users based on GPT-derived traits, 
    *so that** I can suggest high-potential relationships.

* **M3-2: 대화 스타일 적합도 필터링**
    * **As a system**,
    I want to match users with compatible communication styles,
    **so that** friction in interaction is minimized.

* **M3-3: 추천 소셜 그룹 매핑 및 랭킹**
    * **As a user**,
    I want to see a ranked list of social groups that fit my personality,
    **so that** I can join relevant communities.

### 📊 Epic 3 Backlog Table
| ID | User Story | SP | 예상 개발 시간 |
|---|---|---|---|
| M3-1 | 사용자 간 성격 보완성 매칭 알고리즘 구현 | 13 | 91h |
| M3-2 | 대화 스타일 기반 매칭 가중치 시스템 구축 | 8 | 56h |
| M3-3 | 추천 목록 큐레이션 및 소셜 그룹 매핑 엔진 | 9 | 63h |
| **소계** | | **30 SP** | **210h** |

---

## 🟦 EPIC 4 — 분석 리포트 대시보드 및 반응형 UI (154h)
**Purpose:** 분석 결과를 시각화하여 웹 페이지에서 직관적으로 제공

### 📝 User Stories

* **V4-1: 성격 및 스타일 시각화 대시보드**
    * **As a user**,
    I want to see my results in a web dashboard with charts and cards,
    **so that** the information is easy to consume.

* **V4-2: 인터랙티브 매칭 결과 리스트**
    * **As a user**,
    I want to browse my matches with detailed suitability explanations,
    **so that** I can understand why we were paired.

* **V4-3: 반응형 웹 최적화 (Desktop/Mobile)**
    * **As a mobile user**,
    I want the dashboard to be fully responsive,
    **so that** I can check my reports on any device.

### 📊 Epic 4 Backlog Table
| ID | User Story | SP | 예상 개발 시간 |
|---|---|---|---|
| V4-1 | 결과 시각화(Chart.js/D3.js) 및 대시보드 레이아웃 구현 | 10 | 70h |
| V4-2 | 매칭 상세 페이지 및 그룹 추천 UI 개발 | 7 | 49h |
| V4-3 | 반응형 디자인 적용 및 프론트엔드 성능 최적화 | 5 | 35h |
| **소계** | | **22 SP** | **154h** |

---

## 🟦 EPIC 5 — 백엔드 인프라 및 운영 안정화 (140h)
**Purpose:** 확장 가능하고 안전한 시스템 운영 환경 구축

### 📝 User Stories

* **B5-1: Flask/FastAPI 기반 확장형 API 서버**
    * **As a developer**,
    I want to build a modular backend,
    **so that** the system can be easily maintained and updated.

* **B5-2: 분석 이력 및 사용자 데이터베이스 관리**
    * **As a user**,
    I want my past reports to be stored securely,
    **so that** I can access them without re-uploading files.

* **B5-3: AWS 클라우드 배포 및 도메인 보안 설정**
    * **As a system**,
    I want to be hosted on a reliable cloud environment with HTTPS,
    **so that** the service is always available and secure.

### 📊 Epic 5 Backlog Table
| ID | User Story | SP | 예상 개발 시간 |
|---|---|---|---|
| B5-1 | API 아키텍처 설계 및 핵심 비즈니스 로직 구현 | 8 | 56h |
| B5-2 | 데이터베이스(MySQL/PostgreSQL) 모델링 및 연동 | 5 | 35h |
| B5-3 | AWS EC2/RDS 인프라 구축 및 CI/CD 파이프라인 설정 | 7 | 49h |
| **소계** | | **20 SP** | **140h** |

---

## 🔢 Overall Development Summary

| 영역 (Epics) | 총 Story Points | 총 예상 개발 시간 | 비중 |
|---|---|---|---|
| **Data Processing (Epic 1)** | 23 | 161h | 15.7% |
| **GPT Analysis Engine (Epic 2)** | 51 | 357h | 34.9% |
| **Matching Engine (Epic 3)** | 30 | 210h | 20.6% |
| **Web UI & Reporting (Epic 4)** | 22 | 154h | 15.1% |
| **Backend & Infra (Epic 5)** | 20 | 140h | 13.7% |
| **합계 (TOTAL)** | **146 SP** | **1,022h** | **100.0%** |
