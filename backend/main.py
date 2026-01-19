import os
import logging
from functools import wraps
from flask import Flask, request, jsonify, render_template, redirect, url_for, make_response
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from backend.config import get_config
from backend import database as db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__,
            template_folder='/app/templates',
            static_folder='/app/static')

config = get_config()
app.config.from_object(config)

# Initialize rate limiter
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["100 per minute"],
    storage_uri="memory://"
)


# ============================================
# HELPER FUNCTIONS
# ============================================

def get_client_ip():
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        from backend.auth import get_current_user
        user = get_current_user()
        if not user:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Unauthorized'}), 401
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated


def json_response(data, status=200):
    response = jsonify(data)
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    return response, status


def get_settings_context():
    return db.get_all_settings(public_only=True)


def get_navigation_context():
    return db.get_visible_navigation()


# ============================================
# HEALTH CHECK
# ============================================

@app.route('/health')
def health_check():
    try:
        db.db.fetch_one("SELECT 1")
        return jsonify({'status': 'healthy', 'database': 'connected'})
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500


# ============================================
# PUBLIC ROUTES
# ============================================

@app.route('/')
def index():
    settings = get_settings_context()
    navigation = get_navigation_context()
    services = db.get_service_pages()

    return render_template('index.html',
                         settings=settings,
                         navigation=navigation,
                         services=services)


@app.route('/contact')
def contact():
    settings = get_settings_context()
    navigation = get_navigation_context()
    services = db.get_service_pages()

    return render_template('contact.html',
                         settings=settings,
                         navigation=navigation,
                         services=services)


@app.route('/services/<slug>')
def service_page(slug):
    page = db.get_page_by_slug(slug)
    if not page or not page['is_published']:
        return render_template('404.html'), 404

    settings = get_settings_context()
    navigation = get_navigation_context()
    services = db.get_service_pages()

    return render_template('service.html',
                         page=page,
                         settings=settings,
                         navigation=navigation,
                         services=services)


@app.route('/page/<slug>')
def cms_page(slug):
    page = db.get_page_by_slug(slug)
    if not page or not page['is_published']:
        return render_template('404.html'), 404

    settings = get_settings_context()
    navigation = get_navigation_context()

    return render_template('page.html',
                         page=page,
                         settings=settings,
                         navigation=navigation)


@app.route('/about')
def about():
    settings = get_settings_context()
    navigation = get_navigation_context()

    return render_template('about.html',
                         settings=settings,
                         navigation=navigation)


# ============================================
# PUBLIC API ROUTES
# ============================================

@app.route('/api/navigation')
def api_navigation():
    navigation = get_navigation_context()
    return json_response({'items': navigation})


@app.route('/api/settings/public')
def api_public_settings():
    settings = get_settings_context()
    return json_response(settings)


@app.route('/api/contact', methods=['POST'])
@limiter.limit("3 per minute")
def api_contact_submit():
    data = request.get_json()

    if not data:
        return json_response({'error': 'Invalid request'}, 400)

    # Validate required fields
    if not data.get('name') or not data.get('email') or not data.get('message'):
        return json_response({'error': 'Name, email, and message are required'}, 400)

    # Sanitize input
    import bleach
    submission_data = {
        'name': bleach.clean(data['name'][:100]),
        'email': bleach.clean(data['email'][:255]),
        'phone': bleach.clean(data.get('phone', '')[:30]) if data.get('phone') else None,
        'subject': bleach.clean(data.get('subject', '')[:255]) if data.get('subject') else None,
        'message': bleach.clean(data['message'][:5000]),
        'service_interest': bleach.clean(data.get('service_interest', '')[:100]) if data.get('service_interest') else None,
        'ip_address': get_client_ip(),
        'user_agent': request.headers.get('User-Agent', '')[:500]
    }

    try:
        submission = db.create_contact_submission(submission_data)

        # Try to send email notification
        from backend.email_service import send_contact_notification
        email_sent, email_error = send_contact_notification(submission_data)

        if submission:
            db.update_submission_email_status(submission['id'], email_sent, email_error)

        return json_response({
            'success': True,
            'message': 'Thank you for your message. We will get back to you soon.'
        })
    except Exception as e:
        logger.error(f"Contact submission error: {e}")
        return json_response({'error': 'Failed to submit message'}, 500)


