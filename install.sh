#!/bin/bash
#
# TEG Finance Website Installer
# Ubuntu Server 24.04 LTS
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/ruolez/teg-finance/main/install.sh | sudo bash
#
# Or download and run:
#   chmod +x install.sh
#   sudo ./install.sh
#

set -e

# ============================================================================
# Configuration
# ============================================================================

INSTALL_DIR="/opt/teg-finance"
REPO_URL="https://github.com/ruolez/teg-finance.git"
BACKUP_DIR="/tmp/teg-finance-backup"
NGINX_CONF="/etc/nginx/sites-available/teg-finance"
NGINX_ENABLED="/etc/nginx/sites-enabled/teg-finance"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# Helper Functions
# ============================================================================

print_header() {
    echo ""
    echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${BLUE}→ $1${NC}"
}

confirm() {
    local prompt="$1"
    local response
    read -p "$prompt [y/N]: " response
    [[ "$response" =~ ^[Yy]$ ]]
}

generate_password() {
    openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 32
}

generate_secret_key() {
    openssl rand -hex 32
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

check_ubuntu() {
    if ! grep -q "Ubuntu" /etc/os-release 2>/dev/null; then
        print_warning "This script is designed for Ubuntu Server. Proceed with caution."
    fi
}

# ============================================================================
# Installation Functions
# ============================================================================

install_dependencies() {
    print_info "Updating package lists..."
    apt-get update -qq

    print_info "Installing required packages..."
    apt-get install -y -qq \
        apt-transport-https \
        ca-certificates \
        curl \
        gnupg \
        lsb-release \
        git \
        nginx \
        certbot \
        python3-certbot-nginx \
        openssl

    print_success "Dependencies installed"
}

install_docker() {
    if command -v docker &> /dev/null; then
        print_success "Docker already installed"
        return
    fi

    print_info "Installing Docker..."

    # Add Docker's official GPG key
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc

    # Add the repository to Apt sources
    echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
        $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
        tee /etc/apt/sources.list.d/docker.list > /dev/null

    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    # Enable and start Docker
    systemctl enable docker
    systemctl start docker

    print_success "Docker installed"
}

clone_repository() {
    if [[ -d "$INSTALL_DIR" ]]; then
        print_error "Installation directory already exists: $INSTALL_DIR"
        print_info "Use 'update' to update existing installation or 'remove' to uninstall first"
        exit 1
    fi

    print_info "Cloning repository..."
    git clone "$REPO_URL" "$INSTALL_DIR"
    print_success "Repository cloned to $INSTALL_DIR"
}

create_env_file() {
    local domain="$1"
    local env_file="$INSTALL_DIR/.env"

    if [[ -f "$env_file" ]]; then
        print_warning ".env file already exists, preserving it"
        return
    fi

    print_info "Generating secure credentials..."

    local db_password=$(generate_password)
    local secret_key=$(generate_secret_key)
    local admin_password=$(generate_password)

    cat > "$env_file" << EOF
# TEG Finance Environment Configuration
# Generated on $(date)

# Domain
DOMAIN=$domain

# Flask
FLASK_ENV=production
SECRET_KEY=$secret_key

# PostgreSQL
POSTGRES_DB=teg_website
POSTGRES_USER=teg_admin
POSTGRES_PASSWORD=$db_password

# Initial Admin Account
ADMIN_USERNAME=admin
ADMIN_EMAIL=admin@$domain
ADMIN_PASSWORD=$admin_password
EOF

    chmod 600 "$env_file"

    print_success "Environment file created"
    echo ""
    echo -e "${YELLOW}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║  IMPORTANT: Save these credentials securely!                   ║${NC}"
    echo -e "${YELLOW}╠════════════════════════════════════════════════════════════════╣${NC}"
    echo -e "${YELLOW}║  Admin Username: ${NC}admin${YELLOW}                                        ║${NC}"
    echo -e "${YELLOW}║  Admin Password: ${NC}$admin_password${YELLOW}  ║${NC}"
    echo -e "${YELLOW}║  Admin URL:      ${NC}https://$domain/admin${YELLOW}$(printf '%*s' $((24 - ${#domain})) '')║${NC}"
    echo -e "${YELLOW}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

setup_nginx() {
    local domain="$1"
    local include_www="$2"

    print_info "Configuring Nginx..."

    # Determine server_name based on www preference
    local server_names="$domain"
    if [[ "$include_www" == "yes" ]]; then
        server_names="$domain www.$domain"
    fi

    # Create nginx configuration (HTTP only initially, certbot will add SSL)
    cat > "$NGINX_CONF" << EOF
# TEG Finance Website - Nginx Configuration
# Domain: $domain

upstream teg_backend {
    server 127.0.0.1:5000;
}

server {
    listen 80;
    listen [::]:80;
    server_name $server_names;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/json application/xml;

    # Client body size limit for file uploads
    client_max_body_size 10M;

    # Static files
    location /static/ {
        alias $INSTALL_DIR/frontend/static/;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }

    # Uploaded files
    location /uploads/ {
        alias $INSTALL_DIR/data/uploads/;
        expires 30d;
        add_header Cache-Control "public";
    }

    # Proxy to Flask backend
    location / {
        proxy_pass http://teg_backend;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;

        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EOF

    # Enable the site
    ln -sf "$NGINX_CONF" "$NGINX_ENABLED"

    # Remove default site if exists
    rm -f /etc/nginx/sites-enabled/default

    # Test nginx configuration
    nginx -t

    # Reload nginx
    systemctl reload nginx

    print_success "Nginx configured"
}

setup_ssl() {
    local domain="$1"
    local email="$2"
    local include_www="$3"

    print_info "Obtaining SSL certificate from Let's Encrypt..."

    # Build certbot command based on www preference
    if [[ "$include_www" == "yes" ]]; then
        certbot --nginx \
            -d "$domain" \
            -d "www.$domain" \
            --non-interactive \
            --agree-tos \
            --email "$email" \
            --redirect
    else
        certbot --nginx \
            -d "$domain" \
            --non-interactive \
            --agree-tos \
            --email "$email" \
            --redirect
    fi

    # Verify auto-renewal is set up
    systemctl enable certbot.timer
    systemctl start certbot.timer

    print_success "SSL certificate installed with auto-renewal"
}

create_production_compose() {
    local compose_file="$INSTALL_DIR/docker-compose.prod.yml"

    cat > "$compose_file" << 'EOF'
# TEG Finance - Production Docker Compose
# SSL termination handled by host Nginx

services:
  postgres:
    image: postgres:15-alpine
    container_name: teg-postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-teg_website}
      POSTGRES_USER: ${POSTGRES_USER:-teg_admin}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backend/migrations/init_schema.sql:/docker-entrypoint-initdb.d/init.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-teg_admin} -d ${POSTGRES_DB:-teg_website}"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - teg-network

  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    container_name: teg-backend
    restart: unless-stopped
    environment:
      - FLASK_ENV=production
      - DATABASE_URL=postgresql://${POSTGRES_USER:-teg_admin}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB:-teg_website}
      - SECRET_KEY=${SECRET_KEY}
      - UPLOAD_FOLDER=/app/uploads
      - ADMIN_USERNAME=${ADMIN_USERNAME:-admin}
      - ADMIN_EMAIL=${ADMIN_EMAIL}
      - ADMIN_PASSWORD=${ADMIN_PASSWORD}
    volumes:
      - ./backend:/app/backend:ro
      - ./frontend/templates:/app/templates:ro
      - ./frontend/static:/app/static:ro
      - ./data/uploads:/app/uploads
    ports:
      - "127.0.0.1:5000:5000"
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - teg-network

volumes:
  postgres_data:

networks:
  teg-network:
    driver: bridge
EOF

    print_success "Production Docker Compose file created"
}

start_services() {
    print_info "Starting Docker services..."

    cd "$INSTALL_DIR"
    docker compose -f docker-compose.prod.yml up -d --build

    print_success "Services started"
}

create_systemd_service() {
    cat > /etc/systemd/system/teg-finance.service << EOF
[Unit]
Description=TEG Finance Website
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/docker compose -f docker-compose.prod.yml up -d
ExecStop=/usr/bin/docker compose -f docker-compose.prod.yml down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable teg-finance.service

    print_success "Systemd service created"
}

# ============================================================================
# Update Functions
# ============================================================================

backup_data() {
    print_info "Backing up data..."

    mkdir -p "$BACKUP_DIR"

    # Backup uploads
    if [[ -d "$INSTALL_DIR/data/uploads" ]]; then
        cp -r "$INSTALL_DIR/data/uploads" "$BACKUP_DIR/"
        print_success "Uploads backed up"
    fi

    # Backup .env
    if [[ -f "$INSTALL_DIR/.env" ]]; then
        cp "$INSTALL_DIR/.env" "$BACKUP_DIR/"
        print_success ".env backed up"
    fi
}

restore_data() {
    print_info "Restoring data..."

    # Restore uploads
    if [[ -d "$BACKUP_DIR/uploads" ]]; then
        rm -rf "$INSTALL_DIR/data/uploads"
        cp -r "$BACKUP_DIR/uploads" "$INSTALL_DIR/data/"
        print_success "Uploads restored"
    fi

    # Restore .env
    if [[ -f "$BACKUP_DIR/.env" ]]; then
        cp "$BACKUP_DIR/.env" "$INSTALL_DIR/"
        print_success ".env restored"
    fi

    # Cleanup backup
    rm -rf "$BACKUP_DIR"
}

update_installation() {
    if [[ ! -d "$INSTALL_DIR" ]]; then
        print_error "TEG Finance is not installed at $INSTALL_DIR"
        exit 1
    fi

    print_header "Updating TEG Finance"

    # Stop services
    print_info "Stopping services..."
    cd "$INSTALL_DIR"
    docker compose -f docker-compose.prod.yml down 2>/dev/null || docker compose down 2>/dev/null || true

    # Backup data
    backup_data

    # Pull latest code
    print_info "Pulling latest code from GitHub..."
    cd "$INSTALL_DIR"
    git fetch origin
    git reset --hard origin/main

    # Restore data
    restore_data

    # Recreate production compose (in case it changed)
    create_production_compose

    # Rebuild and start
    print_info "Rebuilding and starting services..."
    docker compose -f docker-compose.prod.yml up -d --build

    # Reload nginx (in case config changed)
    systemctl reload nginx

    print_success "Update complete!"
    echo ""
    print_info "Your data and SSL certificates have been preserved"
}

# ============================================================================
# Remove Functions
# ============================================================================

remove_installation() {
    print_header "Removing TEG Finance"

    if [[ ! -d "$INSTALL_DIR" ]]; then
        print_warning "Installation directory not found at $INSTALL_DIR"
    fi

    if ! confirm "This will remove ALL data including database, uploads, and SSL certificates. Continue?"; then
        print_info "Removal cancelled"
        exit 0
    fi

    # Stop and remove containers
    if [[ -d "$INSTALL_DIR" ]]; then
        print_info "Stopping Docker containers..."
        cd "$INSTALL_DIR"
        docker compose -f docker-compose.prod.yml down -v 2>/dev/null || docker compose down -v 2>/dev/null || true
    fi

    # Remove any remaining containers and volumes
    print_info "Cleaning up Docker resources..."
    docker rm -f teg-postgres teg-backend teg-nginx 2>/dev/null || true
    docker volume rm teg-finance_postgres_data 2>/dev/null || true

    # Remove nginx configuration
    print_info "Removing Nginx configuration..."
    rm -f "$NGINX_ENABLED"
    rm -f "$NGINX_CONF"

    # Restore default nginx if needed
    if [[ -f /etc/nginx/sites-available/default ]]; then
        ln -sf /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default
    fi

    systemctl reload nginx 2>/dev/null || true

    # Remove SSL certificates
    print_info "Removing SSL certificates..."
    local domain=""
    if [[ -f "$INSTALL_DIR/.env" ]]; then
        domain=$(grep "^DOMAIN=" "$INSTALL_DIR/.env" | cut -d'=' -f2)
    fi

    if [[ -n "$domain" ]]; then
        certbot delete --cert-name "$domain" --non-interactive 2>/dev/null || true
        certbot delete --cert-name "www.$domain" --non-interactive 2>/dev/null || true
    fi

    # Remove systemd service
    print_info "Removing systemd service..."
    systemctl stop teg-finance.service 2>/dev/null || true
    systemctl disable teg-finance.service 2>/dev/null || true
    rm -f /etc/systemd/system/teg-finance.service
    systemctl daemon-reload

    # Remove installation directory
    print_info "Removing installation directory..."
    rm -rf "$INSTALL_DIR"

    # Remove backup directory if exists
    rm -rf "$BACKUP_DIR"

    print_success "TEG Finance has been completely removed"
}

# ============================================================================
# Install Function
# ============================================================================

install_fresh() {
    print_header "TEG Finance Website Installer"

    # Get domain name
    echo ""
    read -p "Enter your domain name (e.g., example.com): " DOMAIN

    if [[ -z "$DOMAIN" ]]; then
        print_error "Domain name is required"
        exit 1
    fi

    # Validate domain format
    if ! [[ "$DOMAIN" =~ ^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$ ]]; then
        print_error "Invalid domain format"
        exit 1
    fi

    read -p "Enter email for SSL certificate notifications: " EMAIL

    if [[ -z "$EMAIL" ]]; then
        print_error "Email is required for Let's Encrypt"
        exit 1
    fi

    # Ask about www subdomain
    echo ""
    print_info "Do you have a DNS record for www.$DOMAIN?"
    print_info "(Both $DOMAIN and www.$DOMAIN must point to this server's IP)"
    echo ""
    if confirm "Include www.$DOMAIN in SSL certificate?"; then
        INCLUDE_WWW="yes"
    else
        INCLUDE_WWW="no"
    fi

    echo ""
    print_info "Domain: $DOMAIN"
    if [[ "$INCLUDE_WWW" == "yes" ]]; then
        print_info "WWW:    www.$DOMAIN (included)"
    else
        print_info "WWW:    Not included"
    fi
    print_info "Email:  $EMAIL"
    echo ""

    if ! confirm "Proceed with installation?"; then
        print_info "Installation cancelled"
        exit 0
    fi

    # Installation steps
    print_header "Installing Dependencies"
    install_dependencies
    install_docker

    print_header "Setting Up Application"
    clone_repository
    create_env_file "$DOMAIN"
    create_production_compose

    print_header "Configuring Web Server"
    setup_nginx "$DOMAIN" "$INCLUDE_WWW"

    print_header "Starting Services"
    start_services

    # Wait for services to be ready
    print_info "Waiting for services to start..."
    sleep 10

    print_header "Setting Up SSL"
    setup_ssl "$DOMAIN" "$EMAIL" "$INCLUDE_WWW"

    print_header "Finalizing"
    create_systemd_service

    print_header "Installation Complete!"
    echo ""
    echo -e "${GREEN}TEG Finance has been successfully installed!${NC}"
    echo ""
    echo "  Website:     https://$DOMAIN"
    echo "  Admin Panel: https://$DOMAIN/admin"
    echo ""
    echo "  Installation: $INSTALL_DIR"
    echo "  Logs:         docker compose -f $INSTALL_DIR/docker-compose.prod.yml logs -f"
    echo ""
    echo -e "${YELLOW}Remember to save your admin credentials shown above!${NC}"
    echo ""
}

# ============================================================================
# Main Menu
# ============================================================================

show_menu() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║           TEG Finance Website - Installation Script            ║${NC}"
    echo -e "${BLUE}╠════════════════════════════════════════════════════════════════╣${NC}"
    echo -e "${BLUE}║                                                                ║${NC}"
    echo -e "${BLUE}║   1) Install    - Fresh installation                          ║${NC}"
    echo -e "${BLUE}║   2) Update     - Update from GitHub (preserves data)         ║${NC}"
    echo -e "${BLUE}║   3) Remove     - Complete removal                            ║${NC}"
    echo -e "${BLUE}║   4) Exit                                                     ║${NC}"
    echo -e "${BLUE}║                                                                ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

main() {
    check_root
    check_ubuntu

    # If argument provided, use it
    case "${1:-}" in
        install)
            install_fresh
            exit 0
            ;;
        update)
            update_installation
            exit 0
            ;;
        remove)
            remove_installation
            exit 0
            ;;
    esac

    # Interactive menu
    while true; do
        show_menu
        read -p "Select an option [1-4]: " choice

        case $choice in
            1)
                install_fresh
                exit 0
                ;;
            2)
                update_installation
                exit 0
                ;;
            3)
                remove_installation
                exit 0
                ;;
            4)
                print_info "Goodbye!"
                exit 0
                ;;
            *)
                print_error "Invalid option"
                ;;
        esac
    done
}

main "$@"
