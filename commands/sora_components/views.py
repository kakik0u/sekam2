"""
SORAコマンド - Viewクラス群
UI表示とインタラクション処理を担当
"""

from datetime import datetime
from typing import Any
from urllib.parse import quote

import discord
from discord import ui

from database.connection import run_aidb_query


class MainMenuView(ui.View):
    """
    初期メニューのView
    3つのモード選択ボタンを表示
    """

    def __init__(self):
        super().__init__(timeout=180)

    @ui.button(
        label="ランキングを表示する", style=discord.ButtonStyle.primary, emoji="🏆"
    )
    async def show_ranking(self, interaction: discord.Interaction, button: ui.Button):
        """ランキングモードを開始"""
        # 絵文字選択Viewを表示
        view = EmojiSelectView()

        message_content = (
            "🏆 **ランキング - 絵文字選択**\n\n"
            "ランキングを表示する絵文字を選択してください"
        )

        await interaction.response.edit_message(content=message_content, view=view)

    @ui.button(label="検索する", style=discord.ButtonStyle.primary, emoji="🔍")
    async def search(self, interaction: discord.Interaction, button: ui.Button):
        """検索モードを開始"""
        from .modals import SearchConditionModal

        # 検索条件入力Modalを表示
        modal = SearchConditionModal()
        await interaction.response.send_modal(modal)

    @ui.button(label="ランダムで再生", style=discord.ButtonStyle.primary, emoji="🎲")
    async def random_play(self, interaction: discord.Interaction, button: ui.Button):
        """ランダム再生モードを開始"""
        # 現在のメッセージからボタンを削除
        await interaction.response.edit_message(view=None)

        # ランダムに動画を選択
        sql = """
            SELECT m.id
            FROM messages m
            WHERE EXISTS (SELECT 1 FROM attachments a WHERE a.message_id = m.id)
               OR m.content LIKE '%%sora.chatgpt.com%%'
            ORDER BY RAND()
            LIMIT 1
        """
        result = run_aidb_query(sql, (), fetch="one")

        if not result:
            await interaction.followup.send(
                "動画が見つかりませんでした。", ephemeral=True
            )
            return

        message_id = result[0]

        # ランダム再生Viewを表示
        view = RandomPlayView(message_id)
        await view.show(interaction)

    @ui.button(label="タグ一覧", style=discord.ButtonStyle.primary, emoji="🏷️")
    async def show_tags(self, interaction: discord.Interaction, button: ui.Button):
        """タグ一覧を表示"""
        # TagListViewに遷移
        view = TagListView()
        await interaction.response.defer()
        await view.show(interaction)

    @ui.button(label="IDで視聴", style=discord.ButtonStyle.secondary, emoji="🔢")
    async def view_by_id(self, interaction: discord.Interaction, button: ui.Button):
        """動画IDを指定して視聴"""
        from .modals import VideoIdModal

        # 動画ID入力Modalを表示
        modal = VideoIdModal()
        await interaction.response.send_modal(modal)

    @ui.button(label="自分の投稿", style=discord.ButtonStyle.primary, emoji="📝")
    async def my_posts(self, interaction: discord.Interaction, button: ui.Button):
        """自分の投稿一覧を表示"""
        # MyPostsViewに遷移
        view = MyPostsView(interaction.user.id)
        await interaction.response.defer()
        await view.show(interaction)


class EmojiSelectView(ui.View):
    """
    絵文字選択View
    ランキング用の絵文字を選択
    """

    def __init__(self):
        super().__init__(timeout=180)

    @ui.select(
        placeholder="リアクション絵文字を選択",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(label="grin", value="grin", emoji="😁"),
            discord.SelectOption(label="sob", value="sob", emoji="😭"),
            discord.SelectOption(
                label="mo", value="mo", emoji="<:mo:1424391940782293157>"
            ),
            discord.SelectOption(label="cool", value="cool", emoji="😎"),
            discord.SelectOption(label="nerd", value="nerd", emoji="🤓"),
            discord.SelectOption(
                label="raised_hands", value="raised_hands", emoji="🙌"
            ),
            discord.SelectOption(label="older_man", value="older_man", emoji="👴"),
            discord.SelectOption(label="fearful", value="fearful", emoji="😨"),
        ],
    )
    async def emoji_select(self, interaction: discord.Interaction, select: ui.Select):
        """絵文字選択後、日付入力Modalを表示"""
        from .modals import RankingDateModal

        # 選択された絵文字
        emoji_name = select.values[0]

        # 日付入力Modalを表示
        modal = RankingDateModal(emoji_name)
        await interaction.response.send_modal(modal)


