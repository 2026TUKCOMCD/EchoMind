# KakaoPersona  
카카오톡 대화 내보내기(txt)를 기반으로 **자신의 대화 성향을 분석하고 빅파이브 성격 지표를 탐색적으로 추정**하는 프로젝트입니다.  
무료 AI API (Hugging Face Inference API + Google Perspective API)를 활용합니다.

---

## 🚀 기능

### 1. 데이터 파이프라인 및 전처리
* **정교한 카카오톡 파싱:** 정규표현식(Regex)을 활용하여 대화 내역(`txt`)을 구조화된 데이터로 변환
* **타겟 화자 자동 추출:** 분석 대상자의 발화만 자동으로 필터링하여 노이즈 제거

### 2. 하이브리드 NLP 분석 시스템
* **Kiwi 형태소 분석:** 한국어 특성에 최적화된 `Kiwi` 라이브러리를 사용하여 문장 구조, 어휘 다양성(TTR), 종결 어미 등을 정밀 분석
* **AI 감성 & 독성 분석:** * `Hugging Face` 트랜스포머 모델을 활용한 고성능 감정(긍정/부정) 분류
  * 욕설 및 비속어 필터링 알고리즘을 통한 독성(Toxicity) 수치화
* **속도 최적화:** 대용량 대화 데이터 처리를 위한 **통계적 표본 추출(Statistical Sampling)** 기법 적용

### 3. 심리 프로파일링 알고리즘
* **Big 5 (OCEAN) 추론:** 텍스트 마이닝 결과(언어 습관, 감정 패턴)를 기반으로 Big 5 성격 요인 산출
* **MBTI 매핑:** Big 5 점수를 가중치 알고리즘을 통해 MBTI 유형으로 변환 및 논리적 근거 제시

### 4. 웹 대시보드 및 시각화
* **Flask & MySQL 연동:** 회원가입/로그인부터 분석 결과 저장까지 풀스택(Full-Stack) 구조 구현
* **인터랙티브 리포트:** 분석 결과를 직관적인 웹 대시보드(`result.html`)로 시각화하여 제공

---

## 📂 파일 구조

```
KakaoPersona/
│
├── templates/               # 웹 페이지 화면 (HTML)
│   ├── login.html           # 로그인 페이지
│   ├── register.html        # 회원가입 페이지
│   ├── upload.html          # 파일 업로드 화면
│   └── result.html          # 분석 결과 대시보드
│
├── app.py                   # ★ 메인 실행 파일 (Flask 서버 + AI 분석 로직)
├── main.py                  # (구버전) 초기 CLI 테스트용 코드
├── requirements.txt         # 프로젝트 의존성 라이브러리 목록
├── .gitignore               # 깃 업로드 제외 설정
└── README.md                # 프로젝트 설명서
│
└─ out_report/
   ├─ summary.md
   ├─ report.json
   └─ utterances.csv
```

## 🔑 환경 변수 설정


1. `.env` 안에 실제 API 키를 입력합니다. (키는 팀별 개인 계정에서 발급)
   ```
   HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxxxxx
   PERSPECTIVE_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXX
   ```

> ⚠️ `.env` 파일은 `.gitignore`에 등록되어 있어 깃허브에 업로드되지 않습니다.  

---


## 📊 결과물
- `out_report/summary.md` : 사람이 읽기 쉬운 요약 리포트  
- `out_report/report.json` : 세부 분석 JSON  
- `out_report/utterances.csv` : 문장 단위 감성/독성 결과

---

## ⚠️ 주의사항
- 본 프로젝트는 **탐색적 성향 분석 도구**입니다.  
- 결과는 임상적 성격 검사나 심리 진단을 대체하지 않습니다.  
- 대화 데이터는 **본인 동의 하에** 사용해야 하며, 개인정보 보호를 위해 `.env`, 실제 카톡 로그 파일은 절대 깃허브에 업로드하지 마세요.

---

