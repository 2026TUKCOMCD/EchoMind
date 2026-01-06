# 📘 Product Backlog – EchoMind

**Project:** EchoMind  
**Last Updated:** 2026-01  
**Platform:** Web-based AI Conversation Analysis & Social Matching  

---

## 🎯 Product Vision

EchoMind는 사용자의 실제 카카오톡 대화 데이터를 웹 페이지에서 직접 업로드하고,  
AI가 대화 속 언어 패턴과 상호작용 성향을 분석하여  
성향이 잘 맞는 친구를 추천하는 웹 기반 소셜 매칭 플랫폼이다.

설문 없이 자연스러운 언어 표현만으로 성향을 분석하며,  
분석 요청부터 결과 확인까지 모든 과정은 웹에서 이루어진다.

---

## 📌 Estimation Rules

- **Story Point Scale:** Fibonacci (1, 2, 3, 5, 8, 13)
- **1 SP:** ≈ 4–6 hours (순수 개발 시간)
- **Excluded:** QA / 디자인 / 문서화
- **Note:** 시간 범위는 기술 리스크 및 통합 난이도 반영

---

## 🟦 EPIC D1 — Conversation Data Processing
**Purpose:** 웹 환경에서 입력된 대화 데이터를 분석 가능한 형태로 변환

### User Stories

**D1-1 — 웹 기반 카카오톡 대화 파일 업로드**  
As a user,  
I want to upload my KakaoTalk chat file through a web page,  
so that I can submit my conversation data without using the console.

**D1-2 — 대화 참여자 목록 추출**  
As a system,  
I want to extract all speakers from the uploaded chat log,  
so that the user can choose which participant to analyze.

**D1-3 — 분석 대상 화자 선택 UI 제공**  
As a user,  
I want to select the target speaker on the web page,  
so that only my conversation style is analyzed.

**D1-4 — 서버 측 텍스트 전처리**  
As a system,  
I want to remove system messages, emojis, URLs, and noise,  
so that only meaningful text is analyzed.

**D1-5 — 개인정보 자동 마스킹**  
As a system,  
I want to mask personal information before sending data to the LLM,  
so that sensitive data is protected.

### 📊 EPIC D1 Summary Table

| ID | User Story | SP | 예상 개발 시간 |
| :--- | :--- | :---: | :--- |
| D1-1 | 웹 파일 업로드 | 5 | 30–40h |
| D1-2 | 참여자 추출 | 5 | 30–40h |
| D1-3 | 화자 선택 UI | 5 | 30–40h |
| D1-4 | 텍스트 전처리 | 8 | 45–60h |
| D1-5 | 개인정보 마스킹 | 3 | 18–25h |
| **소계** | | **26 SP** | **153–205h** |

---

## 🟦 EPIC A2 — AI Conversation Style Analysis
**Purpose:** 대화 언어 패턴을 성향 지표로 변환

### User Stories

**A2-1 — 말투 및 커뮤니케이션 톤 분석**  
As a system,  
I want to analyze the tone of conversation,  
so that communication style tendencies can be identified.

**A2-2 — 감정 표현 강도 분석**  
As a system,  
I want to estimate how strongly emotions are expressed,  
so that affective communication patterns are observed.

**A2-3 — 직설성 및 완곡성 분석**  
As a system,  
I want to analyze directness in language use,  
so that interaction style can be inferred.

**A2-4 — 공감 표현 신호 분석**  
As a system,  
I want to detect empathy-related expressions,  
so that relational sensitivity can be described.

**A2-5 — 갈등 대응 방식 추론**  
As a system,  
I want to infer conflict handling tendencies,  
so that interaction risks can be explained.

**A2-6 — 성향 분석 결과 구조화(JSON)**  
As a system,  
I want to output analysis results in a fixed JSON schema,  
so that matching algorithms can consume them reliably.

### 📊 EPIC A2 Summary Table

| ID | User Story | SP | 예상 개발 시간 |
| :--- | :--- | :---: | :--- |
| A2-1 | 톤 분석 | 5 | 30–40h |
| A2-2 | 감정 표현 분석 | 8 | 50–65h |
| A2-3 | 직설성 분석 | 5 | 30–40h |
| A2-4 | 공감 신호 분석 | 5 | 30–40h |
| A2-5 | 갈등 대응 추론 | 8 | 50–65h |
| A2-6 | JSON 구조화 | 3 | 18–25h |
| **소계** | | **34 SP** | **208–275h** |

