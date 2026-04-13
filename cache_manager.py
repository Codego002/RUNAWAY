"""
Simple Cache Manager pour Runway ML
Évite les re-uploads et track les modifications
"""
import sqlite3
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
import config


class RunwayCache:
    def __init__(self, db_path=None):
        """Initialize cache database"""
        if db_path is None:
            db_path = config.CACHE_DB
        
        # Ensure it's a string path
        self.db_path = str(db_path)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.create_tables()
    
    def create_tables(self):
        """Create database tables"""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS uploads (
                id INTEGER PRIMARY KEY,
                file_path TEXT,
                file_hash TEXT UNIQUE,
                asset_id TEXT NOT NULL,
                asset_url TEXT NOT NULL,
                file_size INTEGER,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS modifications (
                id INTEGER PRIMARY KEY,
                upload_id INTEGER NOT NULL,
                prompt TEXT NOT NULL,
                task_id TEXT,
                aspect_ratio TEXT DEFAULT '9:16',
                num_images INTEGER DEFAULT 1,
                status TEXT DEFAULT 'pending',
                result_urls TEXT,
                error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (upload_id) REFERENCES uploads(id)
            );
            
            CREATE TABLE IF NOT EXISTS profile (
                id INTEGER PRIMARY KEY DEFAULT 1,
                team_id INTEGER,
                credits_remaining INTEGER,
                last_synced TIMESTAMP,
                CHECK (id = 1)
            );
            
            CREATE INDEX IF NOT EXISTS idx_file_hash ON uploads(file_hash);
            CREATE INDEX IF NOT EXISTS idx_status ON modifications(status);
        """)
        self.conn.commit()
    
    def get_file_hash(self, file_path):
        """Calculate MD5 hash of file"""
        md5 = hashlib.md5()
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    md5.update(chunk)
            return md5.hexdigest()
        except Exception as e:
            print(f"❌ Error hashing file: {e}")
            return None
    
    def check_cached_upload(self, file_path):
        """
        Check if file is already uploaded
        Returns dict with asset info if found, None otherwise
        """
        file_hash = self.get_file_hash(file_path)
        if not file_hash:
            return None
        
        cursor = self.conn.execute(
            "SELECT asset_id, asset_url FROM uploads WHERE file_hash = ?",
            (file_hash,)
        )
        row = cursor.fetchone()
        
        if row:
            print(f"✅ Cache HIT: {Path(file_path).name}")
            return {
                'assetId': row['asset_id'],
                'url': row['asset_url'],
                'cached': True
            }
        return None
    
    def save_upload(self, file_path, asset_id, asset_url):
        """Save uploaded file to cache"""
        file_hash = self.get_file_hash(file_path)
        if not file_hash:
            return None
        
        try:
            file_size = os.path.getsize(file_path)
            cursor = self.conn.execute("""
                INSERT OR REPLACE INTO uploads 
                (file_path, file_hash, asset_id, asset_url, file_size)
                VALUES (?, ?, ?, ?, ?)
            """, (str(file_path), file_hash, asset_id, asset_url, file_size))
            self.conn.commit()
            return cursor.lastrowid
        except Exception as e:
            print(f"❌ Error saving upload: {e}")
            return None
    
    def save_profile(self, team_id, credits):
        """Save user profile info"""
        try:
            self.conn.execute("""
                INSERT OR REPLACE INTO profile (id, team_id, credits_remaining, last_synced)
                VALUES (1, ?, ?, CURRENT_TIMESTAMP)
            """, (team_id, credits))
            self.conn.commit()
        except Exception as e:
            print(f"❌ Error saving profile: {e}")
    
    def get_profile(self):
        """Get user profile"""
        cursor = self.conn.execute("SELECT * FROM profile WHERE id = 1")
        row = cursor.fetchone()
        if row:
            return dict(row)
        return {'team_id': None, 'credits_remaining': 0}
    
    def get_stats(self):
        """Get cache statistics"""
        stats = {}
        
        # Total uploads
        cursor = self.conn.execute("SELECT COUNT(*) FROM uploads")
        stats['total_uploads'] = cursor.fetchone()[0]
        
        # Total modifications
        cursor = self.conn.execute(
            "SELECT COUNT(*) FROM modifications WHERE status='succeeded'"
        )
        stats['total_success'] = cursor.fetchone()[0]
        
        # Total failed
        cursor = self.conn.execute(
            "SELECT COUNT(*) FROM modifications WHERE status='failed'"
        )
        stats['total_failed'] = cursor.fetchone()[0]
        
        # Success rate
        total = stats['total_success'] + stats['total_failed']
        stats['success_rate'] = (stats['total_success'] / total * 100) if total > 0 else 0
        
        return stats
    
    def list_cached_uploads(self):
        """List all cached uploads with details"""
        cursor = self.conn.execute("""
            SELECT 
                file_path,
                file_hash,
                asset_id,
                asset_url,
                file_size,
                uploaded_at
            FROM uploads
            ORDER BY uploaded_at DESC
        """)
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'file_path': row['file_path'],
                'file_hash': row['file_hash'],
                'asset_id': row['asset_id'],
                'asset_url': row['asset_url'],
                'file_size': row['file_size'],
                'uploaded_at': row['uploaded_at']
            })
        
        return results
    
    def remove_upload(self, file_hash):
        """Remove an upload from cache by file hash"""
        try:
            self.conn.execute("DELETE FROM uploads WHERE file_hash = ?", (file_hash,))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ Error removing upload: {e}")
            return False
    
    def clear_all(self):
        """Clear all cached uploads"""
        try:
            self.conn.execute("DELETE FROM uploads")
            self.conn.execute("DELETE FROM modifications")
            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ Error clearing cache: {e}")
            return False
    
    def close(self):
        """Close database connection"""
        self.conn.close()
