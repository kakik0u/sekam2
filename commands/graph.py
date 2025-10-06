"""
グラフ生成コマンド
/myreaction - リアクション分布グラフ
/mylocate - チャンネル書き込み分布グラフ
"""

import discord
from discord import app_commands, Client
from discord.app_commands import allowed_installs
import os
import tempfile
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from PIL import Image, ImageDraw, ImageFont
from pilmoji import Pilmoji

from core.zichi import enforce_zichi_block
from core.log import insert_command_log
from spam.protection import is_overload_allowed
from database.connection import run_statdb_query
from utils.cache import get_reference_data_label
from utils.emoji import emoji_name_to_unicode
from config import debug


class GraphPaginationView(discord.ui.View):
    """
    グラフのページング機能を提供するViewクラス
    左右のボタンで表示範囲を変更可能
    """

    def __init__(
        self,
        all_data: list,
        username: str,
        reference_label: str,
        graph_type: str,
        user_id: int,
    ):
        """
        Args:
            all_data: 全データのリスト [(name, count), ...]
            username: ユーザー名
            reference_label: 参照データラベル
            graph_type: 'channel' または 'reaction'
            user_id: コマンドを実行したユーザーのID
        """
        super().__init__(timeout=600.0)  # 10分でタイムアウト
        self.all_data = all_data
        self.username = username
        self.reference_label = reference_label
        self.graph_type = graph_type
        self.user_id = user_id
        self.offset = 0
        self.show_others = False  # その他の表示フラグ（デフォルト: オフ）
        self.update_buttons()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """インタラクションが投稿主によるものかチェック"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "このボタンはコマンドを実行したユーザーのみが操作できます。",
                ephemeral=True,
            )
            return False
        return True

    def update_buttons(self):
        """ボタンの有効/無効を更新"""
        total = len(self.all_data)
        # 前へボタン: offset=0の時は無効
        self.children[0].disabled = self.offset == 0
        # 次へボタン: これ以上データがない時は無効
        self.children[1].disabled = self.offset + 10 >= total
        # リセットボタン: offset=0の時は無効
        self.children[2].disabled = self.offset == 0
        # その他ボタン: ラベルを更新
        self.children[3].label = "その他: オン" if self.show_others else "その他: オフ"
        self.children[3].style = (
            discord.ButtonStyle.success
            if self.show_others
            else discord.ButtonStyle.secondary
        )

    def get_current_data(self):
        """現在のオフセットに基づいてデータを取得"""
        visible_data = self.all_data[self.offset : self.offset + 10]

        # その他の表示がオフの場合は10件のみ
        if not self.show_others:
            return visible_data

        # その他の表示がオンの場合
        other_data = self.all_data[self.offset + 10 :]

        # その他の処理
        if other_data:
            if len(other_data) == 1:
                # 残り1件の場合は、その項目名を表示
                result = visible_data + [other_data[0]]
            else:
                # 残り2件以上の場合は「その他」として合計
                other_count = sum(item[1] for item in other_data)
                result = visible_data + [("その他", other_count)]
        else:
            result = visible_data

        return result

    def get_status_text(self):
        """現在の状態テキストを取得: '1-10件/50件'"""
        total = len(self.all_data)
        start = self.offset + 1
        end = min(self.offset + 10, total)
        return f"{start}-{end}件/{total}件"

    async def update_graph(self, interaction: discord.Interaction):
        """グラフを再生成してメッセージを更新"""
        try:
            await interaction.response.defer()

            # 現在のデータを取得
            current_data = self.get_current_data()
            status_text = self.get_status_text()

            # グラフ生成
            if self.graph_type == "channel":
                image_path = create_channel_graph(
                    current_data, self.username, self.reference_label, status_text
                )
                message_text = f"{self.username}の書き込み先チャンネル分布\n{self.reference_label} | {status_text}"
            else:  # reaction
                image_path = create_reaction_graph(
                    current_data, self.username, self.reference_label, status_text
                )
                message_text = f"{self.username}のもらったリアクション分布\n{self.reference_label} | {status_text}"

            # ボタンの状態を更新
            self.update_buttons()

            # メッセージを更新
            file = discord.File(
                image_path, filename=f"{self.graph_type}_distribution.png"
            )
            await interaction.edit_original_response(
                content=message_text, attachments=[file], view=self
            )

            # 一時ファイルを削除
            try:
                os.unlink(image_path)
            except Exception:
                pass

        except Exception as e:
            if debug:
                print(f"グラフ更新エラー: {e}")
                import traceback

                traceback.print_exc()
            try:
                await interaction.followup.send(
                    "グラフの更新中にエラーが発生しました。", ephemeral=True
                )
            except Exception:
                pass

    @discord.ui.button(label="前へ", style=discord.ButtonStyle.primary, emoji="◀️")
    async def prev_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """前のページに移動（10件飛ばし）"""
        if self.offset > 0:
            self.offset = max(0, self.offset - 10)
            await self.update_graph(interaction)

    @discord.ui.button(label="次へ", style=discord.ButtonStyle.primary, emoji="▶️")
    async def next_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """次のページに移動（10件飛ばし）"""
        if self.offset + 10 < len(self.all_data):
            self.offset += 10
            await self.update_graph(interaction)

    @discord.ui.button(
        label="リセット", style=discord.ButtonStyle.secondary, emoji="🔄"
    )
    async def reset_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """最初のページに戻る"""
        if self.offset != 0:
            self.offset = 0
            await self.update_graph(interaction)

    @discord.ui.button(
        label="その他: オン", style=discord.ButtonStyle.success, emoji="📊"
    )
    async def toggle_others_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """その他の表示をオンオフ"""
        self.show_others = not self.show_others
        await self.update_graph(interaction)

    async def on_timeout(self):
        """タイムアウト時にボタンを無効化"""
        for child in self.children:
            child.disabled = True


def create_channel_graph(
    data: list, username: str, reference_label: str, status_text: str = ""
) -> str:
    """
    チャンネル統計データから縦棒グラフを生成し、背景画像と合成して画像ファイルを作成する。

    引数:
      data: [(channel_name, count), ...] のリスト（上位10個 + その他）
      username: ユーザー名
      reference_label: 参照データのラベル

    返り値:
      生成された画像ファイルのパス
    """
    try:
        # フォントパスの設定
        font_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fonts")
        normal_font_path = os.path.join(font_dir, "UDShingo2.otf")
        title_font_path = os.path.join(font_dir, "UDShingoL.otf")

        # 入れ物準備
        channel_labels = [name for name, count in data]
        counts = [count for name, count in data]

        # matplotlibでグラフを作成
        fig, ax = plt.subplots(figsize=(13, 5.5), facecolor="#2C2F33")
        ax.set_facecolor("#2C2F33")  # 背景

        # 縦棒グラフを描画
        x_positions = range(len(channel_labels))
        _bars = ax.bar(x_positions, counts, color="#5865F2", width=0.6)

        # X軸のラベル設定（空白にして後でPillowで描画）
        ax.set_xticks(x_positions)
        ax.set_xticklabels([""] * len(channel_labels))

        # フォント設定（Y軸ラベルのみ）
        try:
            prop_normal = fm.FontProperties(fname=normal_font_path, size=12)
            ax.set_ylabel("投稿数", fontproperties=prop_normal, color="white")
            ax.tick_params(axis="y", colors="white")  # Y軸の目盛りを白に
        except Exception as e:
            if debug:
                print(f"フォント設定エラー: {e}")
            ax.set_ylabel("投稿数", color="white")
            ax.tick_params(axis="y", colors="white")

        # グリッド追加
        ax.grid(axis="y", alpha=0.2, color="white")

        # 枠線を削除
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["bottom"].set_visible(False)
        ax.spines["left"].set_color("white")

        # X軸の下側にスペースを確保（チャンネル名用、余白を増やす）
        plt.subplots_adjust(bottom=0.25)

        # レイアウト調整
        plt.tight_layout()

        # 一時ファイルにグラフを保存
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

        # 背景画像と合成
        bg_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "bg/bg_green.png"
        )
        if os.path.exists(bg_path):
            # 背景画像を読み込み
            bg = Image.open(bg_path).convert("RGBA")
            graph_img = Image.open(graph_temp_path).convert("RGBA")

            # グラフサイズと背景サイズを取得
            graph_width, graph_height = graph_img.size
            bg_width, bg_height = bg.size  # 1280x720

            # グラフが背景より大きい場合はリサイズ
            # 左右の余白を最小限にして横幅を最大化: 左右各40pxの余白で1200px
            max_graph_width = bg_width - 80  # 1280 - 80 = 1200px (左右各40px余白)
            max_graph_height = int(
                bg_height * 0.70
            )  # 背景の70%まで（下部に文字用余白確保）

            if graph_width > max_graph_width or graph_height > max_graph_height:
                # アスペクト比を維持してリサイズ
                ratio = min(
                    max_graph_width / graph_width, max_graph_height / graph_height
                )
                new_width = int(graph_width * ratio)
                new_height = int(graph_height * ratio)
                graph_img = graph_img.resize(
                    (new_width, new_height), Image.Resampling.LANCZOS
                )
                graph_width, graph_height = new_width, new_height

            # グラフの配置位置を計算（中央やや上部）
            x_offset = (bg_width - graph_width) // 2
            y_offset = 101  # 上部に配置

            # 新しい画像を作成
            final_img = bg.copy()
            final_img.paste(graph_img, (x_offset, y_offset), graph_img)

            # テキスト追加（ユーザー名と参照ラベル）
            _draw = ImageDraw.Draw(final_img)

            try:
                # フォント読み込み
                title_font = ImageFont.truetype(title_font_path, 36)
                label_font = ImageFont.truetype(normal_font_path, 18)
                channel_label_font = ImageFont.truetype(normal_font_path, 14)
            except Exception:
                # フォールバック
                title_font = ImageFont.load_default()
                label_font = ImageFont.load_default()
                channel_label_font = ImageFont.load_default()

            # Pilmojiを使用してテキストを描画
            with Pilmoji(final_img) as pilmoji:
                # タイトルを左揃えで描画
                title_text = f"{username} の書き込み先チャンネル"
                title_x = 50  # 左端から50px
                title_y = 40
                pilmoji.text(
                    (title_x, title_y), title_text, font=title_font, fill="white"
                )

                # 参照ラベルを左下に描画
                clean_label = reference_label.replace("-# ", "").replace("-#", "")
                label_x = 50  # 左端から50px
                label_y = bg_height - 60  # 下から60px
                pilmoji.text(
                    (label_x, label_y), clean_label, font=label_font, fill="white"
                )

                # 状態テキストを表示（参照ラベルの一行上）
                if status_text:
                    status_x = 50
                    status_y = label_y - 30  # 参照ラベルの30px上
                    pilmoji.text(
                        (status_x, status_y),
                        status_text,
                        font=label_font,
                        fill="#AAAAAA",
                    )

                # X軸のラベルを描画（チャンネル名）
                # グラフの目盛り・余白を除外してバー表示領域のみで計算
                graph_left_margin = 80  # グラフ左側の目盛り余白（固定）
                graph_right_margin = 20  # グラフ右側の余白（固定）
                usable_width = (
                    graph_width - graph_left_margin - graph_right_margin
                )  # 実際のバー表示領域
                bar_width = usable_width / len(channel_labels)  # 各バーの幅

                # グラフの下部にラベルを配置（余白を増やす）
                label_y_pos = (
                    y_offset + graph_height + 15
                )  # グラフの下15px（10px→15px）

                for i, label in enumerate(channel_labels):
                    # 各ラベルの位置を計算（左から右へ、目盛り余白を考慮）
                    label_x_pos = (
                        x_offset
                        + graph_left_margin
                        + int(i * bar_width + bar_width / 2)
                    )

                    # チャンネル名を描画（「その他」以外で長い場合は省略）
                    display_label = label
                    if label != "その他" and len(label) > 10:
                        display_label = label[:8] + "..."

                    # 中央揃えのためのオフセット計算
                    bbox = pilmoji.getsize(display_label, font=channel_label_font)
                    text_width = bbox[0] if bbox else len(display_label) * 7
                    label_x_pos -= text_width // 2

                    pilmoji.text(
                        (label_x_pos, label_y_pos),
                        display_label,
                        font=channel_label_font,
                        fill="white",
                    )

            # 最終画像を保存
            final_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            final_temp_path = final_temp.name
            final_temp.close()
            final_img.save(final_temp_path, "PNG")

            # グラフの一時ファイルを削除
            try:
                os.unlink(graph_temp_path)
            except Exception:
                pass

            return final_temp_path
        else:
            # 背景画像がない場合はグラフのみ
            if debug:
                print("背景画像が見つかりません。グラフのみを使用します。")
            return graph_temp_path

    except Exception as e:
        if debug:
            print(f"グラフ生成エラー: {e}")
        raise


def create_reaction_graph(
    data: list, username: str, reference_label: str, status_text: str = ""
) -> str:
    """
    リアクションデータから縦棒グラフを生成し、背景画像と合成して画像ファイルを作成する。

    引数:
      data: [(emoji_name, count), ...] のリスト（上位10個 + その他）
      username: ユーザー名
      reference_label: 参照データのラベル
      status_text: 状態テキスト（例: "1-10件/50件"）

    返り値:
      生成された画像ファイルのパス
    """
    try:
        # フォントパスの設定
        font_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fonts")
        normal_font_path = os.path.join(font_dir, "UDShingoL.otf")

        # データの準備
        emoji_labels = []  # 絵文字表示用
        counts = []
        for emoji_name, count in data:
            # "その他"は特別扱い
            if emoji_name == "その他":
                emoji_labels.append("その他")
            else:
                # 英名をUnicode絵文字に変換
                emoji_unicode = emoji_name_to_unicode(emoji_name)
                emoji_labels.append(emoji_unicode)
            counts.append(count)

        # matplotlibでグラフを作成（縦棒グラフ用の設定）
        fig, ax = plt.subplots(figsize=(10, 5.5), facecolor="#2C2F33")
        ax.set_facecolor("#2C2F33")  # グラフエリアの背景色

        # 縦棒グラフを描画
        x_positions = range(len(emoji_labels))
        _bars = ax.bar(x_positions, counts, color="#5865F2", width=0.6)

        # X軸のラベル設定（空白にして後でPillowで描画）
        ax.set_xticks(x_positions)
        ax.set_xticklabels([""] * len(emoji_labels))

        # フォント設定（Y軸ラベルのみ）
        try:
            prop_normal = fm.FontProperties(fname=normal_font_path, size=12)
            ax.set_ylabel("回数", fontproperties=prop_normal, color="white")
            ax.tick_params(axis="y", colors="white")  # Y軸の目盛りを白に
        except Exception as e:
            if debug:
                print(f"フォント設定エラー: {e}")
            ax.set_ylabel("回数", color="white")
            ax.tick_params(axis="y", colors="white")

        # グリッド追加（暗めに）
        ax.grid(axis="y", alpha=0.2, color="white")

        # 枠線を削除
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["bottom"].set_visible(False)
        ax.spines["left"].set_color("white")

        # X軸の下側にスペースを確保（絵文字用）
        plt.subplots_adjust(bottom=0.15)

        # レイアウト調整
        plt.tight_layout()

        # 一時ファイルにグラフを保存（背景を透明に）
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

        # 背景画像と合成
        bg_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "bg/bg_blue.png"
        )
        if os.path.exists(bg_path):
            # 背景画像を読み込み
            bg = Image.open(bg_path).convert("RGBA")
            graph_img = Image.open(graph_temp_path).convert("RGBA")

            # グラフサイズと背景サイズを取得
            graph_width, graph_height = graph_img.size
            bg_width, bg_height = bg.size  # 1280x720

            # グラフが背景より大きい場合はリサイズ
            max_graph_width = int(bg_width * 0.75)  # 背景の75%まで
            max_graph_height = int(
                bg_height * 0.75
            )  # 背景の75%まで（70%→75%に拡大、さらに36px削る）

            if graph_width > max_graph_width or graph_height > max_graph_height:
                # アスペクト比を維持してリサイズ
                ratio = min(
                    max_graph_width / graph_width, max_graph_height / graph_height
                )
                new_width = int(graph_width * ratio)
                new_height = int(graph_height * ratio)
                graph_img = graph_img.resize(
                    (new_width, new_height), Image.Resampling.LANCZOS
                )
                graph_width, graph_height = new_width, new_height

            # グラフの配置位置を計算（中央やや上部）
            x_offset = (bg_width - graph_width) // 2
            y_offset = 101  # 上部に配置（161 - 60 = 101に調整）

            # 新しい画像を作成
            final_img = bg.copy()
            final_img.paste(graph_img, (x_offset, y_offset), graph_img)

            # テキスト追加（ユーザー名と参照ラベル）
            _draw = ImageDraw.Draw(final_img)

            try:
                # フォント読み込み
                title_font = ImageFont.truetype(normal_font_path, 36)
                label_font = ImageFont.truetype(normal_font_path, 20)
                emoji_label_font = ImageFont.truetype(normal_font_path, 28)
            except Exception:
                # フォールバック
                title_font = ImageFont.load_default()
                label_font = ImageFont.load_default()
                emoji_label_font = ImageFont.load_default()

            # Pilmojiを使用してテキストを描画
            with Pilmoji(final_img) as pilmoji:
                # タイトルを左揃えで描画（枠線なし）
                title_text = f"{username} のもらったリアクション分布"
                title_x = 50  # 左端から50px
                title_y = 40
                pilmoji.text(
                    (title_x, title_y), title_text, font=title_font, fill="white"
                )

                # 参照ラベルを左下に描画（-#を削除、枠線なし）
                # reference_labelから"-# "を削除
                clean_label = reference_label.replace("-# ", "").replace("-#", "")
                label_x = 50  # 左端から50px
                label_y = bg_height - 60  # 下から60px
                pilmoji.text(
                    (label_x, label_y), clean_label, font=label_font, fill="white"
                )

                # 状態テキストを表示（参照ラベルの一行上）
                if status_text:
                    status_x = 50
                    status_y = label_y - 30  # 参照ラベルの30px上
                    status_font = ImageFont.truetype(normal_font_path, 18)
                    pilmoji.text(
                        (status_x, status_y),
                        status_text,
                        font=status_font,
                        fill="#AAAAAA",
                    )

                # X軸のラベルを描画（絵文字または"その他"）縦棒グラフ用
                # グラフの各列の位置を計算してラベルを配置
                # グラフの左右のマージンを考慮
                left_margin = graph_width * 0.08  # 左側8%を除外
                right_margin = graph_width * 0.02  # 右側2%を除外
                usable_width = graph_width - left_margin - right_margin  # 使用可能な幅
                bar_width = usable_width / len(emoji_labels)  # 各バーの幅

                # グラフの下部にラベルを配置
                label_y_pos = y_offset + graph_height + 10  # グラフの下10px

                for i, label in enumerate(emoji_labels):
                    # 各ラベルの位置を計算（左から右へ）
                    label_x_pos = x_offset + int(
                        left_margin + i * bar_width + bar_width / 2 - 16
                    )

                    # "その他"の場合は通常フォント、それ以外は絵文字として扱う
                    if label == "その他":
                        # 通常フォントで描画
                        pilmoji.text(
                            (label_x_pos, label_y_pos),
                            label,
                            font=label_font,
                            fill="white",
                        )
                    else:
                        # 絵文字を描画（Pilmojiが自動的にカラー絵文字として描画）
                        try:
                            pilmoji.text(
                                (label_x_pos, label_y_pos),
                                label,
                                font=emoji_label_font,
                                fill="white",
                                emoji_scale_factor=1.2,
                            )
                        except Exception as e:
                            if debug:
                                print(f"Pilmoji絵文字描画エラー ({label}): {e}")
                            # フォールバック: 英名を表示
                            original_name = data[i][0]
                            pilmoji.text(
                                (label_x_pos, label_y_pos),
                                original_name,
                                font=label_font,
                                fill="white",
                            )

            # 最終画像を保存
            final_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            final_temp_path = final_temp.name
            final_temp.close()
            final_img.save(final_temp_path, "PNG")

            # グラフの一時ファイルを削除
            try:
                os.unlink(graph_temp_path)
            except Exception:
                pass

            return final_temp_path
        else:
            # 背景画像がない場合はグラフのみ
            if debug:
                print("背景画像が見つかりません。グラフのみを使用します。")
            return graph_temp_path

    except Exception as e:
        if debug:
            print(f"グラフ生成エラー: {e}")
        raise


async def setup_graph_commands(tree: app_commands.CommandTree, client: Client):
    """
    グラフコマンドを登録

    Args:
        tree: Discord CommandTree インスタンス
        client: Discord Client インスタンス (未使用だが統一のため)
    """

    @tree.command(
        name="myreaction",
        description="あなたが受け取ったリアクションの分布を表示します",
    )
    @allowed_installs(guilds=True, users=True)
    async def myreaction(ctx: discord.Interaction):
        """ユーザーが受け取ったリアクションの上位10個+その他を縦棒グラフで表示"""
        if await enforce_zichi_block(ctx, "/myreaction"):
            return

        print(f"myreactionコマンドが実行されました: {ctx.user.name} ({ctx.user.id})")

        try:
            # 過負荷モードチェック
            if not is_overload_allowed(ctx):
                await ctx.response.send_message(
                    "現在過負荷対策により専科外では使えません", ephemeral=True
                )
                insert_command_log(ctx, "/myreaction", "DENY_OVERLOAD")
                return

            # 処理開始を通知
            await ctx.response.defer()

            # ユーザー情報取得
            user = getattr(ctx, "user", None) or getattr(ctx, "author", None)
            username = getattr(user, "display_name", None) or getattr(
                user, "name", str(user)
            )
            uid = int(getattr(user, "id", 0) or 0)

            # 参照データラベル取得
            reference_label = get_reference_data_label()

            # SQLでリアクションデータを取得
            sql = """
              SELECT 
                emoji_name,
                SUM(count) as total_count
              FROM reactions r
              JOIN messages m ON r.message_id = m.id
              WHERE m.author_id = %s
              GROUP BY emoji_name
              ORDER BY total_count DESC
            """

            rows = run_statdb_query(sql, (uid,), fetch="all")

            if not rows or len(rows) == 0:
                # データがない場合
                embed = discord.Embed(
                    title="リアクションデータなし",
                    description="あなたの投稿にリアクションがまだついていないようです。",
                    color=0x5865F2,
                )
                embed.set_footer(
                    text="SEKAM2 - SEKAMの2",
                    icon_url="https://d.kakikou.app/sekam2logo.png",
                )
                await ctx.followup.send(
                    f"{username}のもらったリアクション分布\n{reference_label}",
                    embed=embed,
                )
                insert_command_log(ctx, "/myreaction", "NO_DATA")
                return

            # データ処理: 全データを取得
            all_data = []
            for row in rows:
                emoji_name = row[0]
                count = int(row[1]) if row[1] is not None else 0
                all_data.append((emoji_name, count))

            # GraphPaginationViewを使用して初期グラフを作成
            view = GraphPaginationView(
                all_data, username, reference_label, "reaction", uid
            )

            # 初期データを取得
            current_data = view.get_current_data()
            status_text = view.get_status_text()

            # 初期グラフを生成
            image_path = create_reaction_graph(
                current_data, username, reference_label, status_text
            )

            # Discordに送信（Viewを追加）
            file = discord.File(image_path, filename="reaction_distribution.png")
            await ctx.followup.send(
                f"{username}のもらったリアクション分布\n{reference_label}",
                file=file,
                view=view,
            )

            # 一時ファイルを削除
            try:
                os.unlink(image_path)
            except Exception:
                pass

            insert_command_log(ctx, "/myreaction", "OK")

        except Exception as e:
            if debug:
                print(f"myreactionエラー: {e}")
                import traceback

                traceback.print_exc()
            insert_command_log(ctx, "/myreaction", f"ERROR:{e}")
            try:
                if not ctx.response.is_done():
                    await ctx.response.send_message(
                        "取得中にエラーが発生しました。", ephemeral=True
                    )
                else:
                    await ctx.followup.send(
                        "取得中にエラーが発生しました。", ephemeral=True
                    )
            except Exception:
                pass

    @tree.command(
        name="mylocate",
        description="あなたが普段書き込んでいるチャンネル・スレッドの分布を表示します",
    )
    @allowed_installs(guilds=True, users=True)
    async def mylocate(ctx: discord.Interaction):
        """ユーザーが普段書き込んでいるチャンネル・スレッドの上位10個を縦棒グラフで表示"""
        if await enforce_zichi_block(ctx, "/mylocate"):
            return

        print(f"mylocateコマンドが実行されました: {ctx.user.name} ({ctx.user.id})")

        try:
            # 過負荷モードチェック
            if not is_overload_allowed(ctx):
                await ctx.response.send_message(
                    "現在過負荷対策により専科外では使えません", ephemeral=True
                )
                insert_command_log(ctx, "/mylocate", "DENY_OVERLOAD")
                return

            # 処理開始を通知
            await ctx.response.defer()

            # ユーザー情報取得
            user = getattr(ctx, "user", None) or getattr(ctx, "author", None)
            username = getattr(user, "display_name", None) or getattr(
                user, "name", str(user)
            )
            uid = int(getattr(user, "id", 0) or 0)

            # 参照データラベル取得
            reference_label = get_reference_data_label()

            # SQLでチャンネル別投稿数を取得（全件取得）
            sql = """
              SELECT 
                c.name as channel_name,
                COUNT(*) as message_count
              FROM messages m
              JOIN channels c ON m.channel_id = c.id
              WHERE m.author_id = %s
              GROUP BY c.id, c.name
              ORDER BY message_count DESC
            """

            rows = run_statdb_query(sql, (uid,), fetch="all")

            if not rows or len(rows) == 0:
                # データがない場合
                embed = discord.Embed(
                    title="投稿データなし",
                    description="あなたの投稿データが見つかりませんでした。",
                    color=0x5865F2,
                )
                embed.set_footer(
                    text="SEKAM2 - SEKAMの2",
                    icon_url="https://d.kakikou.app/sekam2logo.png",
                )
                await ctx.followup.send(
                    f"{username}の書き込み先チャンネル分布\n{reference_label}",
                    embed=embed,
                )
                insert_command_log(ctx, "/mylocate", "NO_DATA")
                return

            # データ処理: 全データを取得
            all_data = []
            for row in rows:
                channel_name = row[0] if row[0] else "不明なチャンネル"
                count = int(row[1]) if row[1] is not None else 0
                all_data.append((channel_name, count))

            # GraphPaginationViewを使用して初期グラフを作成
            view = GraphPaginationView(
                all_data, username, reference_label, "channel", uid
            )

            # 初期データを取得
            current_data = view.get_current_data()
            status_text = view.get_status_text()

            # 初期グラフを生成
            image_path = create_channel_graph(
                current_data, username, reference_label, status_text
            )

            # Discordに送信（Viewを追加）
            file = discord.File(image_path, filename="channel_distribution.png")
            await ctx.followup.send(
                f"{username}の書き込み先チャンネル分布\n{reference_label}",
                file=file,
                view=view,
            )

            # 一時ファイルを削除
            try:
                os.unlink(image_path)
            except Exception:
                pass

            insert_command_log(ctx, "/mylocate", "OK")

        except Exception as e:
            if debug:
                print(f"mylocateエラー: {e}")
                import traceback

                traceback.print_exc()
            insert_command_log(ctx, "/mylocate", f"ERROR:{e}")
            try:
                if not ctx.response.is_done():
                    await ctx.response.send_message(
                        "取得中にエラーが発生しました。", ephemeral=True
                    )
                else:
                    await ctx.followup.send(
                        "取得中にエラーが発生しました。", ephemeral=True
                    )
            except Exception:
                pass
