"""
SORAコマンド - ユーティリティ関数群
データ変換、データベース操作、検証機能を提供
"""

from datetime import datetime

from database.connection import run_aidb_query


def parse_date_input(date_str: str | None) -> datetime | None:
    """
    日付文字列をdatetimeオブジェクトに変換

    Args:
        date_str: "YYYY/MM/DD"形式の日付文字列

    Returns:
        datetimeオブジェクト、パース失敗時はNone
    """
    if not date_str or not date_str.strip():
        return None

    try:
        # "YYYY/MM/DD"形式でパース
        date_obj = datetime.strptime(date_str.strip(), "%Y/%m/%d")
        return date_obj
    except ValueError:
        # パース失敗
        return None


def parse_tags_input(tags_str: str) -> list[str] | None:
    """
    カンマ区切りのタグ文字列をリストに変換

    Args:
        tags_str: "tag1,tag2,tag3"形式のタグ文字列

    Returns:
        タグのリスト、パース失敗時はNone
    """
    if not tags_str or not tags_str.strip():
        return []

    # カンマで分割して前後の空白を除去
    tags = [tag.strip() for tag in tags_str.split(",")]

    # 空文字列を除外
    tags = [tag for tag in tags if tag]

    # タグの数が妥当かチェック（最大10個など）
    if len(tags) > 10:
        return None

    # タグの長さチェック（各タグ最大20文字など）
    for tag in tags:
        if len(tag) > 20:
            return None

    return tags


def merge_tags(existing_tags: str, new_tags: list[str]) -> str:
    """
    既存のタグと新しいタグをマージ

    Args:
        existing_tags: カンマ区切りの既存タグ文字列
        new_tags: 新しいタグのリスト

    Returns:
        マージされたカンマ区切りタグ文字列
    """
    # 既存タグをリストに変換
    if existing_tags:
        existing_list = [tag.strip() for tag in existing_tags.split(",")]
    else:
        existing_list = []

    # 新しいタグを追加（重複を除去）
    all_tags = list(set(existing_list + new_tags))

    # カンマ区切りで結合
    return ",".join(all_tags)


def update_video_title(message_id: int, title: str, user_id: int) -> bool:
    """
    動画のタイトルをmetaテーブルに保存

    Args:
        message_id: メッセージID
        title: タイトル
        user_id: 更新者のユーザーID

    Returns:
        更新成功時True、失敗時False
    """
    try:
        # 既存レコードの確認
        check_sql = "SELECT id FROM meta WHERE id = %s"
        existing = run_aidb_query(check_sql, (message_id,), fetch="one")

        if existing:
            # UPDATE
            update_sql = """
                UPDATE meta
                SET title = %s
                WHERE id = %s
            """
            run_aidb_query(update_sql, (title, message_id), commit=True)
        else:
            # INSERT - 必須カラムを含める
            insert_sql = """
                INSERT INTO meta (id, title, tag, description, type, filename, width, height, channelid)
                VALUES (%s, %s, '[]', '', '', '', 0, 0, 0)
            """
            run_aidb_query(insert_sql, (message_id, title), commit=True)

        return True
    except Exception as e:
        print(f"Error updating video title: {e}")
        return False


def update_video_tags(message_id: int, tags: list[str], user_id: int) -> bool:
    """
    動画のタグをmetaテーブルに保存

    Args:
        message_id: メッセージID
        tags: タグのリスト
        user_id: 更新者のユーザーID

    Returns:
        更新成功時True、失敗時False
    """
    try:
        import json

        # 既存レコードの確認
        check_sql = "SELECT tag FROM meta WHERE id = %s"
        existing = run_aidb_query(check_sql, (message_id,), fetch="one")

        if existing:
            # 既存タグとマージ
            existing_tags = []
            if existing[0]:
                try:
                    existing_tags = json.loads(existing[0])
                    if not isinstance(existing_tags, list):
                        existing_tags = []
                except Exception:
                    existing_tags = []

            # 新しいタグを追加（重複排除）
            merged_tags = list(set(existing_tags + tags))
            tags_json = json.dumps(merged_tags, ensure_ascii=False)

            # UPDATE
            update_sql = """
                UPDATE meta
                SET tag = %s
                WHERE id = %s
            """
            run_aidb_query(update_sql, (tags_json, message_id), commit=True)
        else:
            # INSERT - 必須カラムを含める
            tags_json = json.dumps(tags, ensure_ascii=False)
            insert_sql = """
                INSERT INTO meta (id, title, tag, description, type, filename, width, height, channelid)
                VALUES (%s, '', %s, '', '', '', 0, 0, 0)
            """
            run_aidb_query(insert_sql, (message_id, tags_json), commit=True)

        return True
    except Exception as e:
        print(f"Error updating video tags: {e}")
        return False
