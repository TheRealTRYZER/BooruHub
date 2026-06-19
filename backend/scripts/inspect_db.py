import asyncio
import sys
import os

# Add parent directory to sys.path to resolve 'app' imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import async_session
from sqlalchemy import text

async def main():
    async with async_session() as session:
        # Check mappings with correct table name
        mappings = await session.execute(text(
            "SELECT id, user_id, unitag, danbooru_tags, e621_tags, rule34_tags FROM user_tag_mappings"
        ))
        print("--- Tag Mappings ---")
        for m in mappings.fetchall():
            print(f"ID={m.id}, UserID={m.user_id}, Unitag='{m.unitag}', Danbooru='{m.danbooru_tags}', e621='{m.e621_tags}', rule34='{m.rule34_tags}'")

if __name__ == "__main__":
    asyncio.run(main())
