# 🧠 AI 기반 성격 분석을 활용한 소셜 매칭 시스템 — Product Backlog

## 프로젝트 개요
AI가 사용자의 실제 대화 데이터를 분석하여 성격을 자동 파악하고, 성향이 잘 맞는 친구를 추천하는 소셜 매칭 플랫폼을 개발한다.  
*차별점:* 설문 없이 자연어 대화만으로 성격을 분석하며, 이를 통해 언어 패턴이 성향을 얼마나 반영하는지 실험적으로 검증한다.

---

## Epic 1. 데이터 수집 및 전처리 자동화

### Feature 1.1 — 대화 파일 업로드 및 추출
**User Story:**  
사용자는 카카오톡 대화 파일을 업로드하면, 시스템이 내 대화 내용만 자동 추출하길 원한다.  

**Acceptance Criteria:**  
- [ ] 카카오톡 `.txt` 파일 업로드 기능 제공  
- [ ] 발화자 기준으로 사용자 메시지만 추출  
- [ ] 시스템 메시지, 이모티콘, URL, 반복 감정표현(ㅋㅋ,ㅠㅠ 등) 제거  
- [ ] 처리 결과 미리보기 기능 제공  

---

### Feature 1.2 — 개인정보 마스킹
**User Story:**  
사용자는 내 개인정보가 외부 AI에 전달되지 않도록 자동 치환(마스킹)되길 원한다.

**Acceptance Criteria:**  
- [ ] 전화번호, 이메일, 주민번호 등의 정보 자동 탐지 및 `MASKED` 치환  
- [ ] 원문 구조 유지 (대화 문맥 손상 방지)  
- [ ] 마스킹 후 분석 정확도 유지  

---

### Feature 1.3 — 데이터 샘플링 및 요약
**User Story:**  
사용자는 긴 대화에서도 주요 발화만 추출해 효율적으로 분석되길 원한다.

**Acceptance Criteria:**  
- [ ] 너무 긴 대화 파일은 발화 빈도 기반으로 대표 샘플 추출  
- [ ] LLM의 입력 토큰 한도 내에서 요약 수행  
- [ ] 텍스트 의미 유지 및 주제 일관성 검증  

---

## Epic 2. AI 성격 분석 (LLM 기반)

### Feature 2.1 — 프롬프트 설계 및 제약 조건
**User Story:**  
개발자는 LLM이 심리검사처럼 단정하거나 개인정보를 노출하지 않도록 제약을 두고 싶다.

**Acceptance Criteria:**  
- [ ] “단정적 표현/진단”을 금지  
- [ ] 개인정보 직접 언급 금지  
- [ ] 원문 직접 인용 대신 요약/의역만 허용  

---

### Feature 2.2 — JSON Schema 기반 출력 형식
**User Story:**  
LLM은 모든 성격 분석 결과를 정해진 JSON 구조에 맞게 반환한다.

**Acceptance Criteria:**  
- [ ] 아래 필드를 모두 포함하는 JSON 반환  
  ```json
  {
    "communication_style": {
      "tone": "",
      "directness": "",
      "emotion_expression": "",
      "empathy_signals": "",
      "initiative": "",
      "conflict_style": ""
    },
    "notable_patterns": "",
    "strengths": "",
    "cautions": "",
    "matching_tips": "",
    "confidence": 0.0
  }
  ```
- [ ] 필드 누락 시 예외 처리 및 재요청 수행  

---

### Feature 2.3 — 신뢰도(confidence) 계산
**User Story:**  
사용자는 분석 결과의 신뢰도를 알고 싶다.

**Acceptance Criteria:**  
- [ ] 대화량, 일관성, 감정 표현 정도를 기준으로 0~1 값 산출  
- [ ] 대화 데이터가 적을수록 score 낮게 설정  
- [ ] UI에서 시각적으로 표시 (게이지바 형태)  

---

## Epic 3. 성격 매칭 알고리즘 설계

### Feature 3.1 — 성향 정규화
**User Story:**  
시스템은 다양한 성향 지표를 0~1의 수치로 변환해 비교 가능하게 만든다.

**Acceptance Criteria:**  
- [ ] tone, emotion_expression 등 각 속성을 수치화  
- [ ] 값은 [0, 1] 범위 내 정규화  
- [ ] LLM 결과 간 비교 시 일관성 유지  

---

### Feature 3.2 — 매칭 점수 계산
**User Story:**  
사용자는 “비슷한 사람”뿐 아니라 “잘 맞는 사람”을 매칭 받고 싶다.

**Acceptance Criteria:**  
- [ ] 유사성 축 (tone, emotion_expression): 코사인 유사도 활용  
- [ ] 보완성 축 (initiative, directness): 거리 기반 + 규칙 보정  
- [ ] 최종 점수 = (유사도 가중치 + 보완성 가중치) / 2  
- [ ] 상위 N명(예: 5명) 결과 반환  

---

