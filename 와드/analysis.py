"""전력 점수 계산, 팀 분석 임베드, 랭킹"""
import discord

import db
from balance import LANES, Candidate, Player, blue_win_prob
from scoring import power
from tiers import tier_label, tier_score


def user_power(user_id: int):
    user = db.get_user(user_id)
    if user is None:
        return None
    ts = tier_score(user["tier"], user["division"])
    games, wins, kda_avg = db.get_stats(user_id)
    return power(ts, wins, games, kda_avg)


def build_player(user_id: int, lanes) -> Player:
    user = db.get_user(user_id)
    return Player(user_id, user["name"], user_power(user_id), user["main_lane"], tuple(lanes))


def team_embed(c: Candidate, idx: int, total: int, title: str) -> discord.Embed:
    embed = discord.Embed(title=f"⚔️ {title} · 팀 추천 {idx + 1}/{total}", color=0x5865F2)
    avgs = {}
    for key, label, team in (("blue", "🔵 블루", c.blue), ("red", "🔴 레드", c.red)):
        avgs[key] = sum(p.power for p in team) / len(team)
        lines = [f"**{LANES[i]}** <@{p.user_id}> · {p.power:.1f}" for i, p in enumerate(team)]
        embed.add_field(name=f"{label} (평균 {avgs[key]:.1f})", value="\n".join(lines), inline=False)

    matchup = [
        f"{lane}: {c.blue[i].power:.1f} vs {c.red[i].power:.1f} ({c.blue[i].power - c.red[i].power:+.1f})"
        for i, lane in enumerate(LANES)
    ]
    embed.add_field(name="라인별 매치업 (블루 vs 레드)", value="\n".join(matchup), inline=False)

    wp = blue_win_prob(c)
    embed.add_field(
        name="📊 전력 분석",
        value=(f"평균 전력 차이 {abs(avgs['blue'] - avgs['red']):.1f}점\n"
               f"예상 승률(참고용) 🔵 {wp * 100:.0f}% / 🔴 {(1 - wp) * 100:.0f}%"),
        inline=False)

    warns = [f"⚠️ <@{p.user_id}> 님은 {LANES[i]}가 선택한 라인이 아니에요"
             for team in (c.blue, c.red) for i, p in enumerate(team) if LANES[i] not in p.lanes]
    if warns:
        embed.add_field(name="라인 주의", value="\n".join(warns), inline=False)
    return embed


def ranking_embed() -> discord.Embed:
    rows = []
    for u in db.list_users():
        rows.append((user_power(u["user_id"]), u))
    rows.sort(key=lambda x: -x[0])
    embed = discord.Embed(title="🏆 전력 점수 랭킹 TOP 10", color=0xFEE75C)
    if not rows:
        embed.description = "아직 등록된 유저가 없어요."
        return embed
    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for i, (pw, u) in enumerate(rows[:10]):
        games, wins, kda = db.get_stats(u["user_id"])
        record = f"{games}판 {wins}승 · KDA {kda:.2f}" if games else "내전 기록 없음"
        lines.append(f"{medals[i] if i < 3 else f'{i + 1}.'} <@{u['user_id']}> · **{pw:.1f}** "
                     f"({tier_label(u['tier'], u['division'])} / {record})")
    embed.description = "\n".join(lines)
    return embed
