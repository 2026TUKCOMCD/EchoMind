# 📘 Product Backlog – EchoMind

**Project:** EchoMind  
**Last Updated:** 2026-01

---

## 📌 Estimation Rules

* **Story Point (SP) Scale:** Fibonacci (1, 2, 3, 5, 8, 13)
* **1 SP:** ≈ 4–6 hours (순수 개발 시간)
* **Excluded:** QA / 디자인 / 문서화 제외
* **Note:** 시간 범위는 기술 리스크 및 통합 난이도 반영

---

## 🎯 Product Vision

> **EchoMind**는 설문 기반 성격 테스트의 한계를 극복하기 위해 실제 대화 데이터(카카오톡 채팅 로그)를 분석하여 사용자의 언어 습관, 감정 패턴, 상호작용 특성을 기반으로 **Big Five 성격 요인**을 추정하고, 이를 바탕으로 궁합 기반 소셜 매칭 및 관계 인사이트를 제공하는 **AI 기반 성격 분석 플랫폼**이다.

---

## 🧩 Platform / Feature Summary

| Platform / Domain | Feature Count | User Story Count |
| :--- | :---: | :---: |
| Web Client (UI) | 5 | 13 |
| AI Analysis Engine | 5 | 14 |
| Matching & Recommendation | 4 | 10 |
| Backend Server | 4 | 9 |
| **Total** | **18** | **46** |

---

## 🟦 EPIC D1 — Conversation Data Processing
**Purpose:** 실제 대화 데이터를 분석 가능한 구조로 변환

### User Stories

* **D1-1 — 카카오톡 대화 파일 업로드**
    * **As a** user,
    **I want** to upload my KakaoTalk chat log file
    **so that** the system can analyze my real conversation data instead of survey answers.

* **D1-2 — 대화 로그 문장 단위 파싱**
    * **As a** system,
    **I want** to parse raw chat logs into sentence-level structured messages
    **so that** natural language processing can be applied consistently.

* **D1-3 — 화자 자동 분리**
    * **As a** user,
    **I want** the system to automatically identify speakers in the conversation
    **so that** I can select whose personality should be analyzed.

* **D1-4 — 텍스트 정규화**
    * **As a** system,
    **I want** to clean and normalize conversation text
    **so that** emojis, noise, and malformed tokens do not distort analysis results.

* **D1-5 — 분석 대상 화자 선택**
    * **As a** user,
    **I want** to filter the conversation by selected speakers
    **so that** the analysis reflects only relevant communication behavior.

### 📊 EPIC D1 Summary Table
| ID | User Story | SP | 예상 개발 시간 |
| :--- | :--- | :---: | :--- |
| D1-1 | 카카오톡 대화 .txt 파일 업로드 | 5 | 30–40h |
| D1-2 | 대화 로그 문장 단위 파싱 | 8 | 45–60h |
| D1-3 | 화자 자동 분리 및 정규화 | 5 | 30–40h |
| D1-4 | 텍스트 정규화 | 3 | 18–25h |
| D1-5 | 분석 대상 화자 선택 | 5 | 30–40h |
| **소계** | | **26 SP** | **153–205h** |

---

## 🟦 EPIC A2 — AI Personality Analysis Engine
**Purpose:** 언어·감정 신호를 성격 특성으로 변환

### User Stories

* **A2-1 — 자기지시어 비율 분석**
    * **As a** system,
    **I want** to measure self-referencing word usage
    **so that** ego-centric communication tendencies can be inferred.

* **A2-2 — 확실성 / 불확실성 표현 분석**
    * **As a** system,
    **I want** to analyze certainty-related expressions
    **so that** confidence and hesitation traits can be estimated.

* **A2-3 — 어휘 다양도 및 문장 구조 분석**
    * **As a** system,
    **I want** to evaluate vocabulary diversity and sentence complexity
    **so that** linguistic richness can be reflected in personality scoring.

* **A2-4 — 감정 극성 분석**
    * **As a** system,
    **I want** to detect emotional polarity in conversations
    **so that** affective stability can be assessed.

* **A2-5 — 독성(Toxicity) 점수 계산**
    * **As a** system,
    **I want** to calculate toxicity levels in language
    **so that** harmful communication patterns can be identified.

* **A2-6 — Big Five 성격 요인 추정**
    * **As a** system,
    **I want** to infer Big Five personality traits from linguistic signals
    **so that** users receive data-driven personality profiles.

* **A2-7 — 분석 결과 저장**
    * **As a** system,
    **I want** to store analysis results in structured JSON format
    **so that** downstream systems can consume them reliably.

### 📊 EPIC A2 Summary Table
| ID | User Story | SP | 예상 개발 시간 |
| :--- | :--- | :---: | :--- |
| A2-1 | 자기지시어 비율 분석 | 5 | 30–40h |
| A2-2 | 확실성/불확실성 분석 | 5 | 30–40h |
| A2-3 | 어휘 다양도 분석 | 5 | 30–40h |
| A2-4 | 감정 극성 분석 | 8 | 50–65h |
| A2-5 | 독성 점수 계산 | 8 | 50–65h |
| A2-6 | Big Five 추정 | 13 | 85–110h |
| A2-7 | 결과 JSON 저장 | 3 | 18–25h |
| **소계** | | **47 SP** | **293–385h** |

