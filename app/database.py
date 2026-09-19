from __future__ import annotations

import math
from datetime import datetime, timedelta

import aiosqlite

from app.utils import DEFAULT_LANG, MOSCOW_TZ, now_iso, normalize_lang


ANSWER_CARD_SELECT = '''
    SELECT
        tm.id AS message_id,
        tm.ticket_id,
        tm.sender_type AS answer_sender_type,
        tm.sender_id AS admin_id,
        tm.text AS answer_text,
        tm.content_type,
        tm.file_id AS answer_file_id,
        tm.created_at AS answered_at,
        tm.publication_status,
        tm.published_at,
        au.username AS admin_username,
        au.full_name AS admin_full_name,
        t.user_id,
        t.username AS user_username,
        t.full_name AS user_full_name,
        t.category,
        t.status,
        t.language,
        t.question_language,
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
        ) AS question_file_id,
        (
            SELECT COUNT(*)
            FROM ticket_messages numbered
            WHERE numbered.ticket_id = tm.ticket_id
              AND numbered.sender_type IN ('admin', 'sheikh')
              AND numbered.id <= tm.id
        ) AS answer_number,
        (
            SELECT COUNT(*)
            FROM ticket_messages answer_count
            WHERE answer_count.ticket_id = tm.ticket_id
              AND answer_count.sender_type IN ('admin', 'sheikh')
        ) AS answer_count,
        (
            SELECT COUNT(*)
            FROM ticket_messages pending_count
            WHERE pending_count.ticket_id = tm.ticket_id
              AND pending_count.sender_type IN ('admin', 'sheikh')
              AND pending_count.publication_status = 'pending'
        ) AS pending_answer_count,
        (
            SELECT COUNT(*)
            FROM ticket_messages published_count
            WHERE published_count.ticket_id = tm.ticket_id
              AND published_count.sender_type IN ('admin', 'sheikh')
              AND published_count.publication_status = 'published'
        ) AS published_answer_count
    FROM ticket_messages tm
    JOIN tickets t ON t.id = tm.ticket_id
    LEFT JOIN users au ON au.user_id = tm.sender_id
'''


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
            await self._ensure_column(db, 'tickets', 'question_language', "TEXT NOT NULL DEFAULT 'ru'")
            await self._ensure_column(db, 'ticket_messages', 'publication_status', 'TEXT')
            await self._ensure_column(db, 'ticket_messages', 'published_at', 'TEXT')
            await db.execute(
                '''
                UPDATE ticket_messages AS answer
                SET publication_status = CASE
                    WHEN EXISTS (
                        SELECT 1
                        FROM tickets published_ticket
                        WHERE published_ticket.id = answer.ticket_id
                          AND published_ticket.status = 'published'
                    )
                    AND answer.id = (
                        SELECT MAX(latest.id)
                        FROM ticket_messages latest
                        WHERE latest.ticket_id = answer.ticket_id
                          AND latest.sender_type IN ('admin', 'sheikh')
                    ) THEN 'published'
                    ELSE 'pending'
                END
                WHERE answer.sender_type IN ('admin', 'sheikh')
                  AND answer.publication_status IS NULL
                '''
            )
            await db.execute(
                '''
                UPDATE tickets
                SET status = 'answered'
                WHERE status != 'closed'
                  AND EXISTS (
                      SELECT 1
                      FROM ticket_messages pending_answer
                      WHERE pending_answer.ticket_id = tickets.id
                        AND pending_answer.sender_type IN ('admin', 'sheikh')
                        AND pending_answer.publication_status = 'pending'
                  )
                '''
            )
            await db.execute(
                '''
                UPDATE tickets
                SET status = 'published'
                WHERE status != 'closed'
                  AND EXISTS (
                      SELECT 1
                      FROM ticket_messages published_answer
                      WHERE published_answer.ticket_id = tickets.id
                        AND published_answer.sender_type IN ('admin', 'sheikh')
                        AND published_answer.publication_status = 'published'
                  )
                  AND NOT EXISTS (
                      SELECT 1
                      FROM ticket_messages pending_answer
                      WHERE pending_answer.ticket_id = tickets.id
                        AND pending_answer.sender_type IN ('admin', 'sheikh')
                        AND pending_answer.publication_status = 'pending'
                  )
                '''
            )
            await db.execute(
                '''
                CREATE TABLE IF NOT EXISTS user_blocks (
                    user_id INTEGER PRIMARY KEY,
                    blocked_until TEXT,
                    blocked_by INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                '''
            )
            await db.execute(
                '''
                CREATE TABLE IF NOT EXISTS question_rate_limits (
                    user_id INTEGER PRIMARY KEY,
                    last_submitted_at TEXT NOT NULL
                )
                '''
            )
            await db.execute(
                '''
                CREATE TABLE IF NOT EXISTS staff_notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(ticket_id, chat_id, message_id)
                )
                '''
            )
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

    async def create_ticket(
        self,
        *,
        user_id: int,
        username: str | None,
        full_name: str,
        category: str,
        language: str = DEFAULT_LANG,
        question_language: str = 'ru',
    ) -> int:
        ts = now_iso()
        lang = normalize_lang(language)
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                '''
                INSERT INTO tickets(
                    user_id, username, full_name, language, question_language,
                    category, status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?)
                ''',
                (user_id, username, full_name, lang, question_language, category, ts, ts),
            )
            await db.commit()
            return int(cursor.lastrowid)

    async def create_ticket_with_cooldown(
        self,
        *,
        user_id: int,
        username: str | None,
        full_name: str,
        category: str,
        language: str = DEFAULT_LANG,
        question_language: str = 'ru',
        interval_seconds: int = 3600,
    ) -> tuple[int | None, int]:
        """Atomically create a ticket or return seconds left in the cooldown."""
        now = datetime.now(MOSCOW_TZ)
        ts = now.isoformat(timespec='seconds')
        lang = normalize_lang(language)
        async with aiosqlite.connect(self.path) as db:
            await db.execute('BEGIN IMMEDIATE')
            cursor = await db.execute(
                '''
                SELECT COALESCE(
                    (SELECT last_submitted_at FROM question_rate_limits WHERE user_id = ?),
                    (SELECT MAX(created_at) FROM tickets WHERE user_id = ?)
                )
                ''',
                (user_id, user_id),
            )
            row = await cursor.fetchone()
            last_submitted_at = row[0] if row else None
            if last_submitted_at:
                try:
                    elapsed = (now - datetime.fromisoformat(last_submitted_at)).total_seconds()
                except (TypeError, ValueError):
                    elapsed = interval_seconds
                remaining = max(0, math.ceil(interval_seconds - elapsed))
                if remaining > 0:
                    await db.rollback()
                    return None, remaining

            cursor = await db.execute(
                '''
                INSERT INTO tickets(
                    user_id, username, full_name, language, question_language,
                    category, status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?)
                ''',
                (user_id, username, full_name, lang, question_language, category, ts, ts),
            )
            await db.execute(
                '''
                INSERT INTO question_rate_limits(user_id, last_submitted_at)
                VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET last_submitted_at = excluded.last_submitted_at
                ''',
                (user_id, ts),
            )
            await db.commit()
            return int(cursor.lastrowid), 0

    async def question_cooldown_seconds(self, user_id: int, interval_seconds: int = 3600) -> int:
        now = datetime.now(MOSCOW_TZ)
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                '''
                SELECT COALESCE(
                    (SELECT last_submitted_at FROM question_rate_limits WHERE user_id = ?),
                    (SELECT MAX(created_at) FROM tickets WHERE user_id = ?)
                )
                ''',
                (user_id, user_id),
            )
            row = await cursor.fetchone()
        if not row or not row[0]:
            return 0
        try:
            elapsed = (now - datetime.fromisoformat(row[0])).total_seconds()
        except (TypeError, ValueError):
            return 0
        return max(0, math.ceil(interval_seconds - elapsed))

    async def block_user(self, user_id: int, *, blocked_by: int, duration_seconds: int | None) -> dict:
        now = datetime.now(MOSCOW_TZ)
        ts = now.isoformat(timespec='seconds')
        blocked_until = None
        if duration_seconds is not None:
            blocked_until = (now + timedelta(seconds=duration_seconds)).isoformat(timespec='seconds')
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                '''
                INSERT INTO user_blocks(user_id, blocked_until, blocked_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    blocked_until = excluded.blocked_until,
                    blocked_by = excluded.blocked_by,
                    updated_at = excluded.updated_at
                ''',
                (user_id, blocked_until, blocked_by, ts, ts),
            )
            await db.commit()
        return {'user_id': user_id, 'blocked_until': blocked_until, 'blocked_by': blocked_by}

    async def get_active_block(self, user_id: int) -> dict | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('SELECT * FROM user_blocks WHERE user_id = ?', (user_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            result = dict(row)
            blocked_until = result.get('blocked_until')
            if blocked_until:
                try:
                    expired = datetime.fromisoformat(blocked_until) <= datetime.now(MOSCOW_TZ)
                except (TypeError, ValueError):
                    expired = True
                if expired:
                    await db.execute('DELETE FROM user_blocks WHERE user_id = ?', (user_id,))
                    await db.commit()
                    return None
            return result

    async def unblock_user(self, user_id: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute('DELETE FROM user_blocks WHERE user_id = ?', (user_id,))
            await db.commit()

    async def list_active_blocks(self) -> list[dict]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                '''
                SELECT b.*, u.username, u.full_name
                FROM user_blocks b
                LEFT JOIN users u ON u.user_id = b.user_id
                ORDER BY b.updated_at DESC
                '''
            )
            rows = [dict(row) for row in await cursor.fetchall()]
        active: list[dict] = []
        for row in rows:
            block = await self.get_active_block(int(row['user_id']))
            if block:
                row.update(block)
                active.append(row)
        return active

    async def add_staff_notification(self, ticket_id: int, chat_id: int, message_id: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                '''
                INSERT OR IGNORE INTO staff_notifications(ticket_id, chat_id, message_id, created_at)
                VALUES (?, ?, ?, ?)
                ''',
                (ticket_id, chat_id, message_id, now_iso()),
            )
            await db.commit()

    async def list_staff_notifications(self, ticket_id: int) -> list[dict]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                'SELECT chat_id, message_id FROM staff_notifications WHERE ticket_id = ? ORDER BY id',
                (ticket_id,),
            )
            return [dict(row) for row in await cursor.fetchall()]

    async def delete_ticket(self, ticket_id: int) -> bool:
        async with aiosqlite.connect(self.path) as db:
            await db.execute('BEGIN IMMEDIATE')
            cursor = await db.execute('SELECT 1 FROM tickets WHERE id = ?', (ticket_id,))
            exists = await cursor.fetchone()
            if not exists:
                await db.rollback()
                return False
            await db.execute('DELETE FROM staff_notifications WHERE ticket_id = ?', (ticket_id,))
            await db.execute('DELETE FROM ticket_messages WHERE ticket_id = ?', (ticket_id,))
            await db.execute('DELETE FROM tickets WHERE id = ?', (ticket_id,))
            await db.commit()
            return True

    async def add_message(
        self,
        *,
        ticket_id: int,
        sender_type: str,
        sender_id: int,
        text: str | None,
        content_type: str | None,
        file_id: str | None = None,
        publication_status: str | None = None,
    ) -> int:
        ts = now_iso()
        if sender_type not in {'admin', 'sheikh'}:
            publication_status = None
        elif publication_status is None:
            publication_status = 'pending'
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                '''
                INSERT INTO ticket_messages(
                    ticket_id, sender_type, sender_id, text, content_type, file_id,
                    publication_status, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (ticket_id, sender_type, sender_id, text, content_type, file_id, publication_status, ts),
            )
            await db.execute('UPDATE tickets SET updated_at = ? WHERE id = ?', (ts, ticket_id))
            await db.commit()
            return int(cursor.lastrowid)

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
            if status == 'published':
                await db.execute(
                    '''
                    UPDATE ticket_messages
                    SET publication_status = 'published', published_at = COALESCE(published_at, ?)
                    WHERE ticket_id = ?
                      AND sender_type IN ('admin', 'sheikh')
                      AND publication_status != 'published'
                    ''',
                    (ts, ticket_id),
                )
            await db.execute(
                'UPDATE tickets SET status = ?, updated_at = ?, closed_at = COALESCE(?, closed_at) WHERE id = ?',
                (status, ts, closed_at, ticket_id),
            )
            await db.commit()

    async def mark_answer_published(self, message_id: int) -> bool:
        """Mark one answer as published and synchronize its ticket status."""
        ts = now_iso()
        async with aiosqlite.connect(self.path) as db:
            await db.execute('BEGIN IMMEDIATE')
            cursor = await db.execute(
                '''
                SELECT ticket_id
                FROM ticket_messages
                WHERE id = ? AND sender_type IN ('admin', 'sheikh')
                ''',
                (message_id,),
            )
            row = await cursor.fetchone()
            if not row:
                await db.rollback()
                return False
            ticket_id = int(row[0])
            await db.execute(
                '''
                UPDATE ticket_messages
                SET publication_status = 'published', published_at = COALESCE(published_at, ?)
                WHERE id = ?
                ''',
                (ts, message_id),
            )
            await self._sync_ticket_publication_status(db, ticket_id, ts)
            await db.commit()
            return True

    async def _sync_ticket_publication_status(
        self,
        db: aiosqlite.Connection,
        ticket_id: int,
        ts: str | None = None,
    ) -> None:
        cursor = await db.execute('SELECT status FROM tickets WHERE id = ?', (ticket_id,))
        ticket = await cursor.fetchone()
        if not ticket or ticket[0] == 'closed':
            return
        cursor = await db.execute(
            '''
            SELECT
                COUNT(*),
                SUM(CASE WHEN publication_status = 'pending' THEN 1 ELSE 0 END),
                SUM(CASE WHEN publication_status = 'published' THEN 1 ELSE 0 END)
            FROM ticket_messages
            WHERE ticket_id = ? AND sender_type IN ('admin', 'sheikh')
            ''',
            (ticket_id,),
        )
        answer_count, pending_count, published_count = await cursor.fetchone()
        if not answer_count:
            status = 'open'
        elif pending_count:
            status = 'answered'
        elif published_count:
            status = 'published'
        else:
            status = 'answered'
        await db.execute(
            'UPDATE tickets SET status = ?, updated_at = ? WHERE id = ?',
            (status, ts or now_iso(), ticket_id),
        )

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

    async def list_tickets_by_statuses(self, *, statuses: tuple[str, ...], limit: int = 10) -> list[dict]:
        if not statuses:
            return []
        placeholders = ', '.join('?' for _ in statuses)
        query = f'''
            SELECT * FROM tickets
            WHERE status IN ({placeholders})
            ORDER BY updated_at DESC
            LIMIT ?
        '''
        params: list[object] = [*statuses, limit]
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
                ANSWER_CARD_SELECT + '''
                    WHERE tm.sender_type IN ('admin', 'sheikh')
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
                ANSWER_CARD_SELECT + '''
                    WHERE tm.sender_type IN ('admin', 'sheikh') AND tm.id = ?
                    LIMIT 1
                ''',
                (message_id,),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def count_admin_answers(self) -> int:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM ticket_messages WHERE sender_type IN ('admin', 'sheikh')")
            row = await cursor.fetchone()
            return int(row[0] if row else 0)

    async def list_sheikh_answers_for_publication(self, *, status: str = 'answered', limit: int = 10, offset: int = 0) -> list[dict]:
        publication_status = 'pending' if status == 'answered' else status
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                ANSWER_CARD_SELECT + '''
                    WHERE tm.sender_type IN ('admin', 'sheikh')
                      AND tm.publication_status = ?
                      AND (? != 'pending' OR t.status != 'closed')
                    ORDER BY tm.id DESC
                    LIMIT ? OFFSET ?
                ''',
                (publication_status, publication_status, limit, offset),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def count_sheikh_answers_for_publication(self, *, status: str = 'answered') -> int:
        publication_status = 'pending' if status == 'answered' else status
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                '''
                SELECT COUNT(*)
                FROM ticket_messages tm
                JOIN tickets t ON t.id = tm.ticket_id
                WHERE tm.sender_type IN ('admin', 'sheikh')
                  AND tm.publication_status = ?
                  AND (? != 'pending' OR t.status != 'closed')
                ''',
                (publication_status, publication_status),
            )
            row = await cursor.fetchone()
            return int(row[0] if row else 0)

    async def list_ticket_answers_for_publication(
        self,
        ticket_id: int,
        *,
        status: str = 'answered',
    ) -> list[dict]:
        publication_status = 'pending' if status == 'answered' else status
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                ANSWER_CARD_SELECT + '''
                    WHERE tm.sender_type IN ('admin', 'sheikh')
                      AND tm.ticket_id = ?
                      AND tm.publication_status = ?
                    ORDER BY tm.id ASC
                ''',
                (ticket_id, publication_status),
            )
            return [dict(row) for row in await cursor.fetchall()]

    async def get_sheikh_answer_for_publication(self, message_id: int) -> dict | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                ANSWER_CARD_SELECT + '''
                    WHERE tm.sender_type IN ('admin', 'sheikh') AND tm.id = ?
                    LIMIT 1
                ''',
                (message_id,),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def stats(self) -> dict[str, int]:
        async with aiosqlite.connect(self.path) as db:
            result: dict[str, int] = {}
            for status in ('open', 'answered', 'published', 'closed'):
                cursor = await db.execute('SELECT COUNT(*) FROM tickets WHERE status = ?', (status,))
                result[status] = int((await cursor.fetchone())[0])
            cursor = await db.execute('SELECT COUNT(*) FROM tickets')
            result['all'] = int((await cursor.fetchone())[0])
            cursor = await db.execute(
                '''
                SELECT COUNT(*)
                FROM ticket_messages tm
                JOIN tickets t ON t.id = tm.ticket_id
                WHERE tm.sender_type IN ('admin', 'sheikh')
                  AND tm.publication_status = 'pending'
                  AND t.status != 'closed'
                '''
            )
            result['answers_pending'] = int((await cursor.fetchone())[0])
            cursor = await db.execute(
                "SELECT COUNT(*) FROM ticket_messages WHERE sender_type IN ('admin', 'sheikh') AND publication_status = 'published'"
            )
            result['answers_published'] = int((await cursor.fetchone())[0])
            return result