# ============================================
# AUTHENTICATION ROUTES
# ============================================

@app.route('/admin')
@app.route('/admin/')
def admin_index():
    from backend.auth import get_current_user
    user = get_current_user()
    if user:
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('admin_login'))


@app.route('/admin/login')
def admin_login():
    from backend.auth import get_current_user
    if get_current_user():
        return redirect(url_for('admin_dashboard'))
    return render_template('admin/login.html')


@app.route('/api/auth/login', methods=['POST'])
@limiter.limit("5 per 15 minutes")
def api_login():
    from backend.auth import authenticate_user, create_user_session

    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return json_response({'error': 'Username and password required'}, 400)

    result = authenticate_user(
        data['username'],
        data['password'],
        get_client_ip(),
        request.headers.get('User-Agent', '')
    )

    if result.get('error'):
        return json_response({'error': result['error']}, 401)

    if result.get('requires_2fa'):
        return json_response({
            'requires_2fa': True,
            'user_id': str(result['user_id'])
        })

    # Create session
    session_token = create_user_session(
        result['user']['id'],
        get_client_ip(),
        request.headers.get('User-Agent', '')
    )

    response = make_response(json_response({'success': True, 'redirect': '/admin/dashboard'})[0])
    response.set_cookie(
        config.SESSION_COOKIE_NAME,
        session_token,
        httponly=True,
        secure=config.SESSION_COOKIE_SECURE,
        samesite=config.SESSION_COOKIE_SAMESITE,
        max_age=int(config.SESSION_LIFETIME.total_seconds())
    )

    db.create_audit_log(
        result['user']['id'],
        'login',
        ip_address=get_client_ip(),
        user_agent=request.headers.get('User-Agent', '')
    )

    return response


@app.route('/api/auth/verify-2fa', methods=['POST'])
@limiter.limit("5 per 15 minutes")
def api_verify_2fa():
    from backend.auth import verify_totp, create_user_session

    data = request.get_json()
    if not data or not data.get('user_id') or not data.get('code'):
        return json_response({'error': 'User ID and code required'}, 400)

    user = db.get_user_by_id(data['user_id'])
    if not user or not user['totp_enabled']:
        return json_response({'error': 'Invalid request'}, 400)

    if not verify_totp(user['totp_secret'], data['code']):
        return json_response({'error': 'Invalid verification code'}, 401)

    # Create session
    session_token = create_user_session(
        user['id'],
        get_client_ip(),
        request.headers.get('User-Agent', '')
    )

    response = make_response(json_response({'success': True, 'redirect': '/admin/dashboard'})[0])
    response.set_cookie(
        config.SESSION_COOKIE_NAME,
        session_token,
        httponly=True,
        secure=config.SESSION_COOKIE_SECURE,
        samesite=config.SESSION_COOKIE_SAMESITE,
        max_age=int(config.SESSION_LIFETIME.total_seconds())
    )

    db.reset_user_login_attempts(user['id'])
    db.create_audit_log(
        user['id'],
        'login_2fa',
        ip_address=get_client_ip(),
        user_agent=request.headers.get('User-Agent', '')
    )

    return response


@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    from backend.auth import get_current_user

    session_token = request.cookies.get(config.SESSION_COOKIE_NAME)
    user = get_current_user()

    if session_token:
        db.delete_session(session_token)

    if user:
        db.create_audit_log(
            user['user_id'],
            'logout',
            ip_address=get_client_ip(),
            user_agent=request.headers.get('User-Agent', '')
        )

    response = make_response(json_response({'success': True})[0])
    response.delete_cookie(config.SESSION_COOKIE_NAME)
    return response


