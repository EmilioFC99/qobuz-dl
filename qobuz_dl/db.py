import logging
import sqlite3

from qobuz_dl.color import YELLOW, RED

logger = logging.getLogger(__name__)


def create_db(db_path):
    with sqlite3.connect(db_path) as conn:
        try:
            conn.execute("""
            CREATE TABLE downloads (
              "id" text NOT NULL,
              "media_type" text NOT NULL DEFAULT 'album',
              "quality" integer NOT NULL DEFAULT 27,
              "file_format" text NOT NULL DEFAULT 'FLAC',
              "quality_met" integer NOT NULL DEFAULT 0,
              "bit_depth" text,
              "sampling_rate" text,
              "saved_path" text NOT NULL DEFAULT '',
              "status" text NOT NULL DEFAULT 'downloaded',
              "url" text NOT NULL DEFAULT '',
              "release_date" text NOT NULL DEFAULT '',
              PRIMARY KEY ("id", "quality")
            );
            """)
            logger.info(f"{YELLOW}Download-IDs database created")
        except sqlite3.OperationalError:
            pass
        return db_path


def handle_download_id(db_path, item_id, add_id=False, media_type='album', quality=27, file_format='FLAC',
                       quality_met=0, bit_depth=None, sampling_rate=None, saved_path='', status='downloaded',
                       url='', release_date=''):
    if not db_path:
        return

    with sqlite3.connect(db_path) as conn:
        # If add_if is False return a string to know if the ID is in the DB
        # Otherwise just add the ID to the DB
        if add_id:
            try:
                conn.execute(
                    """
                    INSERT INTO downloads (id, media_type, quality, file_format, quality_met, bit_depth, 
                    sampling_rate, saved_path, url, release_date, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (item_id, media_type, quality, file_format, quality_met, bit_depth, sampling_rate,
                     saved_path, url, release_date, status),
                )
                conn.commit()
            except sqlite3.Error as e:
                logger.error(f"{RED}Unexpected DB error: {e}")
        else:
            return conn.execute(
                "SELECT id FROM downloads WHERE id=? AND quality=?",
                (item_id, quality),
            ).fetchone()
