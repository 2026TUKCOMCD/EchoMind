# 📘 Product Backlog – EchoMind

**Project:** AI 기반 성격 분석 및 소셜 매칭 시스템  
**Project Vision:** 카카오톡 대화 로그를 웹에서 업로드하고, OpenAI GPT-4o 모델을 활용해 실제 대화에서 드러나는 언어 패턴을 분석하여 8가지 성격 지표(자신감, 공감 능력, 유머 감각, 사교성, 창의력, 스트레스 대처 능력, 긍정적 태도, 리더십 잠재력)를 추정한다. 분석 결과와 매칭 추천을 웹 페이지에서 바로 확인할 수 있는 반응형 플랫폼을 제공한다.  
**Last Updated:** January 06, 2026  

---

## 📌 Estimation Rules

* **Story Point (SP) Scale:** Fibonacci (1, 2, 3, 5, 8, 13)
* **1 SP ≈ 5.5–7.5 Hours** (순수 개발 시간 기준, QA/디자인/문서화 제외)
* **Time Range:** GPT-4o 프롬프트 정확도 튜닝, 토큰 관리, 비용 최적화, 웹 실시간 처리 리스크 반영

---

## 🟦 EPIC 1 — 대화 데이터 전처리 파이프라인 (150–210h)
**Purpose:** 웹에서 업로드된 카카오톡 대화 로그를 정제하고 GPT 분석에 최적화된 형태로 변환.

### 📝 User Stories

* **D1-1: 다중 포맷 채팅 로그 웹 업로드**  
  **As a user**,
  I want to upload KakaoTalk chat logs (.txt, .csv, .pdf) via web browser,
  **so that** the system can process my real conversations.

* **D1-2: 카카오톡 로그 파싱 및 문장 단위 분리**  
  **As a system**,
  I want to parse raw logs into timestamped, speaker-separated utterances,
  **so that** GPT can accurately interpret context.

* **D1-3: 화자 자동 분리 및 선택 UI**  
  **As a user**,
  I want the system to detect speakers automatically and let me select whose personality to analyze,
  **so that** results reflect the intended person.

* **D1-4: 텍스트 노이즈 제거 및 정규화**  
  **As a system**,
  I want to remove emojis, system messages, URLs, and normalize text,
  **so that** GPT receives clean input.

* **D1-5: 분석 대상 화자 필터링**  
  **As a user**,
  I want to filter the conversation to include only selected speakers,
  **so that** analysis is precise.

### 📊 Epic 1 Backlog Table
| ID   | Title                               | Story Points | 예상 개발 시간 |
|------|-------------------------------------|--------------|----------------|
| D1-1 | 다중 포맷 채팅 로그 웹 업로드        | 5            | 30–40h        |
| D1-2 | 카카오톡 로그 파싱 및 문장 분리      | 8            | 45–65h        |
| D1-3 | 화자 자동 분리 및 선택 UI            | 5            | 30–40h        |
| D1-4 | 텍스트 노이즈 제거 및 정규화         | 3            | 15–25h        |
| D1-5 | 분석 대상 화자 필터링                | 5            | 30–40h        |
| **소계** |                                 | **26 SP**    | **150–210h**  |

---

## 🟦 EPIC 2 — GPT-4o 기반 성격 분석 엔진 (260–370h)
**Purpose:** 정제된 대화 텍스트를 GPT-4o에 전달하여 8가지 성격 지표를 실시간으로 추정.

### 📝 User Stories

* **A2-1: 8가지 성격 지표 프롬프트 설계 및 최적화**  
  **As a developer**,
  I want to design refined prompts that reliably extract the 8 traits (Confidence, Empathy, Humor, Sociability, Creativity, Stress Tolerance, Positivity, Leadership Potential),
  **so that** results are consistent and insightful.

* **A2-2: GPT-4o API 호출 및 구조화된 응답 처리**  
  **As a system**,
  I want to call GPT-4o with conversation context and parse structured output containing the 8 trait scores and explanations, **so that** results can be displayed immediately on the web.

