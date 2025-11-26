# -*- coding: utf-8 -*-
"""
main.py
카카오톡 대화 내보내기(txt) -> 본인 이름 입력 -> 내 발화만 분석
무료 AI API:
 - Hugging Face Inference API (감성: 긍/부/중)
 - Google Perspective API (독성: 0~1)
출력:
 - out_report/summary.md
 - out_report/report.json
 - out_report/utterances.csv
"""

import os
import re
import json
import time
import statistics
import argparse
from pathlib import Path
from collections import Counter

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv

# -----------------------
# 환경변수 로드
# -----------------------
load_dotenv()
HF_TOKEN = os.getenv("HF_TOKEN")  # Hugging Face Inference API 토큰
PERSPECTIVE_API_KEY = os.getenv("PERSPECTIVE_API_KEY")  # Google Perspective API 키

# -----------------------
# 카톡 파서
# -----------------------
LINE_RE = re.compile(r"^\[(?P<name>.+?)\]\s+\[(?P<time>\d{1,2}:\d{2})\]\s+(?P<msg>.+)$")
SKIP_TOKENS = {"사진", "이모티콘", "동영상", "삭제된 메시지입니다."}

def parse_kakao_txt(path: str):
    rows = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.rstrip("\n")
            m = LINE_RE.match(line)
            if not m:
                continue
            rows.append({
                "speaker": m.group("name").strip(),
                "time": m.group("time"),
                "text": m.group("msg").strip(),
                "raw": line,
            })
    return rows

