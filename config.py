# config.py
# -*- coding: utf-8 -*-

"""
Shared configuration for EchoMind.
Contains style definitions, enum values, and scoring matrices used by both
main.py (generation) and recommend.py (matching).
"""

# -------------------------------------------------------------------------
# 1. Style Options (Enums for JSON Schema)
# -------------------------------------------------------------------------
STYLE_OPTIONS = {
    "tone": ["친근함", "공손함", "중립적", "건조함", "공격적"],
    "directness": ["직설적", "완곡적", "상황따라변함"],
    "emotion_expression": ["낮음", "보통", "높음"],
    "empathy_signals": ["낮음", "보통", "높음"],
    "initiative": ["주도형", "반응형", "혼합형"],
    "conflict_style": ["회피", "완화", "직면", "혼합"]
}

# -------------------------------------------------------------------------
# 2. Scoring Maps (Distance Calculation)
# -------------------------------------------------------------------------
# Used in recommend.py to calculate distance between styles.
STYLE_MAP = {
    "tone": {
        "친근함": 0, "공손함": 1, "중립적": 2, "건조함": 3, "공격적": 4
    },
    "directness": {
        "직설적": 0, "상황따라변함": 1, "완곡적": 2
    },
    "emotion_expression": {
        "높음": 2, "보통": 1, "낮음": 0
    },
    "empathy_signals": {
        "높음": 2, "보통": 1, "낮음": 0
    }
}

# -------------------------------------------------------------------------
# 3. Conflict Compatibility Matrix
# -------------------------------------------------------------------------
# (Style A, Style B) -> Score (0.0 ~ 1.0)
# Symmetric definition not required here; helper logic should handle symmetry.
# However, for clarity, we define key pairs consistently.
CONFLICT_SCORES = {
    # 직면 (Direct)
    ("직면", "직면"): 0.3, # Too much friction?
    ("직면", "회피"): 0.0, # Worst combo (Chase vs Flight)
    ("직면", "완화"): 0.9, # Good balance
    ("직면", "혼합"): 0.7,

    # 회피 (Avoid)
    ("회피", "회피"): 0.4, # Nothing gets resolved
    ("회피", "완화"): 0.6, # Better, but passive
    ("회피", "혼합"): 0.6,

    # 완화 (Soothing)
    ("완화", "완화"): 0.8, # Very peaceful
    ("완화", "혼합"): 0.9, 

    # 혼합 (Mixed)
    ("혼합", "혼합"): 1.0, # Flexible + Flexible
}

def get_conflict_score(c1: str, c2: str) -> float:
    """
    Returns compatibility score between two conflict styles.
    Handles symmetry (A, B) == (B, A).
    """
    if c1 == c2:
        return CONFLICT_SCORES.get((c1, c1), 0.5)
    
    # Try both orders
    pair1 = (c1, c2)
    pair2 = (c2, c1)
    
    if pair1 in CONFLICT_SCORES:
        return CONFLICT_SCORES[pair1]
# -------------------------------------------------------------------------
# 4. Continuous Scoring Config (0.00 ~ 1.00)
# -------------------------------------------------------------------------

# LLM Prompt Guide
STYLE_SCALES = {
    "tone": ("건조함/격식(0.0)", "친근함/다정함(1.0)"),
    "directness": ("완곡적/돌려말함(0.0)", "직설적/솔직함(1.0)"),
    "emotion_expression": ("이성적/절제(0.0)", "감성적/풍부(1.0)"),
    "empathy_signals": ("낮음(0.0)", "높음(1.0)"),
    "initiative": ("수동적/반응형(0.0)", "능동적/주도형(1.0)"),
    "conflict_style": ("회피형(0.0)", "직면/도전형(1.0)")
}

# Legacy Data Migration (Text -> Float)
# 기존 텍스트 데이터를 0.0 ~ 1.0 사이의 값으로 매핑합니다.
LEGACY_TO_SCORE_MAP = {
    # Tone
    "건조함": 0.1, "중립적": 0.4, "공손함": 0.6, "친근함": 0.9, "공격적": 0.2, # 공격적은 친근함의 반대? 아니면 건조함의 극치? 여기서는 context상 low friendliness로 매핑
    
    # Directness
    "완곡적": 0.2, "상황따라변함": 0.5, "직설적": 0.9,
    
    # Emotion / Empathy
    "낮음": 0.2, "보통": 0.5, "높음": 0.9,
    
    # Initiative
    "반응형": 0.2, "혼합형": 0.5, "주도형": 0.9,
    
    # Conflict
    "회피": 0.1, "완화": 0.4, "혼합": 0.6, "직면": 0.9
}

# -------------------------------------------------------------------------
# 5. Dictionary & Analysis Config
# -------------------------------------------------------------------------
# 욕설/비속어 리스트 파일 (korean_bad_words.json)
BAD_WORDS_FILE = "korean_bad_words.json"

# KNU 감성 사전 파일명 (main.py와 같은 경로 가정)
SENTIMENT_DICT_FILE = "SentiWord_info.json"
