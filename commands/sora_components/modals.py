"""
SORAコマンド - Modalクラス群
ユーザー入力フォームとデータ検証を担当
"""

from urllib.parse import quote

import discord
from discord import ui

from core.log import insert_command_log
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
        placeholder="例: 2025/10/01（この日より後）",
        required=False,
        max_length=10,
    )

    before_date_input = ui.TextInput(
        label="終了日（YYYY/MM/DD形式、空欄でもOK）",
        placeholder="例: 2025/10/31（この日より前）",
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

        # 日付検証（開始日 > 終了日の場合のみエラー、同じ日付はOK）
        if after_date and before_date and after_date > before_date:
            await interaction.response.send_message(
                "開始日は終了日以前である必要があります。", ephemeral=True
            )
            return

        # RankingResultViewを作成して表示
        from .views import RankingResultView

        view = RankingResultView(self.emoji_name, after_date, before_date)
        await interaction.response.defer()
        await view.show(interaction)


class RangeDateModal(ui.Modal, title="ランキング期間指定"):
    """
    範囲指定ランキング用の日付入力Modal
    日付入力後、絵文字選択に遷移
    """

    # 期間指定（テキスト入力）
    after_date_input = ui.TextInput(
        label="開始日（YYYY/MM/DD形式、空欄でもOK）",
        placeholder="例: 2025/10/01（この日より後）",
        required=False,
        max_length=10,
    )

    before_date_input = ui.TextInput(
        label="終了日（YYYY/MM/DD形式、空欄でもOK）",
        placeholder="例: 2025/10/31（この日より前）",
        required=False,
        max_length=10,
    )

    async def on_submit(self, interaction: discord.Interaction):
        """フォーム送信時の処理"""
        # 日付のパース
        after_date = parse_date_input(self.after_date_input.value)
        before_date = parse_date_input(self.before_date_input.value)

        # 日付検証（開始日 > 終了日の場合のみエラー、同じ日付はOK）
        if after_date and before_date and after_date > before_date:
            await interaction.response.send_message(
                "開始日は終了日以前である必要があります。", ephemeral=True
            )
            return

        # 絵文字選択Viewに遷移
        from .views import EmojiSelectView

        view = EmojiSelectView(
            ranking_type="range", after_date=after_date, before_date=before_date
        )

        message_content = (
            "🏆 **範囲指定ランキング - 絵文字選択**\n\n"
            "ランキングを表示する絵文字を選択してください"
        )

        await interaction.response.send_message(
            content=message_content, view=view, ephemeral=True
        )


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
        placeholder="例: 恐山,sama,オリジナル",
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
        placeholder="例: 恐山,sama,オリジナル",
        required=False,
        max_length=500,
        style=discord.TextStyle.paragraph,
    )

    def __init__(self, message_id: int, previous_view_data: dict | None):
        super().__init__()
        self.message_id = message_id
        self.previous_view_data = previous_view_data

        # 既存情報の取得と初期値設定
        self._load_existing_info()

    def _load_existing_info(self):
        """metaテーブルから既存情報を取得して初期値に設定"""
        import json

        sql = "SELECT title, tag FROM meta WHERE id = %s"
        result = run_aidb_query(sql, (self.message_id,), fetch="one")

        if result:
            title, tag = result
            if title:
                self.title_input.default = title
            if tag:
                try:
                    tag_list = json.loads(tag)
                    if isinstance(tag_list, list):
                        self.tags_input.default = ",".join(tag_list)
                except Exception:
                    pass

    async def on_submit(self, interaction: discord.Interaction):
        """フォーム送信時の処理"""
        try:
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
                    insert_command_log(
                        interaction,
                        "soraInfo",
                        f"ERROR:無効なタグ形式 動画ID:{self.message_id}",
                    )
                    return
            else:
                tags = []

            # データベースへの保存
            user_id = interaction.user.id
            user_name = interaction.user.display_name or interaction.user.name
            success = False

            # 変更内容を記録
            changes = []

            # タイトルの更新
            if title:
                if update_video_title(self.message_id, title, user_id):
                    success = True
                    changes.append(f"タイトル:'{title}'")

            # タグの更新
            if tags:
                if update_video_tags(self.message_id, tags, user_id):
                    success = True
                    changes.append(f"タグ:{','.join(tags)}")

            if not success and not title and not tags:
                await interaction.response.send_message(
                    "何も入力されませんでした。", ephemeral=True
                )
                return

            # コマンドログに記録
            if changes:
                change_summary = " | ".join(changes)
                log_result = f"動画ID:{self.message_id} | ユーザー:{user_name} | 変更:{change_summary}"
                insert_command_log(interaction, "soraInfo", log_result)

            # 更新成功メッセージ
            await interaction.response.send_message(
                "情報を更新しました。Discord側の問題から反映まで10-30分ほどかかります。",
                ephemeral=True,
            )

        except Exception as e:
            print(f"[InfoEditModal] エラー: {e}")
            import traceback

            traceback.print_exc()
            insert_command_log(
                interaction, "soraInfo", f"ERROR:{str(e)} 動画ID:{self.message_id}"
            )
            await interaction.response.send_message(
                "情報の更新中にエラーが発生しました。", ephemeral=True
            )

        # DetailViewの表示を更新（rank=変更済み）
        if self.previous_view_data:
            from .views import DetailView

            view = DetailView(self.message_id, self.previous_view_data)

            # メッセージを編集して更新
            header_parts = ["SEKAM統計所AI部", "専科AI動画 - 詳細"]
            header_message = "\n".join(header_parts)

            encoded_comment = quote("変更済み")
            watch_url = f"https://sekam.site/watch?v={self.message_id}&reaction={encoded_comment}&rank=変更済み"

            message_content = header_message + "\n\n" + watch_url

            # 元のメッセージを編集
            try:
                await interaction.message.edit(content=message_content, view=view)
            except Exception:
                pass


