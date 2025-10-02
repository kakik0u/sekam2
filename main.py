import asyncio
from bot import client, tree, setup_custom_dns
from database.connection import test_db_connection
from events import setup_all_events
from commands import setup_all_commands
import config


async def main():
    """
    エントリー関数
    """
    await setup_custom_dns()
    test_db_connection()
    setup_all_events(client)
    await setup_all_commands(tree, client)
    await client.start(config.TOKEN)


if __name__ == "__main__":
    asyncio.run(main())