## Epic 4. 웹 서비스 구현

### Feature 4.1 — Flask 기반 웹 인터페이스
**User Story:**  
사용자는 웹페이지에서 대화 업로드, 분석 결과 확인, 친구 추천까지 한 번에 수행하길 원한다.

**Acceptance Criteria:**  
- [ ] Flask + HTML/CSS + JS 기반 UI 구축  
- [ ] 업로드 → 분석 → 결과 시각화 → 매칭 리스트 표시 플로우 구현  
- [ ] 그래프 및 카드 형태로 결과 표시  

---

### Feature 4.2 — 회원 관리 및 DB 연동
**User Story:**  
사용자는 로그인 후 이전 분석 기록과 추천 결과를 저장하고 조회하고 싶다.

**Acceptance Criteria:**  
- [ ] MySQL(RDS) 기반 유저, 성격, 매칭 테이블 설계  
- [ ] Flask ORM(SQLAlchemy) 연동  
- [ ] 회원가입, 로그인, 분석 이력 저장 기능 구현  

---

### Feature 4.3 — 서버 배포 (AWS)
**User Story:**  
관리자는 AWS 환경에서 서비스를 안전하게 배포하고 싶다.

**Acceptance Criteria:**  
- [ ] Flask 서버를 AWS EC2에 배포  
- [ ] 정적 리소스는 AWS S3에서 제공  
- [ ] OpenAI API Key 환경 변수로 관리  
- [ ] HTTPS 적용 및 보안 설정 완료  

---

## Epic 5. 시각화 및 UX 개선

### Feature 5.1 — 결과 시각화
**User Story:**  
사용자는 성격 분석 및 매칭 결과를 직관적으로 확인하고 싶다.

**Acceptance Criteria:**  
- [ ] 감정 표현, 주도성, 공감 정도를 그래프로 표현  
- [ ] 매칭 점수 상위 친구 목록을 추천 카드로 출력  
- [ ] 평균 대비 비교 시각화 제공 (ex. radar chart)  

---

### Feature 5.2 — UI 반응성 및 편의성
**User Story:**  
사용자는 결과 화면이 빠르고 직관적으로 반응하길 원한다.

**Acceptance Criteria:**  
- [ ] 분석 요청 후 초기 로딩 알림 표시  
- [ ] 결과 표시 시간 2초 이내 (로컬)  
- [ ] 반응형 UI(모바일 호환) 지원  

---

## Epic 6. 성능 및 확장성 향상

### Feature 6.1 — 응답 속도 최적화
**User Story:**  
사용자는 분석 대기 시간이 짧길 원한다.

**Acceptance Criteria:**  
- [ ] LLM 호출 동시 처리 (비동기 요청)  
- [ ] 평균 응답 시간 10초 이내 유지  
- [ ] 캐싱 및 로그 기반 성능 모니터링 추가  

---

### Feature 6.2 — 멀티 유저 처리 및 확장
**User Story:**  
관리자는 여러 사용자의 대화를 동시에 분석할 수 있도록 확장성을 확보하고 싶다.

**Acceptance Criteria:**  
- [ ] 분석 요청 큐잉 처리 구현  
- [ ] RDS Connection Pool 최적화  
- [ ] 다중 사용자 요청 시 자원 병목 최소화  

---

## Epic 7. 프로젝트 관리 및 향후 확장

### Feature 7.1 — 실험 및 성능 검증
**User Story:**  
개발자는 분석 정확도와 매칭 적합도를 실험적으로 검증하고 싶다.

**Acceptance Criteria:**  
- [ ] 대화 기반 성격 분석 정확도 vs 설문형 검사 비교  
- [ ] 매칭 후 사용자 피드백 기반 평가(정성 데이터 수집)  

---

### Feature 7.2 — 향후 기능 확장 아이디어
**예비 기능 제안:**
- 감정 변화 추적 (Temporal Emotion Analysis)  
- 그룹 성향 매칭 (팀워크 예측)  
- 다른 메신저(디스코드, 텔레그램 등) 연동  

---

## 📅 프로젝트 일정 (추천)
| 기간 | 주요 목표 | 산출물 |
|------|------------|--------|
| 1~2개월 | 데이터 처리 및 AI 분석 로직 구현 | 전처리 모듈, LLM 프롬프트 설계 |
| 3~4개월 | 매칭 알고리즘 설계 및 Flask 웹 프로토타입 | 매칭 점수 계산 모듈, 초기 UI |
| 5~6개월 | AWS 배포, 사용자 인터페이스 개선 | EC2 배포 서비스, DB 연동, 시각화 대시보드 |

---

## 📋 기대 효과
- **혁신성:** 설문 없는 AI 기반 성격 추론 → 거짓 응답 불가  
- **실용성:** SNS, 동아리/학교 커뮤니티 내 친구 추천에 응용 가능  
- **학습효과:** Flask, OpenAI API, AWS, MySQL 등 실무 스택 통합 학습  

---
