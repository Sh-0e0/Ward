import os

import discord
from discord import app_commands
from dotenv import load_dotenv

import analysis
import champions
import db
from balance import LANES
from profile_edit import compute_edit
from recruit import RecruitView
from result import ResultView, build_result_embed
from scoring import power
from tiers import TIERS, has_division, tier_label, tier_score

load_dotenv()

TIER_CHOICES = [app_commands.Choice(name=t, value=t) for t in TIERS]
DIVISION_CHOICES = [app_commands.Choice(name=f"{n}단계", value=n) for n in (4, 3, 2, 1)]
LANE_CHOICES = [app_commands.Choice(name=l, value=l) for l in LANES]
SUB_LANE_CHOICES = LANE_CHOICES + [app_commands.Choice(name="없음 (삭제)", value="none")]
CHAMP_LANE_CHOICES = LANE_CHOICES + [app_commands.Choice(name="전체", value="all")]


class WildRiftBot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        db.init_db()
        guild_id = os.getenv("GUILD_ID")
        if guild_id:  # 테스트 서버를 지정하면 명령어가 바로 반영됨
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()


bot = WildRiftBot()


# ---------- 도움말 ----------
def build_help_embed() -> discord.Embed:
    embed = discord.Embed(title="📖 와일드리프트 내전 도우미 사용법", color=0x5865F2)
    embed.add_field(name="🚀 이렇게 시작하세요", value=(
        "1. `/티어등록` 으로 내 티어와 라인 등록 (처음 한 번)\n"
        "2. `/내전모집` 으로 10명 모집 → 참가 버튼\n"
        "3. 방장이 `팀 짜기` → 마음에 들면 `이 팀으로 내전 시작`\n"
        "4. 내전이 끝나면 `/게임끝` 으로 승패와 KDA 입력 → 방장이 `결과 확정`"), inline=False)
    embed.add_field(name="📋 명령어", value=(
        "`/티어등록` 티어·라인 등록 (다시 하면 덮어써요)\n"
        "`/정보수정` 바뀐 항목만 골라서 수정\n"
        "`/내정보 [유저]` 티어, 전적, 전력 점수 확인\n"
        "`/랭킹` 전력 점수 TOP 10\n"
        "`/내전모집 [제목]` 내전 참가자 10명 모집\n"
        "`/게임끝 [내전번호]` 내전 결과 입력\n"
        "`/챔피언추천 [라인] [개수]` 재미용 랜덤 챔피언\n"
        "`/도움말` 이 안내"), inline=False)
    embed.add_field(name="🧮 전력 점수란?", value=(
        "티어 30% + 내전 성적(승률·KDA) 70%예요. 내전 기록이 쌓일수록 실제 성적이 더 많이 반영돼요."),
        inline=False)
    embed.add_field(name="💡 알아두세요", value=(
        "- KDA는 **누구나 누구 것이든** 입력할 수 있어요 (✏️ = 입력한 사람)\n"
        "- 승리 팀 선택은 누구나, **결과 확정은 방장만** 할 수 있어요\n"
        "- 같은 주 라인이 이미 2명이면 참가 전에 한 번 더 물어봐요"), inline=False)
    return embed


@bot.tree.command(name="도움말", description="봇 사용법과 명령어 목록을 보여줍니다")
async def help_cmd(interaction: discord.Interaction):
    await interaction.response.send_message(embed=build_help_embed(), ephemeral=True)


# ---------- 티어 등록 / 수정 / 내 정보 ----------
@bot.tree.command(name="티어등록", description="내 티어와 라인을 등록합니다")
@app_commands.describe(tier="현재 티어", main_lane="주 라인",
                       division="단계 (마스터 이상은 생략)", sub_lane="부 라인 (선택)")
@app_commands.rename(tier="티어", main_lane="주라인", division="단계", sub_lane="부라인")
@app_commands.choices(tier=TIER_CHOICES, main_lane=LANE_CHOICES,
                      division=DIVISION_CHOICES, sub_lane=LANE_CHOICES)
async def register(interaction: discord.Interaction,
                   tier: app_commands.Choice[str],
                   main_lane: app_commands.Choice[str],
                   division: app_commands.Choice[int] | None = None,
                   sub_lane: app_commands.Choice[str] | None = None):
    if has_division(tier.value) and division is None:
        await interaction.response.send_message(
            f"{tier.value}는 단계(1~4)를 같이 선택해 주세요.", ephemeral=True)
        return
    if sub_lane and sub_lane.value == main_lane.value:
        await interaction.response.send_message("주 라인과 부 라인이 같아요.", ephemeral=True)
        return

    div = division.value if division and has_division(tier.value) else 0
    db.upsert_user(interaction.user.id, interaction.user.display_name, tier.value, div,
                   main_lane.value, sub_lane.value if sub_lane else None)
    await interaction.response.send_message(
        f"{interaction.user.mention} 등록 완료! **{tier_label(tier.value, div)}** / "
        f"{main_lane.value}" + (f" (부: {sub_lane.value})" if sub_lane else ""))


@bot.tree.command(name="정보수정", description="등록한 티어/라인 중 바뀐 것만 골라서 수정합니다")
@app_commands.describe(tier="바뀐 티어", division="바뀐 단계 (마스터 이상은 생략)",
                       main_lane="바뀐 주 라인", sub_lane="바뀐 부 라인 ('없음'을 고르면 삭제)")
