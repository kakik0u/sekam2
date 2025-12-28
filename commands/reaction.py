"""リアクション統計関連のコマンド群"""

import discord
from database.connection import run_statdb_query, run_testdb_query
from discord import app_commands
from spam.protection import is_overload_allowed

import config
from core.log import insert_command_log
from core.zichi import enforce_zichi_block
from utils.cache import get_reference_data_label, load_json_cache, save_json_cache
from utils.emoji import normalize_emoji_and_variants


async def setup_reaction_commands(
    tree: app_commands.CommandTree,
    client: discord.Client,
):
    """リアクション統計コマンドを登録"""

    @tree.command(name="reactionrank", description="リアクションのランキング")
    @app_commands.allowed_installs(guilds=True, users=True)
    async def reactionrank(ctx: discord.Interaction, reaction: str):
        if await enforce_zichi_block(ctx, "/reactionrank"):
            return
        try:
            if not is_overload_allowed(ctx):
                await ctx.response.send_message(
                    "現在過負荷対策により専科外では使えません",
                    ephemeral=True,
                )
                insert_command_log(ctx, "/reactionrank", "DENY_OVERLOAD")
                return
            await ctx.response.defer()

            user = getattr(ctx, "user", None) or getattr(ctx, "author", None)
            username = getattr(user, "display_name", None) or getattr(
                user,
                "name",
                str(user),
            )
            uid = int(getattr(user, "id", 0) or 0)

            base_name, tone_variants = normalize_emoji_and_variants(reaction)
            if not base_name or not tone_variants:
                await ctx.followup.send(
                    "絵文字（または絵文字名）を判別できませんでした。",
                    ephemeral=True,
                )
                return

            cache = load_json_cache("reaction.json", {})

            rows = cache.get(base_name) if isinstance(cache, dict) else None
            if not rows:
                placeholders = ", ".join(["%s"] * len(tone_variants))
                sql = (
                    "SELECT m.author_id, SUM(r.count) as total_reactions "
                    "FROM reactions r "
                    "JOIN messages m ON r.message_id = m.id "
                    f"WHERE r.emoji_name IN ({placeholders}) "
                    "GROUP BY m.author_id "
                    "ORDER BY total_reactions DESC"
                )
                rows = run_statdb_query(sql, tuple(tone_variants), fetch="all") or []
                try:
                    serial_rows = [
                        [
                            int(r[0]) if r and r[0] is not None else 0,
                            int(r[1]) if r and r[1] is not None else 0,
                        ]
                        for r in rows
                    ]
                except Exception:
                    serial_rows = []
                cache[base_name] = serial_rows
                save_json_cache("reaction.json", cache)
                rows = serial_rows

            my_total = 0
            has_user = False
            for r in rows:
                try:
                    author_id, total = int(r[0]), int(r[1]) if r[1] is not None else 0
                except Exception:
                    continue
                if author_id == uid:
                    my_total = total
                    has_user = True
                    break

            if not has_user or my_total <= 0:
                embed = discord.Embed(title=f"ランク外、0個の:{base_name}:")
                embed.set_footer(
                    text="SEKAM2 - SEKAMの2",
                    icon_url="https://example.com/sekam2logo.png",
                )
                await ctx.followup.send(
                    f"{username}の:{base_name}:ランキング\n{get_reference_data_label()}",
                    embed=embed,
                )
                return

            greater = 0
            for r in rows:
                try:
                    total = int(r[1]) if r[1] is not None else 0
                except Exception:
                    total = 0
                if total > my_total:
                    greater += 1
            rank = greater + 1

            if rank == 37:
                embed = discord.Embed(
                    title=f"専科民ランキング{rank}位/{my_total}個の:{base_name}:",
                )
                embed.set_image(url="https://example.com/sekam/something37.gif")
                embed.set_footer(
                    text="SEKAM2 - SEKAMの2",
                    icon_url="https://example.com/sekam2logo.png",
                )
                await ctx.followup.send(
                    f"{username}の:{base_name}:ランキング\n{get_reference_data_label()}",
                    embed=embed,
                )
                insert_command_log(ctx, "/reactionrank", "37")
                return
            embed = discord.Embed(title=f"{rank}位/{my_total}個の:{base_name}:")
            embed.set_footer(
                text="SEKAM2 - SEKAMの2",
                icon_url="https://example.com/sekam2logo.png",
            )
            await ctx.followup.send(
                f"{username}の:{base_name}:ランキング\n{get_reference_data_label()}",
                embed=embed,
            )
            insert_command_log(ctx, "/reactionrank", "OK")
        except Exception as e:
            if config.debug:
                print(f"reactionrankエラー: {e}")
            insert_command_log(ctx, "/reactionrank", f"ERROR:{e}")
            try:
                await ctx.followup.send(
                    "取得中にエラーが発生しました。",
                    ephemeral=True,
                )
            except Exception:
                await ctx.response.send_message(
                    "取得中にエラーが発生しました。",
                    ephemeral=True,
                )

    @tree.command(
        name="givereactionrank",
        description="人にあげたリアクションのランキング",
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    async def givereactionrank(ctx: discord.Interaction, reaction: str):
        print(
            f"givereactionrankコマンドが実行されました: {ctx.user.name} ({ctx.user.id})",
        )
        if await enforce_zichi_block(ctx, "/givereactionrank"):
            return
        try:
            if not is_overload_allowed(ctx):
                await ctx.response.send_message(
                    "現在過負荷対策により専科外では使えません",
                    ephemeral=True,
                )
                insert_command_log(ctx, "/givereactionrank", "DENY_OVERLOAD")
                return
            await ctx.response.defer()

            user = getattr(ctx, "user", None) or getattr(ctx, "author", None)
            username = getattr(user, "display_name", None) or getattr(
                user,
                "name",
                str(user),
            )
            uid = int(getattr(user, "id", 0) or 0)

            base_name, _tone_variants_unused = normalize_emoji_and_variants(reaction)
            if not base_name:
                await ctx.followup.send(
                    "絵文字（または絵文字名）を判別できませんでした。",
                    ephemeral=True,
                )
                return

            cache = load_json_cache("give_reaction.json", {})

            rows = None
            if base_name in cache:
                rows = cache.get(base_name) or []
            if rows is None:
                rows = []

            if not rows:
                sql = (
                    "SELECT user_id, COUNT(*) as grin_reaction_count "
                    "FROM reaction WHERE emoji_code = %s "
                    "GROUP BY user_id ORDER BY grin_reaction_count DESC"
                )
                rows = run_testdb_query(sql, (base_name,), fetch="all") or []
                try:
                    serial_rows = [
                        [
                            int(r[0]) if r and r[0] is not None else 0,
                            int(r[1]) if r and r[1] is not None else 0,
                        ]
                        for r in rows
                    ]
                except Exception:
                    serial_rows = []
                cache[base_name] = serial_rows
                save_json_cache("give_reaction.json", cache)
                rows = serial_rows

            my_total = 0
            has_user = False
            for r in rows:
                try:
                    r_uid = int(str(r[0])) if r[0] is not None else 0
                    cnt = int(r[1]) if r[1] is not None else 0
                except Exception:
                    continue
                if r_uid == uid:
                    my_total = cnt
                    has_user = True
                    break

            if not has_user or my_total <= 0:
                embed = discord.Embed(
                    title=f"ランク外、:{base_name}:は一回もあげてません",
                )
                embed.set_footer(
                    text="SEKAM2 - SEKAMの2",
                    icon_url="https://example.com/sekam2logo.png",
                )
                await ctx.followup.send(
                    f"{username}の:{base_name}:をあげた人ランキング\n{get_reference_data_label()}",
                    embed=embed,
                )
                insert_command_log(ctx, "/givereactionrank", "NO_DATA")
                return
            greater = 0
            for r in rows:
                try:
                    cnt = int(r[1]) if r[1] is not None else 0
                except Exception:
                    cnt = 0
                if cnt > my_total:
                    greater += 1
            rank = greater + 1

            if rank == 37:
                embed = discord.Embed(
                    title=f"専科民ランキング{rank}位/{my_total}個の:{base_name}:をあげました",
                )
                embed.set_image(url="https://example.com/sekam/something37.gif")
            else:
                embed = discord.Embed(
                    title=f"{rank}位/{my_total}個の:{base_name}:をあげました",
                )
            embed.set_footer(
                text="SEKAM2 - SEKAMの2",
                icon_url="https://example.com/sekam2logo.png",
            )
            await ctx.followup.send(
                f"{username}の:{base_name}:をあげた人ランキング\n{get_reference_data_label()}",
                embed=embed,
            )
            insert_command_log(ctx, "/givereactionrank", "OK")
        except Exception as e:
            if config.debug:
                print(f"givereactionrankエラー: {e}")
            insert_command_log(ctx, "/givereactionrank", f"ERROR:{e}")
            try:
                if not ctx.response.is_done():
                    await ctx.response.send_message(
                        "取得中にエラーが発生しました。",
                        ephemeral=True,
                    )
                else:
                    await ctx.followup.send(
                        "取得中にエラーが発生しました。",
                        ephemeral=True,
                    )
            except Exception:
                pass

    @tree.command(name="givegrinrank", description="君があげたgrinについて。")
    @app_commands.allowed_installs(guilds=True, users=True)
    async def givegrinrank(ctx: discord.Interaction):
        print(f"givegrinrankコマンドが実行されました: {ctx.user.name} ({ctx.user.id})")
        if await enforce_zichi_block(ctx, "/givegrinrank"):
            return
        try:
            if not is_overload_allowed(ctx):
                await ctx.response.send_message(
                    "現在過負荷対策により専科外では使えません",
                    ephemeral=True,
                )
                insert_command_log(ctx, "/givegrinrank", "DENY_OVERLOAD")
                return
            await ctx.response.defer()

            exec_user = getattr(ctx, "user", None) or getattr(ctx, "author", None)
            username = getattr(exec_user, "display_name", None) or getattr(
                exec_user,
                "name",
                str(exec_user),
            )
            target_uid = int(getattr(exec_user, "id", 0) or 0)
            give_rows = load_json_cache("givegrinrank.json", [])

            if not give_rows:
                sql = (
                    "SELECT user_id, COUNT(*) as grincount "
                    "FROM reaction WHERE emoji_code = 'grin' "
                    "GROUP BY user_id ORDER BY grincount DESC"
                )
                give_rows = run_testdb_query(sql, (), fetch="all") or []
                save_json_cache("givegrinrank.json", give_rows)

            total = len(give_rows)
            has_give = False
            givegrincount = 0
            for r in give_rows:
                try:
                    uid = int(str(r[0])) if r[0] is not None else 0
                    cnt = int(r[1]) if r[1] is not None else 0
                except Exception:
                    continue
                if uid == target_uid:
                    givegrincount = cnt
                    has_give = True
                    break

            grin_rows = load_json_cache("grinrank.json", [])
            if not grin_rows:
                sql_grin = (
                    "SELECT m.author_id, SUM(r.count) as grincount "
                    "FROM reactions r JOIN messages m ON r.message_id = m.id "
                    "WHERE r.emoji_name = 'grin' "
                    "GROUP BY m.author_id ORDER BY grincount DESC"
                )
                grin_rows = run_statdb_query(sql_grin, (), fetch="all") or []
                save_json_cache("grinrank.json", grin_rows)
            grincount = 0
            for r in grin_rows:
                try:
                    aid = int(str(r[0])) if r[0] is not None else 0
                    cnt = int(r[1]) if r[1] is not None else 0
                except Exception:
                    continue
                if aid == target_uid:
                    grincount = cnt
                    break

            if total == 0 or not has_give:
                embed = discord.Embed(
                    title="誰にも笑ったことがないです。(0個の:grin:をあげました)",
                )
                embed.description = (
                    f"もらった:grin: : {grincount}個\nあげた:grin: : {givegrincount}個"
                )
                embed.set_footer(
                    text="SEKAM2 - SEKAMの2",
                    icon_url="https://example.com/sekam2logo.png",
                )
                await ctx.followup.send(
                    f"{username}の:grin:をあげた人ランキング\n{get_reference_data_label()}",
                    embed=embed,
                )
                insert_command_log(ctx, "/givegrinrank", "NO_DATA")
                return

            greater = sum(
                1
                for r in give_rows
                if (int(r[1]) if r[1] is not None else 0) > givegrincount
            )
            rank = greater + 1

            if rank == 37:
                embed = discord.Embed(
                    title=f"笑顔の専科民ランキング{rank}位/{givegrincount}個の:grin:をあげました！！",
                )
                embed.set_image(url="https://example.com/sekam/smile37.gif")
            else:
                embed = discord.Embed(
                    title=f"{rank}位/{givegrincount}個の:grin:をあげました",
                )
            embed.description = (
                f"もらった:grin: : {grincount}個\nあげた:grin: : {givegrincount}個"
            )
            embed.set_footer(
                text="SEKAM2 - SEKAMの2",
                icon_url="https://example.com/sekam2logo.png",
            )
            await ctx.followup.send(
                f"{username}の:grin:をあげた人ランキング\n{get_reference_data_label()}",
                embed=embed,
            )
            insert_command_log(ctx, "/givegrinrank", "OK")
        except Exception as e:
            if config.debug:
                print(f"givegrinrankエラー: {e}")
            insert_command_log(ctx, "/givegrinrank", f"ERROR:{e}")
            try:
                if not ctx.response.is_done():
                    await ctx.response.send_message(
                        "取得中にエラーが発生しました。",
                        ephemeral=True,
                    )
                else:
                    await ctx.followup.send(
                        "取得中にエラーが発生しました。",
                        ephemeral=True,
                    )
            except Exception:
                pass
