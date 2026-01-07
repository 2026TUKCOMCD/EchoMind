# User Matching Logic Design

이 문서는 `main.py`의 `profile.json` 결과를 활용하여 두 사용자 간의 매칭(궁합) 점수를 산출하기 위한 전략과 아이디어를 정리합니다.

## 1. Goal
단순한 MBTI 매칭을 넘어, 실제 **대화 스타일(Style)**과 **관심사(Topic)**, 그리고 **LLM이 분석한 매칭 팁**을 복합적으로 고려하여 정교한 매칭 점수를 산출합니다.

## 2. Core Columns for Matching (매칭 요소)

### A. 대화 스타일 유사도 (Communication Style Similarity)
> **사용자 의견**: "언어 스타일이 유사할수록 잘 맞는다."

`main.py`의 `communication_style` 항목들을 수치화하여 거리(Distance)나 유사도(Similarity)를 계산합니다.

| 항목 | 값(Enum) | 수치화 전략 (예시) |
| :--- | :--- | :--- |
| **Tone** (어조) | 친근함, 공손함, 중립적, 건조함, 공격적 | 1(친근) ~ 5(공격) 스케일링 후 차이 계산<br>*(친근 vs 공격은 거리가 멀어 점수 낮음)* |
| **Directness** (화법) | 직설적, 완곡적, 상황따라 | 0(완곡) ~ 2(직설) |
| **Emotion** (감정표현) | 낮음, 보통, 높음 | 0, 1, 2 |
| **Initiative** (주도성) | 주도형, 반응형, 혼합형 | **[고려사항]** 유사도 vs 보완성.<br>주도+주도=충돌 가능성? 주도+반응=조화?<br>*일단 사용자 요청대로 '유사도' 우선 적용하되 가중치 조정* |

### B. 관심사 일치도 (Topic Overlap)
> **사용자 의견**: "주제가 비슷하면 잘 맞는다."

현재 `main.py` 스키마에는 명시적인 `topics`(관심 토픽 리스트)가 없습니다. `notable_patterns`에 섞여 있을 뿐입니다.
**[제안]** `profile.json` 스키마에 `topics` 또는 `interests` 필드를 추가하여 명사 키워드(예: '아이돌', '주식', '코딩', '여행')를 추출해야 합니다.

*   **계산법**: Jaccard Similarity (교집합 개수 / 합집합 개수)
*   **심화**: 단순 키워드 매칭이 안 될 경우(예: '주식' vs '재테크'), 임베딩 유사도 사용 고려.

### C. LLM 추천 기반 (Matching Tips Validation)
`profile.json`에는 이미 강력한 힌트가 있습니다.
*   `matching_tips.works_well_with`: "이런 사람과 잘 맞음"
*   `matching_tips.may_clash_with`: "이런 사람과 안 맞음"

**전략**:
1.  User A의 `works_well_with` 키워드가 User B의 `strengths`나 `notable_patterns`에 얼마나 등장하는가?
2.  User A의 `may_clash_with` 키워드가 User B의 `notable_patterns`나 `cautions`에 등장하면 감점 (-).

---

## 3. Proposed Matching Algorithm (매칭 알고리즘)

**Total Score (100점 만점)** =
  (Weight A * **Style Score**) +
  (Weight B * **Topic Score**) +
  (Weight C * **LLM Hint Score**)

### Step 1: Data Preparation
먼저 `main.py`의 `PROFILE_SCHEMA`를 수정하여 `topics` 리스트를 명확히 뽑아내야 합니다.

### Step 2: Scoring Logic
```python
def calculate_match_score(user_a, user_b):
    # 1. Style Score (40%)
    style_diff = calculate_vector_distance(user_a.style_vector, user_b.style_vector)
    style_score = 100 - (style_diff * scaling_factor)

    # 2. Topic Score (30%)
    topic_overlap = len(set(user_a.topics) & set(user_b.topics))
    topic_score = topic_overlap * points_per_topic # (Max 100)

    # 3. LLM Hint Score (30%)
    # A의 이상형에 B가 얼마나 부합하는가?
    hint_match = check_keywords(user_a.works_well_with, user_b.traits)
    hint_clash = check_keywords(user_a.may_clash_with, user_b.traits)
    hint_score = (hint_match * bonus) - (hint_clash * penalty)

    return total_weighted_score
```

## 4. Alternative Ideas (추가 아이디어)

1.  **관계 시뮬레이션 (The "Chatroom" Sim)**
    *   두 사람의 프로필(JSON)을 LLM에게 주고, "두 사람이 소개팅을 한다면 대화가 어떨지 시뮬레이션해줘"라고 요청.
    *   LLM이 생성한 가상 대화의 분위기(긍정/부정)를 분석하여 최종 점수 산출.
    *   *장점*: 매우 정성적이고 재미있는 결과.
    *   *단점*: 비용 발생, 속도 느림.

2.  **보완적 관계 (Complementary)**
    *   사용자는 '유사성'을 원했지만, 실제로는 **"말 많은 사람(E)" + "잘 들어주는 사람(I)"** 조합이 좋을 수 있음.
    *   `Initiative` 항목에서 (주도형 + 반응형) 조합에 가산점을 주는 옵션 고려.

3.  **Conflict Style (갈등 해결 방식)**
    *   `conflict_style`이 '회피' + '직면'일 경우 최악의 궁합일 수 있음.
    *   이 부분은 유사도보다는 **"안 맞는 조합(Deal Breaker)" 필터링** 로직으로 사용.
