# parse.py
# -*- coding: utf-8 -*-

"""
[EchoMind Parser] Universal Compatibility Version
=================================================
PC버전(날짜 헤더 분리형)과 모바일버전(날짜 포함형)을 모두 지원하며,
24시간제(16:01)와 12시간제(오후 4:01) 시간 포맷을 자동으로 처리합니다.
(수정됨: 결과 파일 저장 시 시간 정보 제외)
"""

import os
import re
import argparse
import sys
from datetime import datetime
from typing import Optional

# ----------------------------
# 1. 설정 및 정규식 정의
# ----------------------------
SYSTEM_SKIP_SUBSTR = [
    "사진", "이모티콘", "동영상", "삭제된 메시지입니다", "파일", "보이스톡", "통화", "송금", "입금", "출금", "톡게시판"
]

# (1) 날짜 헤더 패턴 (PC 버전에서 날짜가 바뀌는 줄)
# 예: --------------- 2025년 5월 26일 월요일 ---------------
DATE_HEADER_PATTERN = re.compile(r"^-+\s+(?P<year>\d{4})년\s+(?P<month>\d{1,2})월\s+(?P<day>\d{1,2})일")

# (2) 메시지 라인 패턴
LINE_PATTERNS = [
    # Pattern A: 모바일 (2026. 1. 8. 오후 2:00, 홍길동 : 메시지) - 날짜가 포함됨
    re.compile(r"^(?P<time>\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.\s*.+?),\s*(?P<name>[^:]+?)\s*:\s*(?P<msg>.+)$"),
    # Pattern B: PC ( [홍길동] [16:01] 메시지 ) - 날짜 없음, 시간만 있음
    re.compile(r"^\[(?P<name>.+?)\]\s+\[(?P<time>.+?)\]\s+(?P<msg>.+)$"),
]

# (3) 개인정보 마스킹 패턴
RE_PII_PHONE = re.compile(r"01[0-9]-?\d{3,4}-?\d{4}")
RE_PII_EMAIL = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
RE_PII_RRN = re.compile(r"\d{6}-?[1-4]\d{6}")


# ----------------------------
# 2. 헬퍼 함수: 시간 및 날짜 처리
# ----------------------------
def parse_time_part(time_str: str) -> Optional[tuple]:
    """
    시간 문자열에서 (시, 분) 정수 튜플을 추출합니다.
    입력 예: "16:01", "오후 4:01", "AM 09:00"
    """
    ts = time_str.strip()
    try:
        # Case 1: 24시간제 (숫자와 콜론만 있는 경우, 예: 16:01)
        # '오전/오후'가 없고 ':'가 있으면 24시간제로 간주
        if ':' in ts and not any(x in ts for x in ['오전', '오후', 'AM', 'PM']):
            dt = datetime.strptime(ts, "%H:%M")
            return dt.hour, dt.minute
            
        # Case 2: 12시간제 (오전/오후 포함)
        # 통일을 위해 영어 AM/PM으로 치환 후 파싱
        clean_ts = ts.replace("오전", "AM").replace("오후", "PM")
        if "AM" in clean_ts or "PM" in clean_ts:
            dt = datetime.strptime(clean_ts, "%p %I:%M")
            return dt.hour, dt.minute
            
    except ValueError:
        pass
    
    return None

def parse_full_datetime(time_str: str) -> Optional[datetime]:
    """
    날짜가 포함된 모바일 버전 포맷을 파싱합니다.
    입력 예: "2026. 1. 8. 오후 2:00"
    """
    try:
        ts = time_str.replace("오전", "AM").replace("오후", "PM").strip()
        # 정규식으로 YYYY. MM. DD. 포맷을 YYYY-MM-DD로 변환
        clean_ts = re.sub(r"(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.", r"\1-\2-\3", ts)
        return datetime.strptime(clean_ts, "%Y-%m-%d %p %I:%M")
    except:
        return None


