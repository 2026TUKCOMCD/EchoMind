# main.py
# -*- coding: utf-8 -*-

"""
Upload-time vector builder (single user, LLM-free)

Input:
- KakaoTalk exported .txt
- --name: the user's speaker name in the export
- --user_id: your internal id (DB PK or uuid)

Output:
- a single JSON object (matching vector) suitable for DB insert/upsert

Usage:
  python main.py --file sample_chat.txt --name "홍길동" --user_id "u_123" --out user_vector.json
  python main.py --file sample_chat.txt --name "홍길동" --user_id "u_123"

Notes:
- Multiline messages are not merged (lines not matching patterns are parse_failed).
- avg_gap_sec is computed as gaps between the user's own messages (conservative).
"""

import argparse
import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple


# ----------------------------
# Kakao parsing patterns
# ----------------------------
LINE_PATTERNS = [
    re.compile(r"^\[(?P<name>.+?)\]\s+\[(?P<time>.+?)\]\s+(?P<msg>.+)$"),
    re.compile(r"^(?P<time>\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.\s*.+?),\s*(?P<name>[^:]+?)\s*:\s*(?P<msg>.+)$"),
]

SYSTEM_SKIP_SUBSTR = [
    "사진", "이모티콘", "동영상", "삭제된 메시지입니다", "파일", "보이스톡", "통화",
    "송금", "입금", "출금",
]

RE_URL = re.compile(r"https?://\S+")
RE_LAUGH = re.compile(r"[ㅋㅎ]{2,}")
RE_CRY = re.compile(r"[ㅠㅜ]{2,}")
RE_SPACES = re.compile(r"\s+")

