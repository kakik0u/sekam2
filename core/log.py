"""
ログ記録機能
"""

import traceback

import discord

from config import debug
from database.connection import run_db_query


def insert_log(member, result: str, error: str | None = None) -> bool:
    """
    logテーブルに1件書き込みます。
    展開は関数内で実施:
      - userid: member.id (なければ 0)
      - username: member.display_name or member.name or str(member)
      - server: member.guild.name (なければ 空文字)
      - serverid: member.guild.id (なければ 0)
      - time: NOW()(DB側で現在時刻)
    成功時 True、失敗時 False を返す。

    Args:
        member: Discord Member オブジェクト
        result (str): 処理結果
        error (str | None, optional): エラーメッセージ。デフォルトはNone。

    Returns:
        bool: 成功時 True、失敗時 False
    """
    try:
        uid = int(getattr(member, "id", 0) or 0)
    except Exception:
        uid = 0

    username = (
        getattr(member, "display_name", None)
        or getattr(member, "name", None)
        or str(member)
    )

    guild = getattr(member, "guild", None)
    server_name = getattr(guild, "name", "") if guild else ""

    try:
        server_id = int(getattr(guild, "id", 0) or 0) if guild else 0
    except Exception:
        server_id = 0

    err_text = "" if error is None else str(error)

    try:
        run_db_query(
            "INSERT INTO log (userid, username, time, server, serverid, error, result) "
            "VALUES (%s, %s, NOW(), %s, %s, %s, %s)",
            (uid, username, server_name, server_id, err_text, result),
            commit=True,
        )
        return True
    except Exception as e:
        if debug:
            print(f"データベースエラー(insert_log): {e}")
        return False


def insert_command_log(ctx: discord.Interaction, command: str, result: str) -> None:
    """
    commandlogテーブルにコマンド実行ログを記録

    Args:
        ctx (discord.Interaction): コマンドのコンテキスト
        command (str): コマンド名
        result (str): 実行結果
    """
    try:
        u = getattr(ctx, "user", None) or getattr(ctx, "author", None)
        uid = int(getattr(u, "id", 0) or 0)
        uname = getattr(u, "display_name", None) or getattr(u, "name", None) or str(u)

        g = getattr(ctx, "guild", None)
        gid = int(getattr(g, "id", 0) or 0) if g else 0
        gname = getattr(g, "name", "") if g else ""
        channel = getattr(ctx, "channel", None)
        channel_id = int(getattr(channel, "id", 0) or 0) if channel else 0

        run_db_query(
            "INSERT INTO commandlog (userid, user, time, command, result, serverid, server, channelid) "
            "VALUES (%s, %s, NOW(), %s, %s, %s, %s, %s)",
            (uid, uname, command, result, gid, gname, channel_id),
            commit=True,
        )
    except Exception as e:
        if debug:
            print(f"commandlog挿入エラー: {e}")


async def handle_command_error(
    ctx: discord.Interaction,
    command: str,
    error: Exception,
    user_message: str | None = None,
) -> None:
    """
    コマンド実行時のエラーを統一的に処理する

    Args:
        ctx: Discord Interaction コンテキスト
        command: コマンド名
        error: 発生した例外
        user_message: ユーザーに表示するカスタムメッセージ（Noneの場合はデフォルト）
    """
    if debug:
        print(f"コマンドエラー ({command}): {error}")
        traceback.print_exc()

    error_type = type(error).__name__
    insert_command_log(ctx, command, f"ERROR:{error_type}:{str(error)[:100]}")

    if user_message is None:
        if "MySQLdb" in error_type or "Database" in error_type:
            user_message = "データベースへの接続に失敗しました。しばらく待ってから再度お試しください。"
        elif "Timeout" in error_type or "timeout" in str(error).lower():
            user_message = (
                "処理がタイムアウトしました。時間をおいてから再度お試しください。"
            )
        elif "Permission" in error_type or "Forbidden" in error_type:
            user_message = (
                "必要な権限がありません。サーバー管理者にお問い合わせください。"
            )
        else:
            user_message = (
                "エラーが発生しました。しばらく待ってから再度お試しください。"
            )

    try:
        if not ctx.response.is_done():
            await ctx.response.send_message(user_message, ephemeral=True)
        else:
            await ctx.followup.send(user_message, ephemeral=True)
    except Exception as send_error:
        if debug:
            print(f"エラーメッセージ送信失敗: {send_error}")


def get_error_summary(error: Exception) -> str:
    """
    エラーの概要を取得する（ログ用）

    Args:
        error: 例外オブジェクト

    Returns:
        str: エラーの概要（最大200文字）
    """
    error_type = type(error).__name__
    error_msg = str(error)
    summary = f"{error_type}: {error_msg}"
    return summary[:200]
