import sys
import os

# app.py가 있는 경로를 path에 추가하여 함수 불러오기
sys.path.append(r"c:\Users\mineb\Documents\pfg\EchoMind-dictionary")

try:
    from app import (
        analyze_mbti_features, 
        analyze_linguistic_features, 
        calculate_final_mbti,
        calculate_advanced_big5,
        analyze_korean_style_features,
        analyze_sentiment_score,
        clean_text
    )
    print(">>> app.py 함수 로딩 성공")
except Exception as e:
    print(f">>> app.py 로딩 실패: {e}")
    sys.exit(1)

# ... (기존 테스트 케이스 유지) ...

print("\n[Big5 Advanced Logic Test]")
# Mock sentences (Style analysis requires more text)
sentences = [
    "정말 고마워 사랑해 행복해", 
    "뭔가 기분이 좋아 ㅋㅋㅋ", 
    "아마 그건 아닌 것 같아...", 
    "확실히 이게 맞아!",
    "짜증나 미친 개새끼", # 독성
    "나 오늘 밥 먹었어 ㅋㅋ" # 리액션 + 자기지칭
]
pos, neg, avg = analyze_sentiment_score(sentences)
style = analyze_korean_style_features(sentences)
tox = 0.15 # 독성 15% 가정

print(f"Analysis: Pos={pos:.2f}, Style={style}, Tox={tox}")

big5 = calculate_advanced_big5(style, tox, pos, neg)
print(f"Big5 (Advanced): {big5}")
# Expect: High Extraversion (Laughs, Pos), Low Agreeableness (High Tox), High Neuroticism (Tox, Neg)
