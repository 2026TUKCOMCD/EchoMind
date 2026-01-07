# EchoMind (CLI Version)

카카오톡 대화 내역(`txt`)을 OpenAI GPT로 분석하여 **사용자의 대화 성향 프로필(`json`)을 생성**하고, 여러 사용자 간의 **매칭(궁합)을 분석**해주는 프로젝트입니다.

---

## 🚀 주요 기능

### 1. 성향 분석 (`main.py`)
*   **GPT 기반 심층 분석**: 대화 내용을 LLM(GPT)에게 전달하여 정성적/정량적 성향 분석.
*   **구조화된 출력**: 분석 결과를 체계적인 JSON 포맷으로 생성 (`communication_style`, `topics` 등).
*   **키워드 추출**: 대화에서 자주 등장하는 '관심사(Topics)' 자동 추출.

### 2. 매칭 추천 (`recommend.py`)
*   **1:N 매칭 시스템**: 내 프로필과 N명의 후보자 프로필을 비교 분석.
*   **3단계 점수 산출**:
    1.  **스타일 유사도(50점)**: 대화 톤, 화법, 공감도 비교 (상호보완적 성향 고려).
    2.  **관심사 일치도(30점)**: `topics` 키워드 교집합 분석.
    3.  **AI 매칭 힌트(20점)**: GPT가 분석한 '잘 맞는 성향' 반영.

---

## 🛠️ 설치 및 설정

### 1. 필수 라이브러리 설치
```bash
pip install openai python-dotenv
```

### 2. 환경 변수 설정 (.env)
프로젝트 루트에 `.env` 파일을 만들고 OpenAI API 키를 입력하세요.
```ini
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_MODEL=gpt-5-mini  # 또는 gpt-3.5-turbo (선택 사항)
```

---

## 📖 사용 방법 (Usage)

### Step 1: 내 프로필 생성 (Analysis)
카카오톡 대화 내보내기 파일(`.txt`)을 분석하여 JSON 프로필을 만듭니다.

```bash
# 기본 사용법
python main.py --file "KakaoTalk_20240101.txt" --name "내이름" --out "my_profile.json"

# 옵션: 분석할 말풍선 개수 지정 (기본 200개)
python main.py --file "KakaoTalk_20240101.txt" --name "내이름" --out "my_profile.json" --limit 300
```
> **팁**: `--name`에는 카톡 대화방에서 쓰인 **본인의 닉네임**을 정확히 입력해야 합니다.

### Step 2: 매칭 파트너 찾기 (Recommendation)
내 프로필(`my_profile.json`)과 후보자들의 프로필 파일들이 있는 폴더를 비교합니다.

```bash
# 기본 사용법
python recommend.py --my "my_profile.json" --dir "./candidates"
```
*   `--my`: 기준이 될 내 프로필 파일 경로
*   `--dir`: 비교할 상대방 파일들이 모여있는 **폴더 경로**

**실행 결과 예시:**
```text
[*] '최완우' 님의 베스트 파트너를 찾는 중... (후보: 3명)
============================================================
   MATCHING RESULTS FOR [최완우]
============================================================
[1위] 박코딩 (점수: 88.5점)
  - 대화 스타일: 45.0 / 50
  - 관심사 일치: 25.0 / 30 ['코딩', '주식']
  - AI 분석매칭: 18.5 / 20
...
```

---

## 📂 파일 구조
*   `main.py`: 대화 분석 및 프로필 생성 도구 (Creator)
*   `recommend.py`: 매칭 및 랭킹 산출 도구 (Matcher)
*   `candidates/`: 매칭 후보자들의 JSON 프로필을 모아두는 폴더
*   `app.py`: (Legacy) 웹 서버 버전 (현재 사용 안 함)

---

## ⚠️ 주의사항
*   `main.py` 실행 시 OpenAI API 비용이 발생할 수 있습니다.
*   대화 데이터에는 개인정보가 포함될 수 있으니 파일 관리에 유의하세요.