@app.route('/api/auth/forgot-password', methods=['POST'])
@limiter.limit("3 per hour")
def api_forgot_password():
    from backend.auth import generate_password_reset_token
    from backend.email_service import send_password_reset_email

    data = request.get_json()
    email = data.get('email') if data else None

    if not email:
        return json_response({'error': 'Email required'}, 400)

    user = db.get_user_by_email(email)

    # Always return success to prevent email enumeration
    if user:
        token = generate_password_reset_token(user['id'])
        send_password_reset_email(email, token)

    return json_response({
        'success': True,
        'message': 'If an account exists with that email, a reset link has been sent.'
    })


@app.route('/api/auth/reset-password', methods=['POST'])
def api_reset_password():
    from backend.auth import hash_password

    data = request.get_json()
    token = data.get('token')
    password = data.get('password')

    if not token or not password:
        return json_response({'error': 'Token and password required'}, 400)

    if len(password) < config.PASSWORD_MIN_LENGTH:
        return json_response({'error': f'Password must be at least {config.PASSWORD_MIN_LENGTH} characters'}, 400)

    user = db.get_user_by_reset_token(token)
    if not user:
        return json_response({'error': 'Invalid or expired reset token'}, 400)

    password_hash = hash_password(password)
    db.update_user_password(user['id'], password_hash)
    db.delete_user_sessions(user['id'])

    db.create_audit_log(
        user['id'],
        'password_reset',
        ip_address=get_client_ip(),
        user_agent=request.headers.get('User-Agent', '')
    )

    return json_response({
        'success': True,
        'message': 'Password has been reset. Please log in with your new password.'
    })


@app.route('/api/auth/setup-2fa', methods=['POST'])
@require_auth
def api_setup_2fa():
    from backend.auth import get_current_user, generate_totp_secret, get_totp_qr_code

    user = get_current_user()
    secret = generate_totp_secret()

    # Store secret temporarily (not enabled yet)
    db.update_user_totp(user['user_id'], secret, False)

    qr_code = get_totp_qr_code(secret, user['email'])

    return json_response({
        'secret': secret,
        'qr_code': qr_code
    })


@app.route('/api/auth/enable-2fa', methods=['POST'])
@require_auth
def api_enable_2fa():
    from backend.auth import get_current_user, verify_totp

    data = request.get_json()
    code = data.get('code') if data else None

    if not code:
        return json_response({'error': 'Verification code required'}, 400)

    user = get_current_user()
    user_data = db.get_user_by_id(user['user_id'])

    if not user_data or not user_data['totp_secret']:
        return json_response({'error': '2FA setup not initiated'}, 400)

    if not verify_totp(user_data['totp_secret'], code):
        return json_response({'error': 'Invalid verification code'}, 400)

    db.update_user_totp(user['user_id'], user_data['totp_secret'], True)

    db.create_audit_log(
        user['user_id'],
        '2fa_enabled',
        ip_address=get_client_ip(),
        user_agent=request.headers.get('User-Agent', '')
    )

    return json_response({'success': True, 'message': '2FA has been enabled'})


@app.route('/api/auth/disable-2fa', methods=['POST'])
@require_auth
def api_disable_2fa():
    from backend.auth import get_current_user

    user = get_current_user()
    db.update_user_totp(user['user_id'], None, False)

    db.create_audit_log(
        user['user_id'],
        '2fa_disabled',
        ip_address=get_client_ip(),
        user_agent=request.headers.get('User-Agent', '')
    )

    return json_response({'success': True, 'message': '2FA has been disabled'})


# ============================================
# ADMIN DASHBOARD ROUTES
# ============================================

@app.route('/admin/dashboard')
@require_auth
def admin_dashboard():
    from backend.auth import get_current_user
    user = get_current_user()
    stats = db.get_dashboard_stats()

    return render_template('admin/dashboard.html', user=user, stats=stats)