@app_commands.rename(tier="티어", division="단계", main_lane="주라인", sub_lane="부라인")
@app_commands.choices(tier=TIER_CHOICES, division=DIVISION_CHOICES,
                      main_lane=LANE_CHOICES, sub_lane=SUB_LANE_CHOICES)
async def edit_info(interaction: discord.Interaction,
                    tier: app_commands.Choice[str] | None = None,
                    division: app_commands.Choice[int] | None = None,
                    main_lane: app_commands.Choice[str] | None = None,
                    sub_lane: app_commands.Choice[str] | None = None):
    user = db.get_user(interaction.user.id)
    if user is None:
        await interaction.response.send_message("아직 등록 전이에요. 먼저 /티어등록 을 해 주세요.", ephemeral=True)
        return

    values, changes, error = compute_edit(
        user,
        tier=tier.value if tier else None,
        division=division.value if division else None,
        main_lane=main_lane.value if main_lane else None,
        sub_lane=sub_lane.value if sub_lane else None)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return

    db.upsert_user(interaction.user.id, interaction.user.display_name,
                   values["tier"], values["division"], values["main_lane"], values["sub_lane"])
    await interaction.response.send_message(
        f"{interaction.user.mention} 정보를 수정했어요.\n" + "\n".join(f"- {c}" for c in changes))


@bot.tree.command(name="내정보", description="등록된 티어와 내전 전력 점수를 확인합니다")
@app_commands.describe(member="확인할 유저 (비우면 본인)")
@app_commands.rename(member="유저")
async def my_info(interaction: discord.Interaction, member: discord.Member | None = None):
    target = member or interaction.user
    user = db.get_user(target.id)
    if user is None:
        await interaction.response.send_message(
            f"{target.display_name}님은 아직 /티어등록 을 하지 않았어요.", ephemeral=True)
        return

    ts = tier_score(user["tier"], user["division"])
    games, wins, kda_avg = db.get_stats(target.id)
    pw = power(ts, wins, games, kda_avg)

    embed = discord.Embed(title=f"{target.display_name}님의 정보", color=0x5865F2)
    embed.add_field(name="티어", value=tier_label(user["tier"], user["division"]))
    embed.add_field(name="라인", value=user["main_lane"] + (f" / {user['sub_lane']}" if user["sub_lane"] else ""))
    embed.add_field(name="내전 전적",
                    value=f"{games}판 {wins}승 {games - wins}패 · 평균 KDA {kda_avg:.2f}" if games else "기록 없음",
                    inline=False)
    embed.add_field(name="전력 점수", value=f"**{pw:.1f}** / 100 (티어 {ts:.1f})")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="랭킹", description="내전 전력 점수 상위 10명")
async def ranking(interaction: discord.Interaction):
    await interaction.response.send_message(embed=analysis.ranking_embed())


# ---------- 챔피언 추천 (재미용) ----------
@bot.tree.command(name="챔피언추천", description="재미로 보는 랜덤 챔피언 추천 (와일드리프트 챔피언만)")
@app_commands.describe(lane="라인 (비우면 내 주 라인, 등록 전이면 전체)", count="추천 개수 (1~5)")
@app_commands.rename(lane="라인", count="개수")
@app_commands.choices(lane=CHAMP_LANE_CHOICES)
async def champion_cmd(interaction: discord.Interaction,
                       lane: app_commands.Choice[str] | None = None,
                       count: app_commands.Range[int, 1, 5] = 3):
    if lane is None:
        user = db.get_user(interaction.user.id)
        lane_value = user["main_lane"] if user else None
    else:
        lane_value = None if lane.value == "all" else lane.value
    view = champions.ChampionView(interaction.user.id, lane_value, count)
    await interaction.response.send_message(embed=view.build_embed(), view=view)


# ---------- 내전 모집 / 게임 끝 ----------
@bot.tree.command(name="내전모집", description="와일드리프트 내전 참가자 10명을 모집합니다")
@app_commands.describe(title="모집글 제목 (선택)")
@app_commands.rename(title="제목")
@app_commands.guild_only()
async def recruit_cmd(interaction: discord.Interaction, title: str | None = None):
    view = RecruitView(interaction.user.id, (title or "와일드리프트 내전")[:60])
    await interaction.response.send_message(embed=view.build_embed(), view=view)
    msg = await interaction.original_response()
    view.channel = interaction.channel
    view.message_id = msg.id


@bot.tree.command(name="게임끝", description="내전 결과(승패, KDA)를 입력합니다")
@app_commands.describe(match_id="내전 번호 (비우면 가장 최근 진행 중인 내전)")
@app_commands.rename(match_id="내전번호")
@app_commands.guild_only()
async def game_end(interaction: discord.Interaction, match_id: int | None = None):
    if match_id is None:
        match = db.get_open_match(interaction.guild_id)
    else:
        match = db.get_match(match_id)
        if match is not None and (match["guild_id"] != interaction.guild_id or match["status"] != "open"):
            match = None
    if match is None:
        await interaction.response.send_message(
            "결과를 입력할 진행 중인 내전이 없어요. (/내전모집 으로 먼저 내전을 시작해 주세요)", ephemeral=True)
        return
    await interaction.response.send_message(
        embed=build_result_embed(match["id"]), view=ResultView(match["id"]))


if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise SystemExit(".env 파일에 DISCORD_TOKEN을 넣어 주세요.")
    bot.run(token)
