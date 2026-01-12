import sys
import os

# app.py가 있는 경로를 path에 추가하여 함수 불러오기
sys.path.append(r"c:\Users\mineb\Documents\pfg\EchoMind-dictionary")

try:
    from app import analyze_mbti_features, analyze_linguistic_features, calculate_final_mbti, clean_text
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
    print(f"             J({feats['j_score']:.2f}) vs P({feats['p_score']:.2f}")

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

# Case 3: Mixed Time Formats (검증용)
rows_mixed = [
    {"speaker": "Other", "time": "AM 10:00", "text": "시작"},
    {"speaker": "UserC", "time": "AM 10:05", "text": "5분 뒤 답장. (빠름-E)"}, # 5분 차이
    {"speaker": "UserC", "time": "PM 10:05", "text": "12시간 뒤. (선톡?)"}, # 12시간 차이 -> 선톡 인정
    {"speaker": "UserC", "time": "14:00", "text": "24시간 포맷도 처리 되나?"}, # 14:00 -> PM 2:00
]

run_test("Case 1 (ESTJ 의도)", rows_estj, "UserA")
run_test("Case 2 (INFP 의도)", rows_infp, "UserB")
run_test("Case 3 (시간 포맷 검증)", rows_mixed, "UserC")
