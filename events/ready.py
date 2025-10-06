"""
on_ready イベントハンドラ
"""

import discord

from bot import setup_custom_dns
from fileutil import loadtxt


def setup_ready_event(client: discord.Client):
    """
    on_ready イベントを登録

    Args:
        client: Discord Client インスタンス
    """

    @client.event
    async def on_ready():
        print("SEKAM2起動したンゴねぇ")
        await setup_custom_dns()

        # await tree.sync()
        print("SyncEnd")

        spamer = loadtxt("spamer.txt")
        await client.change_presence(
            activity=discord.CustomActivity(name=f"やっつけたスパム:{spamer}人")
        )
        print("Bot準備完了")
