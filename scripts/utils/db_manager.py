"""
SQLite 数据库管理器 — 语料存储与查询。

表结构：
- videos: 视频元数据
- utterances: 发言记录（说话人标注后）
- danmaku: 弹幕数据
- comments: 评论数据
- fts_utterances: 全文搜索虚拟表
"""

import sqlite3
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SCHEMA = """
-- 视频元数据
CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bvid TEXT UNIQUE NOT NULL,          -- B站 BV 号
    source TEXT,                         -- 来源平台 bilibili/youtube/podcast
    title TEXT,                          -- 视频标题
    description TEXT,                    -- 视频描述
    duration_sec REAL,                   -- 时长（秒）
    upload_date TEXT,                    -- 上传日期 YYYY-MM-DD
    category TEXT,                       -- 内容分类
    url TEXT,                            -- 视频URL
    metadata_json TEXT,                  -- 其他元数据 JSON
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 发言记录
CREATE TABLE IF NOT EXISTS utterances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER REFERENCES videos(id),
    speaker TEXT NOT NULL DEFAULT 'unknown',  -- 说话人：fengge/guest/caller/narrator/unknown
    text TEXT NOT NULL,                       -- 发言文本
    start_ts REAL,                            -- 开始时间（秒）
    end_ts REAL,                              -- 结束时间（秒）
    utterance_index INTEGER,                  -- 在该视频中的序号
    confidence REAL DEFAULT 1.0,              -- 说话人分类置信度
    source_type TEXT,                         -- subtitle/asr/manual
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 索引：按视频+说话人查询
CREATE INDEX IF NOT EXISTS idx_utterances_video ON utterances(video_id);
CREATE INDEX IF NOT EXISTS idx_utterances_speaker ON utterances(speaker);
CREATE INDEX IF NOT EXISTS idx_utterances_video_speaker ON utterances(video_id, speaker);

-- 弹幕
CREATE TABLE IF NOT EXISTS danmaku (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER REFERENCES videos(id),
    text TEXT NOT NULL,
    video_ts REAL,                        -- 弹幕在视频中的时间位置（秒）
    send_time TEXT,                       -- 发送时间
    mode INTEGER,                         -- 弹幕模式
    font_size INTEGER,                    -- 字号
    color INTEGER,                        -- 颜色
    metadata_json TEXT,                   -- 其他字段 JSON
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_danmaku_video ON danmaku(video_id);
CREATE INDEX IF NOT EXISTS idx_danmaku_ts ON danmaku(video_id, video_ts);

-- 评论
CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER REFERENCES videos(id),
    parent_id INTEGER,                    -- 父评论 ID（楼中楼）
    text TEXT NOT NULL,
    likes INTEGER DEFAULT 0,
    replies_count INTEGER DEFAULT 0,
    send_time TEXT,
    user_name TEXT,
    metadata_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_comments_video ON comments(video_id);

-- 全文搜索（FTS5）
CREATE VIRTUAL TABLE IF NOT EXISTS fts_utterances USING fts5(
    text,
    speaker,
    content='utterances',
    content_rowid='id'
);

-- 触发器：保持 FTS 索引同步
CREATE TRIGGER IF NOT EXISTS utterances_ai AFTER INSERT ON utterances BEGIN
    INSERT INTO fts_utterances(rowid, text, speaker) VALUES (new.id, new.text, new.speaker);
END;

CREATE TRIGGER IF NOT EXISTS utterances_ad AFTER DELETE ON utterances BEGIN
    INSERT INTO fts_utterances(fts_utterances, rowid, text, speaker) VALUES('delete', old.id, old.text, old.speaker);
END;

CREATE TRIGGER IF NOT EXISTS utterances_au AFTER UPDATE ON utterances BEGIN
    INSERT INTO fts_utterances(fts_utterances, rowid, text, speaker) VALUES('delete', old.id, old.text, old.speaker);
    INSERT INTO fts_utterances(rowid, text, speaker) VALUES (new.id, new.text, new.speaker);
END;
"""