class RankingResultView(ui.View):
    """
    ランキング結果表示View
    5件のWatch URLとページング・選択機能
    """

    def __init__(
        self,
        emoji_name: str,
        after_date: datetime | None,
        before_date: datetime | None,
        page: int = 1,
    ):
        super().__init__(timeout=180)
        self.emoji_name = emoji_name
        self.after_date = after_date
        self.before_date = before_date
        self.page = page
        self.results: list[tuple] = []
        self.ranking_type = ""

        # ランキング形式ラベルの生成
        self._generate_ranking_label()

    def _generate_ranking_label(self):
        """ランキング形式のラベルを生成"""
        from datetime import timedelta

        if self.before_date is None and self.after_date is None:
            self.ranking_type = f"総合ランキング:{self.emoji_name}:部門"
        elif self.before_date and self.after_date:
            after_plus_one = (self.after_date + timedelta(days=1)).strftime("%Y/%m/%d")
            before_minus_one = (self.before_date - timedelta(days=1)).strftime(
                "%Y/%m/%d"
            )

            if after_plus_one == before_minus_one:
                self.ranking_type = f"デイリーランキング:{self.emoji_name}:部門"
            else:
                self.ranking_type = (
                    f"{after_plus_one}-{before_minus_one}期間:{self.emoji_name}:部門"
                )
        elif self.after_date:
            from datetime import timedelta

            after_plus_one = (self.after_date + timedelta(days=1)).strftime("%Y/%m/%d")
            self.ranking_type = f"{after_plus_one}以降:{self.emoji_name}:部門"
        else:
            from datetime import timedelta

            before_minus_one = (self.before_date - timedelta(days=1)).strftime(
                "%Y/%m/%d"
            )
            self.ranking_type = f"{before_minus_one}まで:{self.emoji_name}:部門"

    async def fetch_results(self):
        """ランキング結果を取得"""
        from utils.emoji import normalize_emoji_and_variants

        base_name, tone_variants = normalize_emoji_and_variants(self.emoji_name)
        placeholders = ", ".join(["%s"] * len(tone_variants))
        params = list(tone_variants)

        where_conditions = [f"r.emoji_name IN ({placeholders})"]

        if self.before_date:
            where_conditions.append("m.timestamp < %s")
            params.append(self.before_date)

        if self.after_date:
            where_conditions.append("m.timestamp > %s")
            params.append(self.after_date)

        where_conditions.append(
            "(EXISTS (SELECT 1 FROM attachments a WHERE a.message_id = m.id) "
            "OR m.content LIKE '%%sora.chatgpt.com%%')"
        )

        where_clause = " AND ".join(where_conditions)
        offset = (self.page - 1) * 5

        sql = f"""
            SELECT
                m.id as message_id,
                m.channel_id,
                m.content,
                SUM(r.count) as total_reaction_count
            FROM messages m
            JOIN reactions r ON m.id = r.message_id
            WHERE {where_clause}
            GROUP BY m.id, m.channel_id, m.content
            ORDER BY total_reaction_count DESC
            LIMIT 5 OFFSET %s
        """
        params.append(offset)

        self.results = run_aidb_query(sql, tuple(params), fetch="all") or []

    async def show(self, interaction: discord.Interaction, edit_message: bool = False):
        """ランキング結果を表示"""
        await self.fetch_results()

        if not self.results:
            if edit_message:
                await interaction.edit_original_response(
                    content=f"指定された条件に一致するメッセージが見つかりませんでした。（ページ{self.page}）",
                    view=None,
                )
            else:
                await interaction.followup.send(
                    f"指定された条件に一致するメッセージが見つかりませんでした。（ページ{self.page}）",
                    ephemeral=True,
                )
            return

        # ヘッダーメッセージ
        header_parts = ["SEKAM統計所AI部", "専科AI動画", self.ranking_type]
        header_parts.append(
            "-# データは前日までのものです。リアクション数は流動します。"
        )
        header_message = "\n".join(header_parts)

        # Watch URLの生成
        watch_urls = []
        offset = (self.page - 1) * 5
        encoded_comment = quote(self.ranking_type)

        for idx, row in enumerate(self.results):
            message_id = row[0]
            rank = offset + idx + 1
            watch_url = f"https://sekam.site/watch?v={message_id}&reaction={encoded_comment}&rank={rank}位"
            watch_urls.append(watch_url)

        message_content = header_message + "\n\n" + "\n".join(watch_urls)

        # ボタンとセレクトの更新
        self._update_components()

        if edit_message:
            # defer()済みの場合はedit_original_responseを使用
            await interaction.edit_original_response(content=message_content, view=self)
        else:
            await interaction.followup.send(message_content, view=self, ephemeral=True)

    def _update_components(self):
        """ボタンとセレクトの状態を更新"""
        try:
            print(
                f"[DEBUG] _update_components called, page={self.page}, results={len(self.results)}"
            )
            # ページングボタンの有効/無効化
            self.children[0].disabled = self.page == 1  # 前のページボタン
            self.children[1].disabled = len(self.results) < 5  # 次のページボタン

            # セレクトメニューの選択肢を更新
            offset = (self.page - 1) * 5
            options = []
            for idx in range(len(self.results)):
                rank = offset + idx + 1
                options.append(discord.SelectOption(label=f"{rank}位", value=str(idx)))

            self.children[2].options = options
            print(f"[DEBUG] Updated select options: {len(options)} items")
        except Exception as e:
            print(f"[ERROR] _update_components error: {e}")
            import traceback

            traceback.print_exc()

    @ui.button(label="前のページ", style=discord.ButtonStyle.secondary, emoji="⬅️")
    async def prev_page(self, interaction: discord.Interaction, button: ui.Button):
        """前のページを表示"""
        try:
            print("[DEBUG] Ranking prev button clicked")
            if self.page > 1:
                self.page -= 1
                await interaction.response.defer()
                await self.show(interaction, edit_message=True)
        except Exception as e:
            print(f"[ERROR] Ranking prev error: {e}")
            import traceback

            traceback.print_exc()

    @ui.button(label="次のページ", style=discord.ButtonStyle.secondary, emoji="➡️")
    async def next_page(self, interaction: discord.Interaction, button: ui.Button):
        """次のページを表示"""
        try:
            print("[DEBUG] Ranking next button clicked")
            self.page += 1
            await interaction.response.defer()
            await self.show(interaction, edit_message=True)
        except Exception as e:
            print(f"[ERROR] Ranking next error: {e}")
            import traceback

            traceback.print_exc()

    @ui.select(placeholder="詳細を見る項目を選択", min_values=1, max_values=1)
    async def select_item(self, interaction: discord.Interaction, select: ui.Select):
        """選択された項目の詳細を表示"""
        try:
            print("[DEBUG] Ranking select triggered")
            print(f"[DEBUG] Selected value: {select.values[0]}")
            print(f"[DEBUG] Results: {len(self.results)}")

            idx = int(select.values[0])
            message_id = self.results[idx][0]

            print(f"[DEBUG] Message ID: {message_id}")

            # DetailViewに遷移
            view_data = {
                "type": "ranking",
                "emoji_name": self.emoji_name,
                "after_date": self.after_date,
                "before_date": self.before_date,
                "page": self.page,
            }

            detail_view = DetailView(message_id, view_data)
            # セレクトの場合はdefer()せずに直接edit_messageを使う
            await detail_view.show(interaction, edit_message=False)
        except Exception as e:
            print(f"[ERROR] Ranking select error: {e}")
            import traceback

            traceback.print_exc()
            if not interaction.response.is_done():
                await interaction.response.send_message(f"エラー: {e}", ephemeral=True)


