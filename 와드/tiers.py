"""와일드리프트 티어 -> 점수(0~100) 환산"""

TIERS = ["아이언", "브론즈", "실버", "골드", "플래티넘", "에메랄드", "다이아몬드",
         "마스터", "그랜드마스터", "챌린저"]

# 마스터 이상은 단계가 없고, 격차를 조금 더 벌려서 점수화
_TOP_POINTS = {"마스터": 30, "그랜드마스터": 33, "챌린저": 36}
MAX_POINTS = 36


def has_division(tier: str) -> bool:
    return tier not in _TOP_POINTS


def tier_points(tier: str, division: int) -> int:
    """아이언 4 = 0점 ... 다이아몬드 1 = 27점, 마스터 30, 그마 33, 챌 36"""
    if tier in _TOP_POINTS:
        return _TOP_POINTS[tier]
    return TIERS.index(tier) * 4 + (4 - division)


def tier_score(tier: str, division: int) -> float:
    return tier_points(tier, division) / MAX_POINTS * 100


def tier_label(tier: str, division: int) -> str:
    return tier if not has_division(tier) else f"{tier} {division}"