class DatabaseManager:
    """语料数据库管理器。"""

    def __init__(self, db_path: str | Path):
        """
        Args:
            db_path: SQLite 数据库文件路径
        """
        self.db_path = Path(db_path)
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self):
        """连接数据库并初始化 schema。"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(SCHEMA)
        self._conn.commit()
        logger.info(f"数据库已连接: {self.db_path}")

    def close(self):
        """关闭数据库连接。"""
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("数据库未连接，请先调用 connect()")
        return self._conn

    # ---- 视频 ----

    def insert_video(self, video: dict) -> int:
        """插入视频记录（重复 bvid 则更新）。

        Returns:
            视频的数据库 ID
        """
        c = self.conn.execute(
            """INSERT INTO videos (bvid, source, title, description, duration_sec,
               upload_date, category, url, metadata_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(bvid) DO UPDATE SET
               title=excluded.title, description=excluded.description,
               duration_sec=excluded.duration_sec, url=excluded.url,
               metadata_json=excluded.metadata_json""",
            (
                video.get('bvid', ''),
                video.get('source', 'bilibili'),
                video.get('title', ''),
                video.get('description', ''),
                video.get('duration_sec', 0),
                video.get('upload_date', ''),
                video.get('category', ''),
                video.get('url', ''),
                json.dumps(video.get('metadata', {}), ensure_ascii=False),
            )
        )
        self.conn.commit()
        return c.lastrowid

    def get_video_by_bvid(self, bvid: str) -> Optional[dict]:
        """根据 BV 号获取视频信息。"""
        row = self.conn.execute(
            "SELECT * FROM videos WHERE bvid=?", (bvid,)
        ).fetchone()
        if row is None:
            return None
        return dict(row)

    def get_video_count(self) -> int:
        """获取视频总数。"""
        return self.conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]

    # ---- 发言 ----

    def insert_utterances(self, utterances: list[dict]):
        """批量插入发言记录。"""
        rows = [
            (
                u['video_id'],
                u.get('speaker', 'unknown'),
                u['text'],
                u.get('start_ts'),
                u.get('end_ts'),
                u.get('utterance_index', 0),
                u.get('confidence', 1.0),
                u.get('source_type', 'asr'),
            )
            for u in utterances
        ]
        self.conn.executemany(
            """INSERT INTO utterances (video_id, speaker, text, start_ts, end_ts,
               utterance_index, confidence, source_type)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            rows
        )
        self.conn.commit()

    def get_utterances_by_speaker(self, speaker: str, limit: int = None) -> list[dict]:
        """获取指定说话人的所有发言。"""
        query = "SELECT * FROM utterances WHERE speaker=? ORDER BY video_id, utterance_index"
        if limit:
            query += f" LIMIT {limit}"
        rows = self.conn.execute(query, (speaker,)).fetchall()
        return [dict(r) for r in rows]

    def get_fengge_texts(self) -> list[str]:
        """获取所有峰哥的发言文本。"""
        rows = self.conn.execute(
            "SELECT text FROM utterances WHERE speaker='fengge' ORDER BY video_id, utterance_index"
        ).fetchall()
        return [r['text'] for r in rows]

    def get_utterance_count(self, speaker: str = None) -> int:
        """获取发言总数（可选按说话人过滤）。"""
        if speaker:
            return self.conn.execute(
                "SELECT COUNT(*) FROM utterances WHERE speaker=?", (speaker,)
            ).fetchone()[0]
        return self.conn.execute("SELECT COUNT(*) FROM utterances").fetchone()[0]

    # ---- 弹幕 ----

    def insert_danmaku_batch(self, danmaku_list: list[dict]):
        """批量插入弹幕。"""
        rows = [
            (
                d['video_id'],
                d['text'],
                d.get('video_ts'),
                d.get('send_time', ''),
                d.get('mode', 1),
                d.get('font_size', 25),
                d.get('color', 16777215),
                json.dumps(d.get('metadata', {}), ensure_ascii=False),
            )
            for d in danmaku_list
        ]
        self.conn.executemany(
            """INSERT INTO danmaku (video_id, text, video_ts, send_time,
               mode, font_size, color, metadata_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            rows
        )
        self.conn.commit()

    def get_danmaku_by_timerange(self, video_id: int, start_ts: float, end_ts: float) -> list[dict]:
        """获取指定时间范围内的弹幕。"""
        rows = self.conn.execute(
            "SELECT * FROM danmaku WHERE video_id=? AND video_ts BETWEEN ? AND ? ORDER BY video_ts",
            (video_id, start_ts, end_ts)
        ).fetchall()
        return [dict(r) for r in rows]

    # ---- 评论 ----

    def insert_comments_batch(self, comments: list[dict]):
        """批量插入评论。"""
        rows = [
            (
                c['video_id'],
                c.get('parent_id'),
                c['text'],
                c.get('likes', 0),
                c.get('replies_count', 0),
                c.get('send_time', ''),
                c.get('user_name', ''),
                json.dumps(c.get('metadata', {}), ensure_ascii=False),
            )
            for c in comments
        ]
        self.conn.executemany(
            """INSERT INTO comments (video_id, parent_id, text, likes,
               replies_count, send_time, user_name, metadata_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            rows
        )
        self.conn.commit()

    # ---- FTS 全文搜索 ----

    def search(self, query: str, speaker: str = None, limit: int = 50) -> list[dict]:
        """全文搜索发言内容。

        Args:
            query: 搜索关键词
            speaker: 按说话人过滤
            limit: 返回上限

        Returns:
            匹配的发言列表
        """
        if speaker:
            sql = """SELECT u.* FROM utterances u
                     JOIN fts_utterances f ON u.id = f.rowid
                     WHERE fts_utterances MATCH ? AND f.speaker = ?
                     ORDER BY rank LIMIT ?"""
            rows = self.conn.execute(sql, (query, speaker, limit)).fetchall()
        else:
            sql = """SELECT u.* FROM utterances u
                     JOIN fts_utterances f ON u.id = f.rowid
                     WHERE fts_utterances MATCH ?
                     ORDER BY rank LIMIT ?"""
            rows = self.conn.execute(sql, (query, limit)).fetchall()
        return [dict(r) for r in rows]

    # ---- 统计 ----

    def get_corpus_stats(self) -> dict:
        """获取语料库统计信息。"""
        return {
            'video_count': self.get_video_count(),
            'utterance_count': self.get_utterance_count(),
            'fengge_utterance_count': self.get_utterance_count('fengge'),
            'fengge_total_chars': sum(
                len(r['text']) for r in self.conn.execute(
                    "SELECT text FROM utterances WHERE speaker='fengge'"
                ).fetchall()
            ),
            'danmaku_count': self.conn.execute("SELECT COUNT(*) FROM danmaku").fetchone()[0],
            'comment_count': self.conn.execute("SELECT COUNT(*) FROM comments").fetchone()[0],
        }