@app.route('/admin/pages')
@require_auth
def admin_pages():
    from backend.auth import get_current_user
    user = get_current_user()
    pages = db.get_all_pages()

    return render_template('admin/pages.html', user=user, pages=pages)


@app.route('/admin/pages/new')
@app.route('/admin/pages/<page_id>')
@require_auth
def admin_page_editor(page_id=None):
    from backend.auth import get_current_user
    user = get_current_user()
    page = db.get_page_by_id(page_id) if page_id else None
    images = db.get_all_images()

    return render_template('admin/page-editor.html', user=user, page=page, images=images)


@app.route('/admin/navigation')
@require_auth
def admin_navigation():
    from backend.auth import get_current_user
    user = get_current_user()
    items = db.get_navigation_items()
    pages = db.get_all_pages(published_only=True)

    return render_template('admin/navigation.html', user=user, items=items, pages=pages)


@app.route('/admin/images')
@require_auth
def admin_images():
    from backend.auth import get_current_user
    user = get_current_user()
    images = db.get_all_images()

    return render_template('admin/images.html', user=user, images=images)


@app.route('/admin/submissions')
@require_auth
def admin_submissions():
    from backend.auth import get_current_user
    user = get_current_user()
    submissions = db.get_contact_submissions()

    return render_template('admin/submissions.html', user=user, submissions=submissions)


@app.route('/admin/settings')
@require_auth
def admin_settings():
    from backend.auth import get_current_user
    user = get_current_user()
    settings = db.get_all_settings()
    user_data = db.get_user_by_id(user['user_id'])

    return render_template('admin/settings.html', user=user, settings=settings, user_data=user_data)


@app.route('/admin/email-config')
@require_auth
def admin_email_config():
    from backend.auth import get_current_user
    user = get_current_user()
    email_config = db.get_email_config()

    return render_template('admin/email-config.html', user=user, email_config=email_config)


# ============================================
# ADMIN API ROUTES - PAGES
# ============================================

@app.route('/api/admin/pages', methods=['GET'])
@require_auth
def api_admin_get_pages():
    pages = db.get_all_pages()
    return json_response({'pages': pages})


@app.route('/api/admin/pages', methods=['POST'])
@require_auth
def api_admin_create_page():
    from backend.auth import get_current_user
    import bleach

    user = get_current_user()
    data = request.get_json()

    if not data or not data.get('title') or not data.get('slug'):
        return json_response({'error': 'Title and slug are required'}, 400)

    # Check for duplicate slug
    existing = db.get_page_by_slug(data['slug'])
    if existing:
        return json_response({'error': 'A page with this URL already exists'}, 400)

    # Sanitize HTML content (allow safe tags for rich text)
    allowed_tags = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'br', 'strong', 'em',
                    'u', 's', 'ul', 'ol', 'li', 'a', 'img', 'blockquote', 'pre', 'code']
    allowed_attrs = {'a': ['href', 'title', 'target'], 'img': ['src', 'alt', 'title']}

    page_data = {
        'slug': bleach.clean(data['slug']),
        'title': bleach.clean(data['title']),
        'meta_title': bleach.clean(data.get('meta_title', '')),
        'meta_description': bleach.clean(data.get('meta_description', '')),
        'content': bleach.clean(data.get('content', ''), tags=allowed_tags, attributes=allowed_attrs),
        'hero_image_id': data.get('hero_image_id'),
        'is_published': data.get('is_published', False),
        'is_service_page': data.get('is_service_page', False),
        'service_icon': data.get('service_icon'),
        'service_order': data.get('service_order', 0),
        'language': data.get('language', 'en')
    }

    page = db.create_page(page_data, user['user_id'])

    db.create_audit_log(
        user['user_id'],
        'page_created',
        'page',
        page['id'],
        new_values={'title': page['title'], 'slug': page['slug']},
        ip_address=get_client_ip(),
        user_agent=request.headers.get('User-Agent', '')
    )

    return json_response({'success': True, 'page': page})


