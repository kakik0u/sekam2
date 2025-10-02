"""
ランキング関連のコマンド群
"""
import discord
from discord import app_commands

from core.zichi import enforce_zichi_block
from core.log import insert_command_log
from spam.protection import is_overload_allowed
from database.connection import run_statdb_query
from utils.cache import load_json_cache, save_json_cache, get_reference_data_label
from utils.emoji import normalize_emoji_and_variants
import config


async def setup_ranking_commands(tree: app_commands.CommandTree, client: discord.Client):
    """ランキングコマンドを登録"""
    
    @tree.command(name="grinrank", description="おもしろ専科民ランキング")
    @app_commands.allowed_installs(guilds=True, users=True)
    async def grinrank(ctx: discord.Interaction):
        if await enforce_zichi_block(ctx, "/grinrank"):
            return
        print(f"grinrankコマンドが実行されました: {ctx.user.name} ({ctx.user.id})")
        try:
            if not is_overload_allowed(ctx):
                await ctx.response.send_message("現在過負荷対策により専科外では使えません", ephemeral=True)
                insert_command_log(ctx, "/grinrank", "DENY_OVERLOAD")
                return
            await ctx.response.defer()

            user = getattr(ctx, "user", None) or getattr(ctx, "author", None)
            username = getattr(user, "display_name", None) or getattr(user, "name", str(user))
            uid = int(getattr(user, "id", 0) or 0)
            reference_label = get_reference_data_label()

            grin_rows = load_json_cache("grinrank.json", [])

            if not grin_rows:
                sql = (
                    "SELECT m.author_id, SUM(r.count) as grincount "
                    "FROM reactions r JOIN messages m ON r.message_id = m.id "
                    "WHERE r.emoji_name = 'grin' "
                    "GROUP BY m.author_id ORDER BY grincount DESC"
                )
                grin_rows = run_statdb_query(sql, (), fetch="all") or []
                try:
                    grin_rows = [[int(r[0]) if r and r[0] is not None else 0,
                                  int(r[1]) if r and r[1] is not None else 0] for r in grin_rows]
                except Exception:
                    grin_rows = []
                save_json_cache("grinrank.json", grin_rows)

            total = len(grin_rows)
            grincount = 0
            has_user = False
            for r in grin_rows:
                try:
                    aid = int(str(r[0])) if r[0] is not None else 0
                    cnt = int(r[1]) if r[1] is not None else 0
                except Exception:
                    continue
                if aid == uid:
                    grincount = cnt
                    has_user = True
                    break

            if total > 0 and has_user:
                outrank = sum(1 for r in grin_rows if (int(r[1]) if r[1] is not None else 0) < grincount)
                percent = int(outrank * 100 / total)
            else:
                percent = 0

            if total == 0 or not has_user:
                embed = discord.Embed(title=f"ランク外、0個の:grin:")
                embed.description = f"対象期間内にデータがありませんでした。\nある意味、人生としてはユーザーの100%を上回っています。"
                embed.set_footer(text="SEKAM2 - SEKAMの2", icon_url="https://d.kakikou.app/sekam2logo.png")
                await ctx.followup.send(f"{username}の:grin:ランキング\n{reference_label}", embed=embed)
                return

            greater = sum(1 for r in grin_rows if (int(r[1]) if r[1] is not None else 0) > grincount)
            rank = greater + 1

            if rank == 37:
                embed = discord.Embed(title=f"おもしろ専科民ランキング{rank}位/{grincount}個の:grin:")
                embed.description = f"ユーザーの{percent}%を上回っています。\nおめでとう、君が専科の恐山だ。"
                embed.set_image(url="https://death.kakikou.app/sekam/senka37.gif")
                embed.set_footer(text="SEKAM2 - SEKAMの2", icon_url="https://d.kakikou.app/sekam2logo.png")
                await ctx.followup.send(f"{username}の:grin:ランキング\n{reference_label}", embed=embed)
                return

            embed = discord.Embed(title=f"{rank}位/{grincount}個の:grin:")
            embed.description = f"ユーザーの{percent}%を上回っています。"
            embed.set_footer(text="SEKAM2 - SEKAMの2", icon_url="https://d.kakikou.app/sekam2logo.png")
            await ctx.followup.send(f"{username}の:grin:ランキング\n{reference_label}", embed=embed)
            insert_command_log(ctx, "/grinrank", "OK")
        except Exception as e:
            if config.debug:
                print(f"grinrankエラー: {e}")
            insert_command_log(ctx, "/grinrank", f"ERROR:{e}")
            try:
                await ctx.followup.send("取得中にエラーが発生しました。", ephemeral=True)
            except Exception:
                await ctx.response.send_message("取得中にエラーが発生しました。", ephemeral=True)

    @tree.command(name="allrank", description="すべてのリアクションの合計ランキング")
    @app_commands.allowed_installs(guilds=True, users=True)
    async def allrank(ctx: discord.Interaction):
        if await enforce_zichi_block(ctx, "/allrank"):
            return
        print(f"allrankコマンドが実行されました: {ctx.user.name} ({ctx.user.id})")
        try:
            if not is_overload_allowed(ctx):
                await ctx.response.send_message("現在過負荷対策により専科外では使えません", ephemeral=True)
                insert_command_log(ctx, "/allrank", "DENY_OVERLOAD")
                return
            await ctx.response.defer()

            user = getattr(ctx, "user", None) or getattr(ctx, "author", None)
            username = getattr(user, "display_name", None) or getattr(user, "name", str(user))
            uid = int(getattr(user, "id", 0) or 0)
            reference_label = get_reference_data_label()

            # キャッシュ読込
            all_rows = load_json_cache("allrank.json", [])

            if not all_rows:
                sql = (
                    "SELECT m.author_id, SUM(r.count) as total_count "
                    "FROM reactions r JOIN messages m ON r.message_id = m.id "
                    "GROUP BY m.author_id ORDER BY total_count DESC"
                )
                all_rows = run_statdb_query(sql, (), fetch="all") or []
                # JSON シリアライズ可能形式へ
                try:
                    all_rows = [[int(r[0]) if r and r[0] is not None else 0,
                                 int(r[1]) if r and r[1] is not None else 0] for r in all_rows]
                except Exception:
                    all_rows = []
                save_json_cache("allrank.json", all_rows)

            total = len(all_rows)
            mycount = 0
            has_user = False
            for r in all_rows:
                try:
                    aid = int(str(r[0])) if r[0] is not None else 0
                    cnt = int(r[1]) if r[1] is not None else 0
                except Exception:
                    continue
                if aid == uid:
                    mycount = cnt
                    has_user = True
                    break

            if total > 0 and has_user:
                outrank = sum(1 for r in all_rows if (int(r[1]) if r[1] is not None else 0) < mycount)
                percent = int(outrank * 100 / total)
            else:
                percent = 0

            if total == 0 or not has_user:
                embed = discord.Embed(title=f"ランク外、0個のリアクション")
                embed.description = f"対象期間内にデータがありませんでした。\n無味乾燥なメッセージ。"
                embed.set_footer(text="SEKAM2 - SEKAMの2", icon_url="https://d.kakikou.app/sekam2logo.png")
                await ctx.followup.send(f"{username}のリアクションランキング\n{reference_label}", embed=embed)
                return

            # 標準競技順位（同率で飛び番）: 自分より大きい件数 + 1
            greater = sum(1 for r in all_rows if (int(r[1]) if r[1] is not None else 0) > mycount)
            rank = greater + 1

            if rank == 37:
                embed = discord.Embed(title=f"反応されまくりランキング{rank}位/{mycount}個のリアクション")
                embed.description = f"ユーザーの{percent}%を上回っています。\nおめでとう、君が専科の恐山のうちの一人だ。"
                embed.set_image(url="https://death.kakikou.app/sekam/senka37.gif")
                embed.set_footer(text="SEKAM2 - SEKAMの2", icon_url="https://d.kakikou.app/sekam2logo.png")
                await ctx.followup.send(f"{username}のリアクションランキング\n{reference_label}", embed=embed)
                return

            embed = discord.Embed(title=f"{rank}位/{mycount}個のリアクション")
            embed.description = f"ユーザーの{percent}%を上回っています。"
            embed.set_footer(text="SEKAM2 - SEKAMの2", icon_url="https://d.kakikou.app/sekam2logo.png")
            await ctx.followup.send(f"{username}のリアクションランキング\n{reference_label}", embed=embed)
            insert_command_log(ctx, "/allrank", "OK")
        except Exception as e:
            if config.debug:
                print(f"allrankエラー: {e}")
            insert_command_log(ctx, "/allrank", f"ERROR:{e}")
            try:
                await ctx.followup.send("取得中にエラーが発生しました。", ephemeral=True)
            except Exception:
                await ctx.response.send_message("取得中にエラーが発生しました。", ephemeral=True)

    @tree.command(name="truthgrinrank", description="本当におもしろい専科民ランキング")
    @app_commands.allowed_installs(guilds=True, users=True)
    async def truthgrinrank(ctx: discord.Interaction):
        if await enforce_zichi_block(ctx, "/truthgrinrank"):
            return
        print(f"truthgrinrankコマンドが実行されました: {ctx.user.name} ({ctx.user.id})")
        try:
            if not is_overload_allowed(ctx):
                await ctx.response.send_message("現在過負荷対策により専科外では使えません", ephemeral=True)
                insert_command_log(ctx, "/truthgrinrank", "DENY_OVERLOAD")
                return
            await ctx.response.defer()

            user = getattr(ctx, "user", None) or getattr(ctx, "author", None)
            username = getattr(user, "display_name", None) or getattr(user, "name", str(user))
            uid = int(getattr(user, "id", 0) or 0)
            reference_label = get_reference_data_label()

            # truthgrinrank キャッシュ読込
            truth_rows = load_json_cache("truthgrinrank.json", [])

            if not truth_rows:
                sql_truth = (
                    "SELECT m.author_id, SUM(r.count) as grincount "
                    "FROM reactions r JOIN messages m ON r.message_id = m.id "
                    "WHERE r.emoji_name = 'grin' "
                    "  AND m.content NOT LIKE '%%http%%' "
                    "  AND m.content NOT LIKE '%%https%%' "
                    "GROUP BY m.author_id ORDER BY grincount DESC"
                )
                truth_rows = run_statdb_query(sql_truth, (), fetch="all") or []
                # JSON化
                try:
                    truth_rows = [[int(r[0]) if r and r[0] is not None else 0,
                                   int(r[1]) if r and r[1] is not None else 0] for r in truth_rows]
                except Exception:
                    truth_rows = []
                save_json_cache("truthgrinrank.json", truth_rows)

            # 自分のtruth数と順位・割合
            total_truth = len(truth_rows)
            truth_count = 0
            has_truth_user = False
            for r in truth_rows:
                try:
                    aid = int(str(r[0])) if r[0] is not None else 0
                    cnt = int(r[1]) if r[1] is not None else 0
                except Exception:
                    continue
                if aid == uid:
                    truth_count = cnt
                    has_truth_user = True
                    break
            if total_truth > 0 and has_truth_user:
                outrank = sum(1 for r in truth_rows if (int(r[1]) if r[1] is not None else 0) < truth_count)
                truth_percent = int(outrank * 100 / total_truth)
            else:
                truth_percent = 0
            truth_rank = (sum(1 for r in truth_rows if (int(r[1]) if r[1] is not None else 0) > truth_count)) + 1

            # grin集計（受け取り側）をキャッシュ/参照
            grin_rows = load_json_cache("grinrank.json", [])
            if not grin_rows:
                sql_grin = (
                    "SELECT m.author_id, SUM(r.count) as grincount "
                    "FROM reactions r JOIN messages m ON r.message_id = m.id "
                    "WHERE r.emoji_name = 'grin' "
                    "GROUP BY m.author_id ORDER BY grincount DESC"
                )
                grin_rows = run_statdb_query(sql_grin, (), fetch="all") or []
                try:
                    grin_rows = [[int(r[0]) if r and r[0] is not None else 0,
                                  int(r[1]) if r and r[1] is not None else 0] for r in grin_rows]
                except Exception:
                    grin_rows = []
                save_json_cache("grinrank.json", grin_rows)
            grin_count = 0
            for r in grin_rows:
                try:
                    aid = int(str(r[0])) if r[0] is not None else 0
                    cnt = int(r[1]) if r[1] is not None else 0
                except Exception:
                    continue
                if aid == uid:
                    grin_count = cnt
                    break

            # truth / grin の比率（0割りを避ける）
            ratio_percent = int((truth_count * 100) / grin_count) if grin_count > 0 else 0

            # モノホン最多メッセージ（URLやwww.を含むものは除外）
            sql = (
                "SELECT "
                "    m.id as message_id, "
                "    m.author_id, "
                "    m.channel_id, "
                "    m.content, "
                "    SUM(r.count) as total_grin_count "
                "FROM messages m "
                "JOIN reactions r ON m.id = r.message_id "
                "WHERE m.author_id = %s AND r.emoji_name = 'grin' "
                "  AND m.content NOT LIKE '%%http://%%' "
                "  AND m.content NOT LIKE '%%https://%%' "
                "  AND m.content NOT LIKE '%%www.%%' "
                "GROUP BY m.id, m.author_id, m.channel_id, m.content "
                "ORDER BY total_grin_count DESC "
                "LIMIT 1"
            )
            top_truth_row = run_statdb_query(sql, (uid,), fetch="one")

            if truth_rank == 37:
                # エンベッド構築
                title = f"本物のおもしろ専科民ランキング{truth_rank}位/{truth_count}個の:grin:"
                desc = f"\"モノホンの:grin:\"においては、ユーザーの{truth_percent}%上回ってます\nお前が本物の恐山だ！！！"

                embed = discord.Embed(title=title, description=desc)
                embed.set_image(url="https://death.kakikou.app/sekam/realgrin37.gif")

                # Field1: 全体のgrin内訳
                field1_lines = [
                    f"マジ:grin: : {truth_count}個",
                    f"人の:grin: : {max(grin_count - truth_count, 0)}個",
                    f"全体 :grin: : {grin_count}個",
                    "",
                    f"__{ratio_percent}%が\"モノホン\"の:grin:です__",
                ]
                embed.add_field(name="全体のgrinの内訳", value="\n".join(field1_lines), inline=False)

                # Field2: モノホン最多メッセージ
                if top_truth_row:
                    message_id = top_truth_row[0]
                    channel_id = top_truth_row[2]
                    content = top_truth_row[3] if top_truth_row[3] is not None else ""
                    link = f"https://discord.com/channels/518371205452005387/{channel_id}/{message_id}"
                    field2_desc = (content if content.strip() != "" else "画像のみ") + f"\n[メッセージにジャンプ]({link})"
                else:
                    field2_desc = "対象のメッセージが見つかりませんでした。"
                embed.add_field(name="モノホンの:grin:最多メッセージ:", value=field2_desc, inline=False)

                embed.set_footer(text="SEKAM2 - SEKAMの2", icon_url="https://d.kakikou.app/sekam2logo.png")

                header = f"{username}の**\"モノホン\"**:grin:統計\n{reference_label}"
                await ctx.followup.send(header, embed=embed)
                insert_command_log(ctx, "/truthgrinrank", "OK")
                return

            # エンベッド構築
            title = f"{truth_rank}位/{truth_count}個の:grin:"
            desc = f"\"モノホンの:grin:\"においては、ユーザーの{truth_percent}%上回ってます"

            embed = discord.Embed(title=title, description=desc)

            # Field1: 全体のgrin内訳
            field1_lines = [
                f"マジ:grin: : {truth_count}個",
                f"人の:grin: : {max(grin_count - truth_count, 0)}個",
                f"全体 :grin: : {grin_count}個",
                "",
                f"__{ratio_percent}%が\"モノホン\"の:grin:です__",
            ]
            embed.add_field(name="全体のgrinの内訳", value="\n".join(field1_lines), inline=False)

            # Field2: モノホン最多メッセージ
            if top_truth_row:
                message_id = top_truth_row[0]
                channel_id = top_truth_row[2]
                content = top_truth_row[3] if top_truth_row[3] is not None else ""
                link = f"https://discord.com/channels/518371205452005387/{channel_id}/{message_id}"
                field2_desc = (content if content.strip() != "" else "画像のみ") + f"\n[メッセージにジャンプ]({link})"
            else:
                field2_desc = "対象のメッセージが見つかりませんでした。"
            embed.add_field(name="モノホンの:grin:最多メッセージ:", value=field2_desc, inline=False)

            embed.set_footer(text="SEKAM2 - SEKAMの2", icon_url="https://d.kakikou.app/sekam2logo.png")

            header = f"{username}の**\"モノホン\"**:grin:統計\n{reference_label}"
            await ctx.followup.send(header, embed=embed)
            insert_command_log(ctx, "/truthgrinrank", "OK")
        except Exception as e:
            if config.debug:
                print(f"truthgrinrankエラー: {e}")
            insert_command_log(ctx, "/truthgrinrank", f"ERROR:{e}")
            try:
                await ctx.followup.send("取得中にエラーが発生しました。", ephemeral=True)
            except Exception:
                await ctx.response.send_message("取得中にエラーが発生しました。", ephemeral=True)

    @tree.command(name="maxgrin", description="最多:grin:投稿を教えますよ")
    @app_commands.allowed_installs(guilds=True, users=True)
    async def maxgrin(ctx: discord.Interaction):
        if await enforce_zichi_block(ctx, "/maxgrin"):
            return
        print(f"maxgrinコマンドが実行されました: {ctx.user.name} ({ctx.user.id})")
        try:
            if not is_overload_allowed(ctx):
                await ctx.response.send_message("現在過負荷対策により専科外では使えません", ephemeral=True)
                insert_command_log(ctx, "/maxgrin", "DENY_OVERLOAD")
                return
            await ctx.response.defer()

            user = getattr(ctx, "user", None) or getattr(ctx, "author", None)
            username = getattr(user, "display_name", None) or getattr(user, "name", str(user))
            uid = int(getattr(user, "id", 0) or 0)
            reference_label = get_reference_data_label()

            sql = (
                "SELECT "
                "    m.id as message_id, "
                "    m.author_id, "
                "    m.channel_id, "
                "    m.content, "
                "    SUM(r.count) as total_grin_count "
                "FROM messages m "
                "JOIN reactions r ON m.id = r.message_id "
                "WHERE m.author_id = %s AND r.emoji_name = 'grin' "
                "GROUP BY m.id, m.author_id, m.channel_id, m.content "
                "ORDER BY total_grin_count DESC "
                "LIMIT 1"
            )
            row = run_statdb_query(sql, (uid,), fetch="one")

            if not row:
                await ctx.followup.send("対象のメッセージが見つかりませんでした。", ephemeral=True)
                return

            message_id = row[0]
            channel_id = row[2]
            content = row[3] if row[3] is not None else ""

            # 画像を取得（attachmentsテーブルから）
            attachment_sql = "SELECT url FROM attachments WHERE message_id = %s LIMIT 1"
            attachment_row = run_statdb_query(attachment_sql, (message_id,), fetch="one")
            image_url = attachment_row[0] if attachment_row and attachment_row[0] else None

            # 表示文言（Twitter/Xリンクが含まれる場合は表題を変更）
            base_title = f"{username}の最多:grin:獲得メッセージ"
            lowered = content.lower()
            if ("twitter.com" in lowered) or ("x.com" in lowered):
                base_title += "(人のツイート)"
            base_title += f"\n{reference_label}"

            # 埋め込みの説明文
            desc = content if content.strip() != "" else "画像のみ"

            # Discordメッセージへのリンク（サーバーIDは固定指示値）
            link = f"https://discord.com/channels/518371205452005387/{channel_id}/{message_id}"

            embed = discord.Embed(title="メッセージに移動", url=link, description=desc)
            if image_url:
                embed.set_image(url=image_url)
            
            embed.set_footer(text="SEKAM2 - SEKAMの2", icon_url="https://d.kakikou.app/sekam2logo.png")

            await ctx.followup.send(base_title, embed=embed)
            insert_command_log(ctx, "/maxgrin", "OK")
        except Exception as e:
            if config.debug:
                print(f"maxgrinエラー: {e}")
            insert_command_log(ctx, "/maxgrin", f"ERROR:{e}")
            try:
                await ctx.followup.send("取得中にエラーが発生しました。", ephemeral=True)
            except Exception:
                await ctx.response.send_message("取得中にエラーが発生しました。", ephemeral=True)

    @tree.command(name="grinper", description="打率")
    @app_commands.allowed_installs(guilds=True, users=True)
    async def grinper(ctx: discord.Interaction):
        if await enforce_zichi_block(ctx, "/grinper"):
            return
        print(f"grinperコマンドが実行されました: {ctx.user.name} ({ctx.user.id})")
        try:
            if not is_overload_allowed(ctx):
                await ctx.response.send_message("現在過負荷対策により専科外では使えません", ephemeral=True)
                insert_command_log(ctx, "/grinper", "DENY_OVERLOAD")
                return
            await ctx.response.defer()

            user = getattr(ctx, "user", None) or getattr(ctx, "author", None)
            username = getattr(user, "display_name", None) or getattr(user, "name", str(user))
            uid = int(getattr(user, "id", 0) or 0)

            # 総メッセージ数
            sql_total = (
                "SELECT author_id, COUNT(*) as total_messages "
                "FROM messages WHERE author_id = %s GROUP BY author_id"
            )
            row_total = run_statdb_query(sql_total, (uid,), fetch="one")
            total_messages = int(row_total[1]) if row_total and row_total[1] is not None else 0

            # grinが付いたメッセージ数（重複message_idを除外）
            sql_grin = (
                "SELECT m.author_id, COUNT(DISTINCT r.message_id) as message_count_with_grin "
                "FROM reactions r JOIN messages m ON r.message_id = m.id "
                "WHERE r.emoji_name = 'grin' AND m.author_id = %s "
                "GROUP BY m.author_id"
            )
            row_grin = run_statdb_query(sql_grin, (uid,), fetch="one")
            message_count_with_grin = int(row_grin[1]) if row_grin and row_grin[1] is not None else 0

            percent = (message_count_with_grin * 100.0 / total_messages) if total_messages > 0 else 0.0
            title_percent = f"{percent:.1f}%"

            embed = discord.Embed(title=title_percent)
            embed.set_footer(text="SEKAM2 - SEKAMの2", icon_url="https://d.kakikou.app/sekam2logo.png")
            await ctx.followup.send(f"{username}の:grin:打率\n{get_reference_data_label()}", embed=embed)
            insert_command_log(ctx, "/grinper", "OK")
        except Exception as e:
            if config.debug:
                print(f"grinperエラー: {e}")
            insert_command_log(ctx, "/grinper", f"ERROR:{e}")
            try:
                await ctx.followup.send("取得中にエラーが発生しました。", ephemeral=True)
            except Exception:
                await ctx.response.send_message("取得中にエラーが発生しました。", ephemeral=True)

    @tree.command(name="maxreaction", description="指定したリアクションを最も多く受け取ったメッセージを表示")
    @app_commands.allowed_installs(guilds=True, users=True)
    async def maxreaction(ctx: discord.Interaction, reaction: str):
        """指定した絵文字を最も多く受け取ったメッセージを表示（/maxgrinの絵文字指定版）"""
        if await enforce_zichi_block(ctx, "/maxreaction"):
            return
        print(f"maxreactionコマンドが実行されました: {ctx.user.name} ({ctx.user.id}), reaction={reaction}")
        try:
            if not is_overload_allowed(ctx):
                await ctx.response.send_message("現在過負荷対策により専科外では使えません", ephemeral=True)
                insert_command_log(ctx, "/maxreaction", "DENY_OVERLOAD")
                return
            await ctx.response.defer()

            user = getattr(ctx, "user", None) or getattr(ctx, "author", None)
            username = getattr(user, "display_name", None) or getattr(user, "name", str(user))
            uid = int(getattr(user, "id", 0) or 0)
            reference_label = get_reference_data_label()

            base_name, tone_variants = normalize_emoji_and_variants(reaction)
            if not base_name or not tone_variants:
                await ctx.followup.send("絵文字（または絵文字名）を判別できませんでした。", ephemeral=True)
                insert_command_log(ctx, "/maxreaction", "INVALID_EMOJI")
                return

            # 指定した絵文字を最も多く受け取ったメッセージを検索
            placeholders = ", ".join(["%s"] * len(tone_variants))
            sql = (
                "SELECT "
                "    m.id as message_id, "
                "    m.author_id, "
                "    m.channel_id, "
                "    m.content, "
                "    SUM(r.count) as total_reaction_count "
                "FROM messages m "
                "JOIN reactions r ON m.id = r.message_id "
                f"WHERE m.author_id = %s AND r.emoji_name IN ({placeholders}) "
                "GROUP BY m.id, m.author_id, m.channel_id, m.content "
                "ORDER BY total_reaction_count DESC "
                "LIMIT 1"
            )
            params = (uid,) + tuple(tone_variants)
            row = run_statdb_query(sql, params, fetch="one")

            if not row:
                await ctx.followup.send(f":{base_name}:を受け取ったメッセージが見つかりませんでした。", ephemeral=True)
                insert_command_log(ctx, "/maxreaction", "NO_DATA")
                return

            message_id = row[0]
            channel_id = row[2]
            content = row[3] if row[3] is not None else ""
            total_count = int(row[4]) if row[4] is not None else 0

            # 画像を取得（attachmentsテーブルから）
            attachment_sql = "SELECT url FROM attachments WHERE message_id = %s LIMIT 1"
            attachment_row = run_statdb_query(attachment_sql, (message_id,), fetch="one")
            image_url = attachment_row[0] if attachment_row and attachment_row[0] else None

            base_title = f"{username}の最多:{base_name}:獲得メッセージ ({total_count}個)"
            lowered = content.lower()
            if ("twitter.com" in lowered) or ("x.com" in lowered):
                base_title += "(人のツイート)"
            base_title += f"\n{reference_label}"

            desc = content if content.strip() != "" else "画像のみ"
            link = f"https://discord.com/channels/518371205452005387/{channel_id}/{message_id}"

            embed = discord.Embed(title="メッセージに移動", url=link, description=desc)
            if image_url:
                embed.set_image(url=image_url)
            
            embed.set_footer(text="SEKAM2 - SEKAMの2", icon_url="https://d.kakikou.app/sekam2logo.png")

            await ctx.followup.send(base_title, embed=embed)
            insert_command_log(ctx, "/maxreaction", "OK")
        except Exception as e:
            if config.debug:
                print(f"maxreactionエラー: {e}")
            insert_command_log(ctx, "/maxreaction", f"ERROR:{e}")
            try:
                await ctx.followup.send("取得中にエラーが発生しました。", ephemeral=True)
            except Exception:
                await ctx.response.send_message("取得中にエラーが発生しました。", ephemeral=True)
