"""
試験的なコマンド群
/test grinrank - 画像形式のgrinrankコマンド
"""

import discord
from discord import app_commands
import os
import json
import time
import tempfile
from datetime import datetime, timedelta
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from PIL import Image, ImageDraw, ImageFont
from pilmoji import Pilmoji

from core.zichi import enforce_zichi_block
from core.log import insert_command_log
from spam.protection import is_overload_allowed
from database.connection import run_statdb_query, run_db_query
from utils.cache import load_json_cache, save_json_cache, get_reference_data_label
from config import debug, CACHE_DIR


async def setup_test_commands(tree: app_commands.CommandTree, client: discord.Client):
    """試験コマンドを登録"""
    
    # /testグループを作成
    test_group = app_commands.Group(name="test", description="試験的な機能のコマンド群")
    
    @test_group.command(name="grinrank", description="【試験】画像形式の:grin:ランキング")
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
                await ctx.response.send_message("現在過負荷対策により専科外では使えません", ephemeral=True)
                insert_command_log(ctx, "/test grinrank", "DENY_OVERLOAD")
                return
            
            # 処理開始を通知
            await ctx.response.defer()
            defer_time = time.time()
            print(f"[Timer] defer完了: {defer_time - start_time:.3f}秒")
            
            # ユーザー情報取得
            user = getattr(ctx, "user", None) or getattr(ctx, "author", None)
            username = getattr(user, "display_name", None) or getattr(user, "name", str(user))
            uid = int(getattr(user, "id", 0) or 0)
            
            # 参照データラベル取得
            reference_label = get_reference_data_label()
            
            # データ取得
            data_start = time.time()
            grinrank_data = get_grinrank_data(uid)
            data_end = time.time()
            print(f"[Timer] データ取得完了: {data_end - data_start:.3f}秒")
            
            if grinrank_data is None:
                embed = discord.Embed(title="データなし", description="データが取得できませんでした。")
                embed.set_footer(text="SEKAM2 - SEKAMの2", icon_url="https://d.kakikou.app/sekam2logo.png")
                await ctx.followup.send(f"{username}の:grin:ランキング（試験版）\n{reference_label}", embed=embed)
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
            await ctx.followup.send(
                f"{username}の:grin:ランキング（試験版）\n{reference_label}",
                file=file
            )
            send_end = time.time()
            print(f"[Timer] Discord送信完了: {send_end - send_start:.3f}秒")
            
            # 一時ファイル削除
            try:
                os.unlink(image_path)
            except Exception:
                pass
            
            total_time = time.time() - start_time
            print(f"[Timer] 総処理時間: {total_time:.3f}秒")
            
            insert_command_log(ctx, "/test grinrank", "OK")
            
        except Exception as e:
            if debug:
                print(f"test grinrankエラー: {e}")
                import traceback
                traceback.print_exc()
            insert_command_log(ctx, "/test grinrank", f"ERROR:{e}")
            try:
                if not ctx.response.is_done():
                    await ctx.response.send_message("取得中にエラーが発生しました。", ephemeral=True)
                else:
                    await ctx.followup.send("取得中にエラーが発生しました。", ephemeral=True)
            except Exception:
                pass
    
    # グループをツリーに追加
    tree.add_command(test_group)


