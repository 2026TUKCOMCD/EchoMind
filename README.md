# EchoMind - 카카오톡 대화 분석 및 MBTI/Big5 예측 시스템

**EchoMind**는 카카오톡 대화 내역을 분석하여 상대방의 **MBTI 성격 유형**과 **Big5 성격 특성**을 예측하는 Python 웹 애플리케이션입니다.  
단순한 키워드 매칭을 넘어, 답장 속도, 대화 주도성, 독성(욕설), 감성(긍정/부정) 등 다양한 상호작용 패턴을 종합적으로 분석합니다.

---

## 🚀 주요 기능

### 1. MBTI 성격 유형 예측
대화 패턴과 언어 습관을 분석하여 4가지 지표를 산출합니다.
- **E (외향) vs I (내향)**: 답장 속도(칼답 vs 신중), 대화 주도(선톡) 횟수, 턴 길이 분석.
    - *한국인의 일반적 특성을 고려하여 E 판별 기준을 엄격하게 적용 (I 가중치 1.2배)*
- **S (감각) vs N (직관)**: 구체적 숫자/단위 사용(S) vs 추상적/가정법 표현(N) 빈도 분석.
- **T (사고) vs F (감정)**: 논리/인과관계 어휘(T) vs 공감/리액션 어휘(F) 빈도 분석.
- **J (판단) vs P (인식)**: 계획/일정 언급(J) vs 유연/즉흥적 표현(P) 빈도 분석.

### 2. Big5 (5대 성격 특성) 정밀 분석
MBTI 결과에 **감성 분석(Sentiment)**과 **독성 분석(Toxicity)** 결과를 결합하여 정밀하게 계산합니다.
- **개방성 (Openness)**: N 성향 + 풍부한 감성 표현
- **성실성 (Conscientiousness)**: J 성향 + 낮은 독성(충동성 억제)
- **외향성 (Extraversion)**: E 성향 + 높은 긍정 에너지
- **친화성 (Agreeableness)**: F 성향 + **높은 긍정 점수** - **높은 독성 점수(욕설 등)**
- **신경성 (Neuroticism)**: 부정적 표현 및 독성 표현 빈도에 비례

### 3. 사용자 맞춤형 튜닝 (Custom Config)
코드 수정 없이 변수 값만 변경하여 분석 민감도를 조절할 수 있습니다 (`app.py` 상단).
```python
# [사용자 설정 예시]
WEIGHT_E = 1.0   # 외향형 가중치
WEIGHT_I = 1.2   # 내향형 가중치 (기본 보정)
WEIGHT_N = 1.2   # 직관형 가중치 (보정)
```

---

## 🛠 기술 스택
- **Language**: Python 3.10+
- **Web Framework**: Flask
- **Database**: MySQL (PyMySQL)
- **NLP Engine**: 
    - **Kiwi (kiwipiepy)**: 고속 한국어 형태소 분석
    - **KNU 감성 사전**: 감성 점수 산출
- **Frontend**: HTML5, CSS3 (Jinja2 Templates)

---

## 📦 설치 및 실행 방법

### 1. 환경 설정
```bash
# 필수 라이브러리 설치
pip install -r requirements.txt
```

### 2. DB 설정
`app.py` 파일 내 `db_config` 항목을 본인의 MySQL 설정에 맞게 수정하세요.
```python
db_config = {
    'host': 'localhost',
    'user': 'root', 
    'password': 'YOUR_PASSWORD',
    'db': 'echomind_db',
    ...
}
```

### 3. 애플리케이션 실행
```bash
python app.py
```
브라우저에서 `http://localhost:5000` 접속

---

## 📂 프로젝트 구조
- `app.py`: 메인 애플리케이션 (Flask 서버, 분석 로직 포함)
- `test_mbti_logic.py`: 분석 로직 검증을 위한 테스트 스크립트
- `SentiWord_info.json`: KNU 한국어 감성 사전 데이터
- `templates/`: HTML 템플릿 파일
- `uploads/`: 업로드된 카카오톡 대화 파일 저장소

---

## 📝 라이선스
This project is for educational purposes.
