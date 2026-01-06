
# ✅ **AI 기반 성격 분석 소셜 매칭 시스템 — Product Backlog (Scrum 기반)**

*Epic → Feature → User Story → Acceptance Criteria*

---

## 🟦 1. EPIC — 데이터 수집 및 전처리

---

### ✅ Feature A1 — 카카오톡 대화 업로드

#### User Story A1-1 — 카카오톡 TXT 파일 업로드

**As a** user  
**I want** to upload my KakaoTalk chat export file  
**so that** the system can analyze my real conversation data.

**AC**
- `.txt` 파일만 업로드 가능
- 파일 크기 제한(예: ≤ 20MB)
- 업로드 실패 시 에러 메시지 반환

---

### ✅ Feature A2 — 발화자 기반 대화 추출

#### User Story A2-1 — 사용자 발화 필터링

**As a** system  
**I want** to extract only the target speaker’s messages  
**so that** personality analysis is based solely on the user’s language.

**AC**
- 발화자 이름 기준 필터링
- 다중 참여자 채팅 지원
- 시스템 메시지 자동 제외

---

### ✅ Feature A3 — 텍스트 정제 및 개인정보 보호

#### User Story A3-1 — 불필요 텍스트 제거

**As a** system  
**I want** to clean raw chat text  
**so that** only meaningful linguistic data is analyzed.

**AC**
- 이모티콘, URL 제거
- 반복 웃음/울음(ㅋㅋㅋ, ㅠㅠ) 정규화 또는 제거

---

#### User Story A3-2 — 개인정보 마스킹

**As a** user  
**I want** my personal information to be masked  
**so that** sensitive data is never sent to the LLM.

**AC**
- 전화번호, 이메일, 주민번호 패턴 탐지
- `***` 형태로 치환
- 원문 복구 불가

---

### ✅ Feature A4 — LLM 입력 최적화

#### User Story A4-1 — 발화 샘플링 및 요약

**As a** system  
**I want** to sample and summarize representative utterances  
**so that** LLM cost and risk are minimized.

**AC**
- 전체 발화 중 대표 샘플 선택
- 최대 토큰 수 제한 준수
- 요약 후 원문 폐기 가능

---

## 🟩 2. EPIC — LLM 기반 성격 분석

---

### ✅ Feature B1 — 안전한 프롬프트 제어

#### User Story B1-1 — 분석 역할 및 제한 강제

**As a** system  
**I want** to strictly control the LLM prompt  
**so that** the output is non-diagnostic and ethical.

**AC**
- 심리/의학적 진단 표현 금지
- 관찰된 경향만 기술
- 개인정보 출력 금지
- 원문 직접 인용 금지

---

### ✅ Feature B2 — JSON Schema 기반 출력

#### User Story B2-1 — 구조화된 성격 분석 결과

**As a** backend  
**I want** the LLM to return results in a fixed JSON schema  
**so that** downstream processing is reliable.

**AC**
- communication_style 필드 포함
- notable_patterns, strengths, cautions 포함
- matching_tips 포함
- confidence 값 0~1 범위

---

## 🟨 3. EPIC — 성격 특성 정규화

---

### ✅ Feature C1 — 성향 수치화

#### User Story C1-1 — 0~1 정규화

**As a** system  
**I want** to normalize all personality attributes  
**so that** users can be compared numerically.

**AC**
- 모든 수치 0~1 범위
- 결측치 처리 규칙 정의

---

### ✅ Feature C2 — 분석 신뢰도 반영

#### User Story C2-1 — confidence 점수 저장

**As a** system  
**I want** to store confidence scores  
**so that** low-reliability results are identifiable.

**AC**
- confidence < 0.4 시 경고 플래그
- UI에 신뢰도 표시 가능

---

## 🟥 4. EPIC — 성격 매칭 알고리즘

---

### ✅ Feature D1 — 유사도 기반 매칭

#### User Story D1-1 — 말투/감정 유사도 계산

**As a** system  
**I want** to calculate similarity on compatible traits  
**so that** conversational friction is minimized.

**AC**
- tone, emotion_expression 사용
- 코사인 유사도 적용
- 값이 높을수록 점수 증가

---

### ✅ Feature D2 — 보완성 기반 매칭

#### User Story D2-1 — 주도성/직설성 보완 계산

**As a** system  
**I want** to evaluate complementary traits  
**so that** balanced interactions are encouraged.

**AC**
- initiative, directness 사용
- 거리 기반 점수 계산
- 규칙 기반 보정 가능

---

### ✅ Feature D3 — 혼합 매칭 점수

#### User Story D3-1 — 최종 매칭 랭킹 생성

**As a** user  
**I want** to see ranked match results  
**so that** I can identify best-fit friends.

**AC**
- 유사도 + 보완성 가중 합
- 상위 N명 추천
- 점수 재현 가능

---

## 🟪 5. EPIC — 웹 서비스 및 UI

---

### ✅ Feature E1 — 사용자 플로우

#### User Story E1-1 — 기본 사용자 흐름

**As a** user  
**I want** a simple end-to-end flow  
**so that** I can get results without confusion.

**AC**
- 회원가입 → 로그인 → 업로드 → 분석 → 결과
- 단계별 상태 표시

---

### ✅ Feature E2 — 성격 리포트 UI

#### User Story E2-1 — 성향 요약 시각화

**As a** user  
**I want** a visual personality report  
**so that** I easily understand my traits.

**AC**
- 카드/차트 기반 요약
- 주요 특징 텍스트 제공

---

### ✅ Feature E3 — 매칭 결과 UI

#### User Story E3-1 — 추천 결과 표시

**As a** user  
**I want** to see why someone matches me  
**so that** recommendations feel trustworthy.

**AC**
- 매칭 이유 문장 표시
- 신뢰도 함께 표시

---

## 🟫 6. EPIC — 데이터베이스 및 배포

---

### ✅ Feature F1 — DB 설계

#### User Story F1-1 — 핵심 테이블 정의

**As a** backend  
**I want** a scalable schema  
**so that** the system can grow to multi-user.

**AC**
- User, ChatLog, PersonalityProfile, MatchingResult
- 사용자 기준 분리 저장

---

### ✅ Feature F2 — AWS 배포

#### User Story F2-1 — 서버 배포

**As a** team  
**I want** the system deployed on AWS  
**so that** demos are reliable.

**AC**
- EC2 + RDS 구성
- OpenAI API 키 안전 관리

---

# ✅ Product Backlog 요약

- Epic: 6
- Feature: 14
- User Story: 20+
- Scrum 기반, Acceptance Criteria 명시
- 졸업작품 평가 및 시연 대응 가능

---
