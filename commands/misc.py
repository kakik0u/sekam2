"""
その他のコマンド
/wick, /zichi
"""

import discord
from discord import app_commands, Client
from discord.app_commands import allowed_installs

from core.zichi import insert_zichi_request
from core.log import insert_command_log
from config import debug


async def setup_misc_commands(tree: app_commands.CommandTree, client: Client):
    """
    その他のコマンドを登録

    Args:
        tree: Discord CommandTree インスタンス
        client: Discord Client インスタンス (未使用だが統一のため)
    """

    @tree.command(name="zichi", description="自治できますよ")
    @allowed_installs(guilds=True, users=True)
    async def zichi(ctx: discord.Interaction):
        print("zichiコマンドが実行されました")
        try:
            if ctx.user.id == 512942239153127425:
                await ctx.response.send_message(
                    "<@668479297551466516> 品田さんがお呼びだぞ"
                )
                insert_command_log(ctx, "/zichi", "SHINADA")
                return

            channel = getattr(ctx, "channel", None)
            if not isinstance(channel, discord.Thread):
                await ctx.response.send_message(
                    "おめーがチャンネルを自治できるとでも思ってんのか？？？"
                )
                insert_command_log(ctx, "/zichi", "CHANNEL")
                return

            guild = getattr(ctx, "guild", None)
            if not guild or int(getattr(guild, "id", 0) or 0) != 518371205452005387:
                await ctx.response.send_message(
                    "鯖主に言って自治してもらいなさい", ephemeral=True
                )
                insert_command_log(ctx, "/zichi", "NOTSENKA")
                return

            class ZichiReasonModal(discord.ui.Modal, title="自治申請"):
                reason_input = discord.ui.TextInput(
                    label="SEKAM2を禁止する理由",
                    placeholder="理由を入力",
                    style=discord.TextStyle.paragraph,
                    max_length=500,
                )

                async def on_submit(self, interaction: discord.Interaction):
                    r = str(self.reason_input.value).strip()[:500]
                    ok = insert_zichi_request(
                        channel.id, interaction.user.id, r or "(空)"
                    )
                    msg = "スレ主であることの確認が手動であるため、反映に時間がかかります。ご了承ください。また、解除する場合はもう一度/zichiを実行してください。"
                    if not interaction.response.is_done():
                        await interaction.response.send_message(msg, ephemeral=True)
                    else:
                        await interaction.followup.send(msg, ephemeral=True)
                    insert_command_log(interaction, "/zichi", "OK" if ok else "NG")

                async def on_error(
                    self, interaction: discord.Interaction, error: Exception
                ) -> None:
                    if debug:
                        print(f"zichi modal error: {error}")
                    if not interaction.response.is_done():
                        await interaction.response.send_message(
                            "エラーが発生しました。", ephemeral=True
                        )
                    else:
                        await interaction.followup.send(
                            "エラーが発生しました。", ephemeral=True
                        )
                    insert_command_log(interaction, "/zichi", f"ERROR:{error}")

            await ctx.response.send_modal(ZichiReasonModal())
        except Exception as e:
            if debug:
                print(f"zichiコマンドエラー: {e}")
            if not ctx.response.is_done():
                await ctx.response.send_message(
                    "エラーが発生しました。", ephemeral=True
                )
            else:
                await ctx.followup.send("エラーが発生しました。", ephemeral=True)
            insert_command_log(ctx, "/zichi", f"ERROR:{e}")

    @tree.command(
        name="wick",
        description="Wickの制限を回避してメッセージを送信できます。メッセージ内容についてSEKAM2は一切の責任の負いません。",
    )
    @allowed_installs(guilds=True, users=True)
    async def wick(ctx: discord.Interaction, message: str):
        print(f"wickコマンドが実行されました: {ctx.user.name} ({ctx.user.id})")
        if "菊池真" in message or "2W African Drumming IMG 0001" in message:
            await ctx.response.send_message(
                "こんなこと言えるわけ無いだろ", ephemeral=True
            )
            insert_command_log(ctx, "/wick", "BlackListWord")
            return
        await ctx.response.send_message(
            f"Wickの制限を回避するためSEKAMがお届けします。\n{message}\n\n"
            f"上記のメッセージについてSEKAM2は一切の責任を負いません。コマンドを実行したユーザーが責任を負います。"
        )
        insert_command_log(ctx, "/wick", f"OK message:{message}")