def clean_text(t: str) -> str:
    t = re.sub(r"https?://\S+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def split_sentences(t: str):
    parts = re.split(r"(?<=[.!?])\s+|\n+", t)
    return [p.strip() for p in parts if p.strip()]

# -----------------------
# 무료 API 클라이언트
# -----------------------
HF_API = "https://api-inference.huggingface.co/models/cardiffnlp/twitter-xlm-roberta-base-sentiment"

def hf_sentiment_labels(texts):
    """
    다국어 감성 분석: POSITIVE / NEGATIVE / NEUTRAL
    무료 할당량 보호를 위해 단건 호출 + 약간의 대기
    """
    headers = {"Authorization": f"Bearer {HF_TOKEN}"} if HF_TOKEN else {}
    out = []
    for t in texts:
        payload = {"inputs": t[:800]}  # 과도한 길이 방지
        r = requests.post(HF_API, headers=headers, json=payload, timeout=30)
        if r.status_code == 503:
            time.sleep(2)
            r = requests.post(HF_API, headers=headers, json=payload, timeout=30)
        r.raise_for_status()
        js = r.json()
        # 응답: [[{label, score}, ...]] 또는 [{label, score}, ...]
        arr = js[0] if isinstance(js, list) and js and isinstance(js[0], list) else js
        top = max(arr, key=lambda x: x["score"])
        out.append(top["label"].upper())
        time.sleep(0.2)  # QPS 여유
    return out

PERSPECTIVE_URL = "https://commentanalyzer.googleapis.com/v1alpha1/comments:analyze"

def perspective_toxicity_scores(texts, lang="ko"):
    """
    독성(TOXICITY) 0~1 점수. 기본 1 QPS 제한 → 호출 간 1초 간격.
    키가 없으면 0.0으로 대체.
    """
    if not PERSPECTIVE_API_KEY:
        return [0.0] * len(texts)
    scores = []
    for t in texts:
        data = {
            "comment": {"text": t[:2000]},
            "languages": [lang],
            "requestedAttributes": {"TOXICITY": {}}
        }
        r = requests.post(f"{PERSPECTIVE_URL}?key={PERSPECTIVE_API_KEY}", json=data, timeout=30)
        r.raise_for_status()
        js = r.json()
        val = js.get("attributeScores", {}).get("TOXICITY", {}).get("summaryScore", {}).get("value", 0.0)
        scores.append(float(val))
        time.sleep(1.05)  # 1 QPS
    return scores

# -----------------------
# 간단 스타일 지표 & 빅파이브(탐색적)
# -----------------------
def style_metrics(sentences):
    joined = " ".join(sentences)
    toks = joined.split()
    total = len(toks) or 1
    self_ref = len(re.findall(r"\b(나|내가|나는|내|제가|제|I|me|my|mine)\b", joined, flags=re.I)) / total
    uncertainty = len(re.findall(r"\b(아마|같다|듯|일지도|maybe|might|could|seems?)\b", joined, flags=re.I)) / total
    certainty = len(re.findall(r"\b(반드시|확실히|틀림없이|definitely|always|never)\b", joined, flags=re.I)) / total
    avg_len = statistics.mean([len(s.split()) for s in sentences]) if sentences else 0.0
    ttr = len(set(toks)) / total
    return {"self_ref": self_ref, "uncertainty": uncertainty, "certainty": certainty, "avg_len": avg_len, "ttr": ttr}

def infer_bigfive(summary):
    s = summary
    st = s["style"]
    avg_len_norm = min(1.0, st["avg_len"] / 30.0)
    openness           = min(1.0, 0.45*st["ttr"] + 0.35*s.get("topic_div", 0.5) + 0.20*avg_len_norm)
    conscientiousness  = min(1.0, 0.50*st["certainty"] + 0.30*(1 - s["toxicity_avg"]) + 0.20*s["positive_ratio"])
    extraversion       = min(1.0, 0.50*st["self_ref"] + 0.30*s["positive_ratio"] + 0.20*avg_len_norm)
    agreeableness      = min(1.0, 0.55*(1 - s["toxicity_avg"]) + 0.25*s["positive_ratio"] + 0.20*(1 - st["uncertainty"]))
    neuroticism        = min(1.0, 0.60*s["negative_ratio"] + 0.20*st["uncertainty"] + 0.20*(1 - st["certainty"]))
    return {
        "openness": round(openness, 3),
        "conscientiousness": round(conscientiousness, 3),
        "extraversion": round(extraversion, 3),
        "agreeableness": round(agreeableness, 3),
        "neuroticism": round(neuroticism, 3),
    }

# -----------------------
# 리포트 저장
# -----------------------
def write_report(outdir, per_sent_records, summary, big5):
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)

    # CSV
    pd.DataFrame(per_sent_records).to_csv(out / "utterances.csv", index=False, encoding="utf-8-sig")

    # JSON
    (out / "report.json").write_text(json.dumps({
        "summary": summary,
        "big_five_exploratory": big5
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    # Markdown
    md = []
    md.append("# 텍스트 성향 리포트(탐색적)\n")
    md.append("## 핵심 지표")
    md.append(f"- 문장 수: {summary['n_sentences']}")
    md.append(f"- 긍정/중립/부정: {summary['positive_ratio']:.2f} / {summary['neutral_ratio']:.2f} / {summary['negative_ratio']:.2f}")
    md.append(f"- 평균 독성 점수: {summary['toxicity_avg']:.3f}")
    md.append(f"- 평균 문장 길이(단어): {summary['style']['avg_len']:.2f}")
    md.append(f"- 어휘 다양성(TTR≈): {summary['style']['ttr']:.3f}")
    md.append("\n## 빅파이브(탐색적, 0~1)")
    for k, v in big5.items():
        md.append(f"- {k.title()}: {v:.2f}")
    md.append("\n> ※ 텍스트 기반 ‘탐색적 추정’으로, 심리검사가 아닙니다.")
    (out / "summary.md").write_text("\n".join(md), encoding="utf-8")

# -----------------------
# 메인 실행
# -----------------------
def main():
    parser = argparse.ArgumentParser(description="카카오톡 대화 성격 분석 (무료 API 사용)")
    parser.add_argument("-f", "--file", required=True, help="카카오톡 내보내기 txt 경로")
    parser.add_argument("-o", "--outdir", default="out_report", help="리포트 출력 폴더")
    args = parser.parse_args()

    if not HF_TOKEN:
        raise SystemExit("환경변수 HF_TOKEN 이 없습니다. .env 파일을 확인하세요. (Hugging Face Inference API 토큰)")
    if not PERSPECTIVE_API_KEY:
        print("[경고] PERSPECTIVE_API_KEY 가 없습니다. 독성 점수는 0으로 처리됩니다.")

    my_name = input("카톡 대화에서 본인 이름(표시명)을 입력하세요: ").strip()
    if not my_name:
        raise SystemExit("이름이 비어 있습니다.")

    rows = parse_kakao_txt(args.file)

    # 내 발화만 추출 → 문장화
    sentences = []
    for r in rows:
        if r["speaker"] != my_name:
            continue
        txt = r["text"]
        if not txt or txt in SKIP_TOKENS:
            continue
        txt = clean_text(txt)
        sentences.extend(split_sentences(txt))

    # 너무 짧은 문장 제거
    sentences = [s for s in sentences if len(s.split()) >= 3]
    if len(sentences) == 0:
        raise SystemExit("분석할 문장이 없습니다. 파일/이름을 확인하세요.")
    if len(sentences) < 10:
        print(f"[안내] 문장 수가 {len(sentences)}개로 적어 결과 신뢰도가 낮을 수 있습니다.")

    # 무료 API 호출
    print("[진행] 감성 분석(Hugging Face Inference API)...")
    senti_labels = hf_sentiment_labels(sentences)  # POSITIVE/NEGATIVE/NEUTRAL

    print("[진행] 독성 분석(Google Perspective API)...")
    tox_scores = perspective_toxicity_scores(sentences, lang="ko")  # 0~1 (키 없으면 0)

    # 요약
    n = len(sentences)
    cnt = Counter(senti_labels)
    pos = cnt.get("POSITIVE", 0) / n
    neg = cnt.get("NEGATIVE", 0) / n
    neu = 1 - pos - neg
    tox_avg = float(np.mean(tox_scores)) if tox_scores else 0.0
    style = style_metrics(sentences)
    topic_div = float(min(1.0, 0.5 + 0.5 * (len(set(sentences)) / n)))  # 간단 근사

    summary = {
        "n_sentences": n,
        "positive_ratio": float(pos),
        "negative_ratio": float(neg),
        "neutral_ratio": float(neu),
        "toxicity_avg": float(tox_avg),
        "style": style,
        "topic_div": topic_div,
    }

    # per-sentence 레코드
    per_sent = [{"sentence": s, "sentiment": l, "toxicity": float(t)} for s, l, t in zip(sentences, senti_labels, tox_scores)]

    # 빅파이브(탐색적)
    big5 = infer_bigfive(summary)

    # 저장
    write_report(args.outdir, per_sent, summary, big5)
    print(f"[완료] 리포트 생성: {Path(args.outdir).resolve()} (summary.md / report.json / utterances.csv)")

if __name__ == "__main__":
    main()
