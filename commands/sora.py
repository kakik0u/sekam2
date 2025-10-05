"""
/sora コマンド
AI動画の検索・ランキング・ランダム再生機能
"""

import discord

import config
from core.log import insert_command_log

from .sora_components import MainMenuView


async def setup_sora_commands(
    tree: discord.app_commands.CommandTree, client: discord.Client
):
    """
    soraコマンドを登録

    Args:
        tree: Discord CommandTree インスタンス
        client: Discord Client インスタンス
    """

    @tree.command(name="sora", description="AI動画を検索・ランキング・ランダム再生")
    async def sora(interaction: discord.Interaction):
        """
        /sora コマンド
        AI動画の検索・ランキング・ランダム再生のメインメニューを表示
        """
        try:
            # MainMenuViewを作成
            view = MainMenuView()

            # 初期メッセージを送信
            embed = discord.Embed(
                title="🌌 AI動画検索ツール",
                description=(
                    "AI動画の検索・ランキング・ランダム再生ができます。\n"
                    "それぞれの動画にユーザーがタグ(例:オリジナル/恐山)やタイトルをつけられます。\n"
                    "下のボタンから操作を選択してください。"
                ),
                color=discord.Color.blue(),
            )

            embed.add_field(
                name="🏆 ランキングを表示する",
                value="リアクション数でランキングを表示します",
                inline=False,
            )
            embed.add_field(
                name="🔍 検索する",
                value="タグやリアクション数で動画を検索します",
                inline=False,
            )
            embed.add_field(
                name="🎲 ランダムで再生",
                value="ランダムに動画を再生します",
                inline=False,
            )
            embed.add_field(
                name="🏷️ タグ一覧",
                value="登録されているタグを一覧表示します",
                inline=False,
            )
            embed.add_field(
                name="🔢 IDで視聴",
                value="動画ID（メッセージID）を指定して視聴します",
                inline=False,
            )

            await interaction.response.send_message(
                embed=embed, view=view, ephemeral=True
            )

            # コマンドログを記録
            insert_command_log(interaction, "/sora", "OK")

            if config.debug:
                print(f"/sora コマンド実行: user={interaction.user.id}")

        except Exception as e:
            # エラーログを記録
            insert_command_log(interaction, "/sora", f"ERROR:{e}")

            if config.debug:
                print(f"/sora コマンドエラー: {e}")
            await interaction.response.send_message(
                "エラーが発生しました。もう一度お試しください。",
                ephemeral=True,
            )