def get_grinrank_data(user_id: int) -> dict:
    """
    grinrankに必要な全データを取得
    
    Args:
        user_id: ユーザーID
    
    Returns:
        dict: 各種データを含む辞書、エラー時はNone
    """
    try:
        import time
        func_start = time.time()
        
        data = {}
        
        # 1. 全体ランキングデータ（キャッシュ使用）
        rank_start = time.time()
        cache_path = os.path.join(CACHE_DIR, "grinrank.json")
        grin_rows = load_json_cache(cache_path, [])
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
            save_json_cache(cache_path, grin_rows)
        
        # 自分の順位と個数を計算
        total = len(grin_rows)
        grincount = 0
        has_user = False
        for r in grin_rows:
            try:
                aid = int(str(r[0])) if r[0] is not None else 0
                cnt = int(r[1]) if r[1] is not None else 0
            except Exception:
                continue
            if aid == user_id:
                grincount = cnt
                has_user = True
                break
        
        if not has_user or total == 0:
            return None
        
        # 順位計算
        greater = sum(1 for r in grin_rows if (int(r[1]) if r[1] is not None else 0) > grincount)
        rank = greater + 1
        
        # パーセント計算
        outrank = sum(1 for r in grin_rows if (int(r[1]) if r[1] is not None else 0) < grincount)
        percent = int(outrank * 100 / total) if total > 0 else 0
        
        data['rank'] = rank
        data['grincount'] = grincount
        data['percent'] = percent
        data['total'] = total
        print(f"[Timer] - 全体ランキング取得: {time.time() - rank_start:.3f}秒")
        
        # 2. 打率計算
        batting_start = time.time()
        # 総メッセージ数
        sql_total = "SELECT COUNT(*) as total FROM messages WHERE author_id = %s"
        row_total = run_statdb_query(sql_total, (user_id,), fetch="one")
        total_messages = int(row_total[0]) if row_total and row_total[0] is not None else 0
        
        # :grin:付きメッセージ数
        sql_grin = (
            "SELECT COUNT(DISTINCT r.message_id) as count "
            "FROM reactions r JOIN messages m ON r.message_id = m.id "
            "WHERE r.emoji_name = 'grin' AND m.author_id = %s"
        )
        row_grin = run_statdb_query(sql_grin, (user_id,), fetch="one")
        grin_messages = int(row_grin[0]) if row_grin and row_grin[0] is not None else 0
        
        batting_avg = (grin_messages * 100.0 / total_messages) if total_messages > 0 else 0.0
        data['batting_avg'] = batting_avg
        print(f"[Timer] - 打率計算: {time.time() - batting_start:.3f}秒")
        
        # 3. 過去7日間のデータ取得
        daily_start = time.time()
        daily_data = get_daily_grin_data(user_id)
        data['daily_data'] = daily_data
        print(f"[Timer] - 過去7日間データ取得: {time.time() - daily_start:.3f}秒")
        
        # 4. 期間別ランキング
        period_start = time.time()
        period_ranks = get_period_rankings(user_id)
        data['period_ranks'] = period_ranks
        print(f"[Timer] - 期間別ランキング取得: {time.time() - period_start:.3f}秒")
        
        print(f"[Timer] - データ取得関数合計: {time.time() - func_start:.3f}秒")
        return data
        
    except Exception as e:
        if debug:
            print(f"get_grinrank_dataエラー: {e}")
            import traceback
            traceback.print_exc()
        return None


