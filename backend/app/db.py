"""SQLite schema and connection management.

Every table that stores a scraped fact carries `source_url` and
`retrieved_at` columns - per the product spec, a fact without provenance is
not allowed to influence a recommendation.
"""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from typing import Iterator

from app.config import DB_PATH

_local = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS courses (
    subject TEXT NOT NULL,
    course_number TEXT NOT NULL,
    title TEXT,
    credit_hours REAL,
    PRIMARY KEY (subject, course_number)
);

CREATE TABLE IF NOT EXISTS professors (
    professor_key TEXT PRIMARY KEY,
    display_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    term_code TEXT NOT NULL,
    subject TEXT NOT NULL,
    course_number TEXT NOT NULL,
    crn TEXT,
    section_id TEXT,
    instructor_raw TEXT,
    professor_key TEXT,
    meeting_days TEXT,
    meeting_time TEXT,
    modality TEXT,
    seats_capacity INTEGER,
    seats_taken INTEGER,
    source_url TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    UNIQUE(term_code, subject, course_number, crn)
);

CREATE TABLE IF NOT EXISTS grade_distributions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    professor_key TEXT NOT NULL,
    subject TEXT NOT NULL,
    course_number TEXT NOT NULL,
    term_code TEXT NOT NULL,
    a_count INTEGER, b_count INTEGER, c_count INTEGER,
    d_count INTEGER, f_count INTEGER, w_count INTEGER,
    gpa REAL,
    sample_size INTEGER,
    source_url TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    UNIQUE(professor_key, subject, course_number, term_code)
);

CREATE TABLE IF NOT EXISTS syllabus_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    professor_key TEXT NOT NULL,
    subject TEXT NOT NULL,
    course_number TEXT NOT NULL,
    term_code TEXT,
    exam_weight REAL,
    homework_weight REAL,
    project_weight REAL,
    attendance_policy TEXT,
    late_work_policy TEXT,
    office_hours_text TEXT,
    assignment_frequency TEXT,
    raw_excerpt TEXT,
    source_url TEXT NOT NULL,
    retrieved_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS teaching_recognition (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    professor_key TEXT NOT NULL,
    description TEXT NOT NULL,
    source_url TEXT NOT NULL,
    retrieved_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS web_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    professor_key TEXT NOT NULL,
    subject TEXT,
    course_number TEXT,
    source TEXT NOT NULL,           -- 'reddit', 'web', etc.
    domain TEXT,
    url TEXT NOT NULL,
    title TEXT,
    published_at TEXT,
    retrieved_at TEXT NOT NULL,
    text_snippet TEXT NOT NULL,
    engagement_score REAL,
    mentions_course INTEGER NOT NULL DEFAULT 0,
    mentions_professor INTEGER NOT NULL DEFAULT 0,
    content_hash TEXT NOT NULL,
    UNIQUE(professor_key, content_hash)
);

CREATE TABLE IF NOT EXISTS trait_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    web_evidence_id INTEGER NOT NULL REFERENCES web_evidence(id),
    trait TEXT NOT NULL,
    polarity REAL NOT NULL,         -- -1..1, sentiment-weighted
    evidence_span TEXT NOT NULL,
    UNIQUE(web_evidence_id, trait, evidence_span)
);

CREATE TABLE IF NOT EXISTS http_cache (
    cache_key TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    url TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    ttl_seconds INTEGER NOT NULL,
    status TEXT NOT NULL,           -- 'ok', 'blocked', 'error', 'not_found'
    payload TEXT
);
"""


def _connect() -> sqlite3.Connection:
    # `timeout` is how long a write waits on a lock held by another
    # connection before raising "database is locked". The research pass runs
    # its fetches on a thread pool and every one of them writes an
    # http_cache row, so the default would surface as spurious failures
    # under load. WAL lets those readers and writers overlap instead of
    # serializing on a single global lock.
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def get_connection() -> sqlite3.Connection:
    if not hasattr(_local, "conn"):
        _local.conn = _connect()
    return _local.conn


def init_db(conn: sqlite3.Connection | None = None) -> None:
    owns = conn is None
    conn = conn or get_connection()
    conn.executescript(SCHEMA)
    conn.commit()
    if owns:
        pass


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
