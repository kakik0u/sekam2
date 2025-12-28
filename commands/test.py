"""試験的なコマンド群
/test grinrank - 画像形式のgrinrankコマンド
/test ai - AI チャットコマンド
"""

import os
import tempfile
from datetime import datetime, timedelta

import aiohttp
import discord
import matplotlib
from discord import app_commands

matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
from database.connection import run_db_query, run_statdb_query
from PIL import Image, ImageDraw, ImageFont
from pilmoji import Pilmoji
from spam.protection import is_overload_allowed

from config import debug
from core.log import insert_command_log
from core.zichi import enforce_zichi_block
from utils.cache import get_reference_data_label


async def setup_test_commands(tree: app_commands.CommandTree, client: discord.Client):
    """試験コマンドを登録"""
    # /testグループを作成
    test_group = app_commands.Group(name="test", description="試験的な機能のコマンド群")

    @test_group.command(
        name="grinrank",
        description="【試験】画像形式の:grin:ランキング",
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    async def test_grinrank(ctx: discord.Interaction):
        """試験的な画像形式のgrinrankコマンド"""
        if await enforce_zichi_block(ctx, "/test grinrank"):
            return

        print(f"test grinrankコマンドが実行されました: {ctx.user.name} ({ctx.user.id})")

        try:
            import time

            start_time = time.time()

            # 過負荷モードチェック
            if not is_overload_allowed(ctx):
                await ctx.response.send_message(
                    "現在過負荷対策により専科外では使えません",
                    ephemeral=True,
                )
                insert_command_log(ctx, "/test grinrank", "DENY_OVERLOAD")
                return

            # 処理開始を通知
            await ctx.response.defer()
            defer_time = time.time()
            print(f"[Timer] defer完了: {defer_time - start_time:.3f}秒")

            # ユーザー情報取得
            user = getattr(ctx, "user", None) or getattr(ctx, "author", None)
            username = getattr(user, "display_name", None) or getattr(
                user,
                "name",
                str(user),
            )
            uid = int(getattr(user, "id", 0) or 0)

            # 参照データラベル取得
            reference_label = get_reference_data_label()

            # データ取得
            data_start = time.time()
            grinrank_data = get_grinrank_data(uid)
            data_end = time.time()
            print(f"[Timer] データ取得完了: {data_end - data_start:.3f}秒")

            if grinrank_data is None:
                embed = discord.Embed(
                    title="データなし",
                    description="データが取得できませんでした。",
                )
                embed.set_footer(
                    text="SEKAM2 - SEKAMの2",
                    icon_url="https://example.app/sekam2logo.png",
                )
                await ctx.followup.send(
                    f"{username}の:grin:ランキング（試験版）\n{reference_label}",
                    embed=embed,
                )
                insert_command_log(ctx, "/test grinrank", "NO_DATA")
                return

            # 画像生成
            image_start = time.time()
            image_path = create_grinrank_image(grinrank_data, username, reference_label)
            image_end = time.time()
            print(f"[Timer] 画像生成完了: {image_end - image_start:.3f}秒")

            # Discordに送信
            send_start = time.time()
            file = discord.File(image_path, filename="grinrank.png")

            # 処理時間のサマリーを作成
            total_time = time.time() - start_time
            defer_duration = defer_time - start_time
            data_duration = data_end - data_start
            image_duration = image_end - image_start
            send_duration = time.time() - send_start  # 送信時間は送信後に計測

            # データ取得の詳細タイミング
            timing_details = grinrank_data.get("_timing", {})
            rank_time = timing_details.get("rank_total", 0)
            rank_cache = timing_details.get("rank_cache_hit", False)
            batting_time = timing_details.get("batting_total", 0)
            batting_q1 = timing_details.get("batting_query1", 0)
            batting_q2 = timing_details.get("batting_query2", 0)
            daily_time = timing_details.get("daily_total", 0)
            period_time = timing_details.get("period_total", 0)

            # 期間別ランキングのキャッシュ情報
            period_ranks = grinrank_data.get("period_ranks", {})
            period_cache = period_ranks.get("_cache_hit", False)

            _ = (
                f"**デバッグ用**\n"
                f"```\n"
                f"総処理時間:        {total_time:.2f}秒\n"
                f"├─ 初期化:          {defer_duration:.2f}秒\n"
                f"├─ データ取得:      {data_duration:.2f}秒\n"
                f"│  ├─ 全体ランク:    {rank_time:.2f}秒 {'(cache)' if rank_cache else '(query)'}\n"
                f"│  ├─ 打率計算:      {batting_time:.2f}秒\n"
                f"│  │  ├─ クエリ1:    {batting_q1:.2f}秒 (総メッセージ数)\n"
                f"│  │  └─ クエリ2:    {batting_q2:.2f}秒 (grin付きメッセージ数)\n"
                f"│  ├─ 7日間データ:  {daily_time:.2f}秒 (最適化済み:1クエリ)\n"
                f"│  └─ 期間別ランク:  {period_time:.2f}秒 {'(cache)' if period_cache else '(query)'}\n"
                f"├─ 画像生成:        {image_duration:.2f}秒\n"
                f"└─ Discord送信:     {send_duration:.2f}秒\n"
                f"```"
            )

            await ctx.followup.send(
                f"{username}の:grin:ランキング（試験版）\n{reference_label}",
                file=file,
            )

            print(f"[Timer] Discord送信完了: {send_duration:.3f}秒")
            print(f"[Timer] 総処理時間: {total_time:.3f}秒")

            # 一時ファイル削除
            try:
                os.unlink(image_path)
            except Exception:
                pass

            insert_command_log(ctx, "/test grinrank", f"OK ({total_time:.2f}s)")

        except Exception as e:
            if debug:
                print(f"test grinrankエラー: {e}")
                import traceback

                traceback.print_exc()
            insert_command_log(ctx, "/test grinrank", f"ERROR:{e}")
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

    @test_group.command(name="ai", description="【試験】AIとチャットする")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.describe(prompt="AIに送信するメッセージ")
    async def test_ai(ctx: discord.Interaction, prompt: str):
        """AI チャット機能（試験版）"""
        if await enforce_zichi_block(ctx, "/test ai"):
            return

        print(f"test aiコマンドが実行されました: {ctx.user.name} ({ctx.user.id})")

        try:
            # 処理開始を通知
            await ctx.response.defer()

            # APIエンドポイント
            api_url = "https://llm.example.app/v1/chat/completions"

            # リクエストボディ
            payload = {
                "model": "vinchanai@q8_0",
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "max_tokens": 75,
            }

            # HTTPリクエスト送信
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    api_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status == 404:
                        await ctx.followup.send(
                            "GPUサーバーがダウンしているか、ゲームに使われています",
                            ephemeral=True,
                        )
                        insert_command_log(ctx, "/test ai", "ERROR:404")
                        return

                    if response.status != 200:
                        await ctx.followup.send(
                            f"GPUサーバーがダウンしているか、ゲームに使われています (Status: {response.status})",
                            ephemeral=True,
                        )
                        insert_command_log(ctx, "/test ai", f"ERROR:{response.status}")
                        return

                    # レスポンス取得
                    data = await response.json()

                    # AIの返答を取得
                    ai_response = (
                        data.get("choices", [{}])[0]
                        .get("message", {})
                        .get("content", "")
                    )

                    if not ai_response:
                        await ctx.followup.send(
                            "AIから返答が得られませんでした。",
                            ephemeral=True,
                        )
                        insert_command_log(ctx, "/test ai", "ERROR:NO_RESPONSE")
                        return

                    # 返答を送信
                    # Discordのメッセージ長制限（2000文字）を考慮
                    if len(ai_response) > 1900:
                        ai_response = ai_response[:1900] + "..."

                    await ctx.followup.send(
                        f"**プロンプト:** {prompt[:100]}{'...' if len(prompt) > 100 else ''}\n\n**AI恐山:**\n{ai_response}",
                    )

                    insert_command_log(ctx, "/test ai", "OK")

        except aiohttp.ClientError as e:
            if debug:
                print(f"test ai ネットワークエラー: {e}")
                import traceback

                traceback.print_exc()
            await ctx.followup.send(
                "GPUサーバーがダウンしているか、ゲームに使われています",
                ephemeral=True,
            )
            insert_command_log(ctx, "/test ai", f"ERROR:NETWORK:{e}")
        except Exception as e:
            if debug:
                print(f"test aiエラー: {e}")
                import traceback

                traceback.print_exc()
            insert_command_log(ctx, "/test ai", f"ERROR:{e}")
            try:
                if not ctx.response.is_done():
                    await ctx.response.send_message(
                        "エラーが発生しました。",
                        ephemeral=True,
                    )
                else:
                    await ctx.followup.send("エラーが発生しました。", ephemeral=True)
            except Exception:
                pass

    # グループをツリーに追加
    tree.add_command(test_group)


def get_grinrank_data(user_id: int) -> dict:
    """grinrankに必要な全データを取得（集計テーブル使用版）

    Args:
        user_id: ユーザーID

    Returns:
        dict: 各種データを含む辞書、エラー時はNone
            timing情報も含まれる

    """
    try:
        import time

        func_start = time.time()
        timing_details = {}

        data = {}

        # 1. 全体ランキング（集計テーブルgrin_user_statsを使用）
        rank_start = time.time()

        # ユーザーのデータを取得
        sql_user = """
        SELECT total_grin_count, total_messages, grin_messages
        FROM grin_user_stats
        WHERE user_id = %s
        """
        user_row = run_statdb_query(sql_user, (user_id,), fetch="one")

        if not user_row:
            # 集計テーブルにデータがない場合はNone
            return None

        grincount = int(user_row[0]) if user_row[0] else 0
        total_messages = int(user_row[1]) if user_row[1] else 0
        grin_messages = int(user_row[2]) if user_row[2] else 0

        # 順位を計算（自分より上の人数 + 1）
        sql_rank = """
        SELECT COUNT(*) + 1 as rank
        FROM grin_user_stats
        WHERE total_grin_count > %s
        """
        rank_row = run_statdb_query(sql_rank, (grincount,), fetch="one")
        rank = int(rank_row[0]) if rank_row else 1

        # 総ユーザー数
        sql_total = "SELECT COUNT(*) FROM grin_user_stats"
        total_row = run_statdb_query(sql_total, (), fetch="one")
        total = int(total_row[0]) if total_row else 0

        # パーセント計算
        sql_percent = """
        SELECT COUNT(*) FROM grin_user_stats WHERE total_grin_count < %s
        """
        percent_row = run_statdb_query(sql_percent, (grincount,), fetch="one")
        outrank = int(percent_row[0]) if percent_row else 0
        percent = int(outrank * 100 / total) if total > 0 else 0

        data["rank"] = rank
        data["grincount"] = grincount
        data["percent"] = percent
        data["total"] = total

        timing_details["rank_total"] = time.time() - rank_start
        timing_details["rank_cache_hit"] = False  # 集計テーブル使用
        print(
            f"[Timer] - 全体ランキング取得（集計テーブル）: {timing_details['rank_total']:.3f}秒",
        )

        # 2. 打率計算（既に集計テーブルから取得済み）
        batting_start = time.time()
        batting_avg = (
            (grin_messages * 100.0 / total_messages) if total_messages > 0 else 0.0
        )
        data["batting_avg"] = batting_avg
        timing_details["batting_total"] = time.time() - batting_start
        timing_details["batting_query1"] = 0.0  # 集計テーブルから取得
        timing_details["batting_query2"] = 0.0
        print(f"[Timer] - 打率計算: {timing_details['batting_total']:.3f}秒")

        # :grin:付きメッセージ数
        query2_start = time.time()
        sql_grin = (
            "SELECT COUNT(DISTINCT r.message_id) as count "
            "FROM reactions r JOIN messages m ON r.message_id = m.id "
            "WHERE r.emoji_name = 'grin' AND m.author_id = %s"
        )
        row_grin = run_statdb_query(sql_grin, (user_id,), fetch="one")
        grin_messages = int(row_grin[0]) if row_grin and row_grin[0] is not None else 0
        timing_details["batting_query2"] = time.time() - query2_start

        batting_avg = (
            (grin_messages * 100.0 / total_messages) if total_messages > 0 else 0.0
        )
        data["batting_avg"] = batting_avg
        timing_details["batting_total"] = time.time() - batting_start
        print(f"[Timer] - 打率計算: {timing_details['batting_total']:.3f}秒")

        # 3. 過去7日間のデータ取得
        daily_start = time.time()
        daily_data = get_daily_grin_data(user_id)
        data["daily_data"] = daily_data
        timing_details["daily_total"] = time.time() - daily_start
        print(f"[Timer] - 過去7日間データ取得: {timing_details['daily_total']:.3f}秒")

        # 4. 期間別ランキング
        period_start = time.time()
        period_ranks = get_period_rankings(user_id)
        data["period_ranks"] = period_ranks
        timing_details["period_total"] = time.time() - period_start
        print(f"[Timer] - 期間別ランキング取得: {timing_details['period_total']:.3f}秒")

        timing_details["func_total"] = time.time() - func_start
        data["_timing"] = timing_details
        print(f"[Timer] - データ取得関数合計: {timing_details['func_total']:.3f}秒")
        return data

    except Exception as e:
        if debug:
            print(f"get_grinrank_dataエラー: {e}")
            import traceback

            traceback.print_exc()
        return None


def get_daily_grin_data(user_id: int) -> dict:
    """過去7日間の日次grinデータを取得（集計テーブルgrin_daily_stats使用）"""
    try:
        # 参照データの最終日を取得
        row = run_db_query(
            "SELECT dblastupdate FROM config WHERE id = 1 LIMIT 1",
            (),
            fetch="one",
        )
        if not row or row[0] is None:
            # デフォルトで今日
            end_date = datetime.now().date()
        else:
            end_date = (
                row[0]
                if isinstance(row[0], datetime)
                else datetime.fromisoformat(str(row[0]))
            )
            if isinstance(end_date, datetime):
                end_date = end_date.date()

        # 過去7日間の日付リストを生成
        dates = [(end_date - timedelta(days=i)) for i in range(6, -1, -1)]
        start_date = dates[0]

        # 集計テーブルから取得
        sql = """
        SELECT date, grin_count, total_messages, grin_messages
        FROM grin_daily_stats
        WHERE user_id = %s AND date >= %s AND date <= %s
        ORDER BY date
        """

        rows = run_statdb_query(sql, (user_id, start_date, end_date), fetch="all")

        # データを辞書に変換
        data_dict = {}
        for row in rows or []:
            date_val = row[0]
            if isinstance(date_val, datetime):
                date_val = date_val.date()
            data_dict[date_val] = {
                "grin_count": int(row[1]) if row[1] else 0,
                "total_messages": int(row[2]) if row[2] else 0,
                "grin_messages": int(row[3]) if row[3] else 0,
            }

        # 各日のデータを整理
        grin_counts = []
        batting_avgs = []

        for date in dates:
            if date in data_dict:
                day_data = data_dict[date]
                grin_counts.append(day_data["grin_count"])

                if day_data["total_messages"] > 0:
                    batting_avg = (
                        day_data["grin_messages"] * 100.0 / day_data["total_messages"]
                    )
                else:
                    batting_avg = 0.0
                batting_avgs.append(batting_avg)
            else:
                grin_counts.append(0)
                batting_avgs.append(0.0)

        return {
            "dates": dates,
            "grin_counts": grin_counts,
            "batting_avgs": batting_avgs,
        }

    except Exception as e:
        if debug:
            print(f"get_daily_grin_dataエラー: {e}")
            import traceback

            traceback.print_exc()
        # エラー時は空データを返す
        end_date = datetime.now().date()
        dates = [(end_date - timedelta(days=i)) for i in range(6, -1, -1)]
        return {"dates": dates, "grin_counts": [0] * 7, "batting_avgs": [0.0] * 7}


def get_period_rankings(user_id: int) -> dict:
    """期間別ランキングを取得（日間/週間/月間）- 集計テーブルgrin_daily_stats使用

    Returns:
        dict: {
            'daily': {'rank': int, 'count': int},
            'weekly': {'rank': int, 'count': int},
            'monthly': {'rank': int, 'count': int},
            '_cache_hit': False  # 集計テーブル使用
        }

    """
    try:
        # 参照データの最終日を取得
        row = run_db_query(
            "SELECT dblastupdate FROM config WHERE id = 1 LIMIT 1",
            (),
            fetch="one",
        )
        if not row or row[0] is None:
            end_date = datetime.now()
        else:
            end_date = (
                row[0]
                if isinstance(row[0], datetime)
                else datetime.fromisoformat(str(row[0]))
            )

        # 期間の定義
        daily_start = (end_date - timedelta(days=1)).date()
        weekly_start = (end_date - timedelta(days=7)).date()
        monthly_start = (end_date - timedelta(days=30)).date()

        end_date_val = (
            end_date
            if isinstance(end_date, datetime)
            else datetime.combine(end_date, datetime.min.time())
        )

        result = {}

        # デイリーランキング
        sql_daily = """
        SELECT
            (SELECT COUNT(DISTINCT user_id) + 1 FROM grin_daily_stats
             WHERE date = %s AND grin_count > (
                SELECT COALESCE(grin_count, 0) FROM grin_daily_stats WHERE user_id = %s AND date = %s
             )) as rank,
            COALESCE((SELECT grin_count FROM grin_daily_stats WHERE user_id = %s AND date = %s), 0) as count
        """
        daily_row = run_statdb_query(
            sql_daily,
            (daily_start, user_id, daily_start, user_id, daily_start),
            fetch="one",
        )
        result["daily"] = {
            "rank": int(daily_row[0]) if daily_row else 0,
            "count": int(daily_row[1]) if daily_row else 0,
        }

        # ウィークリーランキング
        sql_weekly = """
        SELECT
            (SELECT COUNT(DISTINCT t2.user_id) + 1 FROM (
                SELECT user_id, SUM(grin_count) as total FROM grin_daily_stats
                WHERE date >= %s AND date <= %s
                GROUP BY user_id
            ) t2 WHERE t2.total > (
                SELECT COALESCE(SUM(grin_count), 0) FROM grin_daily_stats
                WHERE user_id = %s AND date >= %s AND date <= %s
            )) as rank,
            COALESCE((SELECT SUM(grin_count) FROM grin_daily_stats
                      WHERE user_id = %s AND date >= %s AND date <= %s), 0) as count
        """
        weekly_row = run_statdb_query(
            sql_weekly,
            (
                weekly_start,
                end_date_val,
                user_id,
                weekly_start,
                end_date_val,
                user_id,
                weekly_start,
                end_date_val,
            ),
            fetch="one",
        )
        result["weekly"] = {
            "rank": int(weekly_row[0]) if weekly_row else 0,
            "count": int(weekly_row[1]) if weekly_row else 0,
        }

        # マンスリーランキング
        sql_monthly = """
        SELECT
            (SELECT COUNT(DISTINCT t2.user_id) + 1 FROM (
                SELECT user_id, SUM(grin_count) as total FROM grin_daily_stats
                WHERE date >= %s AND date <= %s
                GROUP BY user_id
            ) t2 WHERE t2.total > (
                SELECT COALESCE(SUM(grin_count), 0) FROM grin_daily_stats
                WHERE user_id = %s AND date >= %s AND date <= %s
            )) as rank,
            COALESCE((SELECT SUM(grin_count) FROM grin_daily_stats
                      WHERE user_id = %s AND date >= %s AND date <= %s), 0) as count
        """
        monthly_row = run_statdb_query(
            sql_monthly,
            (
                monthly_start,
                end_date_val,
                user_id,
                monthly_start,
                end_date_val,
                user_id,
                monthly_start,
                end_date_val,
            ),
            fetch="one",
        )
        result["monthly"] = {
            "rank": int(monthly_row[0]) if monthly_row else 0,
            "count": int(monthly_row[1]) if monthly_row else 0,
        }

        result["_cache_hit"] = False  # 集計テーブル使用

        return result

    except Exception as e:
        if debug:
            print(f"get_period_rankingsエラー: {e}")
            import traceback

            traceback.print_exc()
        return {
            "daily": {"rank": 0, "count": 0},
            "weekly": {"rank": 0, "count": 0},
            "monthly": {"rank": 0, "count": 0},
        }


def create_grinrank_image(data: dict, username: str, reference_label: str) -> str:
    """grinrankの画像を生成

    Args:
        data: get_grinrank_data()で取得したデータ
        username: ユーザー名
        reference_label: 参照データラベル

    Returns:
        str: 生成された画像ファイルのパス

    """
    try:
        import time

        func_start = time.time()

        # フォントパスの設定
        font_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fonts")
        normal_font_path = os.path.join(font_dir, "UDShingoL.otf")
        light_font_path = os.path.join(font_dir, "UDShingoL.otf")

        # グラフを生成
        graph_start = time.time()
        graph_path = create_daily_graph(
            data["daily_data"]["dates"],
            data["daily_data"]["grin_counts"],
            data["daily_data"]["batting_avgs"],
        )
        graph_end = time.time()
        print(f"[Timer] - グラフ生成: {graph_end - graph_start:.3f}秒")

        # 背景画像を読み込み
        bg_load_start = time.time()
        bg_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "bg",
            "bg_grinrank.png",
        )
        bg = Image.open(bg_path).convert("RGBA")
        bg_width, bg_height = bg.size
        print(f"[Timer] - 背景画像読込: {time.time() - bg_load_start:.3f}秒")

        # グラフ画像を読み込み
        graph_load_start = time.time()
        graph_img = Image.open(graph_path).convert("RGBA")
        print(f"[Timer] - グラフ画像読込: {time.time() - graph_load_start:.3f}秒")

        # グラフを背景に貼り付け（右上に配置）
        paste_start = time.time()
        graph_width, graph_height = graph_img.size
        graph_x = bg_width - graph_width - 50  # 右端から50pxの余白
        graph_y = 150  # 上から150pxの位置（より上に配置）
        bg.paste(graph_img, (graph_x, graph_y), graph_img)
        print(f"[Timer] - グラフ貼付: {time.time() - paste_start:.3f}秒")

        # テキストを描画
        _draw = ImageDraw.Draw(bg)

        font_load_start = time.time()
        try:
            # フォント読み込み
            font_title = ImageFont.truetype(normal_font_path, 36)  # 30 → 36 に拡大
            font_72 = ImageFont.truetype(normal_font_path, 72)
            font_60 = ImageFont.truetype(normal_font_path, 60)
            font_48 = ImageFont.truetype(normal_font_path, 48)
            font_24 = ImageFont.truetype(light_font_path, 24)  # 参照データ用に追加
        except Exception:
            # フォールバック
            font_title = ImageFont.load_default()
            font_72 = ImageFont.load_default()
            font_60 = ImageFont.load_default()
            font_48 = ImageFont.load_default()
            font_24 = ImageFont.load_default()
        print(f"[Timer] - フォント読込: {time.time() - font_load_start:.3f}秒")

        # Pilmojiを使用してテキストを描画
        text_start = time.time()
        with Pilmoji(bg) as pilmoji:
            # タイトル（上部中央）- サイズを36ptに拡大
            title_text = f"{username}の:grin:ランキング"
            pilmoji.text((50, 40), title_text, font=font_title, fill="white")

            # コラム1（左上）- 順位・個数・パーセントのみ（ラベルは背景に含まれている）
            # 25px左に移動（130 → 105）
            col1_x = 80 + 50 - 25  # 105
            col1_y_start = 120 + 15  # 135

            # 順位（ラベルなし）
            rank_text = f"{data['rank']}位"
            pilmoji.text(
                (col1_x, col1_y_start + 50),
                rank_text,
                font=font_72,
                fill="white",
            )

            # 個数
            count_text = f"{data['grincount']}個"
            pilmoji.text(
                (col1_x, col1_y_start + 140),
                count_text,
                font=font_60,
                fill="white",
            )

            # パーセントのみ（"上位"は背景に含まれている）
            # 左上を0として(180, 450)の位置に配置
            percent_text = f"{data['percent']}%"
            pilmoji.text((180, 450), percent_text, font=font_60, fill="white")

            # コラム3（左下）- 期間別ランキング（ラベルなし、順位と個数のみ）
            # 90px右に、12px下に移動
            col3_x = 80 + 90  # 170
            col3_y_start = bg_height - 220 + 12  # bg_height - 208

            period_data = data["period_ranks"]
            daily_text = (
                f"{period_data['daily']['rank']}位/{period_data['daily']['count']}個"
            )
            weekly_text = (
                f"{period_data['weekly']['rank']}位/{period_data['weekly']['count']}個"
            )
            monthly_text = f"{period_data['monthly']['rank']}位/{period_data['monthly']['count']}個"

            pilmoji.text((col3_x, col3_y_start), daily_text, font=font_48, fill="white")
            pilmoji.text(
                (col3_x, col3_y_start + 60),
                weekly_text,
                font=font_48,
                fill="white",
            )
            pilmoji.text(
                (col3_x, col3_y_start + 120),
                monthly_text,
                font=font_48,
                fill="white",
            )

            # コラム4（右中央）- パーセントのみ（"打率"は背景に含まれている）
            # 30px左に移動（520 → 550）
            # 右下を0とした時、文字の右上が(550, 140)の位置に
            col4_x = bg_width - 550  # 730
            col4_y = bg_height - 140

            batting_text = f"{data['batting_avg']:.1f}%"
            pilmoji.text(
                (col4_x, col4_y),
                batting_text,
                font=font_72,
                fill="white",
                align="right",
            )

            # コラム5（右下）- 日付のみ（他は背景に含まれている）
            # サイズを24ptに縮小し、右端に寄せる
            col5_y_start = bg_height - 140

            # 参照データから日付部分のみを抽出
            clean_label = reference_label.replace("-# ", "").replace("-#", "")
            # "参照データ:"を削除
            if "参照データ:" in clean_label:
                date_only = clean_label.replace("参照データ:", "")
            else:
                date_only = clean_label

            # テキストの幅を計算して右端に配置
            bbox = pilmoji.getsize(date_only, font=font_24)
            text_width = bbox[0] if bbox else len(date_only) * 12
            col5_x = bg_width - text_width - 30  # 右端から30pxの余白

            pilmoji.text(
                (col5_x, col5_y_start + 70),
                date_only,
                font=font_24,
                fill="white",
            )

        print(f"[Timer] - テキスト描画: {time.time() - text_start:.3f}秒")

        # 最終画像を保存
        save_start = time.time()
        final_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        final_temp_path = final_temp.name
        final_temp.close()
        bg.save(final_temp_path, "PNG")
        print(f"[Timer] - 画像保存: {time.time() - save_start:.3f}秒")

        # グラフの一時ファイルを削除
        try:
            os.unlink(graph_path)
        except Exception:
            pass

        total_image_time = time.time() - func_start
        print(f"[Timer] - 画像生成関数合計: {total_image_time:.3f}秒")

        return final_temp_path

    except Exception:
        # グラフの一時ファイルを削除
        try:
            os.unlink(graph_path)
        except Exception:
            pass

        print(f"[Timer] - 画像生成関数合計: {time.time() - func_start:.3f}秒")
        return final_temp_path

    except Exception as e:
        if debug:
            print(f"create_grinrank_imageエラー: {e}")
            import traceback

            traceback.print_exc()
        raise