* **A2-3: 긴 대화 요약 및 토큰 최적화**  
  **As a system**,
  I want to summarize or chunk long conversations to stay within token limits while preserving key patterns,
  **so that** full histories can be analyzed efficiently.

* **A2-4: 분석 정확도 검증 및 프롬프트 반복 튜닝**  
  **As a developer**,
  I want to test outputs against diverse sample conversations and refine prompts iteratively,
  **so that** trait estimation meets target reliability.

### 📊 Epic 2 Backlog Table
| ID   | Title                                      | Story Points | 예상 개발 시간 |
|------|--------------------------------------------|--------------|----------------|
| A2-1 | 8가지 성격 지표 프롬프트 설계 및 최적화     | 13           | 70–100h       |
| A2-2 | GPT-4o API 호출 및 응답 파싱                | 8            | 45–65h        |
| A2-3 | 긴 대화 요약 및 토큰 관리 로직              | 8            | 45–65h        |
| A2-4 | 분석 정확도 검증 및 프롬프트 튜닝           | 13           | 70–100h       |
| **소계** |                                        | **42 SP**    | **230–330h**  |

---

## 🟦 EPIC 3 — 소셜 매칭 엔진 (180–260h)
**Purpose:** GPT로 추정된 8가지 성격 지표를 기반으로 사용자-소셜 그룹 궁합 계산.

### 📝 User Stories

* **M3-1: 8가지 지표 보완성/유사성 기반 매칭**  
  **As a user**,
  I want to be matched with groups whose average trait profiles complement or align with mine,
  **so that** interactions feel natural and rewarding.

* **M3-2: 감정 톤 및 언어 스타일 유사도 계산**  
  **As a system**,
  I want to compute similarity based on GPT-derived emotional tone and style descriptions,
  **so that** matches have compatible communication vibes.

* **M3-3: 지표별 최적 편차 적용**  
  **As a system**,
  I want to apply optimal deviation rules for certain traits,
  **so that** conversations stay engaging.

* **M3-4: 최종 매칭 점수 산출 엔진**  
  **As a system**,
  I want to combine all trait similarities into a final compatibility score,
  **so that** recommendations are meaningfully ranked.

* **M3-5: 가상 소셜 그룹 프로필 20개 이상 구축**  
  **As a developer**,
  I want to create and maintain 20+ mock group profiles with predefined 8-trait scores,
  **so that** matching can be tested and demonstrated.

* **M3-6: 매칭 가중치 관리 UI**  
  **As a manager**,
  I want an admin interface to adjust trait weights,
  **so that** the algorithm can evolve.

### 📊 Epic 3 Backlog Table
| ID   | Title                                      | Story Points | 예상 개발 시간 |
|------|--------------------------------------------|--------------|----------------|
| M3-1 | 8가지 지표 보완성/유사성 기반 매칭          | 8            | 45–65h        |
| M3-2 | 감정 톤 및 언어 스타일 유사도 계산          | 8            | 45–65h        |
| M3-3 | 지표별 최적 편차 적용                      | 5            | 30–40h        |
| M3-4 | 최종 매칭 점수 산출 엔진                   | 5            | 30–40h        |
| M3-5 | 가상 소셜 그룹 프로필 20개 이상 구축        | 3            | 15–25h        |
| M3-6 | 매칭 가중치 관리 UI                        | 3            | 15–25h        |
| **소계** |                                        | **32 SP**    | **180–260h**  |

---

## 🟦 EPIC 4 — 시각화 및 반응형 웹 UI (160–220h)
**Purpose:** 웹 페이지에서 8가지 성격 지표와 매칭 결과를 실시간으로 직관적으로 확인.

### 📝 User Stories

* **V4-1: 8가지 성격 지표 레이더 차트 시각화**  
  **As a user**,
  I want to see my 8 trait scores on a radar chart immediately after analysis,
  **so that** I can quickly grasp my personality profile.