---

## 🟦 EPIC M3 — Matching & Recommendation
**Purpose:** 성격 기반 관계 형성 지원

### User Stories

* **M3-1 — 성격 궁합 점수 계산**
    * **As a** system,
    **I want** to calculate compatibility scores between users based on their Big Five personality traits
    **so that** relationship suitability can be quantitatively evaluated.

* **M3-2 — 감정 유사도 가중치 반영**
    * **As a** system,
    **I want** to apply emotional similarity weighting to compatibility calculations
    **so that** users with similar affective patterns are matched more accurately.

* **M3-3 — 언어 스타일 보완 매칭**
    * **As a** system,
    **I want** to match users with complementary language styles
    **so that** communication friction is reduced and interaction quality is improved.

* **M3-4 — 독성 사용자 자동 제외**
    * **As a** system,
    **I want** to exclude users with high toxicity scores from recommendations
    **so that** harmful or abusive interaction risks are minimized.

* **M3-5 — 소셜 그룹 추천**
    * **As a** user,
    **I want** to receive recommendations for compatible social groups
    **so that** I can engage in communities aligned with my personality and communication style.

### 📊 EPIC M3 Summary Table
| ID | User Story | SP | 예상 개발 시간 |
| :--- | :--- | :---: | :--- |
| M3-1 | 성격 궁합 점수 계산 | 8 | 50–65h |
| M3-2 | 감정 유사도 가중치 | 5 | 30–40h |
| M3-3 | 언어 스타일 보완 매칭 | 8 | 50–65h |
| M3-4 | 독성 사용자 제외 | 3 | 18–25h |
| M3-5 | 소셜 그룹 추천 | 8 | 50–65h |
| **소계** | | **32 SP** | **198–260h** |

---

## 🟦 EPIC V4 — Visualization & Reporting
**Purpose:** 분석 결과 시각화 및 리포팅

### User Stories

* **V4-1 — Big Five 성격 요인 시각화**
    * **As a** user,
    **I want** to see my Big Five personality traits visualized clearly
    **so that** I can intuitively understand my personality profile.

* **V4-2 — 감정 분포 차트 제공**
    * **As a** user,
    **I want** to view emotion distribution charts derived from my conversations
    **so that** my emotional tendencies over time are easily recognizable.

* **V4-3 — 통합 분석 대시보드**
    * **As a** user,
    **I want** a centralized dashboard that aggregates all analysis results
    **so that** I can explore personality, emotion, and interaction insights in one place.

* **V4-4 — PDF 리포트 생성**
    * **As a** user,
    **I want** to download my personality analysis as a PDF report
    **so that** I can store, share, or review the results offline.

* **V4-5 — 반응형 UI 지원**
    * **As a** user,
    **I want** the analysis interface to be fully responsive
    **so that** I can access insights seamlessly across desktop and mobile devices.

### 📊 EPIC V4 Summary Table
| ID | User Story | SP | 예상 개발 시간 |
| :--- | :--- | :---: | :--- |
| V4-1 | Big Five 시각화 | 5 | 30–40h |
| V4-2 | 감정 분포 차트 | 5 | 30–40h |
| V4-3 | 분석 대시보드 | 8 | 50–65h |
| V4-4 | PDF 리포트 | 5 | 30–40h |
| V4-5 | 반응형 UI | 3 | 18–25h |
| **소계** | | **26 SP** | **158–210h** |

---

## 🟦 EPIC B5 — Backend & Infrastructure
**Purpose:** 확장 가능하고 유지보수 가능한 시스템

### User Stories

* **B5-1 — 분석 파이프라인 모듈화**
    * **As a** system,
    **I want** the analysis pipeline to be modularized
    **so that** individual components can be developed, tested, and maintained independently.

* **B5-2 — 모델 교체 가능 구조 설계**
    * **As a** system,
    **I want** to support interchangeable AI models
    **so that** improvements or experiments can be deployed without major refactoring.

* **B5-3 — API 기반 처리 구조**
    * **As a** system,
    **I want** all core functionalities to be exposed via APIs
    **so that** web, mobile, or external clients can integrate consistently.

* **B5-4 — 서버 배포 및 실행 환경 구성**
    * **As a** system,
    **I want** a production-ready deployment environment
    **so that** the platform can scale reliably and operate stably.

### 📊 EPIC B5 Summary Table
| ID | User Story | SP | 예상 개발 시간 |
| :--- | :--- | :---: | :--- |
| B5-1 | 파이프라인 모듈화 | 8 | 50–65h |
| B5-2 | 모델 교체 구조 | 5 | 30–40h |
| B5-3 | API 기반 처리 | 8 | 50–65h |
| B5-4 | 서버 배포 환경 | 5 | 30–40h |
| **소계** | | **26 SP** | **160–210h** |

---

## 🔢 Overall System Summary

| 영역 | Story Points | 예상 개발 시간 |
| :--- | :---: | :--- |
| Conversation Data Processing | 26 | 153–205h |
| AI Personality Analysis | 47 | 293–385h |
| Matching & Recommendation | 32 | 198–260h |
| Visualization & Reporting | 26 | 158–210h |
| Backend & Infrastructure | 26 | 160–210h |
| **TOTAL** | **157 SP** | **820–1180h** |