def create_daily_graph(dates: list, grin_counts: list, batting_avgs: list) -> str:
    """過去7日間のグラフを生成

    Args:
        dates: 日付リスト
        grin_counts: grin数リスト
        batting_avgs: 打率リスト

    Returns:
        str: グラフ画像ファイルのパス

    """
    try:
        # フォントパスの設定
        font_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fonts")
        font_path = os.path.join(font_dir, "UDShingoL.otf")

        # 日付ラベル作成
        date_labels = [f"{d.month}/{d.day}" for d in dates]

        # グラフ作成
        fig, ax1 = plt.subplots(figsize=(8, 4), facecolor="#2C2F33")
        ax1.set_facecolor("#2C2F33")

        # 棒グラフ（grin数）
        x_positions = range(len(date_labels))
        _bars = ax1.bar(
            x_positions,
            grin_counts,
            color="#5865F2",
            width=0.6,
            label="Grin数",
        )
        ax1.set_xlabel("日付", color="white")
        ax1.set_ylabel("Grin数", color="#5865F2")
        ax1.tick_params(axis="y", labelcolor="#5865F2", colors="white")
        ax1.tick_params(axis="x", colors="white")

        # X軸ラベル設定
        ax1.set_xticks(x_positions)
        ax1.set_xticklabels(date_labels)

        # 第2Y軸（打率）
        ax2 = ax1.twinx()
        _line = ax2.plot(
            x_positions,
            batting_avgs,
            color="#ED4245",
            marker="o",
            linewidth=2,
            label="打率",
        )
        ax2.set_ylabel("打率 (%)", color="#ED4245")
        ax2.tick_params(axis="y", labelcolor="#ED4245", colors="white")
        ax2.set_ylim(0, 100)

        # フォント設定
        try:
            prop = fm.FontProperties(fname=font_path, size=10)
            ax1.set_xlabel("日付", fontproperties=prop, color="white")
            ax1.set_ylabel("Grin数", fontproperties=prop, color="#5865F2")
            ax2.set_ylabel("打率 (%)", fontproperties=prop, color="#ED4245")
            for label in ax1.get_xticklabels():
                label.set_fontproperties(prop)
        except Exception:
            pass

        # グリッド
        ax1.grid(axis="y", alpha=0.2, color="white")

        # 枠線設定
        ax1.spines["top"].set_visible(False)
        ax1.spines["bottom"].set_color("white")
        ax1.spines["left"].set_color("#5865F2")
        ax1.spines["right"].set_visible(False)
        ax2.spines["top"].set_visible(False)
        ax2.spines["bottom"].set_visible(False)
        ax2.spines["left"].set_visible(False)
        ax2.spines["right"].set_color("#ED4245")

        # タイトル
        try:
            title_prop = fm.FontProperties(fname=font_path, size=12)
            plt.title(
                "過去7日間のGrinの数と打率の推移のグラフ",
                fontproperties=title_prop,
                color="white",
                pad=10,
            )
        except Exception:
            plt.title("過去7日間のGrinの数と打率の推移のグラフ", color="white", pad=10)

        # レイアウト調整
        plt.tight_layout()

        # 一時ファイルに保存
        graph_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        graph_temp_path = graph_temp.name
        graph_temp.close()
        plt.savefig(
            graph_temp_path,
            dpi=100,
            bbox_inches="tight",
            facecolor="#2C2F33",
            edgecolor="none",
            transparent=False,
        )
        plt.close(fig)

        return graph_temp_path

    except Exception as e:
        if debug:
            print(f"create_daily_graphエラー: {e}")
            import traceback

            traceback.print_exc()
        raise
