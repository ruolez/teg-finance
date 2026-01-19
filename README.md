# TEG Finance Website

A professional financial services website with admin panel, contact forms, and CMS functionality.

## Tech Stack

- **Backend**: Python 3.11 + Flask
- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **Database**: PostgreSQL 15
- **Deployment**: Docker Compose (nginx + backend + frontend + postgres)
- **Design**: Teal accent (#16A085), Material Design-inspired, responsive

## Features

### Public Website
- Professional homepage with services overview
- Individual service pages
- Contact form with email notifications
- About page
- Responsive design

### Admin Panel (`/admin`)
- Dashboard with statistics
- Page management with rich text editor (Quill.js)
- Image upload and media library
- Navigation menu management
- Site settings configuration
- Email configuration (Gmail SMTP)
- Contact form submissions
- Two-factor authentication (2FA)

## Production Installation (Ubuntu Server 24)

### One-Line Install

```bash
curl -fsSL https://raw.githubusercontent.com/ruolez/teg-finance/main/install.sh | sudo bash
```

Or download and run manually:

```bash
wget https://raw.githubusercontent.com/ruolez/teg-finance/main/install.sh
chmod +x install.sh
sudo ./install.sh
```

The installer will:
- Install Docker, Nginx, and Certbot
- Clone the repository to `/opt/teg-finance`
- Generate secure credentials
- Configure SSL with Let's Encrypt (auto-renewal enabled)
- Start all services

### Update Existing Installation

```bash
sudo /opt/teg-finance/install.sh update
```

This preserves:
- Database data
- User uploads
- Environment configuration (.env)
- SSL certificates

### Remove Installation

```bash
sudo /opt/teg-finance/install.sh remove
```

Completely removes all data, uploads, and SSL certificates.

---

## Local Development

### 1. Clone and Configure

```bash
# Copy environment file
cp .env.example .env

# Edit .env with your settings
nano .env
```

### 2. Start with Docker

```bash
docker-compose up -d --build
```

### 3. Access the Site

- **Public Site**: http://localhost
- **Admin Panel**: http://localhost/admin

Default admin credentials (change in `.env`):
- Username: `admin`
- Password: `ChangeThisPassword123!`

## Services Featured

1. Tax Services (Individual and Business)
2. Business Registration
3. Accounting & Bookkeeping Services
4. Financial Statement Service
5. Advisory & Consulting Services

## Project Structure

```
teg-finance/
├── docker-compose.yml          # Container orchestration
├── Dockerfile.backend          # Python Flask container
├── Dockerfile.frontend         # Nginx container
├── nginx/
│   └── nginx.conf             # Reverse proxy config
├── requirements.txt            # Python dependencies
├── backend/
│   ├── main.py                # Flask app + API routes
│   ├── auth.py                # Authentication + 2FA
│   ├── database.py            # PostgreSQL manager
│   ├── email_service.py       # SMTP email sending
│   └── migrations/
│       └── init_schema.sql    # Database schema
├── frontend/
│   ├── templates/             # Jinja2 templates
│   │   ├── base.html
│   │   ├── index.html
│   │   ├── contact.html
│   │   └── admin/
│   └── static/
│       ├── css/
│       └── js/
└── data/
    └── uploads/               # Uploaded images
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `FLASK_ENV` | Environment mode | `development` |
| `SECRET_KEY` | Flask secret key | Required |
| `POSTGRES_DB` | Database name | `teg_website` |
| `POSTGRES_USER` | Database user | `teg_admin` |
| `POSTGRES_PASSWORD` | Database password | Required |
| `PORT` | Public port | `80` |
| `ADMIN_USERNAME` | Initial admin username | `admin` |
| `ADMIN_EMAIL` | Initial admin email | Required |
| `ADMIN_PASSWORD` | Initial admin password | Required |

## Gmail SMTP Setup

1. Enable 2-Step Verification in your Google Account
2. Generate an App Password:
   - Go to Google Account > Security > App Passwords
   - Create a new password for "Mail"
3. Configure in Admin Panel > Email Config

## Security Features

- Password hashing with bcrypt
- Two-factor authentication (TOTP)
- Rate limiting on login and contact form
- Account lockout after failed attempts
- Server-side session storage
- CSRF protection
- Input sanitization with bleach
- File upload validation

## Development

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run Flask development server
FLASK_ENV=development python -m backend.main
```

### Database Reset

```bash
# Stop containers
docker-compose down

# Remove volume
docker volume rm teg-finance_postgres_data

# Restart
docker-compose up -d
```

## Color Palette

```css
--primary: #16A085;        /* Teal accent */
--primary-hover: #138D75;
--primary-light: #E8F6F3;
--background: #F8F9FA;
--surface: #FFFFFF;
--text-primary: #1A1A1A;
--text-secondary: #5F6368;
```

## License

MIT License