class SearchResultView(ui.View):
    """
    検索結果表示View
    5件のWatch URLとソート・ページング・選択機能
    """

    def __init__(
        self,
        search_conditions: dict[str, Any],
        page: int = 1,
        sort_by: str = "reaction",
    ):
        super().__init__(timeout=180)
        self.search_conditions = search_conditions
        self.page = page
        self.sort_by = sort_by
        self.results: list[tuple] = []

    async def fetch_results(self):
        """検索結果を取得"""
        where_conditions = []
        having_conditions = []
        params = []

        # タイトル検索
        if self.search_conditions.get("title"):
            where_conditions.append("meta.title LIKE %s")
            params.append(f"%{self.search_conditions['title']}%")

        # タグ検索
        if self.search_conditions.get("tags"):
            # タグはJSON配列なので各タグに対してLIKE検索
            tag_conditions = []
            for tag in self.search_conditions["tags"]:
                tag_conditions.append("meta.tag LIKE %s")
                params.append(f"%{tag}%")
            where_conditions.append(f"({' OR '.join(tag_conditions)})")

        # 動画または添付ファイルが存在
        where_conditions.append(
            "(EXISTS (SELECT 1 FROM attachments a WHERE a.message_id = m.id) "
            "OR m.content LIKE '%%sora.chatgpt.com%%')"
        )

        # リアクション数下限はHAVING句で処理
        if self.search_conditions.get("min_reaction") is not None:
            having_conditions.append("reaction_count >= %s")
            params.append(self.search_conditions["min_reaction"])

        # ソート方式
        if self.sort_by == "reaction":
            order_clause = "ORDER BY reaction_count DESC"
        elif self.sort_by == "date_desc":
            order_clause = "ORDER BY m.timestamp DESC"
        elif self.sort_by == "date_asc":
            order_clause = "ORDER BY m.timestamp ASC"
        else:  # random
            order_clause = "ORDER BY RAND()"

        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        having_clause = " AND ".join(having_conditions) if having_conditions else "1=1"
        offset = (self.page - 1) * 5

        sql = f"""
            SELECT
                m.id as message_id,
                m.channel_id,
                m.content,
                COALESCE(SUM(r.count), 0) as reaction_count
            FROM messages m
            LEFT JOIN meta ON m.id = meta.id
            LEFT JOIN reactions r ON m.id = r.message_id
            WHERE {where_clause}
            GROUP BY m.id, m.channel_id, m.content
            HAVING {having_clause}
            {order_clause}
            LIMIT 5 OFFSET %s
        """
        params.append(offset)

        self.results = run_aidb_query(sql, tuple(params), fetch="all") or []

    async def show(self, interaction: discord.Interaction, edit_message: bool = False):
        """検索結果を表示"""
        await self.fetch_results()

        if not self.results:
            if edit_message:
                await interaction.response.edit_message(
                    content=f"検索条件に一致する動画が見つかりませんでした。（ページ{self.page}）",
                    view=None,
                )
            else:
                await interaction.followup.send(
                    f"検索条件に一致する動画が見つかりませんでした。（ページ{self.page}）",
                    ephemeral=True,
                )
            return

        # ヘッダーメッセージ
        header_parts = ["SEKAM統計所AI部", "専科AI動画 - 検索結果"]

        # 検索条件の表示
        conditions = []
        if self.search_conditions.get("title"):
            conditions.append(f"タイトル: {self.search_conditions['title']}")
        if self.search_conditions.get("tags"):
            conditions.append(f"タグ: {', '.join(self.search_conditions['tags'])}")
        if self.search_conditions.get("min_reaction") is not None:
            conditions.append(
                f"リアクション数: {self.search_conditions['min_reaction']}以上"
            )

        if conditions:
            header_parts.append("検索条件: " + " / ".join(conditions))

        header_parts.append("-# ページ " + str(self.page))
        header_message = "\n".join(header_parts)

        # Watch URLの生成
        watch_urls = []
        offset = (self.page - 1) * 5
        encoded_comment = quote("検索結果")

        for idx, row in enumerate(self.results):
            message_id = row[0]
            position = offset + idx + 1
            watch_url = f"https://sekam.site/watch?v={message_id}&reaction={encoded_comment}&rank={position}"
            watch_urls.append(watch_url)

        message_content = header_message + "\n\n" + "\n".join(watch_urls)

        # ボタンとセレクトの更新
        self._update_components()

        if edit_message:
            # defer()済みの場合はedit_original_responseを使用
            await interaction.edit_original_response(content=message_content, view=self)
        else:
            await interaction.followup.send(message_content, view=self, ephemeral=True)

    def _update_components(self):
        """ボタンとセレクトの状態を更新"""
        try:
            print(
                f"[DEBUG] Search _update_components, page={self.page}, results={len(self.results)}"
            )
            # ページングボタンの有効/無効化
            self.children[0].disabled = self.page == 1  # 前のページボタン
            self.children[1].disabled = len(self.results) < 5  # 次のページボタン

            # ソート選択のデフォルト値を更新
            for option in self.children[2].options:
                option.default = option.value == self.sort_by

            # 項目選択セレクトの選択肢を更新
            offset = (self.page - 1) * 5
            options = []
            for idx in range(len(self.results)):
                position = offset + idx + 1
                options.append(
                    discord.SelectOption(label=f"{position}番目", value=str(idx))
                )

            self.children[3].options = options
            print(f"[DEBUG] Updated search select options: {len(options)} items")
        except Exception as e:
            print(f"[ERROR] Search _update_components error: {e}")
            import traceback

            traceback.print_exc()

    @ui.button(label="前のページ", style=discord.ButtonStyle.secondary, emoji="⬅️")
    async def prev_page(self, interaction: discord.Interaction, button: ui.Button):
        """前のページを表示"""
        try:
            print("[DEBUG] Search prev button clicked")
            if self.page > 1:
                self.page -= 1
                await interaction.response.defer()
                await self.show(interaction, edit_message=True)
        except Exception as e:
            print(f"[ERROR] Search prev error: {e}")
            import traceback

            traceback.print_exc()

    @ui.button(label="次のページ", style=discord.ButtonStyle.secondary, emoji="➡️")
    async def next_page(self, interaction: discord.Interaction, button: ui.Button):
        """次のページを表示"""
        try:
            print("[DEBUG] Search next button clicked")
            self.page += 1
            await interaction.response.defer()
            await self.show(interaction, edit_message=True)
        except Exception as e:
            print(f"[ERROR] Search next error: {e}")
            import traceback

            traceback.print_exc()

    @ui.select(
        placeholder="並び替え",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(
                label="リアクション数順", value="reaction", default=True
            ),
            discord.SelectOption(label="日付（新しい順）", value="date_desc"),
            discord.SelectOption(label="日付（古い順）", value="date_asc"),
            discord.SelectOption(label="ランダム", value="random"),
        ],
    )
    async def sort_select(self, interaction: discord.Interaction, select: ui.Select):
        """ソート方式を変更"""
        try:
            print("[DEBUG] Search sort select triggered")
            print(f"[DEBUG] Selected sort: {select.values[0]}")

            self.sort_by = select.values[0]
            self.page = 1  # ページをリセット

            # デフォルト選択肢を更新
            for option in select.options:
                option.default = option.value == self.sort_by

            await interaction.response.defer()
            await self.show(interaction, edit_message=True)
        except Exception as e:
            print(f"[ERROR] Search sort error: {e}")
            import traceback

            traceback.print_exc()

    @ui.select(placeholder="詳細を見る項目を選択", min_values=1, max_values=1)
    async def select_item(self, interaction: discord.Interaction, select: ui.Select):
        """選択された項目の詳細を表示"""
        try:
            print("[DEBUG] Search item select triggered")
            print(f"[DEBUG] Selected value: {select.values[0]}")
            print(f"[DEBUG] Results: {len(self.results)}")

            idx = int(select.values[0])
            message_id = self.results[idx][0]

            print(f"[DEBUG] Message ID: {message_id}")

            # DetailViewに遷移
            view_data = {
                "type": "search",
                "search_conditions": self.search_conditions,
                "page": self.page,
                "sort_by": self.sort_by,
            }

            detail_view = DetailView(message_id, view_data)
            # セレクトの場合はdefer()せずに直接edit_messageを使う
            await detail_view.show(interaction, edit_message=False)
        except Exception as e:
            print(f"[ERROR] Search item select error: {e}")
            import traceback

            traceback.print_exc()
            if not interaction.response.is_done():
                await interaction.response.send_message(f"エラー: {e}", ephemeral=True)


