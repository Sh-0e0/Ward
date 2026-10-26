"""전력 점수 = 티어 30% + 내전 성적(승률 + KDA) 70%"""

TIER_WEIGHT = 0.3
MATCH_WEIGHT = 0.7
K = 5  # 보정 강도: 판수가 K와 같아지면 실제 성적과 티어가 절반씩 반영됨


def kda_value(kills: int, deaths: int, assists: int) -> float:
    return (kills + assists) / max(deaths, 1)


def match_score(wins: int, games: int, kda_avg: float, tier_score: float) -> float:
    if games == 0:
        return tier_score  # 기록이 없으면 티어 점수를 그대로 사용
    win_score = wins / games * 100
    kda_score = max(0.0, min(100.0, (kda_avg - 1) / 4 * 100))  # KDA 1 -> 0점, 5 이상 -> 100점
    raw = win_score * 0.5 + kda_score * 0.5
    return (games * raw + K * tier_score) / (games + K)


def power(tier_score: float, wins: int, games: int, kda_avg: float) -> float:
    ms = match_score(wins, games, kda_avg, tier_score)
    return tier_score * TIER_WEIGHT + ms * MATCH_WEIGHT
