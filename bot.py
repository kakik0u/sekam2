"""
SEKAM2 Bot インスタンス管理
Discord Botのクライアントとコマンドツリーを管理
"""

import discord
from discord import app_commands
import aiodns
from aiohttp import ClientSession, TCPConnector

intents = discord.Intents.all()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


async def setup_custom_dns():
    """
    カスタムDNSリゾルバを設定する非同期関数
    Google Public DNSを使用してDNS解決を行う
    """
    gpd = ["8.8.8.8", "8.8.4.4"]
    resolver = aiodns.DNSResolver(nameservers=gpd)
    connector = TCPConnector(resolver=resolver)
    session = ClientSession(connector=connector)
    client.http.session = session
    print("カスタムDNS設定を適用しました。")