class RandomPlayView(ui.View):
    """
    ランダム再生View
    1件のWatch URLと次へ・情報追加ボタン
    """

    def __init__(self, message_id: int):
        super().__init__(timeout=180)
        self.message_id = message_id

    async def show(self, interaction: discord.Interaction, edit_message: bool = False):
        """ランダム動画を表示"""
        # ヘッダーメッセージ
        header_parts = ["SEKAM統計所AI部", "専科AI動画 - ランダム再生"]
        header_message = "\n".join(header_parts)

        # Watch URL生成（rankパラメータを削除）
        encoded_comment = quote("ランダム再生")
        watch_url = (
            f"https://sekam.site/watch?v={self.message_id}&reaction={encoded_comment}"
        )

        message_content = header_message + "\n\n" + watch_url

        if edit_message:
            await interaction.response.edit_message(content=message_content, view=self)
        else:
            await interaction.followup.send(message_content, view=self, ephemeral=True)

    @ui.button(label="次へ", style=discord.ButtonStyle.primary, emoji="▶️")
    async def next_random(self, interaction: discord.Interaction, button: ui.Button):
        """次のランダム動画を表示"""
        sql = """
            SELECT m.id
            FROM messages m
            WHERE EXISTS (SELECT 1 FROM attachments a WHERE a.message_id = m.id)
               OR m.content LIKE '%%sora.chatgpt.com%%'
            ORDER BY RAND()
            LIMIT 1
        """
        result = run_aidb_query(sql, (), fetch="one")

        if not result:
            await interaction.response.send_message(
                "動画が見つかりませんでした。", ephemeral=True
            )
            return

        self.message_id = result[0]
        await self.show(interaction, edit_message=True)

    @ui.button(label="情報を追加する", style=discord.ButtonStyle.success, emoji="✏️")
    async def edit_info(self, interaction: discord.Interaction, button: ui.Button):
        """情報追加Modalを表示"""
        from .modals import InfoEditModal

        modal = InfoEditModal(self.message_id, None)
        await interaction.response.send_modal(modal)


