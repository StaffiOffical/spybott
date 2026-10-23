import aiosqlite
from datetime import datetime, timedelta
from config import RETENTION_DAYS

DB = "spy.db"

async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_connection_id TEXT,
                chat_id INTEGER,
                message_id INTEGER,
                from_user_id INTEGER,
                from_name TEXT,
                content_type TEXT,
                text TEXT,
                file_id TEXT,
                caption TEXT,
                created_at TEXT,
                UNIQUE(chat_id, message_id)
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_msg ON messages(chat_id, message_id)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_created ON messages(created_at)
        """)
        await db.commit()


async def save_message(
    business_connection_id: str,
    chat_id: int,
    message_id: int,
    from_user_id: int | None,
    from_name: str,
    content_type: str,
    text: str | None = None,
    file_id: str | None = None,
    caption: str | None = None,
):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO messages
            (business_connection_id, chat_id, message_id, from_user_id, from_name,
             content_type, text, file_id, caption, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                business_connection_id,
                chat_id,
                message_id,
                from_user_id,
                from_name,
                content_type,
                text,
                file_id,
                caption,
                datetime.utcnow().isoformat(),
            ),
        )
        await db.commit()


async def get_messages(chat_id: int, message_ids: list[int]) -> list[dict]:
    if not message_ids:
        return []
    placeholders = ",".join("?" * len(message_ids))
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            f"""
            SELECT * FROM messages
            WHERE chat_id = ? AND message_id IN ({placeholders})
            """,
            (chat_id, *message_ids),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def cleanup_old():
    """Удаляем всё старше RETENTION_DAYS"""
    cutoff = (datetime.utcnow() - timedelta(days=RETENTION_DAYS)).isoformat()
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("DELETE FROM messages WHERE created_at < ?", (cutoff,))
        deleted = cur.rowcount
        await db.commit()
        return deleted
