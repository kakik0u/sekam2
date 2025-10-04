"""
管理者向けコマンド
/overload, /sync
"""

from typing import Optional
import discord
from bot import tree

from spam.protection import is_overload_allowed
from core.zichi import enforce_zichi_block
from core.log import insert_command_log, handle_command_error
from config import OVERLOAD_MODE


async def setup_admin_commands(tree, client):
    """
    管理者コマンドを登録

    Args:
        tree: Discord CommandTree インスタンス
        client: Discord Client インスタンス (未使用だが統一のため)
    """

    @tree.command(
        name="overload", description="過負荷モードのON/OFFを切り替えます（管理者専用）"
    )
    @discord.app_commands.allowed_installs(guilds=True, users=True)
    async def overload(ctx: discord.Interaction, enable: Optional[bool] = None):
        import config

        try:
            if await enforce_zichi_block(ctx, "/overload"):
                return
            if int(getattr(ctx.user, "id", 0) or 0) != 668479297551466516:
                await ctx.response.send_message(
                    "テメーの頭が高負荷だろ。", ephemeral=True
                )
                insert_command_log(ctx, "/overload", "DENY")
                return

            if enable is None:
                config.OVERLOAD_MODE = not config.OVERLOAD_MODE
            else:
                config.OVERLOAD_MODE = bool(enable)

            state = "ON (専科限定)" if config.OVERLOAD_MODE else "OFF (制限なし)"
            await ctx.response.send_message(
                f"過負荷モードを {state} にしました。", ephemeral=True
            )
            insert_command_log(ctx, "/overload", f"OK:{state}")
        except Exception as e:
            await handle_command_error(ctx, "/overload", e)

    @tree.command(name="sync", description="使用禁止/CTをDiscord側へ同期申請")
    @discord.app_commands.allowed_installs(guilds=True, users=True)
    async def sync(ctx: discord.Interaction):
        try:
            if await enforce_zichi_block(ctx, "/sync"):
                return
            if int(getattr(ctx.user, "id", 0) or 0) != 668479297551466516:
                await ctx.response.send_message(
                    "使用禁止っつったよな？", ephemeral=True
                )
                insert_command_log(ctx, "/sync", "DENY")
                return

            await tree.sync()
            await ctx.response.send_message("コマンドを同期しました。", ephemeral=True)
            insert_command_log(ctx, "/sync", "OK")
        except Exception as e:
            await handle_command_error(
                ctx, "/sync", e, "コマンド同期中にエラーが発生しました。"
            )