class DetailView(ui.View):
    """
    詳細表示View
    1件のWatch URLと戻る・情報追加ボタン
    """

    def __init__(self, message_id: int, previous_view_data: dict[str, Any]):
        super().__init__(timeout=180)
        self.message_id = message_id
        self.previous_view_data = previous_view_data

    async def show(self, interaction: discord.Interaction, edit_message: bool = False):
        """詳細を表示"""
        # ヘッダーメッセージ
        header_parts = ["SEKAM統計所AI部", "専科AI動画 - 詳細"]
        header_message = "\n".join(header_parts)

        # Watch URL生成
        encoded_comment = quote("詳細表示")
        watch_url = (
            f"https://sekam.site/watch?v={self.message_id}&reaction={encoded_comment}"
        )

        message_content = header_message + "\n\n" + watch_url

        if edit_message:
            # defer()済みまたは既に応答済みの場合
            await interaction.edit_original_response(content=message_content, view=self)
        else:
            # 初回応答の場合
            await interaction.response.edit_message(content=message_content, view=self)

    @ui.button(label="戻る", style=discord.ButtonStyle.secondary, emoji="◀️")
    async def back(self, interaction: discord.Interaction, button: ui.Button):
        """前の画面に戻る"""
        try:
            print("[DEBUG] Detail back button clicked")
            if self.previous_view_data["type"] == "ranking":
                view = RankingResultView(
                    self.previous_view_data["emoji_name"],
                    self.previous_view_data["after_date"],
                    self.previous_view_data["before_date"],
                    self.previous_view_data["page"],
                )
                await interaction.response.defer()
                await view.show(interaction, edit_message=True)
            elif self.previous_view_data["type"] == "search":
                view = SearchResultView(
                    self.previous_view_data["search_conditions"],
                    self.previous_view_data["page"],
                    self.previous_view_data["sort_by"],
                )
                await interaction.response.defer()
                await view.show(interaction, edit_message=True)
            elif self.previous_view_data["type"] == "my_posts":
                view = MyPostsView(
                    self.previous_view_data["user_id"],
                    self.previous_view_data["page"],
                )
                await interaction.response.defer()
                await view.show(interaction, edit_message=True)
        except Exception as e:
            print(f"[ERROR] Detail back error: {e}")
            import traceback

            traceback.print_exc()

    @ui.button(label="情報を追加する", style=discord.ButtonStyle.success, emoji="✏️")
    async def edit_info(self, interaction: discord.Interaction, button: ui.Button):
        """情報追加Modalを表示"""
        from .modals import InfoEditModal

        modal = InfoEditModal(self.message_id, self.previous_view_data)
        await interaction.response.send_modal(modal)