def get_daily_grin_data(user_id: int) -> dict:
    """
    過去7日間の日次データを取得
    
    Returns:
        dict: {
            'dates': [日付リスト],
            'grin_counts': [grin数リスト],
            'batting_avgs': [打率リスト]
        }
    """
    try:
        # 参照データの最終日を取得
        row = run_db_query("SELECT dblastupdate FROM config WHERE id = 1 LIMIT 1", (), fetch="one")
        if not row or row[0] is None:
            # デフォルトで今日
            end_date = datetime.now().date()
        else:
            end_date = row[0] if isinstance(row[0], datetime) else datetime.fromisoformat(str(row[0]))
            if isinstance(end_date, datetime):
                end_date = end_date.date()
        
        # 過去7日間の日付リストを生成
        dates = [(end_date - timedelta(days=i)) for i in range(6, -1, -1)]
        
        # 日次grin数を取得
        sql_grin = (
            "SELECT DATE(m.timestamp) as date, SUM(r.count) as grincount "
            "FROM reactions r JOIN messages m ON r.message_id = m.id "
            "WHERE r.emoji_name = 'grin' AND m.author_id = %s "
            "  AND DATE(m.timestamp) >= %s AND DATE(m.timestamp) <= %s "
            "GROUP BY DATE(m.timestamp)"
        )
        start_date = dates[0]
        rows_grin = run_statdb_query(sql_grin, (user_id, start_date, end_date), fetch="all")
        
        grin_dict = {}
        for row in (rows_grin or []):
            date_val = row[0]
            if isinstance(date_val, datetime):
                date_val = date_val.date()
            grin_dict[date_val] = int(row[1]) if row[1] is not None else 0
        
        # 日次総メッセージ数を取得
        sql_total = (
            "SELECT DATE(timestamp) as date, COUNT(*) as total "
            "FROM messages WHERE author_id = %s "
            "  AND DATE(timestamp) >= %s AND DATE(timestamp) <= %s "
            "GROUP BY DATE(timestamp)"
        )
        rows_total = run_statdb_query(sql_total, (user_id, start_date, end_date), fetch="all")
        
        total_dict = {}
        for row in (rows_total or []):
            date_val = row[0]
            if isinstance(date_val, datetime):
                date_val = date_val.date()
            total_dict[date_val] = int(row[1]) if row[1] is not None else 0
        
        # 日次grin付きメッセージ数を取得
        sql_grin_msg = (
            "SELECT DATE(m.timestamp) as date, COUNT(DISTINCT r.message_id) as count "
            "FROM reactions r JOIN messages m ON r.message_id = m.id "
            "WHERE r.emoji_name = 'grin' AND m.author_id = %s "
            "  AND DATE(m.timestamp) >= %s AND DATE(m.timestamp) <= %s "
            "GROUP BY DATE(m.timestamp)"
        )
        rows_grin_msg = run_statdb_query(sql_grin_msg, (user_id, start_date, end_date), fetch="all")
        
        grin_msg_dict = {}
        for row in (rows_grin_msg or []):
            date_val = row[0]
            if isinstance(date_val, datetime):
                date_val = date_val.date()
            grin_msg_dict[date_val] = int(row[1]) if row[1] is not None else 0
        
        # 各日のデータを整理
        grin_counts = []
        batting_avgs = []
        
        for date in dates:
            grin_count = grin_dict.get(date, 0)
            total_msg = total_dict.get(date, 0)
            grin_msg = grin_msg_dict.get(date, 0)
            
            grin_counts.append(grin_count)
            
            if total_msg > 0:
                batting_avg = (grin_msg * 100.0 / total_msg)
            else:
                batting_avg = 0.0
            batting_avgs.append(batting_avg)
        
        return {
            'dates': dates,
            'grin_counts': grin_counts,
            'batting_avgs': batting_avgs
        }
        
    except Exception as e:
        if debug:
            print(f"get_daily_grin_dataエラー: {e}")
            import traceback
            traceback.print_exc()
        # エラー時は空データを返す
        end_date = datetime.now().date()
        dates = [(end_date - timedelta(days=i)) for i in range(6, -1, -1)]
        return {
            'dates': dates,
            'grin_counts': [0] * 7,
            'batting_avgs': [0.0] * 7
        }