---

## 🟦 EPIC M3 — Matching & Recommendation
**Purpose:** 성향 기반 친구 추천

### User Stories

**M3-1 — 성향 벡터 정규화**  
As a system,  
I want to normalize conversation traits into numerical vectors,  
so that users can be compared consistently.

**M3-2 — 유사 성향 매칭 점수 계산**  
As a system,  
I want to calculate similarity-based scores,  
so that users with similar styles can be matched.

**M3-3 — 보완 성향 매칭 점수 계산**  
As a system,  
I want to calculate complementarity scores,  
so that balanced interactions are encouraged.

**M3-4 — 최종 매칭 점수 통합**  
As a system,  
I want to combine similarity and complementarity scores,  
so that recommendations feel natural.

**M3-5 — 추천 사용자 목록 생성**  
As a user,  
I want to see recommended friends,  
so that I can explore compatible people.

### 📊 EPIC M3 Summary Table

| ID | User Story | SP | 예상 개발 시간 |
| :--- | :--- | :---: | :--- |
| M3-1 | 성향 벡터화 | 5 | 30–40h |
| M3-2 | 유사도 매칭 | 8 | 50–65h |
| M3-3 | 보완 매칭 | 8 | 50–65h |
| M3-4 | 점수 통합 | 5 | 30–40h |
| M3-5 | 추천 리스트 | 5 | 30–40h |
| **소계** | | **31 SP** | **190–250h** |

---

## 🟦 EPIC V4 — Visualization & Reporting
**Purpose:** 분석 결과를 웹 UI로 제공

### User Stories

**V4-1 — 성향 분석 결과 웹 표시**  
As a user,  
I want to view my analysis results on the web page,  
so that I can understand my communication style easily.

**V4-2 — 분석 진행 상태 표시**  
As a user,  
I want to see analysis progress,  
so that I know when results are ready.

**V4-3 — 차트 기반 시각화 제공**  
As a user,  
I want to see charts and indicators,  
so that results are intuitive.

**V4-4 — 매칭 결과 설명 표시**  
As a user,  
I want to see why someone was recommended,  
so that I trust the matching result.

**V4-5 — 이전 결과 재확인**  
As a user,  
I want to revisit past results,  
so that I can track changes.

### 📊 EPIC V4 Summary Table

| ID | User Story | SP | 예상 개발 시간 |
| :--- | :--- | :---: | :--- |
| V4-1 | 결과 출력 | 5 | 30–40h |
| V4-2 | 상태 표시 | 3 | 18–25h |
| V4-3 | 시각화 | 5 | 30–40h |
| V4-4 | 매칭 설명 | 5 | 30–40h |
| V4-5 | 결과 재조회 | 3 | 18–25h |
| **소계** | | **21 SP** | **126–170h** |

---

## 🟦 EPIC B5 — Backend & Infrastructure
**Purpose:** 웹 기반 서비스 운영

### User Stories

**B5-1 — 분석 요청 API 구현**  
As a system,  
I want to expose analysis APIs,  
so that the frontend can trigger AI analysis.

**B5-2 — 결과 저장 DB 설계**  
As a system,  
I want to store analysis and matching results,  
so that data persists.

**B5-3 — 분석 상태 관리**  
As a system,  
I want to track analysis lifecycle states,  
so that progress is visible.

**B5-4 — AWS 웹 서버 배포**  
As a system,  
I want to deploy the backend on AWS,  
so that the service is accessible online.

### 📊 EPIC B5 Summary Table

| ID | User Story | SP | 예상 개발 시간 |
| :--- | :--- | :---: | :--- |
| B5-1 | 분석 API | 8 | 50–65h |
| B5-2 | DB 저장 | 5 | 30–40h |
| B5-3 | 상태 관리 | 5 | 30–40h |
| B5-4 | AWS 배포 | 8 | 50–65h |
| **소계** | | **26 SP** | **160–210h** |

---

## 🔢 Overall System Summary

| 영역 | Story Points | 예상 개발 시간 |
| :--- | :---: | :--- |
| Conversation Data Processing | 26 | 153–205h |
| AI Conversation Analysis | 34 | 208–275h |
| Matching & Recommendation | 31 | 190–250h |
| Visualization & Reporting | 21 | 126–170h |
| Backend & Infrastructure | 26 | 160–210h |
| **TOTAL** | **138 SP** | **837–1110h** |
"""