class TagListView(ui.View):
    """
    タグ一覧表示View
    データベースに登録されているタグを集計して表示
    """

    def __init__(self, page: int = 1, sort_by: str = "count"):
        super().__init__(timeout=180)
        self.page = page
        self.sort_by = sort_by  # "count" (件数順) or "name" (名前順)
        self.tags: list[tuple] = []

    async def fetch_tags(self):
        """タグを集計して取得"""
        import json

        # metaテーブルからすべてのtagを取得
        sql = "SELECT tag FROM meta WHERE tag IS NOT NULL AND tag != ''"
        results = run_aidb_query(sql, (), fetch="all")

        if not results:
            self.tags = []
            return

        # タグをカウント
        tag_count = {}
        for row in results:
            tag_json = row[0]
            if not tag_json:
                continue

            try:
                tags = json.loads(tag_json)
                if isinstance(tags, list):
                    for tag in tags:
                        if tag and isinstance(tag, str):
                            tag_count[tag] = tag_count.get(tag, 0) + 1
            except Exception:
                continue

        # ソート
        if self.sort_by == "count":
            # 件数の多い順
            sorted_tags = sorted(tag_count.items(), key=lambda x: x[1], reverse=True)
        else:  # "name"
            # 名前順
            sorted_tags = sorted(tag_count.items(), key=lambda x: x[0])

        # ページング
        offset = (self.page - 1) * 20
        self.tags = sorted_tags[offset : offset + 20]

    async def show(self, interaction: discord.Interaction, edit_message: bool = False):
        """タグ一覧を表示"""
        await self.fetch_tags()

        if not self.tags:
            message = "タグが登録されていません。"
            if edit_message:
                await interaction.edit_original_response(content=message, view=None)
            else:
                await interaction.followup.send(message, ephemeral=True)
            return

        # ヘッダーメッセージ
        header_parts = ["SEKAM統計所AI部", "専科AI動画 - タグ一覧"]

        sort_label = "件数順" if self.sort_by == "count" else "名前順"
        header_parts.append(f"並び順: {sort_label}")
        header_parts.append(f"-# ページ {self.page}")
        header_message = "\n".join(header_parts)

        # タグリストの生成
        tag_lines = []
        for tag, count in self.tags:
            tag_lines.append(f"**{tag}** ({count}件)")

        message_content = header_message + "\n\n" + "\n".join(tag_lines)

        # ボタンとセレクトの更新
        self._update_components()

        if edit_message:
            await interaction.edit_original_response(content=message_content, view=self)
        else:
            await interaction.followup.send(message_content, view=self, ephemeral=True)

    def _update_components(self):
        """ボタンの状態を更新"""
        try:
            print(
                f"[DEBUG] TagList _update_components, page={self.page}, tags={len(self.tags)}"
            )
            # ページングボタンの有効/無効化
            self.children[0].disabled = self.page == 1  # 前のページボタン
            self.children[1].disabled = len(self.tags) < 20  # 次のページボタン

            # ソート選択のデフォルト値を更新
            for option in self.children[2].options:
                option.default = option.value == self.sort_by

            print("[DEBUG] TagList components updated")
        except Exception as e:
            print(f"[ERROR] TagList _update_components error: {e}")
            import traceback

            traceback.print_exc()

    @ui.button(label="前のページ", style=discord.ButtonStyle.secondary, emoji="⬅️")
    async def prev_page(self, interaction: discord.Interaction, button: ui.Button):
        """前のページを表示"""
        try:
            print("[DEBUG] TagList prev button clicked")
            if self.page > 1:
                self.page -= 1
                await interaction.response.defer()
                await self.show(interaction, edit_message=True)
        except Exception as e:
            print(f"[ERROR] TagList prev error: {e}")
            import traceback

            traceback.print_exc()

    @ui.button(label="次のページ", style=discord.ButtonStyle.secondary, emoji="➡️")
    async def next_page(self, interaction: discord.Interaction, button: ui.Button):
        """次のページを表示"""
        try:
            print("[DEBUG] TagList next button clicked")
            self.page += 1
            await interaction.response.defer()
            await self.show(interaction, edit_message=True)
        except Exception as e:
            print(f"[ERROR] TagList next error: {e}")
            import traceback

            traceback.print_exc()

    @ui.select(
        placeholder="並び替え",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(label="件数順", value="count", default=True),
            discord.SelectOption(label="名前順", value="name"),
        ],
    )
    async def sort_select(self, interaction: discord.Interaction, select: ui.Select):
        """ソート方式を変更"""
        try:
            print("[DEBUG] TagList sort select triggered")
            print(f"[DEBUG] Selected sort: {select.values[0]}")

            self.sort_by = select.values[0]
            self.page = 1  # ページをリセット

            # デフォルト選択肢を更新
            for option in select.options:
                option.default = option.value == self.sort_by

            await interaction.response.defer()
            await self.show(interaction, edit_message=True)
        except Exception as e:
            print(f"[ERROR] TagList sort error: {e}")
            import traceback

            traceback.print_exc()


