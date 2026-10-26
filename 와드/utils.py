import discord

TEAM_NAMES = {"blue": "🔵 블루", "red": "🔴 레드"}


def can_manage(interaction: discord.Interaction, host_id: int) -> bool:
    """방장이거나 서버 관리 권한이 있으면 True"""
    return interaction.user.id == host_id or interaction.permissions.manage_guild