# ----------------------------
# 3. 메인 파싱 및 저장 로직
# ----------------------------
def parse_and_save(input_path: str, target_name: str, output_path: str):
    if not os.path.exists(input_path):
        print(f"[ERROR] 입력 파일을 찾을 수 없습니다: {input_path}")
        sys.exit(1)

    parsed_lines = []
    stats = {
        "total_read": 0,
        "target_saved": 0,
        "system_skipped": 0,
        "others_skipped": 0,
        "date_header_found": 0
    }

    # PC 버전 파싱을 위해 '현재 날짜'를 기억하는 변수
    current_date_context = None

    print(f"분석 시작: '{target_name}'님의 데이터를 추출합니다...")

    # 인코딩 호환성을 위해 utf-8-sig (BOM 제거) 시도 후 cp949 시도
    lines = []
    try:
        with open(input_path, "r", encoding="utf-8-sig") as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        with open(input_path, "r", encoding="cp949") as f:
            lines = f.readlines()

    for line in lines:
        line = line.strip()
        stats["total_read"] += 1
        if not line: continue

        # [단계 1] 날짜 헤더(Date Header) 확인 (PC 버전용)
        # 예: --------------- 2025년 5월 26일 월요일 ---------------
        date_match = DATE_HEADER_PATTERN.search(line)
        if date_match:
            try:
                current_date_context = datetime(
                    int(date_match.group('year')),
                    int(date_match.group('month')),
                    int(date_match.group('day'))
                )
                stats["date_header_found"] += 1
                continue # 날짜 줄은 메시지가 아니므로 넘어감
            except ValueError:
                pass

        # [단계 2] 메시지 패턴 매칭
        match = None
        for pattern in LINE_PATTERNS:
            match = pattern.match(line)
            if match: break
        
        if match:
            name = match.group("name").strip()
            time_part = match.group("time").strip()
            msg = match.group("msg").strip()

            # 시스템 메시지 필터링
            if any(s in msg for s in SYSTEM_SKIP_SUBSTR):
                stats["system_skipped"] += 1
                continue

            # 분석 대상(이름) 필터링
            if name == target_name:
                final_dt = None

                # [시간 처리 A] 날짜가 포함된 포맷 (모바일)
                full_dt = parse_full_datetime(time_part)
                if full_dt:
                    final_dt = full_dt
                
                # [시간 처리 B] 시간만 있는 포맷 (PC) -> 헤더 날짜와 결합
                elif current_date_context:
                    time_tuple = parse_time_part(time_part)
                    if time_tuple:
                        hour, minute = time_tuple
                        final_dt = current_date_context.replace(hour=hour, minute=minute)

                if final_dt:
                    # 개인정보 마스킹
                    clean_msg = re.sub(r"https?://\S+", "", msg).strip() # URL 제거
                    clean_msg = RE_PII_PHONE.sub("(전화번호)", clean_msg)
                    clean_msg = RE_PII_EMAIL.sub("(이메일)", clean_msg)
                    clean_msg = RE_PII_RRN.sub("(주민번호)", clean_msg)

                    if clean_msg:
                        # [수정] 포맷 변경: 시간 정보 제거
                        # 기존: formatted = f"[{final_dt.strftime('%Y-%m-%d %H:%M')}] {clean_msg}"
                        formatted = clean_msg 
                        parsed_lines.append(formatted)
                        stats["target_saved"] += 1
            else:
                stats["others_skipped"] += 1

    # 결과 저장
    if parsed_lines:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(parsed_lines))
        print(f"저장 완료: {output_path}")
        print("\n[처리 결과 요약]")
        print(f"- 읽은 라인 수 : {stats['total_read']} 줄")
        print(f"- 날짜 헤더 발견 : {stats['date_header_found']} 회")
        print(f"- 저장된 메시지 : {stats['target_saved']} 개")
    else:
        print(f"[Warning] 저장된 메시지가 0개입니다.")
        print(f" - 입력한 이름: '{target_name}'")
        print(f" - 날짜 헤더 발견 수: {stats['date_header_found']} (이게 0이면 PC버전 날짜 인식 실패)")
        print(f" - 파일 인코딩 문제이거나 이름이 정확히 일치하지 않을 수 있습니다.")

# ----------------------------
# 4. CLI 실행
# ----------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, help="Input raw text file")
    parser.add_argument("--name", required=True, help="Target user name")
    parser.add_argument("--out", required=True, help="Output clean file")
    args = parser.parse_args()

    parse_and_save(args.file, args.name, args.out)

if __name__ == "__main__":
    main()