class VideoByIdView(ui.View):
    """
    動画ID指定視聴View
    指定されたIDの動画を表示
    """

    def __init__(self, message_id: int):
        super().__init__(timeout=180)
        self.message_id = message_id

    async def show(self, interaction: discord.Interaction, edit_message: bool = False):
        """動画を表示"""
        # ヘッダーメッセージ
        header_parts = ["SEKAM統計所AI部", "専科AI動画 - ID指定視聴"]
        header_parts.append(f"動画ID: {self.message_id}")
        header_message = "\n".join(header_parts)

        # Watch URL生成
        encoded_comment = quote("ID指定視聴")
        watch_url = (
            f"https://sekam.site/watch?v={self.message_id}&reaction={encoded_comment}"
        )

        message_content = header_message + "\n\n" + watch_url

        if edit_message:
            await interaction.edit_original_response(content=message_content, view=self)
        else:
            await interaction.followup.send(message_content, view=self, ephemeral=True)

    @ui.button(label="情報を追加する", style=discord.ButtonStyle.success, emoji="✏️")
    async def edit_info(self, interaction: discord.Interaction, button: ui.Button):
        """情報追加Modalを表示"""
        from .modals import InfoEditModal

        # previous_view_dataをNoneにして、戻るボタンを表示しない
        modal = InfoEditModal(self.message_id, None)
        await interaction.response.send_modal(modal)


