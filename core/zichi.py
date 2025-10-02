"""
自治(チャンネルブロック)機能
"""

import discord

from database.connection import run_db_query
from config import debug

def get_active_zichi(channel_id: int):
    """
    チャンネルの有効な自治設定を取得
    
    Args:
        channel_id (int): チャンネルID
    
    Returns:
        str | None: 自治理由、自治が無効または存在しない場合はNone
    """
    try:
        row = run_db_query(
            "SELECT reason FROM zichi WHERE channelid = %s AND valid = 1 ORDER BY id DESC LIMIT 1",
            (channel_id,),
            fetch="one"
        )
        return row[0] if row else None
    except Exception as e:
        if debug:
            print(f"zichi取得エラー: {e}")
        return None

async def enforce_zichi_block(ctx: discord.Interaction, cmdname: str) -> bool:
    """
    自治ブロック判定。ブロック時 True
    
    Args:
        ctx (discord.Interaction): コマンドのコンテキスト
        cmdname (str): コマンド名
    
    Returns:
        bool: ブロックした場合 True、ブロックしなかった場合 False
    """
    if cmdname == "/zichi":
        return False
    
    try:
        ch = getattr(ctx, 'channel', None)
        if not ch:
            return False
        
        reason = get_active_zichi(getattr(ch, 'id', 0))
        if reason:
            text = (
                f"このチャンネルでは次の理由からSEKAM2は使用できません。\n"
                f"理由:{reason}\n"
                f"解除するには管理者に連絡してください。"
            )
            if not ctx.response.is_done():
                await ctx.response.send_message(text, ephemeral=True)
            else:
                await ctx.followup.send(text, ephemeral=True)
            
            from .log import insert_command_log
            insert_command_log(ctx, cmdname, "DENY_ZICHI")
            return True
    except Exception as e:
        if debug:
            print(f"enforce_zichi_blockエラー: {e}")
    
    return False

def insert_zichi_request(channel_id: int, user_id: int, reason: str):
    """
    自治リクエストをzichiテーブルに挿入
    
    Args:
        channel_id (int): チャンネルID
        user_id (int): リクエストしたユーザーのID
        reason (str): 自治理由
    
    Returns:
        bool: 成功時 True、失敗時 False
    """
    try:
        run_db_query(
            "INSERT INTO zichi (channelid, userid, time, reason, valid) VALUES (%s, %s, NOW(), %s, 0)",
            (channel_id, user_id, reason),
            commit=True
        )
        return True
    except Exception as e:
        if debug:
            print(f"zichi挿入エラー: {e}")
        return False
