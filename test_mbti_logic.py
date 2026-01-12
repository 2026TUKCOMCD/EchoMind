import sys
import os

# app.py가 있는 경로를 path에 추가하여 함수 불러오기
sys.path.append(r"c:\Users\mineb\Documents\pfg\EchoMind-dictionary")

try:
    from app import (
        analyze_mbti_features, 
        analyze_linguistic_features, 
        calculate_final_mbti,
        calculate_real_big5,
        analyze_sentiment_score,
        clean_text
    )
    print(">>> app.py 함수 로딩 성공")
except Exception as e:
    print(f">>> app.py 로딩 실패: {e}")
    sys.exit(1)

# 테스트 케이스 정의
def run_test(case_name, mock_rows, target_name):
    print(f"\n[{case_name}] 테스트 시작...")
    
    # 1. 상호작용 분석
    feats, sentences = analyze_mbti_features(mock_rows, target_name)
    
    if not sentences:
        print(">>> 분석할 문장이 없습니다.")
        return

    # 2. 언어 특징 분석
    feats = analyze_linguistic_features(sentences, feats)
    
    # 3. 최종 결과
    mbti, reason, _ = calculate_final_mbti(feats)
    
    print(f"   예측 MBTI: {mbti}")
    print(f"   특징 점수: E({feats['e_score']:.2f}) vs I({feats['i_score']:.2f})")
    print(f"             S({feats['s_score']:.2f}) vs N({feats['n_score']:.2f})")
    print(f"             T({feats['t_score']:.2f}) vs F({feats['f_score']:.2f})")
    print(f"             J({feats['j_score']:.2f}) vs P({feats['p_score']:.2f})")

# Case 1: ESTJ 유형 (빠른 답장, 구체적, 논리적, 계획적)
rows_estj = [
    {"speaker": "Other", "time": "오전 10:00", "text": "안녕"},
    {"speaker": "UserA", "time": "오전 10:01", "text": "어 안녕! 밥 먹었어?"}, # 빠른 답장(1분), 질문(E)
    {"speaker": "UserA", "time": "오전 10:01", "text": "나 지금 2000원짜리 커피 마시는 중."}, # 구체적 숫자(S)
    {"speaker": "UserA", "time": "오전 10:02", "text": "이따가 1시에 회의 있으니까 미리 준비해야 해."}, # 계획(J), 숫자(S)
    {"speaker": "UserA", "time": "오전 10:02", "text": "결과적으로 이게 효율적이야. 그래서 이렇게 하자."}, # 논리(T), 인과(T)
]

# Case 2: INFP 유형 (느린 답장, 추상적, 감정적, 유연함)
rows_infp = [
    {"speaker": "Other", "time": "오후 2:00", "text": "뭐해?"},
    {"speaker": "UserB", "time": "오후 2:30", "text": "음... 그냥 누워있어."}, # 느린 답장(30분), 모호함(I, P)
    {"speaker": "UserB", "time": "오후 2:30", "text": "만약에 우리가 구름 위를 걸을 수 있다면 어떨까?"}, # 가정법(N), 추상적(N)
    {"speaker": "UserB", "time": "오후 2:31", "text": "뭔가 기분이 몽글몽글해. 너도 그렇지? ㅠㅠ"}, # 감정(F), 공감(F)
    {"speaker": "UserB", "time": "오후 2:31", "text": "나중에 시간 되면 보자. 대충..."}, # 유연함(P)
]

# Case 3: Borderline I Check (검증용)
# 답장이 적당히 빠르지만(3분), 내용은 I스러운 경우 -> I가 나와야 함
rows_borderline_i = [
    {"speaker": "Other", "time": "AM 10:00", "text": "시작"},
    {"speaker": "UserC", "time": "AM 10:03", "text": "어... 생각 좀 해볼게."}, # 3분(애매함), 뜸들이기(I)
    {"speaker": "UserC", "time": "AM 10:03", "text": "지금은 좀 그래."}, # 짧은 턴(E요소)이지만 내용은 거절/신중
    {"speaker": "UserC", "time": "AM 10:04", "text": "나중에 얘기하자."}, # 회피(I/P)
]

run_test("Case 1 (ESTJ 의도)", rows_estj, "UserA")
run_test("Case 2 (INFP 의도)", rows_infp, "UserB")
run_test("Case 3 (I 편향 검증)", rows_borderline_i, "UserC")

print("\n[Big5 Logic Test]")
# Mock sentences
sentences = ["정말 고마워 사랑해 행복해", "기분 좋아", "짜증나 싫어 죽어"]
pos, neg, avg = analyze_sentiment_score(sentences)
print(f"Sentiment: Pos={pos:.2f}, Neg={neg:.2f}")

# Mock MBTI & Tox
mbti = "ENFP"
tox = 0.1 # 10%
big5 = calculate_real_big5(mbti, tox, pos, neg)
print(f"Big5 (ENFP, Tox=0.1, Pos={pos:.2f}): {big5}")
# Expect: High Neuroticism (due to Tox), Modest Agreeableness (Tox lowers it, Pos raises it)
