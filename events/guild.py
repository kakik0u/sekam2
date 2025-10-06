"""
on_guild_join イベントハンドラ
"""

import discord


def setup_guild_events(client: discord.Client):
    """
    on_guild_join イベントを登録

    Args:
        client: Discord Client インスタンス
    """

    @client.event
    async def on_guild_join(guild):
        owner = guild.owner
        greeting_message = (
            "こんにちは、SEKAM2です。\n"
            "サーバーへの採用ありがとうございます。\n"
            "説明が必要な機能が3つあるので説明させてください。"
        )

        embed = discord.Embed(
            title="検出ログ機能",
            description="サーバーの入室者が専科民かどうかを逐一報告する機能です。",
        )
        embed.add_field(
            name="設定方法",
            value="/setting log コマンドをサーバー内で実行し、ログを送信するチャンネルを選択します。(ユーザーに見られないところで実行したほうがいいかも？)",
            inline=True,
        )

        embed2 = discord.Embed(
            title="BAN機能", description="スパムの処し方を選べます。"
        )
        embed2.add_field(
            name="設定方法",
            value="/setting ban コマンドをサーバー内で実行し、処理を選びます(キックかBANか)。",
            inline=True,
        )

        embed3 = discord.Embed(
            title="ブラックリスト機能", description="国際指名手配機能をオフにできます"
        )
        embed3.add_field(
            name="設定方法",
            value="/setting blacklist コマンドをサーバー内で実行し、ONかOFFを選びます(初期設定ではオン)。",
            inline=True,
        )

        try:
            await owner.send(content=greeting_message, embeds=[embed, embed2, embed3])
            await owner.send(
                "よくある勘違いとして「すでにいるメンバーも専科から抜けると自動でキックされる」というものがありますが"
                "そのような機能はありません(50人規模のサーバーでないと現実的ではない)\n"
                "また、Sekamの制限を外したいときは私をキックしてください。\n"
                "私のアイコンをクリックしたら下くらいにある「アプリを追加」から簡単に再追加できます。\n"
                "[プライバシーポリシー](https://death.kakikou.app/sekam/privacy/ )を一応書いてますが"
                "個人情報を集める機能がそもそも備わってないので気にしなくて大丈夫だと思います。"
                "気にする必要が出てきたら場合また連絡します。\n"
                "最後に、お問い合わせとか機能の要望とか、誤検知などはこのDMに送られても気づけないので"
                "開発者(DiscordID:@kakik0u)に連絡して下さい。"
            )
            print(f"サーバー {guild.name} のオーナー {owner.name} にDMを送信しました。")
        except discord.HTTPException:
            print(
                f"サーバー {guild.name} のオーナー {owner.name} にDMを送信できませんでした。"
            )
