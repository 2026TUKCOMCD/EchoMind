# Recommendation System Logic: "Find My Best Match"

이 문서는 **'나의 프로필(My JSON)'**을 기준으로, 여러 사람의 프로필 파일들(Others JSONs) 중에서 **가장 잘 맞는 상대를 추천**해주는 로직을 설계합니다.

## 1. System Overview (시스템 개요)
*   **Input**:
    1.  `Target User` (나): `my_profile.json`
    2.  `Candidates` (상대방들): `profiles/*.json` (여러 파일)
*   **Process**: 1:N 매칭 점수 계산 및 정렬
*   **Output**: 매칭 점수가 가장 높은 상위 N명과 추천 사유

---

## 2. Logic Workflow (처리 흐름)

### Step 1: Loading
1.  내 프로필(`main_user`)을 메모리에 로드합니다.
2.  `candidates_dir` 폴더에 있는 모든 JSON 파일을 순회하며 로드합니다. (본인 제외)

### Step 2: Scoring Loop (점수 산출 루프)
모든 후보자(`candidate`)에 대해 반복:

1.  **필터링 (Filtering) - *Optional***
    *   (예) 특정 언어(`language`)가 다른 경우 제외
    *   (예) 신뢰도(`confidence`)가 너무 낮은 파일 제외

2.  **점수 계산 (Scoring)**
    *   `Total Score` = `Style Compatibility` + `Topic Similarity` + `LLM Bonus`
    *   각 항목은 0~100점 척도로 환산 후 가중치 적용

### Step 3: Ranking
*   계산된 `Total Score`를 기준으로 내림차순 정렬(Sorting).

---

## 3. Detailed Scoring Formula (상세 점수 산출)

**가중치 예시**: `Style(50%)` + `Topic(30%)` + `Bonus(20%)`

### A. Style Compatibility (50점)
"대화 스타일이 비슷할수록 점수가 높다"

*   **Logic**:
    1.  `Profile A`와 `Profile B`의 `communication_style` 값을 비교.
    2.  각 항목(Tone, Directness, Emotion 등)이 일치하면 만점, 다르면 감점.
    3.  **예외 규칙(Complementary Rule)**:
        *   `Initiative`(주도성)의 경우, 둘 다 '주도형'이면 오히려 약간 감점(-5), '주도형'+'반응형'이면 가산점(+5). (서로 대화가 안 끊기고 잘 됨)
    4.  **계산식**:
        ```python
        score = 0
        score += (My.Tone == Your.Tone) ? 10 : 0
        score += (My.Directness == Your.Directness) ? 10 : 0
        # ... 항목별 합산 후 50점 만점으로 스케일링
        ```

### B. Topic Similarity (30점)
"관심사가 겹칠수록 점수가 높다"

*   **Logic**:
    1.  각 프로필의 `notable_patterns`, `strengths` 텍스트에서 **명사 키워드** 추출 (or 향후 추가될 `topics` 필드 사용).
    2.  (나의 키워드 집합) ∩ (상대의 키워드 집합) 교집합 개수 확인.
    3.  **계산식**:
        ```python
        overlap_count = len(my_keywords.intersection(your_keywords))
        score = min(30, overlap_count * 5) # 키워드 1개 겹칠 때마다 5점, 최대 30점
        ```

### C. LLM Match Bonus / Risk Penalty (20점)
"AI가 분석한 추천/주의 사항 반영"

*   **Logic**:
    1.  **Bonus (+)**: 나의 `works_well_with` 키워드가 상대방 프로필에 등장하면 보너스.
    2.  **Penalty (-)**: 나의 `may_clash_with` 키워드가 상대방 프로필에 등장하면 패널티.
    3.  **계산식**:
        ```python
        score = 10 (기본점수)
        if match_found: score += 10
        if clash_found: score -= 10
        ```

---

## 4. Final Output Example (결과 예시)

사용자에게는 가장 점수가 높은 사람을 다음과 같이 추천합니다.

> **[추천 1위] 김철수 님 (매칭 점수: 88점)**
>
> *   **대화 스타일 (45/50)**: 두 분 다 **'친근한'** 어조와 **'솔직한'** 화법을 사용하여 대화가 물 흐르듯 통할 것입니다.
> *   **관심사 (20/30)**: **'주식'**, **'여행'** 이라는 공통 관심사가 발견되었습니다.
> *   **AI 분석**: 김철수 님은 님의 이상형인 **'긍정적인 에너지를 가진 사람'**에 해당합니다.
>
> ---
> **[추천 2위] 이영희 님 (매칭 점수: 72점)**
> *   ...

## 5. Implementation Roadmap (구현 계획 - 코딩 X)
1.  이 로직을 수행할 새로운 파이썬 스크립트(`recommend.py`)가 필요합니다.
2.  이 스크립트는 `main.py`와 달리 **OpenAI API를 쓰지 않고**, 이미 만들어진 **JSON 파일들만 비교**하므로 속도가 매우 빠르고 무료입니다.
