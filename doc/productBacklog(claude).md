# AI 기반 성격 분석을 활용한 소셜 매칭 시스템 - 프로덕트 백로그

## 프로젝트 정보
- **팀 구성**: 3명
- **개발 기간**: 6개월
- **핵심 기술**: OpenAI API (GPT-4o mini), Flask, MySQL, AWS
- **개발 방식**: 단계별 점진적 개발 (Phase 1 → Phase 2 → Phase 3)

---

## Phase 1: 성격 분석 시스템 구축 (1~2개월)

### Epic 1: 데이터 수집 및 전처리
**우선순위: 최상**

#### User Story 1.1: 카카오톡 대화 파일 업로드
- **As a** 사용자
- **I want to** 카카오톡 대화 파일(.txt)을 웹사이트에 업로드
- **So that** 내 대화 내용이 분석될 수 있도록 함
- **Story Points**: 5
- **담당**: 백엔드 개발자
- **상세 작업**:
  - [ ] 파일 업로드 API 엔드포인트 개발 (POST /api/upload)
  - [ ] 파일 크기 제한 설정 (예: 10MB)
  - [ ] 파일 형식 검증 (.txt만 허용)
  - [ ] AWS S3 또는 로컬 임시 저장 디렉토리 설정
  - [ ] 업로드 완료 후 고유 파일 ID 반환

#### User Story 1.2: 대화 데이터 파싱 및 사용자 발화 추출
- **As a** 시스템
- **I want to** 업로드된 카카오톡 파일에서 발화자별 대화를 추출
- **So that** 사용자가 선택한 발화자의 메시지만 분석할 수 있도록 함
- **Story Points**: 8
- **담당**: 백엔드 개발자
- **상세 작업**:
  - [ ] 카카오톡 내보내기 형식 분석
    - 예: `2024. 1. 1. 오후 3:45, 홍길동 : 안녕하세요`
  - [ ] 정규표현식으로 날짜, 시간, 발화자, 메시지 파싱
  - [ ] 발화자 이름 목록 추출 및 중복 제거
  - [ ] 프론트엔드로 발화자 목록 전달
  - [ ] 사용자가 선택한 발화자의 메시지만 필터링