@app.route('/api/admin/pages/<page_id>', methods=['GET'])
@require_auth
def api_admin_get_page(page_id):
    page = db.get_page_by_id(page_id)
    if not page:
        return json_response({'error': 'Page not found'}, 404)
    return json_response({'page': page})


@app.route('/api/admin/pages/<page_id>', methods=['PUT'])
@require_auth
def api_admin_update_page(page_id):
    from backend.auth import get_current_user
    import bleach

    user = get_current_user()
    data = request.get_json()

    page = db.get_page_by_id(page_id)
    if not page:
        return json_response({'error': 'Page not found'}, 404)

    # Check for duplicate slug (if changing)
    if data.get('slug') and data['slug'] != page['slug']:
        existing = db.get_page_by_slug(data['slug'])
        if existing:
            return json_response({'error': 'A page with this URL already exists'}, 400)

    allowed_tags = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'br', 'strong', 'em',
                    'u', 's', 'ul', 'ol', 'li', 'a', 'img', 'blockquote', 'pre', 'code']
    allowed_attrs = {'a': ['href', 'title', 'target'], 'img': ['src', 'alt', 'title']}

    update_data = {}
    if 'slug' in data:
        update_data['slug'] = bleach.clean(data['slug'])
    if 'title' in data:
        update_data['title'] = bleach.clean(data['title'])
    if 'meta_title' in data:
        update_data['meta_title'] = bleach.clean(data['meta_title'])
    if 'meta_description' in data:
        update_data['meta_description'] = bleach.clean(data['meta_description'])
    if 'content' in data:
        update_data['content'] = bleach.clean(data['content'], tags=allowed_tags, attributes=allowed_attrs)
    if 'hero_image_id' in data:
        update_data['hero_image_id'] = data['hero_image_id']
    if 'is_published' in data:
        update_data['is_published'] = data['is_published']
    if 'is_service_page' in data:
        update_data['is_service_page'] = data['is_service_page']
    if 'service_icon' in data:
        update_data['service_icon'] = data['service_icon']
    if 'service_order' in data:
        update_data['service_order'] = data['service_order']
    if 'language' in data:
        update_data['language'] = data['language']

    db.update_page(page_id, update_data, user['user_id'])

    db.create_audit_log(
        user['user_id'],
        'page_updated',
        'page',
        page_id,
        old_values={'title': page['title']},
        new_values=update_data,
        ip_address=get_client_ip(),
        user_agent=request.headers.get('User-Agent', '')
    )

    updated_page = db.get_page_by_id(page_id)
    return json_response({'success': True, 'page': updated_page})


@app.route('/api/admin/pages/<page_id>', methods=['DELETE'])
@require_auth
def api_admin_delete_page(page_id):
    from backend.auth import get_current_user

    user = get_current_user()
    page = db.get_page_by_id(page_id)

    if not page:
        return json_response({'error': 'Page not found'}, 404)

    db.delete_page(page_id)

    db.create_audit_log(
        user['user_id'],
        'page_deleted',
        'page',
        page_id,
        old_values={'title': page['title'], 'slug': page['slug']},
        ip_address=get_client_ip(),
        user_agent=request.headers.get('User-Agent', '')
    )

    return json_response({'success': True})


@app.route('/api/admin/pages/<page_id>/publish', methods=['POST'])
@require_auth
def api_admin_toggle_publish(page_id):
    from backend.auth import get_current_user

    user = get_current_user()
    page = db.get_page_by_id(page_id)

    if not page:
        return json_response({'error': 'Page not found'}, 404)

    new_status = not page['is_published']
    db.update_page(page_id, {'is_published': new_status}, user['user_id'])

    return json_response({'success': True, 'is_published': new_status})


# ============================================
# ADMIN API ROUTES - NAVIGATION
# ============================================

@app.route('/api/admin/navigation', methods=['GET'])
@require_auth
def api_admin_get_navigation():
    items = db.get_navigation_items()
    return json_response({'items': items})


