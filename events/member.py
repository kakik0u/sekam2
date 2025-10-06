"""
on_member_join イベントハンドラ
"""

import os
import discord
import requests

from config import debug
from database.connection import run_db_query
from spam.protection import spamban
from spam.settings import get_setting_value
from core.log import insert_log


def setup_member_events(client: discord.Client):
    """
    on_member_join イベントを登録

    Args:
        client: Discord Client インスタンス
    """

    @client.event
    async def on_member_join(member):
        # Botは除外
        if member.bot:
            print("bot")
            return

        skip = False

        url = (
            f"https://discord.com/api/v10/guilds/518371205452005387/members/{member.id}"
        )
        headers = {"Authorization": os.getenv("SENKATOKEN")}
        response = requests.get(url, headers=headers)

        if response.status_code == 404:
            status = "spam"
            await spamban(client, member, status)
            skip = True
            print("spamreturnon")
            return
        elif response.status_code == 401:
            print("Unauthorized!!!!!!!")

        print("blackliststart")

        try:
            configblack = get_setting_value(member.guild.id, "blacklist")
        except Exception as e:
            if debug:
                print(f"設定取得エラー(blacklist): {e}")
            configblack = True

        if configblack is False or skip is True:
            pass
        else:
            print("blackliststart")
            try:
                row = run_db_query(
                    "SELECT 1 FROM blacklist WHERE id = %s LIMIT 1",
                    (member.id,),
                    fetch="one",
                )
            except Exception as e:
                if debug:
                    print(f"ブラックリスト存在確認エラー: {e}")
                row = None

            if row:
                print("blacklist!!!")
                status = "blacklist"
                await spamban(client, member, status)
                return

        status = "senka"

        try:
            logchannelid = get_setting_value(member.guild.id, "logchannel")
        except Exception as e:
            if debug:
                print(f"設定取得エラー(join logchannel): {e}")
            logchannelid = 0

        if logchannelid not in (0, None):
            logch = client.get_channel(int(logchannelid))
            if logch:
                try:
                    await logch.send(
                        f"{member.display_name}(DiscordID:{member.id})は専科にいます！やったー！"
                    )
                except Exception:
                    print("LOGSEND ERROR")
                    insert_log(
                        member,
                        result="PASS",
                        error="ログチャンネルへの送信に失敗しました。",
                    )

        insert_log(member, result="PASS")