class MyPostsView(ui.View):
    """
    自分の投稿一覧View
    ユーザーの投稿を5件ずつページング表示
    """

    def __init__(self, user_id: int, page: int = 1):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.page = page
        self.results: list[tuple] = []

    def _update_components(self):
        """ボタンとセレクトの状態を更新"""
        try:
            print(
                f"[DEBUG] MyPosts _update_components, page={self.page}, results={len(self.results)}"
            )
            # ページングボタンの有効/無効化
            self.children[0].disabled = self.page == 1  # 前のページボタン
            self.children[1].disabled = len(self.results) < 5  # 次のページボタン

            # 項目選択セレクトの選択肢を更新
            offset = (self.page - 1) * 5
            options = []
            for idx in range(len(self.results)):
                position = offset + idx + 1
                options.append(
                    discord.SelectOption(label=f"{position}番目", value=str(idx))
                )

            self.children[2].options = options
            print(f"[DEBUG] Updated my_posts select options: {len(options)} items")
        except Exception as e:
            print(f"[ERROR] MyPosts _update_components error: {e}")
            import traceback

            traceback.print_exc()

    async def fetch_results(self):
        """ユーザーの投稿を取得"""
        offset = (self.page - 1) * 5

        sql = """
            SELECT
                m.id as message_id,
                m.channel_id,
                m.content,
                COALESCE(SUM(r.count), 0) as reaction_count
            FROM messages m
            LEFT JOIN reactions r ON m.id = r.message_id
            WHERE m.author_id = %s
              AND (EXISTS (SELECT 1 FROM attachments a WHERE a.message_id = m.id)
                   OR m.content LIKE '%%sora.chatgpt.com%%')
            GROUP BY m.id, m.channel_id, m.content
            ORDER BY m.timestamp DESC
            LIMIT 5 OFFSET %s
        """

        self.results = run_aidb_query(sql, (self.user_id, offset), fetch="all") or []

    async def show(self, interaction: discord.Interaction, edit_message: bool = False):
        """投稿一覧を表示"""
        await self.fetch_results()

        if not self.results:
            if edit_message:
                await interaction.edit_original_response(
                    content=f"投稿が見つかりませんでした。（ページ{self.page}）",
                    view=None,
                )
            else:
                await interaction.followup.send(
                    f"投稿が見つかりませんでした。（ページ{self.page}）",
                    ephemeral=True,
                )
            return

        # ヘッダーメッセージ
        header_parts = ["SEKAM統計所AI部", "専科AI動画 - 自分の投稿一覧"]
        header_parts.append("-# ページ " + str(self.page))
        header_message = "\n".join(header_parts)

        # Watch URLの生成
        watch_urls = []
        offset = (self.page - 1) * 5
        encoded_comment = quote("自分の投稿")

        for idx, row in enumerate(self.results):
            message_id = row[0]
            position = offset + idx + 1
            watch_url = f"https://sekam.site/watch?v={message_id}&reaction={encoded_comment}&rank={position}"
            watch_urls.append(watch_url)

        message_content = header_message + "\n\n" + "\n".join(watch_urls)

        # ボタンとセレクトの更新
        self._update_components()

        if edit_message:
            # defer()済みの場合はedit_original_responseを使用
            await interaction.edit_original_response(content=message_content, view=self)
        else:
            await interaction.followup.send(message_content, view=self, ephemeral=True)

    @ui.button(label="前のページ", style=discord.ButtonStyle.secondary, emoji="⬅️")
    async def prev_page(self, interaction: discord.Interaction, button: ui.Button):
        """前のページを表示"""
        try:
            print("[DEBUG] MyPosts prev button clicked")
            if self.page > 1:
                self.page -= 1
                await interaction.response.defer()
                await self.show(interaction, edit_message=True)
        except Exception as e:
            print(f"[ERROR] MyPosts prev error: {e}")
            import traceback

            traceback.print_exc()

    @ui.button(label="次のページ", style=discord.ButtonStyle.secondary, emoji="➡️")
    async def next_page(self, interaction: discord.Interaction, button: ui.Button):
        """次のページを表示"""
        try:
            print("[DEBUG] MyPosts next button clicked")
            self.page += 1
            await interaction.response.defer()
            await self.show(interaction, edit_message=True)
        except Exception as e:
            print(f"[ERROR] MyPosts next error: {e}")
            import traceback

            traceback.print_exc()

    @ui.select(placeholder="詳細を見る項目を選択", min_values=1, max_values=1)
    async def select_item(self, interaction: discord.Interaction, select: ui.Select):
        """選択された項目の詳細を表示"""
        try:
            print("[DEBUG] MyPosts item select triggered")
            print(f"[DEBUG] Selected value: {select.values[0]}")
            print(f"[DEBUG] Results: {len(self.results)}")

            idx = int(select.values[0])
            message_id = self.results[idx][0]

            print(f"[DEBUG] Message ID: {message_id}")

            # DetailViewに遷移
            view_data = {
                "type": "my_posts",
                "user_id": self.user_id,
                "page": self.page,
            }

            detail_view = DetailView(message_id, view_data)
            # セレクトの場合はdefer()せずに直接edit_messageを使う
            await detail_view.show(interaction, edit_message=False)
        except Exception as e:
            print(f"[ERROR] MyPosts item select error: {e}")
            import traceback

            traceback.print_exc()
            if not interaction.response.is_done():
                await interaction.response.send_message(f"エラー: {e}", ephemeral=True)
