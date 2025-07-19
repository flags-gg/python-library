"""SQLite cache implementation for the Flags.gg Python client."""

import json
import os
import sqlite3
import threading
import time
from typing import List, Tuple, Optional
from .cache import Cache
from ..flag import FeatureFlag, Details


class SQLiteCache(Cache):
    """Thread-safe SQLite cache implementation with persistent storage."""
    
    def __init__(self, db_path: str = "/tmp/flags.db"):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._local = threading.local()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get a thread-local database connection."""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path, timeout=30.0)
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA busy_timeout=5000")
            self._local.conn.execute("PRAGMA foreign_keys=ON")
        return self._local.conn
    
    def init(self) -> None:
        """Initialize the SQLite cache and create tables."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Check if we need to migrate from old schema
            cursor.execute("""
                SELECT sql FROM sqlite_master 
                WHERE type='table' AND name='cache_metadata'
            """)
            result = cursor.fetchone()
            
            if result and 'id INTEGER PRIMARY KEY' in result[0]:
                # Old schema detected, drop and recreate
                cursor.execute("DROP TABLE cache_metadata")
            
            # Create flags table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS flags (
                    name TEXT PRIMARY KEY,
                    enabled INTEGER NOT NULL,
                    details TEXT NOT NULL,
                    updated_at INTEGER NOT NULL
                )
            """)
            
            # Create cache metadata table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cache_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            
            # Initialize metadata if not exists
            cursor.execute("""
                INSERT OR IGNORE INTO cache_metadata (key, value)
                VALUES ('next_refresh_time', '0'), ('cache_ttl', '300')
            """)
            
            conn.commit()
    
    def get(self, name: str) -> Tuple[bool, bool]:
        """Get a single flag state from cache."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT enabled FROM flags WHERE name = ?
            """, (name,))
            
            row = cursor.fetchone()
            if row:
                return bool(row[0]), True
            return False, False
    
    def get_all(self) -> List[FeatureFlag]:
        """Get all flags from cache."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT name, enabled, details FROM flags
                ORDER BY name
            """)
            
            flags = []
            for row in cursor.fetchall():
                name, enabled, details_json = row
                details_data = json.loads(details_json)
                flag = FeatureFlag(
                    enabled=bool(enabled),
                    details=Details(
                        name=details_data.get('name', ''),
                        id=details_data.get('id', '')
                    )
                )
                flags.append(flag)
            
            return flags
    
    def refresh(self, flags: List[FeatureFlag], interval_allowed: int) -> None:
        """Refresh the cache with new flag data."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            try:
                # Start transaction
                cursor.execute("BEGIN TRANSACTION")
                
                # Clear existing flags
                cursor.execute("DELETE FROM flags")
                
                # Insert new flags
                current_time = int(time.time())
                for flag in flags:
                    details_json = json.dumps({
                        'name': flag.details.name,
                        'id': flag.details.id
                    })
                    cursor.execute("""
                        INSERT INTO flags (name, enabled, details, updated_at)
                        VALUES (?, ?, ?, ?)
                    """, (flag.details.name, int(flag.enabled), details_json, current_time))
                
                # Update cache metadata
                next_refresh_time = current_time + interval_allowed
                cursor.execute("""
                    UPDATE cache_metadata SET value = ? WHERE key = 'next_refresh_time'
                """, (str(next_refresh_time),))
                
                cursor.execute("""
                    UPDATE cache_metadata SET value = ? WHERE key = 'cache_ttl'
                """, (str(interval_allowed),))
                
                # Commit transaction
                conn.commit()
                
            except Exception:
                # Rollback on error
                conn.rollback()
                raise
    
    def should_refresh_cache(self) -> bool:
        """Check if the cache needs to be refreshed."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT value FROM cache_metadata WHERE key = 'next_refresh_time'
            """)
            
            row = cursor.fetchone()
            if row:
                next_refresh_time = int(row[0])
                return time.time() >= next_refresh_time
            
            return True  # Refresh if no metadata found
    
    def clear(self) -> None:
        """Clear all cached data."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM flags")
            cursor.execute("""
                UPDATE cache_metadata 
                SET value = '0' 
                WHERE key = 'next_refresh_time'
            """)
            
            conn.commit()
    
    def close(self) -> None:
        """Close the database connection."""
        if hasattr(self._local, 'conn') and self._local.conn:
            self._local.conn.close()
            self._local.conn = None