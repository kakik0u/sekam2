"""
形態素解析関連のコマンド群
/markov, /wordcloud, /wordrank
"""
import io
import random
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
import discord
from discord import Client, app_commands
from PIL import Image, ImageDraw, ImageFont
from core.log import insert_command_log
from core.zichi import enforce_zichi_block
from database.connection import run_statdb_query
from spam.protection import is_overload_allowed
try:
    from wordcloud import WordCloud
    WORDCLOUD_LIBRARY_AVAILABLE = True
except ImportError:
    WORDCLOUD_LIBRARY_AVAILABLE = False
WORDCLOUD_FONT_PATH = "./fonts/NotoSansCJKjp-Regular.otf"
WORDCLOUD_FALLBACK_FONT_PATH = "./fonts/NotoSansCJKjp-Regular.otf"
@dataclass
class TimeRange:
    start: str
    end: str
    label: str
async def setup_morpheme_commands(tree: app_commands.CommandTree, client: Client):
    @tree.command(name="markov", description="マルコフ連鎖でテキストを生成（2-gram）")
    @app_commands.describe(
        ch="チャンネル範囲",
        mode="精度（ノーマル=bigram / 高精度=trigram）",
        start="開始ワード（任意）",
        channel_id="特定チャンネルID（ch=全体の場合のみ有効）",
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    async def markov(
        ctx: discord.Interaction,
        ch: Literal["全体", "実行したチャンネル", "自分"] = "自分",
        mode: Literal["ノーマル", "高精度"] = "ノーマル",
        start: str | None = None,
        channel_id: str | None = None,
    ):
        if await enforce_zichi_block(ctx, "/markov"):
            return
        use_trigram = mode == "高精度"
        print(
            f"markovコマンドが実行されました: {ctx.user.name} ({ctx.user.id}) "
            f"ch={ch} , mode={mode}, start={start}, channel_id={channel_id}"
        )
        try:
            if not is_overload_allowed(ctx):
                await ctx.response.send_message(
                    "現在過負荷対策により専科外では使えません", ephemeral=True
                )
                insert_command_log(ctx, "/markov", "DENY_OVERLOAD")
                return
            if ch == "全体":
                await ctx.response.send_message(
                    "全体は廃止されました。", ephemeral=True
                )
                return
            await ctx.response.defer()
            user_id = ctx.user.id if ch == "自分" else None
            target_channel_id = None
            if ch == "実行したチャンネル":
                target_channel_id = ctx.channel.id
            elif channel_id is not None:
                try:
                    target_channel_id = int(channel_id)
                except ValueError:
                    await ctx.edit_original_response(
                        content="チャンネルIDは数値で指定してください。"
                    )
                    insert_command_log(ctx, "/markov", "INVALID_CHANNEL_ID")
                    return
            import asyncio
            try:
                async with asyncio.timeout(60.0):
                    generated_text = await generate_markov_text(
                        user_id=user_id,
                        channel_id=target_channel_id,
                        start_word=start,
                        use_trigram=use_trigram,
                    )
            except asyncio.TimeoutError:
                await ctx.edit_original_response(
                    content="処理がタイムアウトしました。しばらくしてから再度お試しください。"
                )
                insert_command_log(ctx, "/markov", "TIMEOUT")
                return
            if not generated_text:
                await ctx.edit_original_response(
                    content="データが不足しているため、テキストを生成できませんでした。"
                )
                insert_command_log(ctx, "/markov", "NO_DATA")
                return
            processed_text = _process_newlines(generated_text)
            embed = discord.Embed(
                title="生成された文章:",
                description=processed_text,
                color=discord.Color.blue(),
            )
            embed.add_field(name="範囲", value=f"{ch}", inline=True)
            embed.add_field(name="精度", value=mode, inline=True)
            await ctx.edit_original_response(embed=embed)
            insert_command_log(ctx, "/markov", "OK")
        except Exception as e:
            print(f"markovコマンドエラー: {e}")
            import traceback
            traceback.print_exc()
            await ctx.edit_original_response(
                content=f"エラーが発生しました: {str(e)[:100]}"
            )
            insert_command_log(ctx, "/markov", f"ERROR:{str(e)[:50]}")
    @tree.command(name="wordcloud", description="ワードクラウドを生成")
    @app_commands.describe(
        mode="対象範囲",
        ui="表示スタイル",
        range="対象単語範囲",
        time="期間指定モード",
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    async def wordcloud(
        ctx: discord.Interaction,
        mode: Literal["自分", "チャンネル", "特定チャンネル"] = "自分",
        ui: Literal["スタイリッシュ", "ぎっちり"] = "ぎっちり",
        range: Literal["固有名詞のみ", "名詞/固有名詞"] = "固有名詞のみ",
        time: Literal["時間指定しない", "時間指定する"] = "時間指定しない",
    ):
        """ワードクラウド生成"""
        if await enforce_zichi_block(ctx, "/wordcloud"):
            return
        print(
            f"wordcloudコマンドが実行されました: {ctx.user.name} ({ctx.user.id}) "
            f"mode={mode}, ui={ui}, time={time}"
        )
        try:
            if not is_overload_allowed(ctx):
                await ctx.response.send_message(
                    "現在過負荷対策により専科外では使えません", ephemeral=True
                )
                insert_command_log(ctx, "/wordcloud", "DENY_OVERLOAD")
                return
            if range == "固有名詞のみ":
                pos_id_condition = "ws.pos_id IN (2)"
            else:
                pos_id_condition = "ws.pos_id IN (1,2)"
            is_time_specified = time == "時間指定する"
            if mode == "特定チャンネル":
                embed = discord.Embed(
                    title="📌 チャンネル指定",
                    description="チャンネルIDか、チャンネルのメッセージリンクをペーストしてください。",
                    color=discord.Color.blue(),
                )
                embed.set_image(url="https://sekam.site/guidemessage.png")
                view = ChannelInputView(
                    ui,
                    range,
                    pos_id_condition,
                    ctx.user.id,
                    is_time_specified,
                )
                await ctx.response.send_message(embed=embed, view=view, ephemeral=False)
                insert_command_log(ctx, "/wordcloud", "CHANNEL_INPUT_REQUESTED")
                return
            if mode == "自分":
                user_id = ctx.user.id
                channel_id = None
                scope_name = f"{ctx.user.display_name}"
            else:
                user_id = None
                channel_id = ctx.channel.id
                scope_name = f"
            if is_time_specified:
                embed = discord.Embed(
                    title="🗓 時間指定",
                    description="開始月と終了月を YYYY/MM 形式で入力してください。",
                    color=discord.Color.blurple(),
                )
                view = TimeRangeRequestView(
                    ui=ui,
                    scope_name=scope_name,
                    user_id=user_id,
                    channel_id=channel_id,
                    pos_id_condition=pos_id_condition,
                    command_user_id=ctx.user.id,
                )
                await ctx.response.send_message(embed=embed, view=view, ephemeral=False)
                insert_command_log(ctx, "/wordcloud", "TIME_RANGE_REQUESTED")
                return
            await ctx.response.defer()
            word_data = await get_wordcloud_data(
                user_id=user_id,
                channel_id=channel_id,
                pos_id_condition=pos_id_condition,
            )
            if not word_data:
                await ctx.edit_original_response(
                    content="データが不足しているため、ワードクラウドを生成できませんでした。"
                )
                insert_command_log(ctx, "/wordcloud", "NO_DATA")
                return
            if ui == "ぎっちり":
                if not WORDCLOUD_LIBRARY_AVAILABLE:
                    await ctx.edit_original_response(
                        content="ぎっちりスタイルは現在利用できません。スタイリッシュをお試しください。"
                    )
                    insert_command_log(ctx, "/wordcloud", "LIBRARY_NOT_AVAILABLE")
                    return
                image_bytes = await generate_wordcloud_image_wordcloud(word_data)
                view = WordCloudMoreButtonView(
                    word_data,
                    scope_name,
                    user_id,
                    channel_id,
                    ctx.user.id,
                    time_range=None,
                )
            else:
                image_bytes = await generate_wordcloud_image_pillow(word_data)
                view = None
            file = discord.File(fp=io.BytesIO(image_bytes), filename="wordcloud.png")
            embed = discord.Embed(
                title=f"{scope_name}のワードクラウド（{ui}）",
                color=discord.Color.green(),
            )
            embed.set_image(url="attachment://wordcloud.png")
            await ctx.edit_original_response(embed=embed, attachments=[file], view=view)
            insert_command_log(ctx, "/wordcloud", f"OK:{ui}")
        except Exception as e:
            print(f"wordcloudコマンドエラー: {e}")
            import traceback
            traceback.print_exc()
            await ctx.edit_original_response(
                content=f"エラーが発生しました: {str(e)[:100]}"
            )
            insert_command_log(ctx, "/wordcloud", f"ERROR:{str(e)[:50]}")
    @tree.command(name="wordrank", description="固有名詞ランキング")
    @app_commands.describe(mode="対象範囲", range="対象期間")
    @app_commands.allowed_installs(guilds=True, users=True)
    async def wordrank(
        ctx: discord.Interaction,
        mode: Literal["自分", "チャンネル"] = "自分",
        range: Literal[
            "全期間", "2018", "2019", "2020", "2021", "2022", "2023", "2024", "2025"
        ] = "全期間",
    ):
        """固有名詞ランキング表示（ページネーション付き）"""
        if await enforce_zichi_block(ctx, "/wordrank"):
            return
        print(
            f"wordrankコマンドが実行されました: {ctx.user.name} ({ctx.user.id}) "
            f"mode={mode}, range={range}"
        )
        try:
            if not is_overload_allowed(ctx):
                await ctx.response.send_message(
                    "現在過負荷対策により専科外では使えません", ephemeral=True
                )
                insert_command_log(ctx, "/wordrank", "DENY_OVERLOAD")
                return
            await ctx.response.defer()
            if mode == "自分":
                user_id = ctx.user.id
                channel_id = None
                scope_name = f"{ctx.user.display_name}さん"
            else:
                user_id = None
                channel_id = ctx.channel.id
                scope_name = f"
            if range == "全期間":
                year_start = None
                year_end = None
            else:
                year_start = f"{range}-01-01"
                year_end = f"{range}-12-01"
            ranking = await get_proper_noun_ranking(
                user_id=user_id,
                channel_id=channel_id,
                year_month_start=year_start,
                year_month_end=year_end,
                limit=1000,
            )
            if not ranking:
                await ctx.edit_original_response(
                    content="データが不足しているため、ランキングを表示できませんでした。"
                )
                insert_command_log(ctx, "/wordrank", "NO_DATA")
                return
            view = WordRankPaginationView(ranking, scope_name, range, ctx.user.id)
            embed = view.create_embed(page=0)
            await ctx.edit_original_response(embed=embed, view=view)
            insert_command_log(ctx, "/wordrank", "OK")
        except Exception as e:
            print(f"wordrankコマンドエラー: {e}")
            import traceback
            traceback.print_exc()
            await ctx.edit_original_response(
                content=f"エラーが発生しました: {str(e)[:100]}"
            )
            insert_command_log(ctx, "/wordrank", f"ERROR:{str(e)[:50]}")
def _process_newlines(text: str) -> str:
    """
    改行コードを処理する
    - 2行までの連続改行: そのまま保持
    - 3行以上の連続改行: "(n行 改行)" という表記に変換
    Args:
        text: 処理対象のテキスト
    Returns:
        処理後のテキスト
    Examples:
        "あいうえお\n\nかきくけこ" → "あいうえお\n\nかきくけこ" (2行なのでそのまま)
        "あいうえお\n\n\nかきくけこ" → "あいうえお(3行 改行)かきくけこ"
        "あいうえお\n\n\n\n\nかきくけこ" → "あいうえお(5行 改行)かきくけこ"
    """
    import re
    def replace_multiple_newlines(match):
        newline_count = len(match.group(0))
        return f"({newline_count}行 改行)"
    processed = re.sub(r"\n{3,}", replace_multiple_newlines, text)
    return processed
async def generate_markov_text(
    user_id: int | None,
    channel_id: int | None,
    max_length: int = 100,
    start_word: str | None = None,
    use_trigram: bool = False,
) -> str | None:
    """
    マルコフ連鎖でテキストを生成（非同期ラッパー）
    Args:
        user_id: ユーザーID（Noneで全体、user_markov/から読み込み）
        channel_id: チャンネルID（Noneで全体、channel_markov/から読み込み）
        max_length: 生成する最大文字数
        start_word: 開始ワード（指定された場合、その単語から始まる）
        use_trigram: trigramを使用する場合はTrue（高精度モード）
    Returns:
        生成されたテキスト（失敗時はNone）
    """
    import asyncio
    if user_id is not None:
        try:
            markov_data = await _load_user_markov_async(
                user_id, use_trigram=use_trigram
            )
            if not markov_data:
                if use_trigram:
                    markov_data = await _load_user_markov_async(
                        user_id, use_trigram=False
                    )
                    use_trigram = False
                if not markov_data:
                    return None
            return await asyncio.to_thread(
                _generate_text_from_json,
                markov_data,
                use_trigram=use_trigram,
                max_length=max_length,
                start_word=start_word,
            )
        except FileNotFoundError:
            return None
        except Exception as e:
            print(f"user_markov読み込みエラー: {e}")
            return None
    if channel_id is not None:
        try:
            markov_data = await _load_channel_markov_async(
                channel_id, use_trigram=use_trigram
            )
            if not markov_data:
                if use_trigram:
                    markov_data = await _load_channel_markov_async(
                        channel_id, use_trigram=False
                    )
                    use_trigram = False
                if not markov_data:
                    return None
            return await asyncio.to_thread(
                _generate_text_from_json,
                markov_data,
                use_trigram=use_trigram,
                max_length=max_length,
                start_word=start_word,
            )
        except FileNotFoundError:
            return None
        except Exception as e:
            print(f"channel_markov読み込みエラー: {e}")
            return None
    return await asyncio.to_thread(
        _generate_markov_text_sync, channel_id, max_length, start_word
    )
def _generate_markov_text_sync(
    channel_id: int | None,
    max_length: int = 100,
    start_word: str | None = None,
) -> str | None:
    """
    マルコフ連鎖でテキストを生成（同期処理、bigramのみ）
        channel_id: チャンネルID（Noneで全体、bigram_statsから取得）
        max_length: 生成する最大文字数
        start_word: 開始ワード（指定された場合、その単語から始まる）
    Returns:
        生成されたテキスト（失敗時はNone）
    """
    table_name = "bigram_stats"
    if start_word is not None:
        sql_get_word_id = "SELECT word_id FROM words WHERE word = %s LIMIT 1"
        word_id_row = run_statdb_query(sql_get_word_id, (start_word,), fetch="one")
        if not word_id_row:
            sql_start = f"""
                SELECT word1_id, word2_id
                FROM {table_name}
                ORDER BY RAND()
                LIMIT 1
            """
            start_row = run_statdb_query(sql_start, (), fetch="one")
        else:
            start_word_id = word_id_row[0]
            sql_start = f"""
                SELECT word1_id, word2_id
                FROM {table_name}
                WHERE word1_id = %s
                ORDER BY count DESC
                LIMIT 1
            """
            start_row = run_statdb_query(sql_start, (start_word_id,), fetch="one")
    else:
        sql_start = f"""
            SELECT word1_id, word2_id
            FROM {table_name}
            ORDER BY RAND()
            LIMIT 1
        """
        start_row = run_statdb_query(sql_start, (), fetch="one")
    if not start_row:
        return None
    word1_id, word2_id = start_row
    word1 = get_word_by_id(word1_id)
    word2 = get_word_by_id(word2_id)
    result = [word1, word2]
    current_word_id = word2_id
    for _ in range(50):
        if len("".join(result)) >= max_length:
            break
        sql_next = f"""
            SELECT word2_id, count
            FROM {table_name}
            WHERE word1_id = %s
            ORDER BY count DESC
            LIMIT 10
        """
        next_rows = run_statdb_query(sql_next, (current_word_id,), fetch="all")
        if not next_rows:
            sql_fallback = f"""
                SELECT word1_id, word2_id
                FROM {table_name}
                WHERE word1_id = %s
                ORDER BY RAND()
                LIMIT 1
            """
            fallback_row = run_statdb_query(
                sql_fallback, (current_word_id,), fetch="one"
            )
            if not fallback_row:
                break
            word1_id, word2_id = fallback_row
            word2 = get_word_by_id(word2_id)
            result.append(word2)
            current_word_id = word2_id
            continue
        total_count = sum(row[1] for row in next_rows)
        rand = random.randint(1, total_count)
        cumulative = 0
        next_word_id = next_rows[0][0]
        for word_id, count in next_rows:
            cumulative += count
            if cumulative >= rand:
                next_word_id = word_id
                break
        next_word = get_word_by_id(next_word_id)
        result.append(next_word)
        current_word_id = next_word_id
    return "".join(result)
async def _load_user_markov_async(user_id: int, use_trigram: bool) -> dict | None:
    """
    user_markov/{user_id}/bigram.json または trigram.json を非同期で読み込み
    Args:
        user_id: ユーザーID
        use_trigram: trigramを使用する場合はTrue
    Returns:
        JSONデータの"data"フィールド（辞書）、失敗時はNone
    """
    import asyncio
    import json
    from pathlib import Path
    filename = "trigram.json" if use_trigram else "bigram.json"
    file_path = Path(f"user_markov/{user_id}/{filename}")
    def _load_json_sync(path: Path) -> dict | None:
        if not path.exists():
            raise FileNotFoundError(f"{path} does not exist")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("data")
    return await asyncio.to_thread(_load_json_sync, file_path)
async def _load_channel_markov_async(
    channel_id: int, use_trigram: bool = False
) -> dict | None:
    """
    channel_markov/{channel_id}/bigram.json または trigram.json を非同期で読み込み
    Args:
        channel_id: チャンネルID
        use_trigram: trigramを使用する場合はTrue
    Returns:
        JSONデータの"data"フィールド（辞書）、失敗時はNone
    """
    import asyncio
    import json
    from pathlib import Path
    filename = "trigram.json" if use_trigram else "bigram.json"
    file_path = Path(f"channel_markov/{channel_id}/{filename}")
    def _load_json_sync(path: Path) -> dict | None:
        if not path.exists():
            raise FileNotFoundError(f"{path} does not exist")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("data")
    return await asyncio.to_thread(_load_json_sync, file_path)
def _generate_text_from_json(
    markov_data: dict,
    use_trigram: bool,
    max_length: int = 100,
    start_word: str | None = None,
) -> str | None:
    """
    user_markov/またはchannel_markov/のJSONデータからマルコフ連鎖テキストを生成
    Args:
        markov_data: JSONの"data"フィールド
            bigram: {"word1:word2": count, ...}
            trigram: {"word1:word2:word3": count, ...}
        use_trigram: trigramを使用する場合はTrue
        max_length: 生成する最大文字数
        start_word: 開始ワード（指定された場合、その単語から始まる）
    Returns:
        生成されたテキスト（失敗時はNone）
    """
    if not markov_data:
        return None
    all_pairs = list(markov_data.keys())
    if not all_pairs:
        return None
    if use_trigram:
        return _generate_text_from_trigram(
            markov_data, all_pairs, max_length, start_word
        )
    else:
        return _generate_text_from_bigram(
            markov_data, all_pairs, max_length, start_word
        )
def _generate_text_from_bigram(
    markov_data: dict,
    all_pairs: list,
    max_length: int,
    start_word: str | None,
) -> str | None:
    """Bigramデータからテキストを生成"""
    result = []
    if start_word:
        prefix = f"{start_word}:"
        matching_pairs = [k for k in all_pairs if k.startswith(prefix)]
        if matching_pairs:
            weighted_pairs = [(k, markov_data[k]) for k in matching_pairs]
            total = sum(count for _, count in weighted_pairs)
            rand = random.randint(1, total)
            cumulative = 0
            start_pair = matching_pairs[0]
            for pair, count in weighted_pairs:
                cumulative += count
                if cumulative >= rand:
                    start_pair = pair
                    break
        else:
            start_pair = random.choice(all_pairs)
    else:
        start_pair = random.choice(all_pairs)
    words = start_pair.split(":")
    if len(words) < 2:
        return None
    current_word = words[0]
    result.append(current_word)
    for _ in range(50):
        if len("".join(result)) >= max_length:
            break
        prefix = f"{current_word}:"
        candidates = [(k, v) for k, v in markov_data.items() if k.startswith(prefix)]
        if not candidates:
            break
        total_count = sum(count for _, count in candidates)
        rand = random.randint(1, total_count)
        cumulative = 0
        next_word = None
        for key, count in candidates:
            cumulative += count
            if cumulative >= rand:
                words = key.split(":")
                if len(words) >= 2:
                    next_word = words[1]
                break
        if not next_word:
            break
        result.append(next_word)
        current_word = next_word
    return "".join(result) if result else None
def _generate_text_from_trigram(
    markov_data: dict,
    all_pairs: list,
    max_length: int,
    start_word: str | None,
) -> str | None:
    """Trigramデータからテキストを生成"""
    result = []
    if start_word:
        matching_pairs = [k for k in all_pairs if k.startswith(f"{start_word}:")]
        if matching_pairs:
            weighted_pairs = [(k, markov_data[k]) for k in matching_pairs]
            total = sum(count for _, count in weighted_pairs)
            rand = random.randint(1, total)
            cumulative = 0
            start_pair = matching_pairs[0]
            for pair, count in weighted_pairs:
                cumulative += count
                if cumulative >= rand:
                    start_pair = pair
                    break
        else:
            start_pair = random.choice(all_pairs)
    else:
        start_pair = random.choice(all_pairs)
    words = start_pair.split(":")
    if len(words) < 3:
        return None
    result.append(words[0])
    result.append(words[1])
    prev_word = words[0]
    current_word = words[1]
    for _ in range(50):
        if len("".join(result)) >= max_length:
            break
        prefix = f"{prev_word}:{current_word}:"
        candidates = [(k, v) for k, v in markov_data.items() if k.startswith(prefix)]
        if not candidates:
            break
        total_count = sum(count for _, count in candidates)
        rand = random.randint(1, total_count)
        cumulative = 0
        next_word = None
        for key, count in candidates:
            cumulative += count
            if cumulative >= rand:
                words = key.split(":")
                if len(words) >= 3:
                    next_word = words[2]
                break
        if not next_word:
            break
        result.append(next_word)
        prev_word = current_word
        current_word = next_word
    return "".join(result) if result else None
class ChannelInputModal(discord.ui.Modal, title="チャンネル指定"):
    """特定チャンネルのワードクラウド用のチャンネル入力Modal"""
    channel_input = discord.ui.TextInput(
        label="チャンネルIDまたはメッセージリンク",
        placeholder="数字のIDか、メッセージリンクをペーストしてください",
        required=True,
        max_length=200,
    )
    def __init__(
        self,
        ui: str,
        range_condition: str,
        pos_id_condition: str,
        original_message=None,
        command_user_id: int | None = None,
        is_time_specified: bool = False,
    ):
        super().__init__()
        self.ui = ui
        self.range_condition = range_condition
        self.pos_id_condition = pos_id_condition
        self.original_message = original_message
        self.command_user_id = command_user_id
        self.is_time_specified = is_time_specified
    async def on_submit(self, interaction: discord.Interaction):
        """Modal送信時の処理"""
        await interaction.response.defer()
        try:
            input_text = self.channel_input.value.strip()
            channel_id = None
            if input_text.startswith("https://discord.com/channels/"):
                parts = input_text.replace("https://discord.com/channels/", "").split(
                    "/"
                )
                if len(parts) >= 2:
                    guild_id = parts[0]
                    extracted_channel_id = parts[1]
                    if guild_id != "518371205452005387":
                        await interaction.followup.send(
                            f"❌ 指定されたサーバーID（{guild_id}）は専科サーバーではありません。",
                            ephemeral=True,
                        )
                        return
                    channel_id = int(extracted_channel_id)
                else:
                    await interaction.followup.send(
                        "❌ メッセージリンクの形式が正しくありません。", ephemeral=True
                    )
                    return
            elif input_text == "専科全体":
                channel_id = None
            else:
                try:
                    channel_id = int(input_text)
                except ValueError:
                    await interaction.followup.send(
                        "❌ チャンネルIDは数字で入力してください。", ephemeral=True
                    )
                    return
            scope_name = None
            try:
                channel = interaction.client.get_channel(channel_id)
                if channel and hasattr(channel, "name"):
                    scope_name = f"
            except Exception:
                pass
            if scope_name is None:
                try:
                    channel = await interaction.client.fetch_channel(channel_id)
                    if channel and hasattr(channel, "name"):
                        scope_name = f"
                except Exception:
                    pass
            if scope_name is None:
                try:
                    from database.connection import run_statdb_query
                    sql = "SELECT name FROM channels WHERE id = %s"
                    result = run_statdb_query(sql, (channel_id,), fetch="one")
                    if result and result[0]:
                        scope_name = f"
                except Exception:
                    pass
            if channel_id == 0:
                scope_name = "専科全体"
            if scope_name is None:
                scope_name = f"チャンネル<{channel_id}>"
            if self.is_time_specified:
                time_embed = discord.Embed(
                    title="🗓 時間指定",
                    description="開始月と終了月を YYYY/MM 形式で入力してください。",
                    color=discord.Color.blurple(),
                )
                time_view = TimeRangeRequestView(
                    ui=self.ui,
                    scope_name=scope_name,
                    user_id=None,
                    channel_id=channel_id,
                    pos_id_condition=self.pos_id_condition,
                    command_user_id=self.command_user_id,
                )
                await interaction.followup.edit_message(
                    self.original_message.id,
                    content=None,
                    embed=time_embed,
                    attachments=[],
                    view=time_view,
                )
                return
            word_data = await get_wordcloud_data(
                user_id=None,
                channel_id=channel_id,
                pos_id_condition=self.pos_id_condition,
            )
            if not word_data:
                await self.original_message.edit(
                    content="データが不足しているため、ワードクラウドを生成できませんでした。",
                    embed=None,
                    view=None,
                )
                return
            if self.ui == "ぎっちり":
                if not WORDCLOUD_LIBRARY_AVAILABLE:
                    await self.original_message.edit(
                        content="ぎっちりスタイルは現在利用できません。",
                        embed=None,
                        view=None,
                    )
                    return
                image_bytes = await generate_wordcloud_image_wordcloud(word_data)
                view = WordCloudMoreButtonView(
                    word_data,
                    scope_name,
                    None,
                    channel_id,
                    self.command_user_id,
                    time_range=None,
                )
            else:
                image_bytes = await generate_wordcloud_image_pillow(word_data)
                view = None
            file = discord.File(fp=io.BytesIO(image_bytes), filename="wordcloud.png")
            embed = discord.Embed(
                title=f"{scope_name}のワードクラウド（{self.ui}）",
                color=discord.Color.green(),
            )
            embed.set_image(url="attachment://wordcloud.png")
            await interaction.followup.edit_message(
                self.original_message.id, embed=embed, attachments=[file], view=view
            )
        except Exception as e:
            print(f"チャンネル入力Modalエラー: {e}")
            import traceback
            traceback.print_exc()
            await interaction.followup.send(
                f"エラーが発生しました: {str(e)[:100]}", ephemeral=True
            )
class ChannelInputView(discord.ui.View):
    """チャンネル入力を促すView"""
    def __init__(
        self,
        ui: str,
        range_condition: str,
        pos_id_condition: str,
        user_id: int,
        is_time_specified: bool,
    ):
        super().__init__(timeout=180)
        self.ui = ui
        self.range_condition = range_condition
        self.pos_id_condition = pos_id_condition
        self.user_id = user_id
        self.is_time_specified = is_time_specified
    @discord.ui.button(label="📝 入力する", style=discord.ButtonStyle.primary)
    async def input_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """入力ボタン"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "このボタンはコマンドを実行したユーザーのみが使用できます。",
                ephemeral=True,
            )
            return
        modal = ChannelInputModal(
            self.ui,
            self.range_condition,
            self.pos_id_condition,
            interaction.message,
            self.user_id,
            self.is_time_specified,
        )
        await interaction.response.send_modal(modal)
class TimeRangeRequestView(discord.ui.View):
    """時間指定を促すためのView"""
    def __init__(
        self,
        ui: str,
        scope_name: str,
        user_id: int | None,
        channel_id: int | None,
        pos_id_condition: str,
        command_user_id: int,
    ):
        super().__init__(timeout=180)
        self.ui = ui
        self.scope_name = scope_name
        self.user_id = user_id
        self.channel_id = channel_id
        self.pos_id_condition = pos_id_condition
        self.command_user_id = command_user_id
    @discord.ui.button(label="🗓 期間を入力", style=discord.ButtonStyle.primary)
    async def open_modal(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.id != self.command_user_id:
            await interaction.response.send_message(
                "このボタンはコマンドを実行したユーザーのみが使用できます。",
                ephemeral=True,
            )
            return
        if interaction.message is None:
            await interaction.response.send_message(
                "元のメッセージを取得できませんでした。", ephemeral=True
            )
            return
        modal = TimeRangeModal(
            ui=self.ui,
            scope_name=self.scope_name,
            user_id=self.user_id,
            channel_id=self.channel_id,
            pos_id_condition=self.pos_id_condition,
            command_user_id=self.command_user_id,
            original_message=interaction.message,
        )
        await interaction.response.send_modal(modal)
class TimeRangeModal(discord.ui.Modal, title="🗓 期間を指定"):
    """開始月・終了月を受け取るモーダル"""
    start_month = discord.ui.TextInput(
        label="開始月",
        placeholder="例: 2023/10",
        required=True,
        max_length=7,
    )
    end_month = discord.ui.TextInput(
        label="終了月",
        placeholder="例: 2024/03",
        required=True,
        max_length=7,
    )
    def __init__(
        self,
        ui: str,
        scope_name: str,
        user_id: int | None,
        channel_id: int | None,
        pos_id_condition: str,
        command_user_id: int,
        original_message: discord.Message | None,
    ):
        super().__init__()
        self.ui = ui
        self.scope_name = scope_name
        self.user_id = user_id
        self.channel_id = channel_id
        self.pos_id_condition = pos_id_condition
        self.command_user_id = command_user_id
        self.original_message = original_message
    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.command_user_id:
            await interaction.response.send_message(
                "このモーダルはコマンドを実行したユーザーのみが使用できます。",
                ephemeral=True,
            )
            return
        await interaction.response.defer()
        try:
            time_range = parse_time_range_inputs(
                self.start_month.value.strip(), self.end_month.value.strip()
            )
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return
        if not self.original_message:
            await interaction.followup.send(
                "元のメッセージを取得できませんでした。", ephemeral=True
            )
            return
        await edit_message_with_wordcloud(
            interaction=interaction,
            target_message=self.original_message,
            scope_name=self.scope_name,
            ui=self.ui,
            pos_id_condition=self.pos_id_condition,
            user_id=self.user_id,
            channel_id=self.channel_id,
            command_user_id=self.command_user_id,
            time_range=time_range,
            log_suffix="TIME_RANGE_CHANNEL" if self.channel_id else "TIME_RANGE_USER",
        )
class WordCloudMoreButtonView(discord.ui.View):
    """ぎっちりスタイル用の「もっとぎっちり」ボタン"""
    def __init__(
        self,
        word_data: list[tuple[str, int]],
        scope_name: str,
        user_id: int | None,
        channel_id: int | None,
        command_user_id: int | None,
        time_range: TimeRange | None = None,
        current_max_words: int = 200,
    ):
        super().__init__(timeout=300)
        self.word_data = word_data
        self.scope_name = scope_name
        self.user_id = user_id
        self.channel_id = channel_id
        self.command_user_id = command_user_id
        self.time_range = time_range
        self.current_max_words = current_max_words
        self.generation_count = 1
    @discord.ui.button(label="🔥 もっとぎっちり", style=discord.ButtonStyle.primary)
    async def more_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """単語数を2倍にして再生成 or 破壊する"""
        if self.command_user_id and interaction.user.id != self.command_user_id:
            await interaction.response.send_message(
                "このボタンはコマンドを実行したユーザーのみが使用できます。",
                ephemeral=True,
            )
            return
        await interaction.response.defer()
        try:
            self.current_max_words *= 2
            self.generation_count += 1
            if len(self.word_data) < self.current_max_words:
                new_word_data = await get_wordcloud_data(
                    user_id=self.user_id,
                    channel_id=self.channel_id,
                    limit=self.current_max_words,
                    year_month_start=self.time_range.start if self.time_range else None,
                    year_month_end=self.time_range.end if self.time_range else None,
                )
                if new_word_data:
                    self.word_data = new_word_data
            image_bytes = await generate_wordcloud_image_wordcloud(
                self.word_data, max_words=self.current_max_words
            )
            file = discord.File(fp=io.BytesIO(image_bytes), filename="wordcloud.png")
            description = f"現在の単語数: 最大{self.current_max_words}単語"
            if self.time_range:
                description = f"期間: {self.time_range.label}\n{description}"
            embed = discord.Embed(
                title=f"{self.scope_name}のワードクラウド（ぎっちり × {self.generation_count}）",
                description=description,
                color=discord.Color.green(),
            )
            embed.set_image(url="attachment://wordcloud.png")
            await interaction.edit_original_response(
                embed=embed, attachments=[file], view=self
            )
        except Exception as e:
            print(f"もっとぎっちりボタンエラー: {e}")
            import traceback
            traceback.print_exc()
            await interaction.followup.send(
                f"エラーが発生しました: {str(e)[:100]}", ephemeral=True
            )
    async def _destroy_mode(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """破壊モード"""
        try:
            mask_path = "bg/killyoucloud.png"
            cover_path = "bg/killyoucover.png"
            import os
            if not os.path.exists(mask_path) or not os.path.exists(cover_path):
                await interaction.followup.send("破壊失敗", ephemeral=True)
                return
            image_bytes = await generate_wordcloud_image_wordcloud_masked(
                self.word_data, mask_path=mask_path, cover_path=cover_path
            )
            file = discord.File(fp=io.BytesIO(image_bytes), filename="destroyed.png")
            embed = discord.Embed(
                title=f"💥 {self.scope_name}のワードクラウド(破壊ありがとう)",
                description="ぎっちりUIのせいで負荷がかかる\nSEKAMおじさんの気持ちも考えて欲しい",
                color=discord.Color.red(),
            )
            embed.set_image(url="attachment://destroyed.png")
            button.disabled = True
            await interaction.edit_original_response(
                embed=embed, attachments=[file], view=self
            )
        except Exception as e:
            print(f"破壊モードエラー: {e}")
            import traceback
            traceback.print_exc()
            await interaction.followup.send(
                f"破壊に失敗しました: {str(e)[:100]}", ephemeral=True
            )
def parse_time_range_inputs(start_text: str, end_text: str) -> TimeRange:
    """文字列からTimeRangeを生成"""
    def _parse(value: str, label: str) -> datetime:
        try:
            return datetime.strptime(value, "%Y/%m")
        except ValueError as exc:
            raise ValueError(f"{label}は YYYY/MM 形式で入力してください。") from exc
    start_dt = _parse(start_text, "開始月")
    end_dt = _parse(end_text, "終了月")
    if start_dt > end_dt:
        raise ValueError("開始月は終了月よりも前に設定してください。")
    start_key = start_dt.strftime("%Y-%m-01")
    end_key = end_dt.strftime("%Y-%m-01")
    label = f"{start_dt.strftime('%Y/%m')}〜{end_dt.strftime('%Y/%m')}"
    return TimeRange(start=start_key, end=end_key, label=label)
async def edit_message_with_wordcloud(
    interaction: discord.Interaction,
    target_message: discord.Message,
    scope_name: str,
    ui: str,
    pos_id_condition: str,
    user_id: int | None,
    channel_id: int | None,
    command_user_id: int | None,
    time_range: TimeRange | None,
    log_suffix: str = "TIME_RANGE",
):
    """既存メッセージをワードクラウド結果で更新"""
    word_data = await get_wordcloud_data(
        user_id=user_id,
        channel_id=channel_id,
        pos_id_condition=pos_id_condition,
        year_month_start=time_range.start if time_range else None,
        year_month_end=time_range.end if time_range else None,
    )
    if not word_data:
        await interaction.followup.edit_message(
            target_message.id,
            content="データが不足しているため、ワードクラウドを生成できませんでした。",
            embed=None,
            attachments=[],
            view=None,
        )
        insert_command_log(interaction, "/wordcloud", f"NO_DATA_{log_suffix}")
        return
    if ui == "ぎっちり":
        if not WORDCLOUD_LIBRARY_AVAILABLE:
            await interaction.followup.edit_message(
                target_message.id,
                content="ぎっちりスタイルは現在利用できません。スタイリッシュをお試しください。",
                embed=None,
                attachments=[],
                view=None,
            )
            insert_command_log(
                interaction, "/wordcloud", f"LIBRARY_NOT_AVAILABLE_{log_suffix}"
            )
            return
        image_bytes = await generate_wordcloud_image_wordcloud(word_data)
        view = WordCloudMoreButtonView(
            word_data,
            scope_name,
            user_id,
            channel_id,
            command_user_id,
            time_range=time_range,
        )
    else:
        image_bytes = await generate_wordcloud_image_pillow(word_data)
        view = None
    file = discord.File(fp=io.BytesIO(image_bytes), filename="wordcloud.png")
    embed = discord.Embed(
        title=f"{scope_name}のワードクラウド（{ui}）",
        color=discord.Color.green(),
    )
    if time_range:
        embed.description = f"対象期間: {time_range.label}"
    embed.set_image(url="attachment://wordcloud.png")
    await interaction.followup.edit_message(
        target_message.id,
        content=None,
        embed=embed,
        attachments=[file],
        view=view,
    )
    insert_command_log(interaction, "/wordcloud", f"OK:{ui}_{log_suffix}")
class WordRankPaginationView(discord.ui.View):
    """固有名詞ランキングのページネーション表示"""
    def __init__(
        self,
        ranking: list[tuple[str, int]],
        scope_name: str,
        range_text: str,
        user_id: int,
    ):
        super().__init__(timeout=180)
        self.ranking = ranking
        self.scope_name = scope_name
        self.range_text = range_text
        self.user_id = user_id
        self.current_page = 0
        self.items_per_page = 10
        self.max_page = (len(ranking) - 1) // self.items_per_page
        self._update_buttons()
    def _update_buttons(self):
        """ボタンの有効/無効を更新"""
        self.previous_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page >= self.max_page
    def create_embed(self, page: int) -> discord.Embed:
        """指定ページのEmbedを作成"""
        start_idx = page * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(self.ranking))
        page_data = self.ranking[start_idx:end_idx]
        embed = discord.Embed(
            title=f"📊 {self.scope_name}の固有名詞ランキング",
            description=f"期間: {self.range_text} | ページ {page + 1}/{self.max_page + 1}",
            color=discord.Color.gold(),
        )
        medals = ["🥇", "🥈", "🥉"]
        for i, (word, count) in enumerate(page_data):
            rank = start_idx + i + 1
            if rank <= 3:
                medal = medals[rank - 1]
            elif rank <= 0:
                medal = f"{rank}️⃣"
            else:
                medal = f"**{rank}位**"
            embed.add_field(
                name=f"{medal} {word}",
                value=f"{count:,} 回",
                inline=False,
            )
        return embed
    @discord.ui.button(label="◀ 前へ", style=discord.ButtonStyle.secondary)
    async def previous_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """前のページへ"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "このボタンはコマンド実行者のみ操作できます。", ephemeral=True
            )
            return
        if self.current_page > 0:
            self.current_page -= 1
            self._update_buttons()
            embed = self.create_embed(self.current_page)
            await interaction.response.edit_message(embed=embed, view=self)
    @discord.ui.button(label="次へ ▶", style=discord.ButtonStyle.secondary)
    async def next_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """次のページへ"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "このボタンはコマンド実行者のみ操作できます。", ephemeral=True
            )
            return
        if self.current_page < self.max_page:
            self.current_page += 1
            self._update_buttons()
            embed = self.create_embed(self.current_page)
            await interaction.response.edit_message(embed=embed, view=self)
def _apply_sekam_watermark(
    image: Image.Image,
    watermark_path: str = "bg/sekam2logo.png",
    opacity: float = 0.2,
    margin: int = 10,
) -> Image.Image:
    import os
    try:
        if not os.path.exists(watermark_path):
            return image
        wm = Image.open(watermark_path).convert("RGBA")
        target_w = int(image.width * 0.18)
        if target_w <= 0:
            return image
        ratio = target_w / wm.width
        target_h = max(1, int(wm.height * ratio))
        wm_resized = wm.resize((target_w, target_h), Image.LANCZOS)
        alpha = wm_resized.split()[3]
        alpha = alpha.point(lambda p: int(p * opacity))
        wm_resized.putalpha(alpha)
        base_was_rgba = image.mode == "RGBA"
        base = image.convert("RGBA")
        pos = (
            base.width - wm_resized.width - margin,
            base.height - wm_resized.height - margin,
        )
        base.paste(wm_resized, pos, wm_resized)
        if base_was_rgba:
            return base
        return base.convert("RGB")
    except Exception:
        return image
async def get_wordcloud_data(
    user_id: int | None,
    channel_id: int | None,
    limit: int = 150,
    pos_id_condition: str = "ws.pos_id IN (2)",
    year_month_start: str | None = None,
    year_month_end: str | None = None,
) -> list[tuple[str, int]]:
    where_conditions = []
    params = []
    if user_id is not None:
        where_conditions.append("ws.scope = 'user'")
        where_conditions.append("ws.scope_id = %s")
        params.append(user_id)
    elif channel_id is not None:
        where_conditions.append("ws.scope = 'channel'")
        where_conditions.append("ws.scope_id = %s")
        params.append(channel_id)
    else:
        where_conditions.append("ws.scope = 'global'")
        where_conditions.append("ws.scope_id = 0")
    where_conditions.append(pos_id_condition)
    if year_month_start and year_month_end:
        start_year = int(year_month_start.split("-")[0])
        start_month = int(year_month_start.split("-")[1])
        end_year = int(year_month_end.split("-")[0])
        end_month = int(year_month_end.split("-")[1])
        where_conditions.append(
            "((ws.year > %s) OR (ws.year = %s AND ws.month >= %s)) AND "
            "((ws.year < %s) OR (ws.year = %s AND ws.month <= %s))"
        )
        params.extend(
            [start_year, start_year, start_month, end_year, end_year, end_month]
        )
    else:
        where_conditions.append("ws.year = 0")
        where_conditions.append("ws.month = 0")
    where_clause = " AND ".join(where_conditions)
    sql = f"""
        SELECT
            w.word,
            SUM(ws.count) AS total_count
        FROM word_stats ws
        JOIN words w ON ws.word_id = w.word_id
        WHERE {where_clause}
        GROUP BY w.word
        ORDER BY total_count DESC
        LIMIT %s
    """
    params.append(limit)
    rows = run_statdb_query(sql, tuple(params), fetch="all")
    return [(row[0], row[1]) for row in rows] if rows else []
async def get_proper_noun_ranking(
    user_id: int | None,
    channel_id: int | None,
    year_month_start: str | None,
    year_month_end: str | None,
    limit: int = 5,
) -> list[tuple[str, int]]:
    where_conditions = []
    params = []
    if user_id is not None:
        where_conditions.append("ws.scope = 'user'")
        where_conditions.append("ws.scope_id = %s")
        params.append(user_id)
    elif channel_id is not None:
        where_conditions.append("ws.scope = 'channel'")
        where_conditions.append("ws.scope_id = %s")
        params.append(channel_id)
    else:
        where_conditions.append("ws.scope = 'global'")
        where_conditions.append("ws.scope_id = 0")
    where_conditions.append("ws.pos_id IN (2)")
    if year_month_start and year_month_end:
        start_year = int(year_month_start.split("-")[0])
        start_month = int(year_month_start.split("-")[1])
        end_year = int(year_month_end.split("-")[0])
        end_month = int(year_month_end.split("-")[1])
        where_conditions.append(
            "((ws.year > %s) OR (ws.year = %s AND ws.month >= %s)) AND "
            "((ws.year < %s) OR (ws.year = %s AND ws.month <= %s))"
        )
        params.extend(
            [start_year, start_year, start_month, end_year, end_year, end_month]
        )
    else:
        where_conditions.append("ws.year = 0")
        where_conditions.append("ws.month = 0")
    where_clause = " AND ".join(where_conditions)
    sql = f"""
        SELECT
            w.word,
            SUM(ws.count) AS total_count
        FROM word_stats ws
        JOIN words w ON ws.word_id = w.word_id
        WHERE {where_clause}
        GROUP BY w.word
        ORDER BY total_count DESC
        LIMIT %s
    """
    params.append(limit)
    rows = run_statdb_query(sql, tuple(params), fetch="all")
    return [(row[0], row[1]) for row in rows] if rows else []
def get_word_by_id(word_id: int) -> str:
    """
    word_idから単語を取得
    Args:
        word_id: 単語ID
    Returns:
        単語文字列
    """
    sql = "SELECT word FROM words WHERE word_id = %s"
    row = run_statdb_query(sql, (word_id,), fetch="one")
    return row[0] if row else ""
async def generate_wordcloud_image_pillow(
    word_data: list[tuple[str, int]], width: int = 1000, height: int = 700
) -> bytes:
    if not word_data:
        img = Image.new("RGB", (width, height), color="white")
        draw = ImageDraw.Draw(img)
        draw.text((width // 2 - 100, height // 2), "データがありません", fill="gray")
        output = io.BytesIO()
        img.save(output, format="PNG")
        output.seek(0)
        return output.read()
    img = Image.new("RGB", (width, height), color="
    draw = ImageDraw.Draw(img)
    try:
        font_sizes = {
            "huge": ImageFont.truetype(WORDCLOUD_FONT_PATH, 60),
            "xlarge": ImageFont.truetype(WORDCLOUD_FONT_PATH, 50),
            "large": ImageFont.truetype(WORDCLOUD_FONT_PATH, 40),
            "medium": ImageFont.truetype(WORDCLOUD_FONT_PATH, 32),
            "small": ImageFont.truetype(WORDCLOUD_FONT_PATH, 24),
            "xsmall": ImageFont.truetype(WORDCLOUD_FONT_PATH, 18),
            "tiny": ImageFont.truetype(WORDCLOUD_FONT_PATH, 15),
        }
    except Exception:
        try:
            font_sizes = {
                "huge": ImageFont.truetype(WORDCLOUD_FALLBACK_FONT_PATH, 60),
                "xlarge": ImageFont.truetype(WORDCLOUD_FALLBACK_FONT_PATH, 50),
                "large": ImageFont.truetype(WORDCLOUD_FALLBACK_FONT_PATH, 40),
                "medium": ImageFont.truetype(WORDCLOUD_FALLBACK_FONT_PATH, 32),
                "small": ImageFont.truetype(WORDCLOUD_FALLBACK_FONT_PATH, 24),
                "xsmall": ImageFont.truetype(WORDCLOUD_FALLBACK_FONT_PATH, 18),
                "tiny": ImageFont.truetype(WORDCLOUD_FALLBACK_FONT_PATH, 15),
            }
        except Exception:
            default_font = ImageFont.load_default()
            font_sizes = {
                "huge": default_font,
                "xlarge": default_font,
                "large": default_font,
                "medium": default_font,
                "small": default_font,
                "xsmall": default_font,
                "tiny": default_font,
            }
    colors = [
        "
        "
        "
        "
        "
        "
        "
        "
        "
        "
    ]
    max_count = float(word_data[0][1]) if word_data else 1.0
    min_count = float(word_data[-1][1]) if word_data else 1.0
    count_range = max_count - min_count if max_count > min_count else 1.0
    def get_font_size(count: int, index: int) -> tuple[str, any]:
        """出現回数とインデックスからフォントサイズを決定"""
        normalized = (
            (float(count) - min_count) / count_range if count_range > 0 else 0.5
        )
        if index < 5:
            size_key = "huge" if normalized > 0.7 else "xlarge"
        elif index < 12:
            size_key = "xlarge" if normalized > 0.6 else "large"
        elif index < 25:
            size_key = "large" if normalized > 0.5 else "medium"
        elif index < 45:
            size_key = "medium" if normalized > 0.4 else "small"
        elif index < 70:
            size_key = "small" if normalized > 0.3 else "xsmall"
        else:
            size_key = "xsmall" if normalized > 0.2 else "tiny"
        return size_key, font_sizes[size_key]
    GRID_COLS = 12
    GRID_ROWS = 8
    cell_width = (width - 60) // GRID_COLS
    cell_height = (height - 60) // GRID_ROWS
    occupied_cells = set()
    placed_rects = []
    def check_cell_available(
        col: int, row: int, cols_needed: int = 1, rows_needed: int = 1
    ) -> bool:
        """指定されたセル範囲が利用可能かチェック"""
        for c in range(col, min(col + cols_needed, GRID_COLS)):
            for r in range(row, min(row + rows_needed, GRID_ROWS)):
                if (c, r) in occupied_cells:
                    return False
        return True
    def mark_cells_occupied(
        col: int, row: int, cols_needed: int = 1, rows_needed: int = 1
    ):
        """指定されたセル範囲を使用済みにマーク"""
        for c in range(col, min(col + cols_needed, GRID_COLS)):
            for r in range(row, min(row + rows_needed, GRID_ROWS)):
                occupied_cells.add((c, r))
    def check_rect_overlap(x: int, y: int, w: int, h: int, margin: int = 5) -> bool:
        """既存の配置と重なるかチェック（微調整用）"""
        new_rect = (x - margin, y - margin, x + w + margin, y + h + margin)
        for rect in placed_rects:
            if not (
                new_rect[2] < rect[0]
                or new_rect[0] > rect[2]
                or new_rect[3] < rect[1]
                or new_rect[1] > rect[3]
            ):
                return True
        return False
    def find_grid_position(
        text: str, font: any, size_key: str
    ) -> tuple[int, int] | None:
        """グリッドベースで配置位置を探す（高速版）"""
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        cols_needed = max(1, (text_width + cell_width - 1) // cell_width)
        rows_needed = max(1, (text_height + cell_height - 1) // cell_height)
        if size_key in ["huge", "xlarge"]:
            search_order = [
                (col, row)
                for row in range(GRID_ROWS // 2 - 2, GRID_ROWS // 2 + 3)
                for col in range(GRID_COLS // 2 - 3, GRID_COLS // 2 + 4)
                if 0 <= row < GRID_ROWS and 0 <= col < GRID_COLS
            ]
        else:
            search_order = [
                (col, row) for row in range(GRID_ROWS) for col in range(GRID_COLS)
            ]
            random.shuffle(search_order)
        for col, row in search_order:
            if check_cell_available(col, row, cols_needed, rows_needed):
                offset_x = random.randint(-15, 15)
                offset_y = random.randint(-15, 15)
                x = 30 + col * cell_width + offset_x
                y = 30 + row * cell_height + offset_y
                x = max(30, min(x, width - text_width - 30))
                y = max(30, min(y, height - text_height - 30))
                if not check_rect_overlap(x, y, text_width, text_height):
                    mark_cells_occupied(col, row, cols_needed, rows_needed)
                    return x, y
        return None
    placed_count = 0
    max_words = min(100, len(word_data))
    for idx in range(max_words):
        word, count = word_data[idx]
        size_key, font = get_font_size(count, idx)
        color = colors[idx % len(colors)]
        position = find_grid_position(word, font, size_key)
        if position:
            x, y = position
            draw.text((x, y), word, fill=color, font=font)
            bbox = draw.textbbox((x, y), word, font=font)
            placed_rects.append((bbox[0], bbox[1], bbox[2], bbox[3]))
            placed_count += 1
        if placed_count >= 80:
            break
    img = _apply_sekam_watermark(img)
    output = io.BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output.read()
async def generate_wordcloud_image_wordcloud(
    word_data: list[tuple[str, int]],
    width: int = 1000,
    height: int = 700,
    max_words: int = 200,
) -> bytes:
    """
    ワードクラウド画像を生成（wordcloudライブラリ使用）
    「ぎっちり」スタイル：
    wordcloudライブラリを使用して高密度で単語を配置。
    カラフルな色合いと日本語フォントに対応。
    Args:
        word_data: [(単語, 出現回数), ...] のリスト
        width: 画像幅
        height: 画像高さ
        max_words: 最大単語数（デフォルト200、もっとぎっちりで増加）
    Returns:
        PNG画像のバイト列
    """
    if not WORDCLOUD_LIBRARY_AVAILABLE:
        raise ImportError("wordcloudライブラリがインストールされていません")
    if not word_data:
        img = Image.new("RGB", (width, height), color="white")
        draw = ImageDraw.Draw(img)
        draw.text((width // 2 - 100, height // 2), "データがありません", fill="gray")
        output = io.BytesIO()
        img.save(output, format="PNG")
        output.seek(0)
        return output.read()
    word_freq = {word: float(count) for word, count in word_data}
    import os
    font_path = None
    if os.path.exists(WORDCLOUD_FONT_PATH):
        font_path = WORDCLOUD_FONT_PATH
    elif os.path.exists(WORDCLOUD_FALLBACK_FONT_PATH):
        font_path = WORDCLOUD_FALLBACK_FONT_PATH
    def custom_color_func(
        word, font_size, position, orientation, random_state=None, **kwargs
    ):
        """カラフルな色を生成"""
        if random_state is None:
            random_state = random.Random()
        hue = random_state.randint(0, 360)
        saturation = random_state.randint(70, 90)
        lightness = random_state.randint(35, 55)
        return f"hsl({hue}, {saturation}%, {lightness}%)"
    wc = WordCloud(
        width=width,
        height=height,
        background_color="
        max_words=max_words,
        font_path=font_path,
        min_font_size=10,
        max_font_size=100,
        relative_scaling=0.5,
        color_func=custom_color_func,
        margin=10,
        prefer_horizontal=0.7,
        random_state=42,
    )
    wc.generate_from_frequencies(word_freq)
    img = wc.to_image()
    img = _apply_sekam_watermark(img)
    output = io.BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output.read()
async def generate_wordcloud_image_wordcloud_masked(
    word_data: list[tuple[str, int]],
    mask_path: str,
    cover_path: str,
    width: int = 1000,
    height: int = 700,
) -> bytes:
    """
    マスク画像を使用したワードクラウド生成（破壊モード専用）
    Args:
        word_data: [(単語, 出現回数), ...] のリスト
        mask_path: マスク画像のパス（黒い部分に単語を配置）
        cover_path: カバー画像のパス（最後に合成）
        width: 画像幅
        height: 画像高さ
    Returns:
        PNG画像のバイト列
    """
    if not WORDCLOUD_LIBRARY_AVAILABLE:
        raise ImportError("wordcloudライブラリがインストールされていません")
    import numpy as np
    mask_image = Image.open(mask_path)
    mask_array = np.array(mask_image)
    cover_image = Image.open(cover_path).convert("RGBA")
    word_freq = {word: float(count) for word, count in word_data}
    import os
    font_path = None
    if os.path.exists(WORDCLOUD_FONT_PATH):
        font_path = WORDCLOUD_FONT_PATH
    elif os.path.exists(WORDCLOUD_FALLBACK_FONT_PATH):
        font_path = WORDCLOUD_FALLBACK_FONT_PATH
    def destroy_color_func(
        word, font_size, position, orientation, random_state=None, **kwargs
    ):
        """赤・オレンジ系の破壊的な色を生成"""
        if random_state is None:
            random_state = random.Random()
        hue = random_state.randint(0, 60)
        saturation = random_state.randint(80, 100)
        lightness = random_state.randint(40, 60)
        return f"hsl({hue}, {saturation}%, {lightness}%)"
    wc = WordCloud(
        width=mask_array.shape[1],
        height=mask_array.shape[0],
        background_color=None,
        mode="RGBA",
        mask=mask_array,
        max_words=1600,
        font_path=font_path,
        min_font_size=8,
        max_font_size=80,
        relative_scaling=0.5,
        color_func=destroy_color_func,
        margin=2,
        prefer_horizontal=0.6,
        random_state=42,
        contour_width=0,
        contour_color="red",
    )
    wc.generate_from_frequencies(word_freq)
    wordcloud_img = wc.to_image().convert("RGBA")
    cover_resized = cover_image.resize(wordcloud_img.size, Image.LANCZOS)
    final_image = Image.alpha_composite(wordcloud_img, cover_resized)
    final_image = _apply_sekam_watermark(final_image)
    output = io.BytesIO()
    final_image.save(output, format="PNG")
    output.seek(0)
    return output.read()
