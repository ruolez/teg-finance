#!/usr/bin/env python3
"""
Reset admin password from environment variables.
Run this script to sync the admin user's password with ADMIN_PASSWORD env var.
"""

import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import bcrypt
import psycopg2
from psycopg2.extras import RealDictCursor


def get_database_url():
    """Get database URL from environment"""
    return os.environ.get(
        'DATABASE_URL',
        'postgresql://teg_admin:teg_secure_password_2025@localhost:5432/teg_website'
    )


def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def parse_database_url(url: str) -> dict:
    """Parse PostgreSQL connection URL"""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return {
        'host': parsed.hostname,
        'port': parsed.port or 5432,
        'database': parsed.path.lstrip('/'),
        'user': parsed.username,
        'password': parsed.password,
    }


def reset_admin_password():
    """Reset admin password from environment variables"""
    # Get configuration from environment
    admin_username = os.environ.get('ADMIN_USERNAME', 'admin')
    admin_password = os.environ.get('ADMIN_PASSWORD')
    admin_email = os.environ.get('ADMIN_EMAIL', 'admin@example.com')
    database_url = get_database_url()

    if not admin_password:
        print("ERROR: ADMIN_PASSWORD environment variable not set")
        sys.exit(1)

    print(f"Resetting password for admin user: {admin_username}")

    # Hash the password
    password_hash = hash_password(admin_password)
    print("Password hashed successfully")

    # Connect to database
    conn_params = parse_database_url(database_url)

    try:
        conn = psycopg2.connect(**conn_params)
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Check if user exists
        cursor.execute(
            "SELECT id, username FROM users WHERE username = %s",
            (admin_username,)
        )
        existing = cursor.fetchone()

        if existing:
            # Update existing user's password
            cursor.execute(
                "UPDATE users SET password_hash = %s, email = %s WHERE username = %s",
                (password_hash, admin_email, admin_username)
            )
            print(f"Updated password for existing user: {admin_username}")
        else:
            # Create new admin user
            cursor.execute(
                """INSERT INTO users (username, email, password_hash, is_active)
                   VALUES (%s, %s, %s, TRUE)""",
                (admin_username, admin_email, password_hash)
            )
            print(f"Created new admin user: {admin_username}")

        conn.commit()
        print("Database changes committed successfully")

    except Exception as e:
        print(f"ERROR: Database operation failed: {e}")
        sys.exit(1)
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    print("Admin password reset complete!")


if __name__ == '__main__':
    reset_admin_password()
