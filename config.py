# config.py

BAD_WORDS_FILE = "korean_bad_words.json"
SENTIMENT_DICT_FILE = "SentiWord_info.json"

# 스타일 척도 정의 (0.0 ~ 1.0)
STYLE_SCALES = {
    "tone": ["이성적/건조함", "감성적/따뜻함"],
    "directness": ["우회적/신중함", "직설적/솔직함"],
    "emotion_expression": ["절제됨/차분함", "풍부함/다양함"],
    "empathy_signals": ["해결책중심", "리액션/공감중심"],
    "initiative": ["수동적/듣는편", "주도적/이끄는편"],
    "conflict_style": ["평화주의/회피", "논쟁선호/직면"]
}

# Legacy support for recommend.py if strings are used
LEGACY_TO_SCORE_MAP = {
    "Low": 0.2,
    "Medium": 0.5,
    "High": 0.8,
    "Very Low": 0.1,
    "Very High": 0.9
}

STYLE_OPTIONS = {} # Backward compatibility if needed