* **V4-2: 성격 지표별 상세 설명 웹 페이지**  
  **As a user**,
  I want detailed explanations for each trait derived from GPT, displayed on the web,
  **so that** I can reflect on my communication patterns.

* **V4-3: 추천 소셜 그룹 랭킹 리스트 웹 표시**  
  **As a user**,
  I want a ranked list of recommended groups with compatibility scores shown on the web,
  **so that** I can explore the best matches right away.

* **V4-4: 반응형 웹 인터페이스 및 흐름 최적화**  
  **As a mobile user**,
  I want a fully responsive design with smooth flow (upload → processing → results),
  **so that** the entire experience is seamless on any device.

* **V4-5: 분석 진행 상태 실시간 표시**  
  **As a user**,
  I want to see progress indicators during GPT processing,
  **so that** I know the analysis is running.

### 📊 Epic 4 Backlog Table
| ID   | Title                                      | Story Points | 예상 개발 시간 |
|------|--------------------------------------------|--------------|----------------|
| V4-1 | 8가지 성격 지표 레이더 차트 시각화          | 5            | 30–40h        |
| V4-2 | 성격 지표별 상세 설명 웹 페이지             | 8            | 45–65h        |
| V4-3 | 추천 소셜 그룹 랭킹 리스트 웹 표시          | 5            | 30–40h        |
| V4-4 | 반응형 웹 인터페이스 및 흐름 최적화         | 8            | 45–65h        |
| V4-5 | 분석 진행 상태 실시간 표시                  | 3            | 15–25h        |
| **소계** |                                        | **29 SP**    | **165–235h**  |

---

## 🟦 EPIC 5 — 시스템 인프라 및 백엔드 안정화 (120–170h)
**Purpose:** 웹 서비스의 안정적 운영을 위한 백엔드 및 배포 환경 구축.

### 📝 User Stories

* **B5-1: 비동기 GPT 처리 큐 구현**  
  **As a developer**,
  I want asynchronous task queuing,
  **so that** long GPT calls don't block the web server.

* **B5-2: 세션 기반 임시 결과 저장**  
  **As a system**,
  I want to temporarily store analysis results in session or cache,
  **so that** users can view results without permanent DB storage.

* **B5-3: AWS 배포 및 고동시 처리**  
  **As a system**,
  I want deployment supporting 100 concurrent users with <2s page load,
  **so that** service remains responsive.

* **B5-4: GPT API 키 관리 및 비용 모니터링**  
  **As a developer**,
  I want secure key management and usage logging,
  **so that** operational costs are controlled.

### 📊 Epic 5 Backlog Table
| ID   | Title                                      | Story Points | 예상 개발 시간 |
|------|--------------------------------------------|--------------|----------------|
| B5-1 | 비동기 GPT 처리 큐 구현                     | 8            | 45–65h        |
| B5-2 | 세션 기반 임시 결과 저장                    | 3            | 15–25h        |
| B5-3 | AWS 배포 및 성능 튜닝                       | 5            | 30–40h        |
| B5-4 | GPT API 키 관리 및 비용 모니터링             | 3            | 15–25h        |
| **소계** |                                        | **19 SP**    | **105–155h**  |

---

## 🔢 Overall Development Summary

| 영역 (Epics)                  | 총 Story Points | 총 예상 개발 시간 | 비중  |
|-------------------------------|-----------------|-------------------|-------|
| Data Processing (Epic 1)      | 26              | 150–210h          | 17%   |
| GPT Analysis Engine (Epic 2)  | 42              | 230–330h          | 30%   |
| Matching Engine (Epic 3)      | 32              | 180–260h          | 21%   |
| Web UI & Visualization (Epic 4) | 29            | 165–235h          | 19%   |
| Infra & Backend (Epic 5)      | 19              | 105–155h          | 13%   |
| **합계 (TOTAL)**              | **148 SP**      | **830–1,190h**    | **100%** |
