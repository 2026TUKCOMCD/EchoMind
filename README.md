# EchoMind
# KakaoPersona  
카카오톡 대화 내보내기(txt)를 기반으로 **자신의 대화 성향을 분석하고 빅파이브 성격 지표를 탐색적으로 추정**하는 프로젝트입니다.  
무료 AI API (Hugging Face Inference API + Google Perspective API)를 활용합니다.

---

## 기능
- 카카오톡 대화 내보내기(txt) 파싱
- 본인 이름 입력 → 자신의 발화만 자동 추출
- 무료 AI API로 감성 분석(긍/부정/중립), 독성 점수 계산
- 어휘 다양성/자기지시어/확신·불확실 표현 등 스타일 지표 계산
- 빅파이브(Big Five: OCEAN) 성격 특성 탐색적 추정
- 결과를 **Markdown, JSON, CSV** 리포트로 저장

---

## 파일 구조

```
KakaoPersona/
├─ .gitignore
├─ .env.example
├─ requirements.txt
├─ README.md
├─ main.py
│
├─ src/
│  ├─ __init__.py
│  ├─ kakao_parser.py
│  ├─ api_clients.py
│  ├─ analyzer.py
│  └─ report.py
│
├─ data/
│  └─ sample_chat.txt
│
└─ out_report/
   ├─ summary.md
   ├─ report.json
   └─ utterances.csv
```

---

## 환경 변수 설정


1. `.env` 안에 실제 API 키를 입력합니다. (키는 팀별 개인 계정에서 발급)
   ```
   HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxxxxx
   PERSPECTIVE_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXX
   ```

>  `.env` 파일은 `.gitignore`에 등록되어 있어 깃허브에 업로드되지 않습니다.  

---

##  실행 방법
# 기본 실행 (샘플 데이터)
python main.py -f data/sample_chat.txt -o out_report

# 실제 내보낸 카톡 파일 분석
python main.py -f "C:/Users/내이름/Desktop/KakaoTalk_Chat.txt" -o out_results

---

##  결과물
- `out_report/summary.md` : 사람이 읽기 쉬운 요약 리포트  
- `out_report/report.json` : 세부 분석 JSON  
- `out_report/utterances.csv` : 문장 단위 감성/독성 결과

---

##  주의사항
- 본 프로젝트는 **탐색적 성향 분석 도구**입니다.  
- 결과는 임상적 성격 검사나 심리 진단을 대체하지 않습니다.  
- 대화 데이터는 **본인 동의 하에** 사용해야 하며, 개인정보 보호를 위해 `.env`, 실제 카톡 로그 파일은 절대 깃허브에 업로드하지 마세요.

---
