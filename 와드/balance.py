"""내전 팀 조합 추천: 전력 균형 + 라인 선호를 함께 고려"""
import math
import random
from dataclasses import dataclass
from itertools import combinations, permutations

LANES = ["탑", "정글", "미드", "원딜", "서폿"]

SUB_LANE_PENALTY = 2.0    # 고른 라인이지만 주 라인은 아닐 때
OFF_LANE_PENALTY = 15.0   # 고르지 않은 라인에 배치될 때
LANE_DIFF_WEIGHT = 0.3    # 라인별 매치업 격차 반영 비중
ASSIGN_KEEP = 6           # 팀마다 라인 배치 후보를 몇 개까지 볼지
WIN_PROB_SCALE = 10.0     # 예상 승률 곡선 완만함 (클수록 완만)


@dataclass(frozen=True)
class Player:
    user_id: int
    name: str
    power: float
    main_lane: str
    lanes: tuple  # 플레이 가능한 라인들


@dataclass
class Candidate:
    blue: tuple  # LANES 순서대로 5명
    red: tuple
    score: float  # 낮을수록 좋음


def lane_penalty(p: Player, lane: str) -> float:
    if lane in p.lanes:
        return 0.0 if lane == p.main_lane else SUB_LANE_PENALTY
    return OFF_LANE_PENALTY


def _best_assignments(team):
    options = []
    for perm in permutations(team):
        pen = sum(lane_penalty(p, LANES[i]) for i, p in enumerate(perm))
        options.append((pen, perm))
    options.sort(key=lambda x: x[0])
    return options[:ASSIGN_KEEP]


def recommend(players, top_n: int = 12, rng=None):
    """10명을 5:5로 나누고 라인을 배치한 추천 조합을 점수 순으로 반환"""
    if len(players) != 10:
        raise ValueError("10명이 필요합니다")
    rng = rng or random
    players = list(players)
    rng.shuffle(players)

    best_per_split = {}
    for combo in combinations(range(1, 10), 4):  # 0번 선수는 항상 한쪽에 고정해 중복 제거
        blue_idx = (0,) + combo
        blue = [players[i] for i in blue_idx]
        red = [players[i] for i in range(10) if i not in blue_idx]
        power_gap = abs(sum(p.power for p in blue) - sum(p.power for p in red))

        best = None
        for pen_b, ab in _best_assignments(blue):
            for pen_r, ar in _best_assignments(red):
                lane_gap = sum(abs(ab[i].power - ar[i].power) for i in range(5))
                score = power_gap + LANE_DIFF_WEIGHT * lane_gap + pen_b + pen_r
                if best is None or score < best.score:
                    best = Candidate(ab, ar, score)
        best_per_split[blue_idx] = best

    ranked = sorted(best_per_split.values(), key=lambda c: c.score)[:top_n]
    result = []
    for c in ranked:  # 블루/레드 진영은 무작위로 섞기
        result.append(Candidate(c.red, c.blue, c.score) if rng.random() < 0.5 else c)
    return result


def blue_win_prob(c: Candidate) -> float:
    diff = sum(p.power for p in c.blue) / 5 - sum(p.power for p in c.red) / 5
    return 1 / (1 + math.exp(-diff / WIN_PROB_SCALE))