def get_period_rankings(user_id: int) -> dict:
    """
    期間別ランキングを取得（日間/週間/月間）
    最適化版: 30日分のデータを1回のクエリで取得し、Python側でフィルタリング
    キャッシュ有効期限: 10分
    
    Returns:
        dict: {
            'daily': {'rank': int, 'count': int},
            'weekly': {'rank': int, 'count': int},
            'monthly': {'rank': int, 'count': int}
        }
    """
    try:
        # 参照データの最終日を取得
        row = run_db_query("SELECT dblastupdate FROM config WHERE id = 1 LIMIT 1", (), fetch="one")
        if not row or row[0] is None:
            end_date = datetime.now()
        else:
            end_date = row[0] if isinstance(row[0], datetime) else datetime.fromisoformat(str(row[0]))
        
        # キャッシュの確認
        cache_file = os.path.join(CACHE_DIR, "period_rankings_raw.json")
        cache_valid = False
        cached_data = None
        
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                    cache_timestamp = cached_data.get('timestamp', 0)
                    cache_age = time.time() - cache_timestamp
                    # 10分以内のキャッシュは有効
                    if cache_age < 600:
                        cache_valid = True
                        if debug:
                            print(f"[Cache] 期間別ランキングキャッシュ使用 (age: {cache_age:.1f}秒)")
            except Exception as e:
                if debug:
                    print(f"[Cache] キャッシュ読み込みエラー: {e}")
        
        # キャッシュが有効な場合は使用
        if cache_valid and cached_data:
            all_user_data = cached_data.get('data', [])
        else:
            # 30日分のデータを1回のクエリで取得
            start_date = end_date - timedelta(days=30)
            
            sql = (
                "SELECT m.author_id, m.timestamp, r.count "
                "FROM reactions r JOIN messages m ON r.message_id = m.id "
                "WHERE r.emoji_name = 'grin' AND m.timestamp >= %s AND m.timestamp <= %s"
            )
            rows = run_statdb_query(sql, (start_date, end_date), fetch="all") or []
            
            # ユーザーごとに集計（author_id -> [(timestamp, count), ...]）
            user_messages = {}
            for row in rows:
                try:
                    author_id = int(row[0]) if row[0] is not None else 0
                    timestamp = row[1] if isinstance(row[1], datetime) else datetime.fromisoformat(str(row[1]))
                    count = int(row[2]) if row[2] is not None else 0
                    
                    if author_id not in user_messages:
                        user_messages[author_id] = []
                    user_messages[author_id].append((timestamp, count))
                except Exception:
                    continue
            
            # 各ユーザーの期間別集計を事前計算
            all_user_data = []
            for author_id, messages in user_messages.items():
                daily_count = 0
                weekly_count = 0
                monthly_count = 0
                
                daily_start = end_date - timedelta(days=1)
                weekly_start = end_date - timedelta(days=7)
                monthly_start = end_date - timedelta(days=30)
                
                for timestamp, count in messages:
                    monthly_count += count
                    if timestamp >= weekly_start:
                        weekly_count += count
                    if timestamp >= daily_start:
                        daily_count += count
                
                all_user_data.append({
                    'author_id': author_id,
                    'daily': daily_count,
                    'weekly': weekly_count,
                    'monthly': monthly_count
                })
            
            # キャッシュに保存
            try:
                os.makedirs(CACHE_DIR, exist_ok=True)
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        'timestamp': time.time(),
                        'data': all_user_data
                    }, f, ensure_ascii=False)
                if debug:
                    print(f"[Cache] 期間別ランキングをキャッシュに保存")
            except Exception as e:
                if debug:
                    print(f"[Cache] キャッシュ保存エラー: {e}")
        
        # 期間ごとにランキングを計算
        result = {}
        for period_name in ['daily', 'weekly', 'monthly']:
            # 該当期間のカウントでソート
            sorted_users = sorted(all_user_data, key=lambda x: x[period_name], reverse=True)
            
            # ユーザーの順位とカウントを取得
            user_count = 0
            rank = 0
            
            for idx, user_data in enumerate(sorted_users):
                if user_data['author_id'] == user_id:
                    user_count = user_data[period_name]
                    # 同じカウントを持つユーザーがいる場合、最高順位を付与
                    rank = idx + 1
                    break
            
            result[period_name] = {
                'rank': rank,
                'count': user_count
            }
        
        return result
        
    except Exception as e:
        if debug:
            print(f"get_period_rankingsエラー: {e}")
            import traceback
            traceback.print_exc()
        return {
            'daily': {'rank': 0, 'count': 0},
            'weekly': {'rank': 0, 'count': 0},
            'monthly': {'rank': 0, 'count': 0}
        }


