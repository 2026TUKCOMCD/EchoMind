import json
import random
import os

CANDIDATES_DIR = "candidates"
os.makedirs(CANDIDATES_DIR, exist_ok=True)

TOPICS_POOL = ["주식", "부동산", "운동", "헬스", "여행", "맛집", "코딩", "파이썬", "게임", "롤", 
               "영화", "넷플릭스", "독서", "음악", "노래방", "아이돌", "패션", "쇼핑", "자동차", "드라이브"]

NAMES = ["김철수", "이영희", "박지민", "최민수", "정하윤", "강서준", "윤서연", "임도현", "한지은", "오준호",
         "송예원", "신우진", "배수지", "권혁수", "류민지"]

def generate_profile(name):
    return {
        "language": "ko",
        "big5": {
            "openness": round(random.random(), 2),
            "conscientiousness": round(random.random(), 2),
            "extraversion": round(random.random(), 2),
            "agreeableness": round(random.random(), 2),
            "neuroticism": round(random.random(), 2)
        },
        "communication_style": {
            "tone": round(random.random(), 2),
            "directness": round(random.random(), 2),
            "emotion_expression": round(random.random(), 2),
            "empathy_signals": round(random.random(), 2),
            "initiative": round(random.random(), 2),
            "conflict_style": round(random.random(), 2)
        },
        "topics": random.sample(TOPICS_POOL, k=random.randint(1, 5)),
        "confidence": round(random.uniform(0.7, 0.99), 2),
        "stats": {
            "msg_share": round(random.uniform(30, 70), 1),
            "avg_reply_latency": round(random.uniform(1, 100), 1),
            "question_ratio": round(random.uniform(0.0, 0.5), 2)
        },
        "_meta": {
            "source": "dummy_generator",
            "target_name": name
        }
    }

print(f"[*] Generating {len(NAMES)} dummy profiles in '{CANDIDATES_DIR}'...")

for name in NAMES:
    profile = generate_profile(name)
    fname = os.path.join(CANDIDATES_DIR, f"candidate_{name}.json")
    with open(fname, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)
    print(f"Created: {fname}")

print("[*] Done.")
