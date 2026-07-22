"""EchoMind 활동 요약 보조 함수 모음."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence

# 날짜와 시간 표시 형식은 템플릿에서 그대로 재사용한다.
DATE_LABEL_FORMAT = "%m/%d"
DATETIME_LABEL_FORMAT = "%Y-%m-%d %H:%M"
ISO_DATE_FORMAT = "%Y-%m-%d"


# 개별 활동을 카드 형태로 정리하는 데이터 구조다.
@dataclass(frozen=True)
class ActivityCard:
    """템플릿에서 바로 보여줄 수 있는 활동 요약 카드."""

    icon: str
    title: str
    value: str
    description: str

    def to_dict(self) -> Dict[str, str]:
        """카드를 템플릿용 딕셔너리로 바꾼다."""

        return {
            "icon": self.icon,
            "title": self.title,
            "value": self.value,
            "description": self.description,
        }


# 활동 페이지 전체 요약을 한 덩어리로 묶는 데이터 구조다.
@dataclass(frozen=True)
class ActivitySummary:
    """활동 페이지에서 쓸 전체 요약 데이터."""

    window_days: int
    generated_at: datetime
    total_count: int
    login_count: int
    analysis_count: int
    matching_count: int
    active_days: int
    average_per_day: float
    latest_timestamp: Optional[datetime]
    latest_label: Optional[str]
    peak_day: Optional[Dict[str, Any]]
    cards: List[ActivityCard]
    daily_counts: List[Dict[str, Any]]
    breakdown: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        """템플릿과 JSON 응답에서 쓰기 좋은 딕셔너리로 바꾼다."""

        return {
            "window_days": self.window_days,
            "generated_at": self.generated_at.isoformat(timespec="seconds"),
            "total_count": self.total_count,
            "login_count": self.login_count,
            "analysis_count": self.analysis_count,
            "matching_count": self.matching_count,
            "active_days": self.active_days,
            "average_per_day": round(self.average_per_day, 2),
            "latest_timestamp": self.latest_timestamp.isoformat(timespec="seconds") if self.latest_timestamp else None,
            "latest_label": self.latest_label,
            "peak_day": self.peak_day,
            "cards": [card.to_dict() for card in self.cards],
            "daily_counts": self.daily_counts,
            "breakdown": self.breakdown,
        }


def _as_iterable(collection: Optional[Sequence[Any]]) -> List[Any]:
    """입력값을 안전한 리스트로 정리한다."""

    if not collection:
        return []
    if isinstance(collection, list):
        return collection
    return list(collection)


def _extract_timestamp(activity: Any) -> Optional[datetime]:
    """객체나 딕셔너리에서 timestamp 값을 꺼낸다."""

    # 활동이 객체인지 딕셔너리인지에 따라 timestamp 접근 방법이 다르다.
    value: Any = None

    if isinstance(activity, Mapping):
        value = activity.get("timestamp")
    else:
        value = getattr(activity, "timestamp", None)

    if isinstance(value, datetime):
        return value

    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None
        try:
            return datetime.fromisoformat(normalized.replace("Z", "+00:00"))
        except ValueError:
            return None

    return None


def _extract_date_key(activity: Any) -> Optional[str]:
    """활동 시각을 YYYY-MM-DD 문자열로 바꾼다."""

    # 일 단위 집계를 위해 날짜만 떼어낸다.
    stamp = _extract_timestamp(activity)
    if stamp is None:
        return None
    return stamp.date().isoformat()


def _format_decimal(value: float) -> str:
    """소수값을 카드에 맞는 짧은 문자열로 바꾼다."""

    text = f"{value:.1f}"
    if text.endswith(".0"):
        return text[:-2]
    return text


def _format_count(value: int) -> str:
    """큰 숫자는 k, m 접미사로 짧게 표시한다."""

    # 카드 영역이 너무 길어지지 않도록 큰 값은 축약 표기한다.
    if value < 1000:
        return str(value)
    if value < 1000000:
        return _format_decimal(value / 1000.0) + "k"
    return _format_decimal(value / 1000000.0) + "m"


def _summarize_latest_timestamp(*collections: Sequence[Any]) -> Optional[datetime]:
    """여러 활동 묶음 중 가장 최근 시각을 찾는다."""

    # 로그인, 분석, 매칭 전체 중 가장 늦은 시각을 찾는다.
    latest: Optional[datetime] = None
    for collection in collections:
        for activity in collection:
            stamp = _extract_timestamp(activity)
            if stamp is None:
                continue
            if latest is None or stamp > latest:
                latest = stamp
    return latest


def _group_daily_counts(*collections: Sequence[Any]) -> List[Dict[str, Any]]:
    """하루 단위 활동 수를 모아서 정렬한다."""

    # 날짜별로 활동 수를 세어서 차트나 통계 카드에 바로 쓰게 만든다.
    counts: Counter[str] = Counter()
    for collection in collections:
        for activity in collection:
            key = _extract_date_key(activity)
            if key is not None:
                counts[key] += 1

    daily_counts: List[Dict[str, Any]] = []
    for key in sorted(counts.keys()):
        daily_counts.append(
            {
                "date": key,
                "label": datetime.strptime(key, ISO_DATE_FORMAT).strftime(DATE_LABEL_FORMAT),
                "count": counts[key],
            }
        )
    return daily_counts


def _build_peak_day(daily_counts: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """가장 활동이 많았던 하루를 찾는다."""

    # 최댓값을 가진 날짜를 대표 피크 값으로 잡는다.
    if not daily_counts:
        return None
    peak = max(daily_counts, key=lambda item: item["count"])
    return {
        "date": peak["date"],
        "label": peak["label"],
        "count": peak["count"],
    }


def _build_breakdown(
    login_count: int,
    analysis_count: int,
    matching_count: int,
) -> List[Dict[str, Any]]:
    """로그인, 분석, 매칭 비중을 백분율로 정리한다."""

    # 비율 계산의 기준은 세 항목의 합계다.
    total = login_count + analysis_count + matching_count
    if total == 0:
        total = 1

    def _row(label: str, count: int, icon: str, color: str) -> Dict[str, Any]:
        percentage = round((count / total) * 100, 1)
        return {
            "label": label,
            "count": count,
            "percentage": percentage,
            "icon": icon,
            "color": color,
        }

    return [
        _row("로그인", login_count, "로그", "slate"),
        _row("분석", analysis_count, "분석", "indigo"),
        _row("매칭", matching_count, "매칭", "emerald"),
    ]


def _build_cards(
    total_count: int,
    login_count: int,
    analysis_count: int,
    matching_count: int,
    active_days: int,
    average_per_day: float,
    latest_timestamp: Optional[datetime],
    peak_day: Optional[Dict[str, Any]],
) -> List[ActivityCard]:
    """활동 페이지 상단에 보여줄 카드 목록을 만든다."""

    # 템플릿은 이 카드 배열만 순회하면 되도록 미리 문구를 완성해 둔다.
    latest_label = latest_timestamp.strftime(DATETIME_LABEL_FORMAT) if latest_timestamp else "-"
    peak_label = f"{peak_day['label']} ({peak_day['count']})" if peak_day else "-"

    return [
        ActivityCard(
            icon="총",
            title="전체 활동",
            value=_format_count(total_count),
            description="현재 기간에 기록된 전체 활동 수입니다.",
        ),
        ActivityCard(
            icon="로그",
            title="로그인 기록",
            value=_format_count(login_count),
            description="성공과 실패를 모두 포함한 로그인 기록입니다.",
        ),
        ActivityCard(
            icon="분석",
            title="프로필 분석",
            value=_format_count(analysis_count),
            description="사용자 프로필을 분석한 기록입니다.",
        ),
        ActivityCard(
            icon="매칭",
            title="매칭 활동",
            value=_format_count(matching_count),
            description="신청, 응답, 상태 변경을 포함한 매칭 기록입니다.",
        ),
        ActivityCard(
            icon="일수",
            title="활동 일수",
            value=_format_count(active_days),
            description="활동이 한 번이라도 있었던 날짜 수입니다.",
        ),
        ActivityCard(
            icon="평균",
            title="일평균",
            value=_format_decimal(average_per_day),
            description="현재 기간 기준의 하루 평균 활동 수입니다.",
        ),
        ActivityCard(
            icon="최근",
            title="최근 활동",
            value=latest_label,
            description="세 영역 중 가장 최근에 기록된 시간입니다.",
        ),
        ActivityCard(
            icon="최다",
            title="최다 활동일",
            value=peak_label,
            description="현재 기간에서 활동 수가 가장 많았던 날짜입니다.",
        ),
    ]


def build_activity_summary(
    login_activities: Optional[Sequence[Any]],
    analysis_activities: Optional[Sequence[Any]],
    matching_activities: Optional[Sequence[Any]],
    window_days: int = 30,
) -> Dict[str, Any]:
    """활동 페이지용 전체 요약 데이터를 만든다."""

    # 세 종류 활동을 각각 안전한 리스트로 정리한 뒤 통계를 계산한다.
    login_list = _as_iterable(login_activities)
    analysis_list = _as_iterable(analysis_activities)
    matching_list = _as_iterable(matching_activities)

    login_count = len(login_list)
    analysis_count = len(analysis_list)
    matching_count = len(matching_list)
    total_count = login_count + analysis_count + matching_count

    latest_timestamp = _summarize_latest_timestamp(login_list, analysis_list, matching_list)
    daily_counts = _group_daily_counts(login_list, analysis_list, matching_list)
    peak_day = _build_peak_day(daily_counts)
    active_days = len(daily_counts)
    average_per_day = total_count / max(window_days, 1)
    cards = _build_cards(
        total_count=total_count,
        login_count=login_count,
        analysis_count=analysis_count,
        matching_count=matching_count,
        active_days=active_days,
        average_per_day=average_per_day,
        latest_timestamp=latest_timestamp,
        peak_day=peak_day,
    )

    # 최종적으로 템플릿과 JSON에서 바로 쓸 수 있는 요약 객체를 만든다.
    summary = ActivitySummary(
        window_days=window_days,
        generated_at=datetime.now(),
        total_count=total_count,
        login_count=login_count,
        analysis_count=analysis_count,
        matching_count=matching_count,
        active_days=active_days,
        average_per_day=average_per_day,
        latest_timestamp=latest_timestamp,
        latest_label=latest_timestamp.strftime(DATETIME_LABEL_FORMAT) if latest_timestamp else None,
        peak_day=peak_day,
        cards=cards,
        daily_counts=daily_counts,
        breakdown=_build_breakdown(login_count, analysis_count, matching_count),
    )

    return summary.to_dict()


def build_activity_window_label(window_days: int) -> str:
    """기간 표시용 짧은 라벨을 만든다."""

    return f"최근 {max(window_days, 1)}일"


def merge_activity_counts(*collections: Sequence[Any]) -> Dict[str, int]:
    """여러 활동 묶음의 개수를 합쳐서 돌려준다."""

    counts = [len(_as_iterable(collection)) for collection in collections]
    result = {
        "group_1": counts[0] if len(counts) > 0 else 0,
        "group_2": counts[1] if len(counts) > 1 else 0,
        "group_3": counts[2] if len(counts) > 2 else 0,
    }
    result["total"] = sum(result.values())
    return result


def build_activity_export_payload(
    login_activities: Optional[Sequence[Any]],
    analysis_activities: Optional[Sequence[Any]],
    matching_activities: Optional[Sequence[Any]],
    window_days: int = 30,
) -> Dict[str, Any]:
    """CSV, JSON, 웹훅 내보내기용 평평한 구조를 만든다."""

    summary = build_activity_summary(
        login_activities=login_activities,
        analysis_activities=analysis_activities,
        matching_activities=matching_activities,
        window_days=window_days,
    )

    return {
        "window_days": summary["window_days"],
        "generated_at": summary["generated_at"],
        "total_count": summary["total_count"],
        "login_count": summary["login_count"],
        "analysis_count": summary["analysis_count"],
        "matching_count": summary["matching_count"],
        "active_days": summary["active_days"],
        "average_per_day": summary["average_per_day"],
        "latest_label": summary["latest_label"],
        "peak_day": summary["peak_day"],
        "daily_counts": summary["daily_counts"],
        "cards": summary["cards"],
        "breakdown": summary["breakdown"],
    }


__all__ = [
    "ActivityCard",
    "ActivitySummary",
    "build_activity_export_payload",
    "build_activity_summary",
    "build_activity_window_label",
    "merge_activity_counts",
]