import secrets
import base64
from datetime import datetime, timezone
from io import BytesIO

import bcrypt
import pyotp
import qrcode
from flask import request

from backend.config import get_config
from backend import database as db

config = get_config()


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=config.BCRYPT_ROUNDS)
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    except Exception:
        return False


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def generate_password_reset_token(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + config.PASSWORD_RESET_EXPIRY
    db.set_password_reset_token(user_id, token, expires)
    return token


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def verify_totp(secret: str, code: str) -> bool:
    if not secret or not code:
        return False
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)


def get_totp_qr_code(secret: str, email: str) -> str:
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(email, issuer_name="TEG Finance Admin")

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(provisioning_uri)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)

    img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    return f"data:image/png;base64,{img_base64}"


def is_account_locked(user: dict) -> bool:
    if not user.get('locked_until'):
        return False
    locked_until = user['locked_until']
    if locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) < locked_until


def authenticate_user(username: str, password: str, ip_address: str, user_agent: str) -> dict:
    user = db.get_user_by_username(username)

    if not user:
        return {'error': 'Invalid username or password'}

    # Check if account is locked
    if is_account_locked(user):
        return {'error': 'Account is temporarily locked. Please try again later.'}

    # Verify password
    if not verify_password(password, user['password_hash']):
        # Increment failed attempts
        attempts = user['failed_login_attempts'] + 1
        locked_until = None

        if attempts >= config.MAX_LOGIN_ATTEMPTS:
            locked_until = datetime.now(timezone.utc) + config.LOCKOUT_DURATION
            db.update_user_login_attempts(user['id'], attempts, locked_until)
            return {'error': 'Account locked due to too many failed attempts.'}

        db.update_user_login_attempts(user['id'], attempts, None)
        remaining = config.MAX_LOGIN_ATTEMPTS - attempts
        return {'error': f'Invalid username or password. {remaining} attempts remaining.'}

    # Check if 2FA is enabled
    if user['totp_enabled']:
        return {
            'requires_2fa': True,
            'user_id': user['id']
        }

    # Reset failed attempts on successful login
    db.reset_user_login_attempts(user['id'])

    return {'user': user}


def create_user_session(user_id: str, ip_address: str, user_agent: str) -> str:
    session_token = generate_session_token()
    expires_at = datetime.now(timezone.utc) + config.SESSION_LIFETIME

    db.create_session(
        user_id,
        session_token,
        ip_address,
        user_agent[:500] if user_agent else None,
        expires_at
    )

    return session_token


def get_current_user():
    session_token = request.cookies.get(config.SESSION_COOKIE_NAME)

    if not session_token:
        return None

    session = db.get_session_by_token(session_token)

    if not session:
        return None

    # Update last activity
    db.update_session_activity(session['id'])

    return session


def invalidate_session(session_token: str):
    db.delete_session(session_token)


def invalidate_all_user_sessions(user_id: str):
    db.delete_user_sessions(user_id)
