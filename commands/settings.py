"""
設定コマンド群
/setting log, /setting ban, /setting blacklist
"""

import discord
from discord import app_commands, Client

from discord.ext import commands
from discord.app_commands import guild_only, allowed_contexts, allowed_installs

from core.zichi import enforce_zichi_block
from core.log import insert_command_log
from spam.settings import set_setting_value


async def setup_settings_commands(tree: app_commands.CommandTree, client: Client):
    """
    設定コマンド群を登録

    Args:
        tree: Discord CommandTree インスタンス
        client: Discord Client インスタンス
    """

    class setting(app_commands.Group):
        """設定コマンドグループ"""

        def __init__(self, bot: commands.Bot):
            super().__init__()
            self.bot = bot

        @app_commands.command(name="log", description="ログチャンネルを指定できます。")
        @guild_only
        @allowed_contexts(guilds=True, dms=False, private_channels=False)
        @allowed_installs(guilds=True, users=False)
        @app_commands.describe(
            channel="ログを送信するチャンネル(Botが見えている必要があります。)"
        )
        async def logchsetting(
            self, ctx: discord.Interaction, channel: discord.TextChannel
        ):
            if await enforce_zichi_block(ctx, "/setting log"):
                return
            if ctx.guild is None:
                await ctx.response.send_message(
                    "このコマンドはサーバー内でのみ実行できます。", ephemeral=True
                )
                insert_command_log(ctx, "/setting log", "DENY_NO_GUILD")
                return
            if not ctx.is_guild_integration():
                await ctx.response.send_message(
                    "このコマンドはサーバーに導入されたときのみ使えますよ。",
                    ephemeral=True,
                )
                insert_command_log(ctx, "/setting log", "DENY_NOT_INSTALLED")
                return
            if not ctx.user.guild_permissions.administrator:
                await ctx.response.send_message(
                    "管理者権限がないのに設定変更しようだなんて、貴様もしやスパムか！？？！？！？",
                    ephemeral=True,
                )
                insert_command_log(ctx, "/setting log", "DENY_PERM")
                return

            chid = int(channel.id)
            ok = set_setting_value(ctx.guild.id, "logchannel", chid)
            view = discord.ui.View()
            button = discord.ui.Button(
                style=discord.ButtonStyle.danger,
                label="ログ送信をテストする",
                custom_id="logtest",
            )
            view.add_item(button)
            msg = "設定されました。" if ok else "設定に失敗しました。"
            await ctx.response.send_message(msg, view=view, ephemeral=True)
            insert_command_log(ctx, "/setting log", "OK" if ok else "NG")

        @app_commands.command(name="ban", description="BANするかしないか")
        @guild_only
        @allowed_contexts(guilds=True, dms=False, private_channels=False)
        @allowed_installs(guilds=True, users=False)
        @app_commands.describe(setting="初期設定ではキックになっています。")
        @app_commands.choices(
            setting=[
                app_commands.Choice(name="BANする", value="on"),
                app_commands.Choice(name="キックで許す(BANしない)", value="off"),
            ]
        )
        async def bansetting(self, ctx: discord.Interaction, setting: str):
            if await enforce_zichi_block(ctx, "/setting ban"):
                return
            if ctx.guild is None:
                await ctx.response.send_message(
                    "このコマンドはサーバー内でのみ実行できます。", ephemeral=True
                )
                insert_command_log(ctx, "/setting ban", "DENY_NO_GUILD")
                return
            if not ctx.is_guild_integration():
                await ctx.response.send_message(
                    "このコマンドはサーバーに導入されたときのみ使えますよ。",
                    ephemeral=True,
                )
                insert_command_log(ctx, "/setting ban", "DENY_NOT_INSTALLED")
                return
            if not ctx.user.guild_permissions.administrator:
                await ctx.response.send_message(
                    "管理者権限がないのに設定変更しようだなんて、貴様もしやスパムか！？？！？！？",
                    ephemeral=True,
                )
                insert_command_log(ctx, "/setting ban", "DENY_PERM")
                return

            choice = str(setting)
            ok = set_setting_value(
                ctx.guild.id, "ban", True if choice == "on" else False
            )
            message1 = "設定されました。" if ok else "設定に失敗しました。"
            if choice == "on":
                message1 += "BANには追加権限が必要なことがあります。初回の場合は[このボタン](https://discord.com/oauth2/authorize?client_id=1406588918387703859&permissions=35910&integration_type=0&scope=bot)から追加権限を付与してください。"
            await ctx.response.send_message(message1, ephemeral=True)
            insert_command_log(ctx, "/setting ban", "OK" if ok else "NG")

        @app_commands.command(
            name="blacklist", description="ブラックリストに参加するかを設定できます。"
        )
        @guild_only
        @allowed_contexts(guilds=True, dms=False, private_channels=False)
        @allowed_installs(guilds=True, users=False)
        @app_commands.describe(setting="初期設定ではオンになっています。")
        @app_commands.choices(
            setting=[
                app_commands.Choice(name="ブラックリストに参加します", value="on"),
                app_commands.Choice(name="ブラックリストに参加しません", value="off"),
            ]
        )
        async def blacklist(self, ctx: discord.Interaction, setting: str):
            if await enforce_zichi_block(ctx, "/setting blacklist"):
                return
            if ctx.guild is None:
                await ctx.response.send_message(
                    "このコマンドはサーバー内でのみ実行できます。", ephemeral=True
                )
                insert_command_log(ctx, "/setting blacklist", "DENY_NO_GUILD")
                return
            if not ctx.is_guild_integration():
                await ctx.response.send_message(
                    "このコマンドはサーバーに導入されたときのみ使えますよ。",
                    ephemeral=True,
                )
                insert_command_log(ctx, "/setting blacklist", "DENY_NOT_INSTALLED")
                return
            if not ctx.user.guild_permissions.administrator:
                await ctx.response.send_message(
                    "管理者権限がないのに設定変更しようだなんて、貴様もしやスパムか！？？！？！？",
                    ephemeral=True,
                )
                insert_command_log(ctx, "/setting blacklist", "DENY_PERM")
                return

            choice = str(setting)
            ok = set_setting_value(
                ctx.guild.id, "blacklist", True if choice == "on" else False
            )
            msg = "設定されました。" if ok else "設定に失敗しました。"
            await ctx.response.send_message(msg, ephemeral=True)
            insert_command_log(ctx, "/setting blacklist", "OK" if ok else "NG")

    bot = commands.Bot
    tree.add_command(setting(bot))