@app.route('/api/admin/navigation', methods=['POST'])
@require_auth
def api_admin_create_navigation():
    from backend.auth import get_current_user
    import bleach

    user = get_current_user()
    data = request.get_json()

    if not data or not data.get('label'):
        return json_response({'error': 'Label is required'}, 400)

    item_data = {
        'label': bleach.clean(data['label']),
        'url': bleach.clean(data.get('url', '')),
        'page_id': data.get('page_id'),
        'parent_id': data.get('parent_id'),
        'position': data.get('position', 0),
        'is_visible': data.get('is_visible', True),
        'open_in_new_tab': data.get('open_in_new_tab', False)
    }

    item = db.create_navigation_item(item_data)

    db.create_audit_log(
        user['user_id'],
        'navigation_created',
        'navigation',
        item['id'],
        new_values={'label': item['label']},
        ip_address=get_client_ip(),
        user_agent=request.headers.get('User-Agent', '')
    )

    return json_response({'success': True, 'item': item})


@app.route('/api/admin/navigation/<item_id>', methods=['PUT'])
@require_auth
def api_admin_update_navigation(item_id):
    from backend.auth import get_current_user
    import bleach

    user = get_current_user()
    data = request.get_json()

    update_data = {}
    if 'label' in data:
        update_data['label'] = bleach.clean(data['label'])
    if 'url' in data:
        update_data['url'] = bleach.clean(data['url'])
    if 'page_id' in data:
        update_data['page_id'] = data['page_id']
    if 'parent_id' in data:
        update_data['parent_id'] = data['parent_id']
    if 'position' in data:
        update_data['position'] = data['position']
    if 'is_visible' in data:
        update_data['is_visible'] = data['is_visible']
    if 'open_in_new_tab' in data:
        update_data['open_in_new_tab'] = data['open_in_new_tab']

    db.update_navigation_item(item_id, update_data)

    db.create_audit_log(
        user['user_id'],
        'navigation_updated',
        'navigation',
        item_id,
        new_values=update_data,
        ip_address=get_client_ip(),
        user_agent=request.headers.get('User-Agent', '')
    )

    return json_response({'success': True})


@app.route('/api/admin/navigation/<item_id>', methods=['DELETE'])
@require_auth
def api_admin_delete_navigation(item_id):
    from backend.auth import get_current_user

    user = get_current_user()
    db.delete_navigation_item(item_id)

    db.create_audit_log(
        user['user_id'],
        'navigation_deleted',
        'navigation',
        item_id,
        ip_address=get_client_ip(),
        user_agent=request.headers.get('User-Agent', '')
    )

    return json_response({'success': True})


@app.route('/api/admin/navigation/reorder', methods=['POST'])
@require_auth
def api_admin_reorder_navigation():
    from backend.auth import get_current_user

    user = get_current_user()
    data = request.get_json()

    if not data or not data.get('items'):
        return json_response({'error': 'Items are required'}, 400)

    db.reorder_navigation_items(data['items'])

    db.create_audit_log(
        user['user_id'],
        'navigation_reordered',
        ip_address=get_client_ip(),
        user_agent=request.headers.get('User-Agent', '')
    )

    return json_response({'success': True})


# ============================================
# ADMIN API ROUTES - IMAGES
# ============================================

@app.route('/api/admin/images', methods=['GET'])
@require_auth
def api_admin_get_images():
    images = db.get_all_images()
    return json_response({'images': images})


