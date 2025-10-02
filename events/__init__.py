"""
Discordイベントハンドラ
"""

from .ready import setup_ready_event
from .member import setup_member_events
from .guild import setup_guild_events
from .interaction import setup_interaction_events

__all__ = [
    "setup_ready_event",
    "setup_member_events",
    "setup_guild_events",
    "setup_interaction_events",
]


def setup_all_events(client):
    """
    すべてのイベントハンドラを登録
    
    Args:
        client: Discord Client インスタンス
    """
    setup_ready_event(client)
    setup_member_events(client)
    setup_guild_events(client)
    setup_interaction_events(client)
