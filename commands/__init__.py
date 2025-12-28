"""
コマンド登録モジュール
"""

from discord import Client, app_commands

from .admin import setup_admin_commands
from .graph import setup_graph_commands
from .misc import setup_misc_commands
from .morpheme import setup_morpheme_commands
from .ranking import setup_ranking_commands
from .reaction import setup_reaction_commands
from .rewind import setup_rewind_commands
from .settings import setup_settings_commands
from .sora import setup_sora_commands
from .test import setup_test_commands
from .vote import setup_vote_commands

__all__ = [
    "setup_admin_commands",
    "setup_settings_commands",
    "setup_ranking_commands",
    "setup_reaction_commands",
    "setup_graph_commands",
    "setup_misc_commands",
    "setup_test_commands",
    "setup_sora_commands",
    "setup_morpheme_commands",
    "setup_vote_commands",
    "setup_rewind_commands",
    "setup_all_commands",
]


async def setup_all_commands(tree: app_commands.CommandTree, client: Client):
    """
    すべてのコマンドを登録

    Args:
        tree: Discord CommandTree インスタンス
        client: Discord Client インスタンス
    """
    await setup_admin_commands(tree, client)
    await setup_settings_commands(tree, client)
    await setup_ranking_commands(tree, client)
    await setup_reaction_commands(tree, client)
    await setup_graph_commands(tree, client)
    await setup_misc_commands(tree, client)
    await setup_test_commands(tree, client)
    await setup_sora_commands(tree, client)
    await setup_morpheme_commands(tree, client)
    await setup_vote_commands(tree, client)
    await setup_rewind_commands(tree, client)