@app.route('/api/admin/images', methods=['POST'])
@require_auth
def api_admin_upload_image():
    from backend.auth import get_current_user
    from PIL import Image
    import uuid
    import os

    user = get_current_user()

    if 'file' not in request.files:
        return json_response({'error': 'No file provided'}, 400)

    file = request.files['file']
    if not file.filename:
        return json_response({'error': 'No file selected'}, 400)

    # Check file extension
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in config.ALLOWED_EXTENSIONS:
        return json_response({'error': 'File type not allowed'}, 400)

    # Check MIME type
    if file.content_type not in config.ALLOWED_MIME_TYPES:
        return json_response({'error': 'Invalid file type'}, 400)

    # Generate unique filename
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(config.UPLOAD_FOLDER, filename)

    # Save file
    file.save(filepath)

    # Get file size
    file_size = os.path.getsize(filepath)

    # Get image dimensions
    width, height = None, None
    try:
        with Image.open(filepath) as img:
            width, height = img.size
    except Exception:
        pass

    # Create database record
    image_data = {
        'filename': filename,
        'original_filename': file.filename,
        'mime_type': file.content_type,
        'file_size': file_size,
        'width': width,
        'height': height,
        'alt_text': request.form.get('alt_text', ''),
        'uploaded_by': user['user_id']
    }

    image = db.create_image(image_data)

    db.create_audit_log(
        user['user_id'],
        'image_uploaded',
        'image',
        image['id'],
        new_values={'filename': filename},
        ip_address=get_client_ip(),
        user_agent=request.headers.get('User-Agent', '')
    )

    return json_response({'success': True, 'image': image})


@app.route('/api/admin/images/<image_id>', methods=['PUT'])
@require_auth
def api_admin_update_image(image_id):
    from backend.auth import get_current_user
    import bleach

    user = get_current_user()
    data = request.get_json()

    if data and 'alt_text' in data:
        db.update_image(image_id, {'alt_text': bleach.clean(data['alt_text'])})

    db.create_audit_log(
        user['user_id'],
        'image_updated',
        'image',
        image_id,
        ip_address=get_client_ip(),
        user_agent=request.headers.get('User-Agent', '')
    )

    return json_response({'success': True})


@app.route('/api/admin/images/<image_id>', methods=['DELETE'])
@require_auth
def api_admin_delete_image(image_id):
    from backend.auth import get_current_user
    import os

    user = get_current_user()
    image = db.get_image_by_id(image_id)

    if not image:
        return json_response({'error': 'Image not found'}, 404)

    # Delete file
    filepath = os.path.join(config.UPLOAD_FOLDER, image['filename'])
    if os.path.exists(filepath):
        os.remove(filepath)

    # Delete database record
    db.delete_image(image_id)

    db.create_audit_log(
        user['user_id'],
        'image_deleted',
        'image',
        image_id,
        old_values={'filename': image['filename']},
        ip_address=get_client_ip(),
        user_agent=request.headers.get('User-Agent', '')
    )

    return json_response({'success': True})


# ============================================
# ADMIN API ROUTES - SETTINGS
# ============================================

@app.route('/api/admin/settings', methods=['GET'])
@require_auth
def api_admin_get_settings():
    settings = db.get_all_settings()
    return json_response({'settings': settings})


@app.route('/api/admin/settings', methods=['PUT'])
@require_auth
def api_admin_update_settings():
    from backend.auth import get_current_user
    import bleach

    user = get_current_user()
    data = request.get_json()

    if not data:
        return json_response({'error': 'No settings provided'}, 400)

    # Sanitize all values
    sanitized = {key: bleach.clean(str(value)) for key, value in data.items()}

    db.update_settings(sanitized, user['user_id'])

    db.create_audit_log(
        user['user_id'],
        'settings_updated',
        new_values=list(sanitized.keys()),
        ip_address=get_client_ip(),
        user_agent=request.headers.get('User-Agent', '')
    )

    return json_response({'success': True})


# ============================================
# ADMIN API ROUTES - EMAIL CONFIG
# ============================================

@app.route('/api/admin/email-config', methods=['GET'])
@require_auth
def api_admin_get_email_config():
    config_data = db.get_email_config()
    if config_data:
        # Don't send password
        config_data['smtp_password'] = '********' if config_data.get('smtp_password') else ''
    return json_response({'config': config_data})