def create_grinrank_image(data: dict, username: str, reference_label: str) -> str:
    """
    grinrankの画像を生成
    
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
        emoji_font_path = os.path.join(font_dir, "twiemoji.ttf")
        
        # グラフを生成
        graph_start = time.time()
        graph_path = create_daily_graph(
            data['daily_data']['dates'],
            data['daily_data']['grin_counts'],
            data['daily_data']['batting_avgs']
        )
        graph_end = time.time()
        print(f"[Timer] - グラフ生成: {graph_end - graph_start:.3f}秒")
        
        # 背景画像を読み込み
        bg_load_start = time.time()
        bg_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "bg", "bg_grinrank.png")
        bg = Image.open(bg_path).convert('RGBA')
        bg_width, bg_height = bg.size
        print(f"[Timer] - 背景画像読込: {time.time() - bg_load_start:.3f}秒")
        
        # グラフ画像を読み込み
        graph_load_start = time.time()
        graph_img = Image.open(graph_path).convert('RGBA')
        print(f"[Timer] - グラフ画像読込: {time.time() - graph_load_start:.3f}秒")
        
        # グラフを背景に貼り付け（右上に配置）
        paste_start = time.time()
        graph_width, graph_height = graph_img.size
        graph_x = bg_width - graph_width - 50  # 右端から50pxの余白
        graph_y = 150  # 上から150pxの位置（より上に配置）
        bg.paste(graph_img, (graph_x, graph_y), graph_img)
        print(f"[Timer] - グラフ貼付: {time.time() - paste_start:.3f}秒")
        
        # テキストを描画
        draw = ImageDraw.Draw(bg)
        
        font_load_start = time.time()
        try:
            # フォント読み込み
            font_title = ImageFont.truetype(normal_font_path, 36)  # 30 → 36 に拡大
            font_72 = ImageFont.truetype(normal_font_path, 72)
            font_60 = ImageFont.truetype(normal_font_path, 60)
            font_48 = ImageFont.truetype(normal_font_path, 48)
            font_30 = ImageFont.truetype(light_font_path, 30)
            font_24 = ImageFont.truetype(light_font_path, 24)  # 参照データ用に追加
        except Exception:
            # フォールバック
            font_title = ImageFont.load_default()
            font_72 = ImageFont.load_default()
            font_60 = ImageFont.load_default()
            font_48 = ImageFont.load_default()
            font_30 = ImageFont.load_default()
            font_24 = ImageFont.load_default()
        print(f"[Timer] - フォント読込: {time.time() - font_load_start:.3f}秒")
        
        # Pilmojiを使用してテキストを描画
        text_start = time.time()
        with Pilmoji(bg) as pilmoji:
            # タイトル（上部中央）- サイズを36ptに拡大
            title_text = f"{username}の:grin:ランキング"
            pilmoji.text((50, 40), title_text, font=font_title, fill='white')
            
            # コラム1（左上）- 順位・個数・パーセントのみ（ラベルは背景に含まれている）
            # 25px左に移動（130 → 105）
            col1_x = 80 + 50 - 25  # 105
            col1_y_start = 120 + 15  # 135
            
            # 順位（ラベルなし）
            rank_text = f"{data['rank']}位"
            pilmoji.text((col1_x, col1_y_start + 50), rank_text, font=font_72, fill='white')
            
            # 個数
            count_text = f"{data['grincount']}個"
            pilmoji.text((col1_x, col1_y_start + 140), count_text, font=font_60, fill='white')
            
            # パーセントのみ（"上位"は背景に含まれている）
            # 左上を0として(180, 450)の位置に配置
            percent_text = f"{data['percent']}%"
            pilmoji.text((180, 450), percent_text, font=font_60, fill='white')
            
            # コラム3（左下）- 期間別ランキング（ラベルなし、順位と個数のみ）
            # 90px右に、12px下に移動
            col3_x = 80 + 90  # 170
            col3_y_start = bg_height - 220 + 12  # bg_height - 208
            
            period_data = data['period_ranks']
            daily_text = f"{period_data['daily']['rank']}位/{period_data['daily']['count']}個"
            weekly_text = f"{period_data['weekly']['rank']}位/{period_data['weekly']['count']}個"
            monthly_text = f"{period_data['monthly']['rank']}位/{period_data['monthly']['count']}個"
            
            pilmoji.text((col3_x, col3_y_start), daily_text, font=font_48, fill='white')
            pilmoji.text((col3_x, col3_y_start + 60), weekly_text, font=font_48, fill='white')
            pilmoji.text((col3_x, col3_y_start + 120), monthly_text, font=font_48, fill='white')
            
            # コラム4（右中央）- パーセントのみ（"打率"は背景に含まれている）
            # 30px左に移動（520 → 550）
            # 右下を0とした時、文字の右上が(550, 140)の位置に
            col4_x = bg_width - 550  # 730
            col4_y = bg_height - 140
            
            batting_text = f"{data['batting_avg']:.1f}%"
            pilmoji.text((col4_x, col4_y), batting_text, font=font_72, fill='white', align='right')
            
            # コラム5（右下）- 日付のみ（他は背景に含まれている）
            # サイズを24ptに縮小し、右端に寄せる
            col5_y_start = bg_height - 140
            
            # 参照データから日付部分のみを抽出
            clean_label = reference_label.replace('-# ', '').replace('-#', '')
            # "参照データ:"を削除
            if '参照データ:' in clean_label:
                date_only = clean_label.replace('参照データ:', '')
            else:
                date_only = clean_label
            
            # テキストの幅を計算して右端に配置
            bbox = pilmoji.getsize(date_only, font=font_24)
            text_width = bbox[0] if bbox else len(date_only) * 12
            col5_x = bg_width - text_width - 30  # 右端から30pxの余白
            
            pilmoji.text((col5_x, col5_y_start + 70), date_only, font=font_24, fill='white')
        
        print(f"[Timer] - テキスト描画: {time.time() - text_start:.3f}秒")
        
        # 最終画像を保存
        save_start = time.time()
        final_temp = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
        final_temp_path = final_temp.name
        final_temp.close()
        bg.save(final_temp_path, 'PNG')
        print(f"[Timer] - 画像保存: {time.time() - save_start:.3f}秒")
        
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
    """
    過去7日間のグラフを生成
    
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
        fig, ax1 = plt.subplots(figsize=(8, 4), facecolor='#2C2F33')
        ax1.set_facecolor('#2C2F33')
        
        # 棒グラフ（grin数）
        x_positions = range(len(date_labels))
        bars = ax1.bar(x_positions, grin_counts, color='#5865F2', width=0.6, label='Grin数')
        ax1.set_xlabel('日付', color='white')
        ax1.set_ylabel('Grin数', color='#5865F2')
        ax1.tick_params(axis='y', labelcolor='#5865F2', colors='white')
        ax1.tick_params(axis='x', colors='white')
        
        # X軸ラベル設定
        ax1.set_xticks(x_positions)
        ax1.set_xticklabels(date_labels)
        
        # 第2Y軸（打率）
        ax2 = ax1.twinx()
        line = ax2.plot(x_positions, batting_avgs, color='#ED4245', marker='o', linewidth=2, label='打率')
        ax2.set_ylabel('打率 (%)', color='#ED4245')
        ax2.tick_params(axis='y', labelcolor='#ED4245', colors='white')
        ax2.set_ylim(0, 100)
        
        # フォント設定
        try:
            prop = fm.FontProperties(fname=font_path, size=10)
            ax1.set_xlabel('日付', fontproperties=prop, color='white')
            ax1.set_ylabel('Grin数', fontproperties=prop, color='#5865F2')
            ax2.set_ylabel('打率 (%)', fontproperties=prop, color='#ED4245')
            for label in ax1.get_xticklabels():
                label.set_fontproperties(prop)
        except Exception:
            pass
        
        # グリッド
        ax1.grid(axis='y', alpha=0.2, color='white')
        
        # 枠線設定
        ax1.spines['top'].set_visible(False)
        ax1.spines['bottom'].set_color('white')
        ax1.spines['left'].set_color('#5865F2')
        ax1.spines['right'].set_visible(False)
        ax2.spines['top'].set_visible(False)
        ax2.spines['bottom'].set_visible(False)
        ax2.spines['left'].set_visible(False)
        ax2.spines['right'].set_color('#ED4245')
        
        # タイトル
        try:
            title_prop = fm.FontProperties(fname=font_path, size=12)
            plt.title('過去7日間のGrinの数と打率の推移のグラフ', fontproperties=title_prop, color='white', pad=10)
        except Exception:
            plt.title('過去7日間のGrinの数と打率の推移のグラフ', color='white', pad=10)
        
        # レイアウト調整
        plt.tight_layout()
        
        # 一時ファイルに保存
        graph_temp = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
        graph_temp_path = graph_temp.name
        graph_temp.close()
        plt.savefig(graph_temp_path, dpi=100, bbox_inches='tight',
                    facecolor='#2C2F33', edgecolor='none', transparent=False)
        plt.close(fig)
        
        return graph_temp_path
        
    except Exception as e:
        if debug:
            print(f"create_daily_graphエラー: {e}")
            import traceback
            traceback.print_exc()
        raise