#### User Story 1.3: 노이즈 제거 및 데이터 정제
- **As a** 시스템
- **I want to** 불필요한 내용을 제거하고 분석 가능한 텍스트만 추출
- **So that** 정확한 성격 분석이 가능하도록 함
- **Story Points**: 8
- **담당**: 백엔드 개발자
- **상세 작업**:
  - [ ] 시스템 메시지 제거
    - "사진을 보냈습니다", "동영상을 보냈습니다" 등
  - [ ] 이모티콘 제거 (카카오톡 이모티콘 텍스트)
  - [ ] URL 제거 (http://, https://)
  - [ ] 반복 웃음/울음 제거
    - ㅋㅋㅋ, ㅎㅎㅎ, ㅠㅠㅠ → 각각 ㅋ, ㅎ, ㅠ 한 번만 남기거나 제거
  - [ ] 빈 메시지 제거 (공백만 있는 경우)
  - [ ] 결과를 리스트 형태로 반환

#### User Story 1.4: 개인정보 마스킹 처리
- **As a** 시스템
- **I want to** 대화에서 개인정보를 자동으로 탐지하고 마스킹
- **So that** LLM에 민감한 정보가 전달되지 않도록 함
- **Story Points**: 8
- **담당**: 백엔드 개발자
- **상세 작업**:
  - [ ] 전화번호 탐지 및 마스킹
    - 정규식: `010-XXXX-XXXX`, `010XXXXXXXX` → `[전화번호]`
  - [ ] 이메일 탐지 및 마스킹
    - 정규식: `example@domain.com` → `[이메일]`
  - [ ] 주민번호 탐지 및 마스킹
    - 정규식: `XXXXXX-XXXXXXX` → `[주민번호]`
  - [ ] 신용카드 번호, 계좌번호 등 추가 고려
  - [ ] 마스킹 로그 기록 (통계용)

#### User Story 1.5: 샘플링 및 대표 발화 추출
- **As a** 시스템
- **I want to** 너무 긴 대화는 샘플링하여 대표 발화만 추출
- **So that** API 호출 비용을 줄이고 효율적으로 분석할 수 있도록 함
- **Story Points**: 5
- **담당**: 백엔드 개발자
- **상세 작업**:
  - [ ] 전체 메시지 개수 확인
  - [ ] 1000개 이상인 경우 샘플링 전략 적용
    - 최근 메시지 우선 (최근 500개 + 과거 무작위 500개)
    - 또는 시간 간격 기반 균등 샘플링
  - [ ] 샘플링된 메시지를 하나의 텍스트로 결합
  - [ ] 토큰 수 계산 (대략 한글 2자 = 1토큰)
  - [ ] 최대 토큰 제한 (예: 4000 토큰) 내로 조정

---

### Epic 2: LLM 기반 성격 분석 엔진 개발
**우선순위: 최상**

#### User Story 2.1: OpenAI API 연동 및 프롬프트 설계
- **As a** 시스템
- **I want to** OpenAI GPT-4o mini API를 호출하여 대화 분석 요청
- **So that** 사용자의 대화 성향을 자동으로 분석할 수 있도록 함
- **Story Points**: 13
- **담당**: AI/데이터 개발자
- **상세 작업**:
  - [ ] OpenAI API 키 발급 및 환경변수 설정
  - [ ] Python `openai` 라이브러리 설치
  - [ ] 시스템 프롬프트 작성
    ```
    당신은 대화 텍스트를 분석하여 사용자의 커뮤니케이션 스타일을 파악하는 전문가입니다.
    다음 제약을 반드시 지켜주세요:
    - 심리 검사나 의학적 진단처럼 단정하지 마세요
    - 텍스트에서 관찰되는 경향만 기술하세요
    - 개인정보를 출력하지 마세요
    - 원문을 길게 인용하지 말고 의역/요약만 하세요
    ```
  - [ ] 사용자 프롬프트 작성
    ```
    다음은 한 사용자의 대화 내용입니다. 이 사람의 커뮤니케이션 스타일을 분석해주세요.
    
    [대화 내용]
    {샘플링된 대화 텍스트}
    ```
  - [ ] API 호출 함수 구현
  - [ ] 타임아웃 및 재시도 로직 구현

#### User Story 2.2: JSON Schema 기반 구조화된 출력 구현
- **As a** 시스템
- **I want to** LLM이 정해진 형식의 JSON을 반환하도록 강제
- **So that** 일관된 형태로 결과를 저장하고 처리할 수 있도록 함
- **Story Points**: 13
- **담당**: AI/데이터 개발자
- **상세 작업**:
  - [ ] JSON Schema 정의
    ```json
    {
      "communication_style": {
        "tone": "친근|공손|중립|건조|공격 중 하나",
        "directness": "직설|완곡|상황따라 중 하나",
        "emotion_expression": "낮음|보통|높음 중 하나",
        "empathy_signals": "낮음|보통|높음 중 하나",
        "initiative": "주도|반응|혼합 중 하나",
        "conflict_style": "회피|완화|직면|혼합 중 하나"
      },
      "notable_patterns": ["말버릇이나 패턴 설명"],
      "strengths": ["강점 요약"],
      "cautions": ["주의할 점 요약"],
      "matching_tips": {
        "compatible": "잘 맞는 유형",
        "incompatible": "충돌하기 쉬운 유형"
      },
      "confidence": 0.85
    }
    ```
  - [ ] OpenAI Function Calling 활용
    - `response_format={"type": "json_object"}` 설정
    - 또는 `functions` 파라미터로 스키마 전달
  - [ ] JSON 파싱 및 검증 로직
  - [ ] 스키마 불일치 시 에러 처리

#### User Story 2.3: 성격 분석 결과 저장
- **As a** 시스템
- **I want to** LLM이 반환한 JSON 결과를 데이터베이스에 저장
- **So that** 나중에 매칭에 활용하고 사용자가 다시 볼 수 있도록 함
- **Story Points**: 5
- **담당**: 백엔드 개발자
- **상세 작업**:
  - [ ] Profiles 테이블에 JSON 컬럼 추가
    - `analysis_result` (JSON 또는 TEXT 타입)
  - [ ] 분석 완료 시 데이터 저장 API (POST /api/profile)
  - [ ] 사용자별 프로필 조회 API (GET /api/profile/:user_id)
  - [ ] 분석 날짜 기록 (created_at, updated_at)

#### User Story 2.4: 성격 분석 신뢰도 표시
- **As a** 사용자
- **I want to** 분석 결과의 신뢰도(confidence)를 확인
- **So that** 데이터가 부족하거나 애매한 경우를 알 수 있도록 함
- **Story Points**: 3
- **담당**: AI/데이터 개발자
- **상세 작업**:
  - [ ] LLM에게 신뢰도 점수(0~1) 반환 요청
  - [ ] 신뢰도가 0.5 미만이면 경고 메시지 표시
  - [ ] 신뢰도 낮은 이유 안내 (예: "대화량 부족", "패턴 불명확")

---

### Epic 3: 기본 웹 인터페이스 구축
**우선순위: 높음**

#### User Story 3.1: 메인 페이지 및 서비스 소개
- **As a** 사용자
- **I want to** 서비스가 무엇인지 이해하고 시작할 수 있는 랜딩 페이지
- **So that** 첫 방문 시 서비스 개요를 파악할 수 있도록 함
- **Story Points**: 3
- **담당**: 프론트엔드 개발자
- **상세 작업**:
  - [ ] HTML/CSS로 랜딩 페이지 디자인
  - [ ] 서비스 소개 문구 작성
    - "대화로 알아보는 나의 성격"
    - "AI가 당신과 잘 맞는 친구를 찾아드립니다"
  - [ ] "시작하기" 버튼 → 회원가입/로그인 페이지 연결
  - [ ] 반응형 디자인 (모바일 대응)

#### User Story 3.2: 회원가입 및 로그인 페이지
- **As a** 사용자
- **I want to** 간단하게 계정을 만들고 로그인
- **So that** 내 분석 결과를 저장하고 다시 볼 수 있도록 함
- **Story Points**: 8
- **담당**: 백엔드 + 프론트엔드 개발자
- **상세 작업**:
  - [ ] 회원가입 폼 (아이디, 비밀번호, 이메일)
  - [ ] 로그인 폼 (아이디, 비밀번호)
  - [ ] 회원가입 API (POST /api/register)
  - [ ] 로그인 API (POST /api/login)
  - [ ] 비밀번호 해싱 (bcrypt 사용)
  - [ ] 세션 관리 (Flask-Session 또는 JWT)
  - [ ] 유효성 검증 (아이디 중복 체크 등)

#### User Story 3.3: 파일 업로드 페이지
- **As a** 사용자
- **I want to** 카카오톡 대화 파일을 쉽게 업로드
- **So that** 번거로움 없이 분석을 시작할 수 있도록 함
- **Story Points**: 5
- **담당**: 프론트엔드 개발자
- **상세 작업**:
  - [ ] 파일 선택 버튼 또는 드래그 앤 드롭 UI
  - [ ] 업로드 진행 상태 표시 (progress bar)
  - [ ] 카카오톡 내보내기 방법 안내
    - "대화방 → 설정 → 대화 내보내기"
  - [ ] 파일 업로드 후 발화자 선택 UI
  - [ ] "분석 시작" 버튼

#### User Story 3.4: 분석 진행 상태 표시
- **As a** 사용자
- **I want to** 분석이 진행 중임을 확인
- **So that** 기다리는 동안 불안하지 않도록 함
- **Story Points**: 3
- **담당**: 프론트엔드 개발자
- **상세 작업**:
  - [ ] 로딩 애니메이션 (스피너)
  - [ ] 분석 단계별 메시지 표시
    - "대화 파일을 분석하고 있어요..."
    - "성격 패턴을 찾고 있어요..."
  - [ ] 예상 소요 시간 안내 (약 30초~1분)

#### User Story 3.5: 성격 분석 결과 페이지
- **As a** 사용자
- **I want to** 내 대화 스타일 분석 결과를 시각적으로 확인
- **So that** 나의 커뮤니케이션 특성을 한눈에 이해할 수 있도록 함
- **Story Points**: 13
- **담당**: 프론트엔드 개발자
- **상세 작업**:
  - [ ] 결과 페이지 레이아웃 설계
  - [ ] communication_style 시각화
    - tone, directness 등을 레이더 차트 또는 막대 그래프로 표시
    - Chart.js 또는 D3.js 사용
  - [ ] notable_patterns 표시 (말버릇/패턴)
  - [ ] strengths, cautions 표시
  - [ ] matching_tips 표시 (잘 맞는/안 맞는 유형)
  - [ ] 신뢰도(confidence) 게이지 표시
  - [ ] "친구 찾기" 버튼 → 매칭 페이지 연결

---

### Epic 4: 데이터베이스 설계 및 구축
**우선순위: 높음**

#### User Story 4.1: 데이터베이스 스키마 설계
- **As a** 개발자
- **I want to** 사용자, 프로필, 매칭 기록을 저장할 데이터베이스 구조
- **So that** 데이터를 체계적으로 관리할 수 있도록 함
- **Story Points**: 5
- **담당**: 백엔드 개발자
- **상세 작업**:
  - [ ] ERD(Entity-Relationship Diagram) 작성
  - [ ] Users 테이블
    - `id` (PK), `username`, `password_hash`, `email`, `created_at`
  - [ ] Profiles 테이블
    - `id` (PK), `user_id` (FK), `analysis_result` (JSON), `confidence`, `created_at`, `updated_at`
  - [ ] Matches 테이블 (Phase 2에서 사용)
    - `id` (PK), `user_id` (FK), `matched_user_id` (FK), `score`, `created_at`
  - [ ] Interests 테이블 (Phase 2에서 사용)
    - `id` (PK), `from_user_id` (FK), `to_user_id` (FK), `created_at`

#### User Story 4.2: MySQL 데이터베이스 구축
- **As a** 개발자
- **I want to** 로컬 또는 클라우드에 MySQL 데이터베이스 생성
- **So that** 실제 데이터를 저장하고 조회할 수 있도록 함
- **Story Points**: 5
- **담당**: 백엔드 개발자
- **상세 작업**:
  - [ ] 로컬 MySQL 설치 (개발용)
  - [ ] 데이터베이스 생성 (`CREATE DATABASE personality_match;`)
  - [ ] 테이블 생성 SQL 스크립트 작성
  - [ ] Flask-SQLAlchemy 또는 PyMySQL 연동
  - [ ] 연결 테스트

#### User Story 4.3: ORM 또는 쿼리 함수 작성
- **As a** 개발자
- **I want to** Python 코드에서 데이터베이스를 쉽게 조작
- **So that** SQL을 직접 작성하지 않고도 CRUD 작업을 수행할 수 있도록 함
- **Story Points**: 8
- **담당**: 백엔드 개발자
- **상세 작업**:
  - [ ] SQLAlchemy 모델 정의 (User, Profile, Match, Interest)
  - [ ] 회원가입 함수 (create_user)
  - [ ] 로그인 검증 함수 (authenticate_user)
  - [ ] 프로필 저장 함수 (save_profile)
  - [ ] 프로필 조회 함수 (get_profile_by_user_id)

---

## Phase 2: 매칭 시스템 구현 (3~4개월)

### Epic 5: 대화 성향 정규화 및 벡터화
**우선순위: 최상**

#### User Story 5.1: communication_style을 수치형 벡터로 변환
- **As a** 시스템
- **I want to** 텍스트 기반 분석 결과를 0~1 사이의 숫자로 변환
- **So that** 수학적으로 유사도를 계산할 수 있도록 함
- **Story Points**: 8
- **담당**: AI/데이터 개발자
- **상세 작업**:
  - [ ] tone 인코딩
    - 친근: 1.0, 공손: 0.75, 중립: 0.5, 건조: 0.25, 공격: 0.0
  - [ ] directness 인코딩
    - 직설: 1.0, 상황따라: 0.5, 완곡: 0.0
  - [ ] emotion_expression 인코딩
    - 높음: 1.0, 보통: 0.5, 낮음: 0.0
  - [ ] empathy_signals 인코딩 (동일)
  - [ ] initiative 인코딩
    - 주도: 1.0, 혼합: 0.5, 반응: 0.0
  - [ ] conflict_style 인코딩
    - 직면: 1.0, 혼합: 0.67, 완화: 0.33, 회피: 0.0
  - [ ] 각 사용자를 6차원 벡터로 표현

#### User Story 5.2: 벡터를 데이터베이스에 저장
- **As a** 시스템
- **I want to** 정규화된 벡터를 Profiles 테이블에 추가
- **So that** 매칭 계산 시 빠르게 조회할 수 있도록 함
- **Story Points**: 3
- **담당**: 백엔드 개발자
- **상세 작업**:
  - [ ] Profiles 테이블에 벡터 컬럼 추가
    - `tone_score`, `directness_score`, `emotion_score`, `empathy_score`, `initiative_score`, `conflict_score`
  - [ ] 분석 결과 저장 시 자동으로 벡터 계산 및 저장

---

### Epic 6: 매칭 알고리즘 개발
**우선순위: 최상**

#### User Story 6.1: 유사도 기반 매칭 점수 계산
- **As a** 시스템
- **I want to** 유사도가 중요한 축(tone, emotion_expression)에서 비슷한 사람에게 높은 점수 부여
- **So that** 말투나 감정 표현이 비슷해서 편안한 사람끼리 매칭되도록 함
- **Story Points**: 8
- **담당**: AI/데이터 개발자
- **상세 작업**:
  - [ ] 코사인 유사도 계산 함수
    ```python
    def cosine_similarity(vec1, vec2):
        dot_product = sum(a*b for a, b in zip(vec1, vec2))
        magnitude1 = sqrt(sum(a**2 for a in vec1))
        magnitude2 = sqrt(sum(b**2 for b in vec2))
        return dot_product / (magnitude1 * magnitude2)
    ```
  - [ ] tone, emotion_expression 축만 추출하여 유사도 계산
  - [ ] 유사도를 0~100점으로 스케일링

#### User Story 6.2: 보완성 기반 매칭 점수 계산
- **As a** 시스템
- **I want to** 보완이 가능한 축(initiative, directness)에서 적절히 다른 사람에게 높은 점수 부여
- **So that** 주도형-반응형, 직설-완곡 조합이 잘 맞도록 함
- **Story Points**: 8
- **담당**: AI/데이터 개발자
- **상세 작업**:
  - [ ] initiative 보완 점수
    - 한쪽이 주도(1.0), 한쪽이 반응(0.0)이면 높은 점수
    - `complementarity_score = 1 - abs(initiative1 - initiative2)`
  - [ ] directness 보완 점수 (동일 방식)
  - [ ] empathy_signals는 둘 다 높으면 좋음 (최소값 기준)
  - [ ] conflict_style은 한쪽이 낮을수록 좋음 (회피형이 있으면 좋음)

#### User Story 6.3: 종합 매칭 점수 계산
- **As a** 시스템
- **I want to** 유사도 점수와 보완성 점수를 가중 합산하여 최종 점수 산출
- **So that** 균형 잡힌 매칭 결과를 제공할 수 있도록 함
- **Story Points**: 5
- **담당**: AI/데이터 개발자
- **상세 작업**:
  - [ ] 가중치 설정
    - 유사도 점수: 40%
    - 보완성 점수: 40%
    - empathy/conflict 보너스: 20%
  - [ ] 최종 점수 = (similarity * 0.4) + (complementarity * 0.4) + (bonus * 0.2)
  - [ ] 0~100점으로 정규화
  - [ ] 가중치는 추후 조정 가능하도록 설정 파일로 분리

#### User Story 6.4: 전체 사용자 대상 매칭 실행
- **As a** 시스템
- **I want to** 현재 사용자와 모든 다른 사용자를 비교하여 점수 계산
- **So that** 가장 잘 맞는 사람을 찾을 수 있도록 함
- **Story Points**: 8
- **담당**: 백엔드 개발자
- **상세 작업**:
  - [ ] 데이터베이스에서 모든 사용자 프로필 조회
  - [ ] 본인 제외 필터링
  - [ ] 각 사용자와 매칭 점수 계산
  - [ ] 점수 순으로 정렬
  - [ ] 상위 10명 추출
  - [ ] Matches 테이블에 기록 저장 (선택사항)

---

### Epic 7: 추천 친구 목록 UI
**우선순위: 높음**

#### User Story 7.1: 추천 친구 목록 API
- **As a** 프론트엔드
- **I want to** 사용자의 추천 친구 목록을 요청
- **So that** 화면에 표시할 수 있도록 함
- **Story Points**: 5
- **담당**: 백엔드 개발자
- **상세 작업**:
  - [ ] 추천 API 엔드포인트 (GET /api/recommendations/:user_id)
  - [ ] 반환 형식 설계
    ```json
    {
      "recommendations": [
        {
          "user_id": 123,
          "username": "철수",
          "score": 87.5,
          "match_reason": "말투와 감정 표현이 비슷하고, 주도-반응 조합이 잘 맞아요"
        }
      ]
    }
    ```
  - [ ] 페이지네이션 (10명씩)

#### User Story 7.2: 추천 친구 카드 UI
- **As a** 사용자
- **I want to** 추