@app.route('/api/admin/email-config', methods=['POST'])
@require_auth
def api_admin_update_email_config():
    from backend.auth import get_current_user

    user = get_current_user()
    data = request.get_json()

    if not data:
        return json_response({'error': 'No configuration provided'}, 400)

    # Get existing config to preserve password if not changed
    existing = db.get_email_config()

    config_data = {
        'smtp_host': data.get('smtp_host', 'smtp.gmail.com'),
        'smtp_port': int(data.get('smtp_port', 587)),
        'use_tls': data.get('use_tls', True),
        'smtp_username': data.get('smtp_username'),
        'from_email': data.get('from_email'),
        'from_name': data.get('from_name', 'TEG Finance'),
        'recipient_email': data.get('recipient_email'),
        'is_configured': True
    }

    # Only update password if provided and not placeholder
    if data.get('smtp_password') and data['smtp_password'] != '********':
        config_data['smtp_password'] = data['smtp_password']
    elif existing:
        config_data['smtp_password'] = existing.get('smtp_password')

    db.update_email_config(config_data, user['user_id'])

    db.create_audit_log(
        user['user_id'],
        'email_config_updated',
        ip_address=get_client_ip(),
        user_agent=request.headers.get('User-Agent', '')
    )

    return json_response({'success': True})


@app.route('/api/admin/email-config/test', methods=['POST'])
@require_auth
def api_admin_test_email():
    from backend.email_service import send_test_email

    success, error = send_test_email()

    if success:
        return json_response({'success': True, 'message': 'Test email sent successfully'})
    else:
        return json_response({'success': False, 'error': error}, 500)


# ============================================
# ADMIN API ROUTES - SUBMISSIONS
# ============================================

@app.route('/api/admin/submissions', methods=['GET'])
@require_auth
def api_admin_get_submissions():
    unread_only = request.args.get('unread', 'false').lower() == 'true'
    limit = min(int(request.args.get('limit', 50)), 100)
    offset = int(request.args.get('offset', 0))

    submissions = db.get_contact_submissions(unread_only, limit, offset)
    stats = db.get_submission_stats()

    return json_response({'submissions': submissions, 'stats': stats})


@app.route('/api/admin/submissions/<submission_id>/read', methods=['PUT'])
@require_auth
def api_admin_mark_submission_read(submission_id):
    data = request.get_json()
    is_read = data.get('is_read', True) if data else True

    db.mark_submission_read(submission_id, is_read)
    return json_response({'success': True})


@app.route('/api/admin/submissions/<submission_id>', methods=['DELETE'])
@require_auth
def api_admin_delete_submission(submission_id):
    from backend.auth import get_current_user

    user = get_current_user()
    db.delete_contact_submission(submission_id)

    db.create_audit_log(
        user['user_id'],
        'submission_deleted',
        'submission',
        submission_id,
        ip_address=get_client_ip(),
        user_agent=request.headers.get('User-Agent', '')
    )

    return json_response({'success': True})


# ============================================
# ERROR HANDLERS
# ============================================

@app.errorhandler(404)
def not_found(e):
    if request.path.startswith('/api/'):
        return json_response({'error': 'Not found'}, 404)
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(e):
    logger.error(f"Internal error: {e}")
    if request.path.startswith('/api/'):
        return json_response({'error': 'Internal server error'}, 500)
    return render_template('500.html'), 500


@app.errorhandler(429)
def ratelimit_handler(e):
    return json_response({'error': 'Too many requests. Please try again later.'}, 429)


# ============================================
# STARTUP
# ============================================

def init_admin_user():
    """Create initial admin user if none exists"""
    from backend.auth import hash_password

    try:
        existing = db.get_user_by_username(config.ADMIN_USERNAME)
        if not existing:
            password_hash = hash_password(config.ADMIN_PASSWORD)
            db.create_admin_user(
                config.ADMIN_USERNAME,
                config.ADMIN_EMAIL,
                password_hash
            )
            logger.info(f"Created initial admin user: {config.ADMIN_USERNAME}")
    except Exception as e:
        logger.error(f"Failed to create admin user: {e}")


# Initialize on first request
@app.before_request
def before_first_request():
    if not hasattr(app, '_initialized'):
        init_admin_user()
        app._initialized = True


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