RE_PHONE = re.compile(r"(01[016789])[-.\s]?\d{3,4}[-.\s]?\d{4}")
RE_EMAIL = re.compile(r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b")
RE_KR_ID = re.compile(r"\b\d{6}[-\s]?\d{7}\b")

RE_QUESTION = re.compile(r"\?")
RE_EMO = re.compile(r"(?:\:\)|\:\(|\^\^|ㅎㅎ|ㅋ|ㅠ|ㅜ|😄|😂|😭|🙂|🙃|😅|😢)")
RE_HONORIFIC = re.compile(r"(습니다|세요|해요|했어요|예요|이에요)\b")
RE_CASUAL = re.compile(r"(야\b|지\b|해\b|했어\b|임\b|ㄱㄱ|ㅇㅇ)")
RE_HEDGE = re.compile(r"(혹시|아마|같아요|같은데|면|일지도|일까|가능할까요)")


# ----------------------------
# Data structures
# ----------------------------
@dataclass
class ParseQuality:
    total_lines: int
    parsed_lines: int
    parse_failed_lines: int
    filtered_system_lines: int
    empty_text_lines: int
    pii_masked_hits: int


@dataclass
class RhythmFeatures:
    avg_msg_len: float
    question_ratio: float
    avg_gap_sec: Optional[float]


@dataclass
class LanguageFeatures:
    honorific_ratio: float
    casual_ratio: float
    emoji_ratio: float
    hedge_ratio: float


# ----------------------------
# Helpers
# ----------------------------
def looks_like_system_message(text: str) -> bool:
    t = text.strip()
    if not t:
        return True
    return any(s in t for s in SYSTEM_SKIP_SUBSTR)


def clean_text_ko(text: str) -> str:
    text = RE_URL.sub(" ", text)
    text = RE_LAUGH.sub(" ", text)
    text = RE_CRY.sub(" ", text)
    text = RE_SPACES.sub(" ", text).strip()
    return text


def mask_pii(text: str) -> Tuple[str, int]:
    hits = 0

    new = RE_PHONE.sub("[전화번호]", text)
    if new != text:
        hits += 1
    text = new

    new = RE_EMAIL.sub("[이메일]", text)
    if new != text:
        hits += 1
    text = new

    new = RE_KR_ID.sub("[주민번호]", text)
    if new != text:
        hits += 1
    text = new

    return text, hits


def try_parse_kakao_time(t: str) -> Optional[datetime]:
    # best-effort: "2025. 1. 1. 오후 1:23"
    if not t:
        return None
    s = t.replace(" ", "")
    try:
        s2 = s.replace("년", ".").replace("월", ".").replace("일", ".")
        date_part = s2.split("오전")[0].split("오후")[0]
        ampm = "오전" if "오전" in s2 else ("오후" if "오후" in s2 else None)
        if ampm is None:
            return None
        time_part = s2.split(ampm, 1)[1]
        date_part = date_part.strip(".")
        y, m, d = [int(x) for x in date_part.split(".")]
        hh, mm = [int(x) for x in time_part.split(":")]
        if ampm == "오후" and hh != 12:
            hh += 12
        if ampm == "오전" and hh == 12:
            hh = 0
        return datetime(y, m, d, hh, mm)
    except Exception:
        return None


# ----------------------------
# Parse TXT and filter only target user
# ----------------------------
def parse_target_rows(filepath: str, target_name: str) -> Tuple[List[Dict[str, str]], ParseQuality]:
    total_lines = parsed = failed = filtered_system = empty_text = pii_hits_total = 0
    rows: List[Dict[str, str]] = []

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            total_lines += 1
            line = raw.rstrip("\n")
            if not line.strip():
                failed += 1
                continue

            m = None
            for pat in LINE_PATTERNS:
                m = pat.match(line)
                if m:
                    break
            if not m:
                failed += 1
                continue

            speaker = m.group("name").strip()
            if speaker != target_name:
                continue

            time_str = m.group("time").strip()
            text = m.group("msg").strip()

            if looks_like_system_message(text):
                filtered_system += 1
                continue

            text = clean_text_ko(text)
            if not text:
                empty_text += 1
                continue

            text, hits = mask_pii(text)
            pii_hits_total += hits

            rows.append({"speaker": speaker, "time": time_str, "text": text})
            parsed += 1

    quality = ParseQuality(
        total_lines=total_lines,
        parsed_lines=parsed,
        parse_failed_lines=failed,
        filtered_system_lines=filtered_system,
        empty_text_lines=empty_text,
        pii_masked_hits=pii_hits_total,
    )
    return rows, quality


# ----------------------------
# Feature extraction
# ----------------------------
def compute_rhythm(rows: List[Dict[str, str]]) -> RhythmFeatures:
    texts = [r["text"] for r in rows]
    n = max(len(texts), 1)

    avg_len = sum(len(t) for t in texts) / n
    q_ratio = sum(1 for t in texts if RE_QUESTION.search(t)) / n

    times = [try_parse_kakao_time(r.get("time", "")) for r in rows]
    dts = [dt for dt in times if dt is not None]
    if len(dts) >= 2:
        dts_sorted = sorted(dts)
        gaps = [(dts_sorted[i] - dts_sorted[i - 1]).total_seconds() for i in range(1, len(dts_sorted))]
        avg_gap = sum(gaps) / len(gaps)
    else:
        avg_gap = None

    return RhythmFeatures(avg_msg_len=avg_len, question_ratio=q_ratio, avg_gap_sec=avg_gap)


def compute_language(rows: List[Dict[str, str]]) -> LanguageFeatures:
    texts = [r["text"] for r in rows]
    n = max(len(texts), 1)

    honor = sum(1 for t in texts if RE_HONORIFIC.search(t)) / n
    casual = sum(1 for t in texts if RE_CASUAL.search(t)) / n
    emo = sum(1 for t in texts if RE_EMO.search(t)) / n
    hedge = sum(1 for t in texts if RE_HEDGE.search(t)) / n

    return LanguageFeatures(
        honorific_ratio=honor,
        casual_ratio=casual,
        emoji_ratio=emo,
        hedge_ratio=hedge,
    )


def estimate_confidence(message_count: int, time_parsed_ok: bool) -> float:
    # conservative baseline: message count driven
    if message_count < 15:
        base = 0.30
    elif message_count < 30:
        base = 0.45
    elif message_count < 80:
        base = 0.65
    elif message_count < 150:
        base = 0.78
    else:
        base = 0.85

    if not time_parsed_ok:
        base -= 0.05

    return max(0.0, min(1.0, base))


# ----------------------------
# CLI
# ----------------------------
def main():
    ap = argparse.ArgumentParser(description="Build a single user matching vector from KakaoTalk TXT (LLM-free)")
    ap.add_argument("--file", required=True, help="KakaoTalk exported .txt file path")
    ap.add_argument("--name", required=True, help="Target speaker name in the export (the uploader)")
    ap.add_argument("--user_id", required=True, help="Your internal user id (DB PK/UUID)")
    ap.add_argument("--out", default="", help="Output JSON path (optional)")
    ap.add_argument("--min_msgs", type=int, default=30, help="Minimum messages required to save (default: 30)")
    args = ap.parse_args()

    rows, quality = parse_target_rows(args.file, args.name)
    if len(rows) < args.min_msgs:
        raise SystemExit(
            f"분석 가능한 발화가 부족합니다: {len(rows)}개 (< {args.min_msgs}). "
            f"--name(대화명) 또는 --min_msgs를 확인하세요."
        )

    rhythm = compute_rhythm(rows)
    language = compute_language(rows)
    conf = estimate_confidence(len(rows), rhythm.avg_gap_sec is not None)

    out_obj = {
        "meta": {
            "source": "kakao_export_txt",
            "generated_at_utc": datetime.utcnow().isoformat() + "Z",
            "file": args.file,
            "speaker_name": args.name,
        },
        "parse_quality": asdict(quality),
        "user": {
            "user_id": args.user_id,
            "display_name": args.name,
            "message_count": len(rows),
            "rhythm": asdict(rhythm),
            "language": asdict(language),
            "confidence": conf,
        },
    }

    text = json.dumps(out_obj, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"[OK] Saved: {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
