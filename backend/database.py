import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from typing import Optional, List, Dict, Any
import logging

from backend.config import get_config

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self):
        self.config = get_config()
        self._connection_params = self._parse_database_url(self.config.DATABASE_URL)

    def _parse_database_url(self, url: str) -> dict:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return {
            'host': parsed.hostname,
            'port': parsed.port or 5432,
            'database': parsed.path.lstrip('/'),
            'user': parsed.username,
            'password': parsed.password,
        }

    @contextmanager
    def get_connection(self):
        conn = None
        try:
            conn = psycopg2.connect(**self._connection_params)
            yield conn
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            raise
        finally:
            if conn:
                conn.close()

    @contextmanager
    def get_cursor(self, commit: bool = False):
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                yield cursor
                if commit:
                    conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error(f"Database query error: {e}")
                raise
            finally:
                cursor.close()

    def execute(self, query: str, params: tuple = None, commit: bool = True) -> Optional[int]:
        with self.get_cursor(commit=commit) as cursor:
            cursor.execute(query, params)
            return cursor.rowcount

    def fetch_one(self, query: str, params: tuple = None) -> Optional[Dict[str, Any]]:
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            result = cursor.fetchone()
            return dict(result) if result else None

    def fetch_all(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            results = cursor.fetchall()
            return [dict(row) for row in results]

    def insert_returning(self, query: str, params: tuple = None) -> Optional[Dict[str, Any]]:
        with self.get_cursor(commit=True) as cursor:
            cursor.execute(query, params)
            result = cursor.fetchone()
            return dict(result) if result else None


# Singleton instance
db = DatabaseManager()


# Helper functions for common operations
def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    return db.fetch_one(
        "SELECT * FROM users WHERE username = %s AND is_active = TRUE",
        (username,)
    )


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    return db.fetch_one(
        "SELECT * FROM users WHERE email = %s AND is_active = TRUE",
        (email,)
    )


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    return db.fetch_one(
        "SELECT * FROM users WHERE id = %s AND is_active = TRUE",
        (user_id,)
    )


def get_user_by_reset_token(token: str) -> Optional[Dict[str, Any]]:
    return db.fetch_one(
        """SELECT * FROM users
           WHERE password_reset_token = %s
           AND password_reset_expires > CURRENT_TIMESTAMP
           AND is_active = TRUE""",
        (token,)
    )


def update_user_login_attempts(user_id: str, attempts: int, locked_until=None):
    db.execute(
        """UPDATE users
           SET failed_login_attempts = %s, locked_until = %s
           WHERE id = %s""",
        (attempts, locked_until, user_id)
    )


def reset_user_login_attempts(user_id: str):
    db.execute(
        "UPDATE users SET failed_login_attempts = 0, locked_until = NULL WHERE id = %s",
        (user_id,)
    )


def update_user_password(user_id: str, password_hash: str):
    db.execute(
        """UPDATE users
           SET password_hash = %s,
               password_reset_token = NULL,
               password_reset_expires = NULL
           WHERE id = %s""",
        (password_hash, user_id)
    )


def set_password_reset_token(user_id: str, token: str, expires):
    db.execute(
        """UPDATE users
           SET password_reset_token = %s, password_reset_expires = %s
           WHERE id = %s""",
        (token, expires, user_id)
    )


def update_user_totp(user_id: str, secret: str, enabled: bool):
    db.execute(
        "UPDATE users SET totp_secret = %s, totp_enabled = %s WHERE id = %s",
        (secret, enabled, user_id)
    )


# Session functions
def create_session(user_id: str, session_token: str, ip_address: str,
                   user_agent: str, expires_at) -> Optional[Dict[str, Any]]:
    return db.insert_returning(
        """INSERT INTO sessions (user_id, session_token, ip_address, user_agent, expires_at)
           VALUES (%s, %s, %s, %s, %s)
           RETURNING *""",
        (user_id, session_token, ip_address, user_agent, expires_at)
    )


def get_session_by_token(token: str) -> Optional[Dict[str, Any]]:
    return db.fetch_one(
        """SELECT s.*, u.username, u.email, u.totp_enabled
           FROM sessions s
           JOIN users u ON s.user_id = u.id
           WHERE s.session_token = %s
           AND s.expires_at > CURRENT_TIMESTAMP
           AND u.is_active = TRUE""",
        (token,)
    )


def update_session_activity(session_id: str):
    db.execute(
        "UPDATE sessions SET last_activity = CURRENT_TIMESTAMP WHERE id = %s",
        (session_id,)
    )


def delete_session(token: str):
    db.execute("DELETE FROM sessions WHERE session_token = %s", (token,))


def delete_user_sessions(user_id: str):
    db.execute("DELETE FROM sessions WHERE user_id = %s", (user_id,))


def clean_expired_sessions():
    db.execute("DELETE FROM sessions WHERE expires_at < CURRENT_TIMESTAMP")


# Page functions
def get_all_pages(published_only: bool = False) -> List[Dict[str, Any]]:
    if published_only:
        return db.fetch_all(
            """SELECT p.*, i.filename as hero_image_filename
               FROM pages p
               LEFT JOIN images i ON p.hero_image_id = i.id
               WHERE p.is_published = TRUE
               ORDER BY p.is_service_page DESC, p.service_order, p.title"""
        )
    return db.fetch_all(
        """SELECT p.*, i.filename as hero_image_filename
           FROM pages p
           LEFT JOIN images i ON p.hero_image_id = i.id
           ORDER BY p.is_service_page DESC, p.service_order, p.title"""
    )


def get_service_pages() -> List[Dict[str, Any]]:
    return db.fetch_all(
        """SELECT p.*, i.filename as hero_image_filename
           FROM pages p
           LEFT JOIN images i ON p.hero_image_id = i.id
           WHERE p.is_service_page = TRUE AND p.is_published = TRUE
           ORDER BY p.service_order, p.title"""
    )


def get_page_by_slug(slug: str) -> Optional[Dict[str, Any]]:
    return db.fetch_one(
        """SELECT p.*, i.filename as hero_image_filename
           FROM pages p
           LEFT JOIN images i ON p.hero_image_id = i.id
           WHERE p.slug = %s""",
        (slug,)
    )


def get_page_by_id(page_id: str) -> Optional[Dict[str, Any]]:
    return db.fetch_one(
        """SELECT p.*, i.filename as hero_image_filename
           FROM pages p
           LEFT JOIN images i ON p.hero_image_id = i.id
           WHERE p.id = %s""",
        (page_id,)
    )


def create_page(data: Dict[str, Any], user_id: str) -> Optional[Dict[str, Any]]:
    return db.insert_returning(
        """INSERT INTO pages
           (slug, title, meta_title, meta_description, content, hero_image_id,
            is_published, is_service_page, service_icon, service_order, language,
            created_by, updated_by)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
           RETURNING *""",
        (data['slug'], data['title'], data.get('meta_title'),
         data.get('meta_description'), data.get('content'),
         data.get('hero_image_id'), data.get('is_published', False),
         data.get('is_service_page', False), data.get('service_icon'),
         data.get('service_order', 0), data.get('language', 'en'),
         user_id, user_id)
    )


def update_page(page_id: str, data: Dict[str, Any], user_id: str):
    fields = []
    values = []

    for key in ['slug', 'title', 'meta_title', 'meta_description', 'content',
                'hero_image_id', 'is_published', 'is_service_page',
                'service_icon', 'service_order', 'language']:
        if key in data:
            fields.append(f"{key} = %s")
            values.append(data[key])

    if not fields:
        return

    fields.append("updated_by = %s")
    values.append(user_id)
    values.append(page_id)

    db.execute(
        f"UPDATE pages SET {', '.join(fields)} WHERE id = %s",
        tuple(values)
    )


def delete_page(page_id: str):
    db.execute("DELETE FROM pages WHERE id = %s", (page_id,))


# Navigation functions
def get_navigation_items() -> List[Dict[str, Any]]:
    return db.fetch_all(
        """SELECT n.*, p.slug as page_slug
           FROM navigation_items n
           LEFT JOIN pages p ON n.page_id = p.id
           ORDER BY n.position"""
    )


def get_visible_navigation() -> List[Dict[str, Any]]:
    items = db.fetch_all(
        """SELECT n.*, p.slug as page_slug
           FROM navigation_items n
           LEFT JOIN pages p ON n.page_id = p.id
           WHERE n.is_visible = TRUE
           ORDER BY n.position"""
    )

    # Build tree structure
    root_items = []
    children_map = {}

    for item in items:
        item['children'] = []
        if item['parent_id']:
            if item['parent_id'] not in children_map:
                children_map[item['parent_id']] = []
            children_map[item['parent_id']].append(item)
        else:
            root_items.append(item)

    for item in root_items:
        item['children'] = children_map.get(item['id'], [])

    return root_items


def create_navigation_item(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    return db.insert_returning(
        """INSERT INTO navigation_items (label, url, page_id, parent_id, position, is_visible, open_in_new_tab)
           VALUES (%s, %s, %s, %s, %s, %s, %s)
           RETURNING *""",
        (data['label'], data.get('url'), data.get('page_id'),
         data.get('parent_id'), data.get('position', 0),
         data.get('is_visible', True), data.get('open_in_new_tab', False))
    )


def update_navigation_item(item_id: str, data: Dict[str, Any]):
    fields = []
    values = []

    for key in ['label', 'url', 'page_id', 'parent_id', 'position',
                'is_visible', 'open_in_new_tab']:
        if key in data:
            fields.append(f"{key} = %s")
            values.append(data[key])

    if not fields:
        return

    values.append(item_id)
    db.execute(
        f"UPDATE navigation_items SET {', '.join(fields)} WHERE id = %s",
        tuple(values)
    )


def delete_navigation_item(item_id: str):
    db.execute("DELETE FROM navigation_items WHERE id = %s", (item_id,))


def reorder_navigation_items(items: List[Dict[str, Any]]):
    with db.get_cursor(commit=True) as cursor:
        for item in items:
            cursor.execute(
                "UPDATE navigation_items SET position = %s, parent_id = %s WHERE id = %s",
                (item['position'], item.get('parent_id'), item['id'])
            )


# Image functions
def get_all_images() -> List[Dict[str, Any]]:
    return db.fetch_all(
        """SELECT i.*, u.username as uploaded_by_name
           FROM images i
           LEFT JOIN users u ON i.uploaded_by = u.id
           ORDER BY i.created_at DESC"""
    )


def get_image_by_id(image_id: str) -> Optional[Dict[str, Any]]:
    return db.fetch_one("SELECT * FROM images WHERE id = %s", (image_id,))


def create_image(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    return db.insert_returning(
        """INSERT INTO images
           (filename, original_filename, mime_type, file_size, width, height, alt_text, uploaded_by)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
           RETURNING *""",
        (data['filename'], data['original_filename'], data['mime_type'],
         data['file_size'], data.get('width'), data.get('height'),
         data.get('alt_text'), data.get('uploaded_by'))
    )


def update_image(image_id: str, data: Dict[str, Any]):
    if 'alt_text' in data:
        db.execute(
            "UPDATE images SET alt_text = %s WHERE id = %s",
            (data['alt_text'], image_id)
        )


def delete_image(image_id: str):
    db.execute("DELETE FROM images WHERE id = %s", (image_id,))


# Settings functions
def get_all_settings(public_only: bool = False) -> Dict[str, Any]:
    if public_only:
        rows = db.fetch_all(
            "SELECT setting_key, setting_value FROM site_settings WHERE is_public = TRUE"
        )
    else:
        rows = db.fetch_all("SELECT setting_key, setting_value FROM site_settings")

    return {row['setting_key']: row['setting_value'] for row in rows}


def get_setting(key: str) -> Optional[str]:
    result = db.fetch_one(
        "SELECT setting_value FROM site_settings WHERE setting_key = %s",
        (key,)
    )
    return result['setting_value'] if result else None


def update_setting(key: str, value: str, user_id: str = None):
    db.execute(
        """INSERT INTO site_settings (setting_key, setting_value, updated_by)
           VALUES (%s, %s, %s)
           ON CONFLICT (setting_key)
           DO UPDATE SET setting_value = %s, updated_by = %s""",
        (key, value, user_id, value, user_id)
    )


def update_settings(settings: Dict[str, str], user_id: str = None):
    with db.get_cursor(commit=True) as cursor:
        for key, value in settings.items():
            cursor.execute(
                """INSERT INTO site_settings (setting_key, setting_value, updated_by)
                   VALUES (%s, %s, %s)
                   ON CONFLICT (setting_key)
                   DO UPDATE SET setting_value = %s, updated_by = %s""",
                (key, value, user_id, value, user_id)
            )


# Email config functions
def get_email_config() -> Optional[Dict[str, Any]]:
    return db.fetch_one("SELECT * FROM email_config LIMIT 1")


def update_email_config(data: Dict[str, Any], user_id: str = None):
    existing = get_email_config()

    if existing:
        db.execute(
            """UPDATE email_config SET
               smtp_host = %s, smtp_port = %s, use_tls = %s,
               smtp_username = %s, smtp_password = %s,
               from_email = %s, from_name = %s, recipient_email = %s,
               is_configured = %s, updated_by = %s
               WHERE id = %s""",
            (data.get('smtp_host', 'smtp.gmail.com'),
             data.get('smtp_port', 587),
             data.get('use_tls', True),
             data.get('smtp_username'),
             data.get('smtp_password'),
             data.get('from_email'),
             data.get('from_name', 'TEG Finance'),
             data.get('recipient_email'),
             data.get('is_configured', False),
             user_id,
             existing['id'])
        )
    else:
        db.insert_returning(
            """INSERT INTO email_config
               (smtp_host, smtp_port, use_tls, smtp_username, smtp_password,
                from_email, from_name, recipient_email, is_configured, updated_by)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING *""",
            (data.get('smtp_host', 'smtp.gmail.com'),
             data.get('smtp_port', 587),
             data.get('use_tls', True),
             data.get('smtp_username'),
             data.get('smtp_password'),
             data.get('from_email'),
             data.get('from_name', 'TEG Finance'),
             data.get('recipient_email'),
             data.get('is_configured', False),
             user_id)
        )


# Contact submissions functions
def get_contact_submissions(unread_only: bool = False, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    if unread_only:
        return db.fetch_all(
            """SELECT * FROM contact_submissions
               WHERE is_read = FALSE
               ORDER BY created_at DESC
               LIMIT %s OFFSET %s""",
            (limit, offset)
        )
    return db.fetch_all(
        """SELECT * FROM contact_submissions
           ORDER BY created_at DESC
           LIMIT %s OFFSET %s""",
        (limit, offset)
    )


def get_contact_submission_by_id(submission_id: str) -> Optional[Dict[str, Any]]:
    return db.fetch_one(
        "SELECT * FROM contact_submissions WHERE id = %s",
        (submission_id,)
    )


def create_contact_submission(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    return db.insert_returning(
        """INSERT INTO contact_submissions
           (name, email, phone, subject, message, service_interest, ip_address, user_agent)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
           RETURNING *""",
        (data['name'], data['email'], data.get('phone'),
         data.get('subject'), data['message'], data.get('service_interest'),
         data.get('ip_address'), data.get('user_agent'))
    )


def mark_submission_read(submission_id: str, is_read: bool = True):
    db.execute(
        "UPDATE contact_submissions SET is_read = %s WHERE id = %s",
        (is_read, submission_id)
    )


def update_submission_email_status(submission_id: str, sent: bool, error: str = None):
    db.execute(
        "UPDATE contact_submissions SET email_sent = %s, email_error = %s WHERE id = %s",
        (sent, error, submission_id)
    )


def delete_contact_submission(submission_id: str):
    db.execute("DELETE FROM contact_submissions WHERE id = %s", (submission_id,))


def get_submission_stats() -> Dict[str, int]:
    result = db.fetch_one(
        """SELECT
           COUNT(*) as total,
           COUNT(*) FILTER (WHERE is_read = FALSE) as unread,
           COUNT(*) FILTER (WHERE created_at > CURRENT_DATE - INTERVAL '7 days') as this_week
           FROM contact_submissions"""
    )
    return result if result else {'total': 0, 'unread': 0, 'this_week': 0}


# Audit log functions
def create_audit_log(user_id: str, action: str, entity_type: str = None,
                     entity_id: str = None, old_values: dict = None,
                     new_values: dict = None, ip_address: str = None,
                     user_agent: str = None):
    import json
    db.execute(
        """INSERT INTO audit_log
           (user_id, action, entity_type, entity_id, old_values, new_values, ip_address, user_agent)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        (user_id, action, entity_type, entity_id,
         json.dumps(old_values) if old_values else None,
         json.dumps(new_values) if new_values else None,
         ip_address, user_agent)
    )


# Admin user creation (for initial setup)
def create_admin_user(username: str, email: str, password_hash: str) -> Optional[Dict[str, Any]]:
    existing = get_user_by_username(username)
    if existing:
        return existing

    return db.insert_returning(
        """INSERT INTO users (username, email, password_hash, is_active)
           VALUES (%s, %s, %s, TRUE)
           RETURNING *""",
        (username, email, password_hash)
    )


def get_dashboard_stats() -> Dict[str, Any]:
    pages = db.fetch_one("SELECT COUNT(*) as count FROM pages")
    published = db.fetch_one("SELECT COUNT(*) as count FROM pages WHERE is_published = TRUE")
    submissions = get_submission_stats()

    return {
        'total_pages': pages['count'] if pages else 0,
        'published_pages': published['count'] if published else 0,
        'total_submissions': submissions['total'],
        'unread_submissions': submissions['unread'],
        'submissions_this_week': submissions['this_week']
    }
