# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TEG Finance website with admin panel, contact forms, and CMS functionality. A professional financial services website built with Flask backend, PostgreSQL database, and vanilla JavaScript frontend, deployed via Docker Compose.

## Tech Stack

- **Backend**: Python 3.11 + Flask (Gunicorn in production)
- **Database**: PostgreSQL 15 with UUID primary keys
- **Frontend**: Jinja2 templates + vanilla JavaScript
- **Deployment**: Docker Compose (nginx → Flask backend → PostgreSQL)
- **Design**: Teal accent (#16A085), Material Design-inspired

## Common Commands

### Development

```bash
# Start all services
docker-compose up -d --build

# View logs
docker-compose logs -f backend

# Restart after backend changes
docker-compose restart backend

# Database reset (removes all data)
docker-compose down && docker volume rm teg-finance_postgres_data && docker-compose up -d
```

### Local Development (without Docker)

```bash
pip install -r requirements.txt
FLASK_ENV=development DATABASE_URL=postgresql://... python -m backend.main
```

### Access Points

- Public site: http://localhost
- Admin panel: http://localhost/admin
- Health check: http://localhost/health

## Architecture

### Container Structure

```
nginx (port 80)
  ├── /static/* → served directly
  ├── /uploads/* → served directly
  └── /* → proxy to backend:5000

backend (Flask on port 5000)
  └── PostgreSQL connection

postgres (port 5432)
  └── init_schema.sql runs on first start
```

### Backend Organization

- `backend/main.py` - Flask app, all routes (public + admin + API), rate limiting
- `backend/database.py` - PostgreSQL manager singleton (`db`), all DB helper functions
- `backend/auth.py` - Password hashing (bcrypt), TOTP 2FA, session management
- `backend/email_service.py` - SMTP email sending via Gmail
- `backend/config.py` - Environment-based configuration

### Key Patterns

**Database Access**: All queries go through `database.py` helper functions. The `db` singleton handles connections:
```python
from backend import database as db
user = db.get_user_by_username(username)
```

**Authentication**: Cookie-based sessions with `@require_auth` decorator:
```python
@require_auth
def admin_route():
    user = get_current_user()  # Returns session data with user_id
```

**API Responses**: Use `json_response()` helper which adds no-cache headers:
```python
return json_response({'success': True, 'data': data})
return json_response({'error': 'Message'}, 400)
```

**Input Sanitization**: All user input sanitized with `bleach.clean()`:
```python
import bleach
title = bleach.clean(data['title'])
```

### Database Schema

Key tables in `backend/migrations/init_schema.sql`:
- `users` - Admin accounts with 2FA (TOTP), lockout tracking
- `sessions` - Server-side session storage
- `pages` - CMS content with service page support
- `navigation_items` - Hierarchical menu structure
- `site_settings` - Key-value configuration
- `email_config` - SMTP settings
- `contact_submissions` - Form submissions
- `audit_log` - Security tracking

All tables use UUID primary keys (`uuid_generate_v4()`).

### Frontend Structure

- `frontend/templates/` - Jinja2 templates (base.html inheritance)
- `frontend/templates/admin/` - Admin panel templates
- `frontend/static/css/` - Stylesheets (style.css, admin.css)
- `frontend/static/js/` - JavaScript (vanilla, no frameworks)
- `frontend/static/js/admin/` - Admin panel JS modules

### Rate Limiting

Applied via Flask-Limiter:
- Login: 5 per 15 minutes
- Contact form: 3 per minute
- Password reset: 3 per hour
- Default: 100 per minute

### File Uploads

- Stored in `data/uploads/` (mounted volume)
- Validated by extension and MIME type
- Served directly by nginx at `/uploads/`
- Image dimensions captured with Pillow

## Environment Variables

Key variables in `.env`:
- `SECRET_KEY` - Flask secret key (required)
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` - Database credentials
- `ADMIN_USERNAME`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` - Initial admin account
- `PORT` - Public port (default: 80)

## Security Features

- Password hashing: bcrypt with configurable rounds
- 2FA: TOTP-based with QR code generation
- Account lockout after failed login attempts
- Server-side session storage
- Input sanitization with bleach
- Rate limiting on sensitive endpoints
- Audit logging for admin actions
