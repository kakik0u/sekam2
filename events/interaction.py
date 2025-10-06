"""
on_interaction イベントハンドラ
"""

import discord

from config import debug
from spam.settings import get_setting_value
from core.log import insert_command_log


def setup_interaction_events(client: discord.Client):
    """
    on_interaction イベントを登録

    Args:
        client: Discord Client インスタンス
    """

    @client.event
    async def on_interaction(inter: discord.Interaction):
        try:
            if inter.data["component_type"] == 2:
                await on_button_click(inter)
        except KeyError:
            pass

    async def on_button_click(inter: discord.Interaction):
        custom_id = inter.data["custom_id"]

        if custom_id == "logtest":
            try:
                logchannelid = get_setting_value(inter.guild.id, "logchannel")
            except Exception as e:
                if debug:
                    print(f"設定取得エラー(logtest): {e}")
                logchannelid = 0

            if not logchannelid:
                await inter.response.send_message(
                    "ログチャンネルが設定されていません。/setting log で設定してください。",
                    ephemeral=True,
                )
                insert_command_log(inter, "button:logtest", "NO_LOGCH")
                return

            logch = client.get_channel(int(logchannelid))
            try:
                await logch.send("テスト送信")
                await inter.response.send_message("ちゃんと動きました", ephemeral=True)
                insert_command_log(inter, "button:logtest", "OK")
            except Exception:
                await inter.response.send_message(
                    "エラーが発生しました。SEKAMがそのチャンネルを見ること/送信することができるかご確認ください。",
                    ephemeral=True,
                )
                insert_command_log(inter, "button:logtest", "NG")
