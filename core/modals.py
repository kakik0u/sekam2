"""
SORAコマンド - Modalクラス群
ユーザー入力フォームとデータ検証を担当
"""

from typing import Optional

import discord
from discord import ui

from database.connection import run_aidb_query

from .utils import (
    parse_date_input,
    parse_tags_input,
    update_video_tags,
    update_video_title,
)


class RankingDateModal(ui.Modal, title="ランキング期間指定"):
    """
    ランキング日付入力Modal
    期間指定を受け付ける
    """

    # 期間指定（テキスト入力）
    after_date_input = ui.TextInput(
        label="開始日（YYYY/MM/DD形式、空欄でもOK）",
        placeholder="例: 2024/01/01（この日より後）",
        required=False,
        max_length=10,
    )

    before_date_input = ui.TextInput(
        label="終了日（YYYY/MM/DD形式、空欄でもOK）",
        placeholder="例: 2024/12/31（この日より前）",
        required=False,
        max_length=10,
    )

    def __init__(self, emoji_name: str):
        super().__init__()
        self.emoji_name = emoji_name

    async def on_submit(self, interaction: discord.Interaction):
        """フォーム送信時の処理"""
        # 日付のパース
        after_date = parse_date_input(self.after_date_input.value)
        before_date = parse_date_input(self.before_date_input.value)

        # 日付検証
        if after_date and before_date and after_date >= before_date:
            await interaction.response.send_message(
                "開始日は終了日より前である必要があります。", ephemeral=True
            )
            return

        # RankingResultViewを作成して表示
        from .views import RankingResultView

        view = RankingResultView(self.emoji_name, after_date, before_date)
        await interaction.response.defer()
        await view.show(interaction)


class SearchConditionModal(ui.Modal, title="検索条件指定"):
    """
    検索条件入力Modal
    タイトル、タグ、リアクション数下限を受け付ける
    """

    # タイトル検索
    title_input = ui.TextInput(
        label="タイトル（部分一致、空欄でもOK）",
        placeholder="検索したいタイトルを入力",
        required=False,
        max_length=50,
    )

    # タグ検索
    tags_input = ui.TextInput(
        label="タグ（カンマ区切り、空欄でもOK）",
        placeholder="例: ドラえもん,猫,風景",
        required=False,
        max_length=100,
    )

    # リアクション数下限
    min_reaction_input = ui.TextInput(
        label="リアクション数下限（空欄でもOK）",
        placeholder="例: 10",
        required=False,
        max_length=10,
    )

    async def on_submit(self, interaction: discord.Interaction):
        """フォーム送信時の処理"""
        from .utils import parse_tags_input
        from .views import SearchResultView

        # 入力値の取得
        title = self.title_input.value.strip() if self.title_input.value else None
        tags_str = self.tags_input.value.strip() if self.tags_input.value else None
        min_reaction_str = (
            self.min_reaction_input.value.strip()
            if self.min_reaction_input.value
            else None
        )

        # タグのパース
        tags = []
        if tags_str:
            parsed = parse_tags_input(tags_str)
            if parsed is None:
                await interaction.response.send_message(
                    "タグの形式が正しくありません。カンマ区切りで入力してください。",
                    ephemeral=True,
                )
                return
            tags = parsed

        # リアクション数のパース
        min_reaction = None
        if min_reaction_str:
            try:
                min_reaction = int(min_reaction_str)
                if min_reaction < 0:
                    raise ValueError
            except ValueError:
                await interaction.response.send_message(
                    "リアクション数は正の整数で入力してください。", ephemeral=True
                )
                return

        # 検索条件の作成
        search_conditions = {
            "title": title,
            "tags": tags,
            "min_reaction": min_reaction,
        }

        # SearchResultViewに遷移
        view = SearchResultView(search_conditions)
        await interaction.response.defer()
        await view.show(interaction)


class InfoEditModal(ui.Modal, title="動画情報の追加・編集"):
    """
    動画情報追加・編集Modal
    タイトル、タグを編集してmetaテーブルに保存
    """

    # タイトル編集
    title_input = ui.TextInput(
        label="タイトル（100文字以内）",
        placeholder="動画のタイトルを入力",
        required=False,
        max_length=100,
        style=discord.TextStyle.short,
    )

    # タグ編集
    tags_input = ui.TextInput(
        label="タグ（カンマ区切り）",
        placeholder="例: ドラえもん,猫,風景",
        required=False,
        max_length=500,
        style=discord.TextStyle.paragraph,
    )

    def __init__(self, message_id: int, previous_view_data: Optional[dict]):
        super().__init__()
        self.message_id = message_id
        self.previous_view_data = previous_view_data

        # 既存情報の取得と初期値設定
        self._load_existing_info()

    def _load_existing_info(self):
        """metaテーブルから既存情報を取得して初期値に設定"""
        sql = "SELECT title, tags FROM meta WHERE message_id = %s"
        result = run_aidb_query(sql, (self.message_id,), fetch="one")

        if result:
            title, tags = result
            if title:
                self.title_input.default = title
            if tags:
                self.tags_input.default = tags

    async def on_submit(self, interaction: discord.Interaction):
        """フォーム送信時の処理"""
        title = self.title_input.value.strip() if self.title_input.value else None
        tags_str = self.tags_input.value.strip() if self.tags_input.value else None

        # タグのパースとバリデーション
        if tags_str:
            tags = parse_tags_input(tags_str)
            if tags is None:
                await interaction.response.send_message(
                    "タグの形式が正しくありません。カンマ区切りで入力してください。",
                    ephemeral=True,
                )
                return
        else:
            tags = []

        # データベースへの保存
        user_id = interaction.user.id

        # タイトルの更新
        if title:
            update_video_title(self.message_id, title, user_id)

        # タグの更新
        if tags:
            update_video_tags(self.message_id, tags, user_id)

        # 元の画面に戻る
        await interaction.response.send_message(
            "情報を更新しました。Discord側の問題から反映まで10-30分ほどかかります。",
            ephemeral=True,
        )

        if self.previous_view_data:
            # DetailViewに戻る
            from .views import DetailView

            view = DetailView(self.message_id, self.previous_view_data)
            await view.show(interaction)