class VideoIdModal(ui.Modal, title="動画ID指定"):
    """
    動画ID入力Modal
    メッセージIDを指定して動画を視聴
    """

    video_id_input = ui.TextInput(
        label="動画ID（メッセージID）",
        placeholder="例: 1234567890123456789",
        required=True,
        max_length=20,
    )

    async def on_submit(self, interaction: discord.Interaction):
        """フォーム送信時の処理"""
        try:
            # IDの検証
            video_id_str = self.video_id_input.value.strip()

            if not video_id_str.isdigit():
                await interaction.response.send_message(
                    "動画IDは数字で入力してください。", ephemeral=True
                )
                return

            message_id = int(video_id_str)

            # メッセージが存在するか確認
            sql = """
                SELECT m.id
                FROM messages m
                WHERE m.id = %s
                AND EXISTS (SELECT 1 FROM attachments a WHERE a.message_id = m.id AND (
                    a.filename LIKE '%%.mp4' OR a.filename LIKE '%%.mov' OR
                    a.filename LIKE '%%.avi' OR a.filename LIKE '%%.webm' OR
                    a.filename LIKE '%%.mkv' OR a.filename LIKE '%%.flv' OR
                    a.filename LIKE '%%.wmv' OR a.filename LIKE '%%.m4v'))
            """
            result = run_aidb_query(sql, (message_id,), fetch="one")

            if not result:
                await interaction.response.send_message(
                    f"ID {message_id} の動画が見つかりませんでした。", ephemeral=True
                )
                return

            # VideoByIdViewを表示
            from .views import VideoByIdView

            view = VideoByIdView(message_id)
            await interaction.response.defer()
            await view.show(interaction)

        except ValueError:
            await interaction.response.send_message(
                "無効な動画IDです。数字のみを入力してください。", ephemeral=True
            )
        except Exception as e:
            print(f"[ERROR] VideoIdModal error: {e}")
            import traceback

            traceback.print_exc()
            await interaction.response.send_message(
                f"エラーが発生しました: {e}", ephemeral=True
            )
