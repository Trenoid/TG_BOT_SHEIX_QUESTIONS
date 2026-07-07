from __future__ import annotations

import aiosqlite

from app.utils import DEFAULT_LANG, now_iso, normalize_lang


class Database:
    def __init__(self, path: str) -> None:
        self.path = path

    async def init(self) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute('PRAGMA journal_mode=WAL')
            await db.execute('PRAGMA foreign_keys=ON')
            await db.execute(
                '''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    language TEXT NOT NULL DEFAULT 'ru',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                '''
            )
            await db.execute(
                '''
                CREATE TABLE IF NOT EXISTS tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    full_name TEXT,
                    language TEXT NOT NULL DEFAULT 'ru',
                    category TEXT NOT NULL DEFAULT 'other',
                    status TEXT NOT NULL DEFAULT 'open',
                    priority TEXT NOT NULL DEFAULT 'normal',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    closed_at TEXT
                )
                '''
            )
            await db.execute(
                '''
                CREATE TABLE IF NOT EXISTS ticket_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id INTEGER NOT NULL,
                    sender_type TEXT NOT NULL,
                    sender_id INTEGER NOT NULL,
                    text TEXT,
                    content_type TEXT,
                    file_id TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
                )
                '''
            )
            await self._ensure_column(db, 'tickets', 'language', "TEXT NOT NULL DEFAULT 'ru'")
            await db.commit()

    async def _ensure_column(self, db: aiosqlite.Connection, table: str, column: str, definition: str) -> None:
        cursor = await db.execute(f'PRAGMA table_info({table})')
        rows = await cursor.fetchall()
        if column not in {row[1] for row in rows}:
            await db.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')

    async def upsert_user(self, *, user_id: int, username: str | None, full_name: str, language: str | None = None) -> None:
        ts = now_iso()
        lang = normalize_lang(language)
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                '''
                INSERT INTO users(user_id, username, full_name, language, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    full_name = excluded.full_name,
                    language = COALESCE(?, users.language),
                    updated_at = excluded.updated_at
                ''',
                (user_id, username, full_name, lang, ts, ts, lang if language else None),
            )
            await db.commit()

    async def get_user_language(self, user_id: int) -> str:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute('SELECT language FROM users WHERE user_id = ?', (user_id,))
            row = await cursor.fetchone()
            return normalize_lang(row[0] if row else DEFAULT_LANG)

    async def set_user_language(self, user_id: int, language: str) -> None:
        ts = now_iso()
        lang = normalize_lang(language)
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                '''
                INSERT INTO users(user_id, language, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET language = excluded.language, updated_at = excluded.updated_at
                ''',
                (user_id, lang, ts, ts),
            )
            await db.commit()

    async def create_ticket(self, *, user_id: int, username: str | None, full_name: str, category: str, language: str = DEFAULT_LANG) -> int:
        ts = now_iso()
        lang = normalize_lang(language)
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                '''
                INSERT INTO tickets(user_id, username, full_name, language, category, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'open', ?, ?)
                ''',
                (user_id, username, full_name, lang, category, ts, ts),
            )
            await db.commit()
            return int(cursor.lastrowid)

    async def add_message(
        self,
        *,
        ticket_id: int,
        sender_type: str,
        sender_id: int,
        text: str | None,
        content_type: str | None,
        file_id: str | None = None,
    ) -> None:
        ts = now_iso()
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                '''
                INSERT INTO ticket_messages(ticket_id, sender_type, sender_id, text, content_type, file_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''',
                (ticket_id, sender_type, sender_id, text, content_type, file_id, ts),
            )
            await db.execute('UPDATE tickets SET updated_at = ? WHERE id = ?', (ts, ticket_id))
            await db.commit()

    async def get_ticket(self, ticket_id: int) -> dict | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def set_status(self, ticket_id: int, status: str) -> None:
        ts = now_iso()
        closed_at = ts if status == 'closed' else None
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                'UPDATE tickets SET status = ?, updated_at = ?, closed_at = COALESCE(?, closed_at) WHERE id = ?',
                (status, ts, closed_at, ticket_id),
            )
            await db.commit()

    async def list_tickets(self, *, status: str | None = None, user_id: int | None = None, limit: int = 10) -> list[dict]:
        query = 'SELECT * FROM tickets'
        params: list[object] = []
        conditions: list[str] = []
        if status:
            conditions.append('status = ?')
            params.append(status)
        if user_id:
            conditions.append('user_id = ?')
            params.append(user_id)
        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)
        query += ' ORDER BY updated_at DESC LIMIT ?'
        params.append(limit)

        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_last_messages(self, ticket_id: int, limit: int = 5) -> list[dict]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                '''
                SELECT * FROM ticket_messages
                WHERE ticket_id = ?
                ORDER BY id DESC
                LIMIT ?
                ''',
                (ticket_id, limit),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in reversed(rows)]



    async def get_messages_with_senders(self, ticket_id: int, limit: int = 20) -> list[dict]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                '''
                SELECT
                    tm.*,
                    u.username AS sender_username,
                    u.full_name AS sender_full_name
                FROM ticket_messages tm
                LEFT JOIN users u ON u.user_id = tm.sender_id
                WHERE tm.ticket_id = ?
                ORDER BY tm.id DESC
                LIMIT ?
                ''',
                (ticket_id, limit),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in reversed(rows)]

    async def list_admin_answers(self, limit: int = 20, offset: int = 0) -> list[dict]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                '''
                SELECT
                    tm.id AS message_id,
                    tm.ticket_id,
                    tm.sender_id AS admin_id,
                    tm.text AS answer_text,
                    tm.content_type,
                    tm.file_id AS answer_file_id,
                    tm.created_at AS answered_at,
                    au.username AS admin_username,
                    au.full_name AS admin_full_name,
                    t.user_id,
                    t.username AS user_username,
                    t.full_name AS user_full_name,
                    t.category,
                    t.status,
                    t.language,
                    t.created_at AS question_created_at,
                    t.updated_at AS ticket_updated_at,
                    (
                        SELECT qm.text
                        FROM ticket_messages qm
                        WHERE qm.ticket_id = t.id AND qm.sender_type = 'user'
                        ORDER BY qm.id ASC
                        LIMIT 1
                    ) AS question_text,
                    (
                        SELECT qm.content_type
                        FROM ticket_messages qm
                        WHERE qm.ticket_id = t.id AND qm.sender_type = 'user'
                        ORDER BY qm.id ASC
                        LIMIT 1
                    ) AS question_content_type,
                    (
                        SELECT qm.file_id
                        FROM ticket_messages qm
                        WHERE qm.ticket_id = t.id AND qm.sender_type = 'user'
                        ORDER BY qm.id ASC
                        LIMIT 1
                    ) AS question_file_id
                FROM ticket_messages tm
                JOIN tickets t ON t.id = tm.ticket_id
                LEFT JOIN users au ON au.user_id = tm.sender_id
                WHERE tm.sender_type = 'admin'
                ORDER BY tm.id DESC
                LIMIT ? OFFSET ?
                ''',
                (limit, offset),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_admin_answer(self, message_id: int) -> dict | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                '''
                SELECT
                    tm.id AS message_id,
                    tm.ticket_id,
                    tm.sender_id AS admin_id,
                    tm.text AS answer_text,
                    tm.content_type,
                    tm.file_id AS answer_file_id,
                    tm.created_at AS answered_at,
                    au.username AS admin_username,
                    au.full_name AS admin_full_name,
                    t.user_id,
                    t.username AS user_username,
                    t.full_name AS user_full_name,
                    t.category,
                    t.status,
                    t.language,
                    t.created_at AS question_created_at,
                    t.updated_at AS ticket_updated_at,
                    (
                        SELECT qm.text
                        FROM ticket_messages qm
                        WHERE qm.ticket_id = t.id AND qm.sender_type = 'user'
                        ORDER BY qm.id ASC
                        LIMIT 1
                    ) AS question_text,
                    (
                        SELECT qm.content_type
                        FROM ticket_messages qm
                        WHERE qm.ticket_id = t.id AND qm.sender_type = 'user'
                        ORDER BY qm.id ASC
                        LIMIT 1
                    ) AS question_content_type,
                    (
                        SELECT qm.file_id
                        FROM ticket_messages qm
                        WHERE qm.ticket_id = t.id AND qm.sender_type = 'user'
                        ORDER BY qm.id ASC
                        LIMIT 1
                    ) AS question_file_id
                FROM ticket_messages tm
                JOIN tickets t ON t.id = tm.ticket_id
                LEFT JOIN users au ON au.user_id = tm.sender_id
                WHERE tm.sender_type = 'admin' AND tm.id = ?
                LIMIT 1
                ''',
                (message_id,),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def count_admin_answers(self) -> int:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM ticket_messages WHERE sender_type = 'admin'")
            row = await cursor.fetchone()
            return int(row[0] if row else 0)

    async def stats(self) -> dict[str, int]:
        async with aiosqlite.connect(self.path) as db:
            result: dict[str, int] = {}
            for status in ('open', 'answered', 'closed'):
                cursor = await db.execute('SELECT COUNT(*) FROM tickets WHERE status = ?', (status,))
                result[status] = int((await cursor.fetchone())[0])
            cursor = await db.execute('SELECT COUNT(*) FROM tickets')
            result['all'] = int((await cursor.fetchone())[0])
            return result
