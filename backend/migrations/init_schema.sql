-- TEG Finance Website Database Schema
-- PostgreSQL 15

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================
-- USERS TABLE - Admin accounts with 2FA
-- ============================================
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    totp_secret VARCHAR(32),
    totp_enabled BOOLEAN DEFAULT FALSE,
    failed_login_attempts INTEGER DEFAULT 0,
    locked_until TIMESTAMP WITH TIME ZONE,
    password_reset_token VARCHAR(255),
    password_reset_expires TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_reset_token ON users(password_reset_token);

-- ============================================
-- SESSIONS TABLE - Server-side session storage
-- ============================================
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_token VARCHAR(255) UNIQUE NOT NULL,
    ip_address VARCHAR(45),
    user_agent TEXT,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sessions_token ON sessions(session_token);
CREATE INDEX idx_sessions_user ON sessions(user_id);
CREATE INDEX idx_sessions_expires ON sessions(expires_at);

-- ============================================
-- IMAGES TABLE - Uploaded media
-- ============================================
CREATE TABLE images (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    file_size INTEGER NOT NULL,
    width INTEGER,
    height INTEGER,
    alt_text VARCHAR(255),
    uploaded_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_images_filename ON images(filename);

-- ============================================
-- PAGES TABLE - Dynamic CMS content
-- ============================================
CREATE TABLE pages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    slug VARCHAR(255) UNIQUE NOT NULL,
    title VARCHAR(255) NOT NULL,
    meta_title VARCHAR(255),
    meta_description TEXT,
    content TEXT,
    hero_image_id UUID REFERENCES images(id) ON DELETE SET NULL,
    is_published BOOLEAN DEFAULT FALSE,
    is_service_page BOOLEAN DEFAULT FALSE,
    service_icon VARCHAR(100),
    service_order INTEGER DEFAULT 0,
    language VARCHAR(10) DEFAULT 'en',
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    updated_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_pages_slug ON pages(slug);
CREATE INDEX idx_pages_published ON pages(is_published);
CREATE INDEX idx_pages_service ON pages(is_service_page);

-- ============================================
-- NAVIGATION ITEMS TABLE - Menu structure
-- ============================================
CREATE TABLE navigation_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    label VARCHAR(100) NOT NULL,
    url VARCHAR(255),
    page_id UUID REFERENCES pages(id) ON DELETE SET NULL,
    parent_id UUID REFERENCES navigation_items(id) ON DELETE CASCADE,
    position INTEGER DEFAULT 0,
    is_visible BOOLEAN DEFAULT TRUE,
    open_in_new_tab BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_navigation_parent ON navigation_items(parent_id);
CREATE INDEX idx_navigation_position ON navigation_items(position);

-- ============================================
-- SITE SETTINGS TABLE - Key-value config
-- ============================================
CREATE TABLE site_settings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    setting_key VARCHAR(100) UNIQUE NOT NULL,
    setting_value TEXT,
    setting_type VARCHAR(50) DEFAULT 'string',
    is_public BOOLEAN DEFAULT FALSE,
    description TEXT,
    updated_by UUID REFERENCES users(id) ON DELETE SET NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_settings_key ON site_settings(setting_key);

-- ============================================
-- EMAIL CONFIG TABLE - SMTP settings
-- ============================================
CREATE TABLE email_config (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    smtp_host VARCHAR(255) DEFAULT 'smtp.gmail.com',
    smtp_port INTEGER DEFAULT 587,
    use_tls BOOLEAN DEFAULT TRUE,
    smtp_username VARCHAR(255),
    smtp_password VARCHAR(255),
    from_email VARCHAR(255),
    from_name VARCHAR(100) DEFAULT 'TEG Finance',
    recipient_email VARCHAR(255),
    is_configured BOOLEAN DEFAULT FALSE,
    updated_by UUID REFERENCES users(id) ON DELETE SET NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- CONTACT SUBMISSIONS TABLE - Form data
-- ============================================
CREATE TABLE contact_submissions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(30),
    subject VARCHAR(255),
    message TEXT NOT NULL,
    service_interest VARCHAR(100),
    ip_address VARCHAR(45),
    user_agent TEXT,
    is_read BOOLEAN DEFAULT FALSE,
    email_sent BOOLEAN DEFAULT FALSE,
    email_error TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_contact_read ON contact_submissions(is_read);
CREATE INDEX idx_contact_created ON contact_submissions(created_at DESC);

-- ============================================
-- AUDIT LOG TABLE - Security tracking
-- ============================================
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50),
    entity_id UUID,
    old_values JSONB,
    new_values JSONB,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_user ON audit_log(user_id);
CREATE INDEX idx_audit_action ON audit_log(action);
CREATE INDEX idx_audit_entity ON audit_log(entity_type, entity_id);
CREATE INDEX idx_audit_created ON audit_log(created_at DESC);

-- ============================================
-- DEFAULT DATA
-- ============================================

-- Insert default site settings
INSERT INTO site_settings (setting_key, setting_value, setting_type, is_public, description) VALUES
    ('site_name', 'TEG Finance', 'string', true, 'Website name displayed in header and title'),
    ('site_tagline', 'Professional Accounting & Tax Services', 'string', true, 'Tagline displayed below site name'),
    ('contact_phone', '(555) 123-4567', 'string', true, 'Main contact phone number'),
    ('contact_email', 'info@tegfinance.com', 'string', true, 'Main contact email'),
    ('contact_address', '123 Business Ave, Suite 100, City, ST 12345', 'string', true, 'Physical address'),
    ('business_hours', 'Mon-Fri: 9AM-5PM', 'string', true, 'Business hours'),
    ('facebook_url', '', 'string', true, 'Facebook page URL'),
    ('linkedin_url', '', 'string', true, 'LinkedIn profile URL'),
    ('twitter_url', '', 'string', true, 'Twitter/X profile URL'),
    ('footer_text', '© 2025 TEG Finance. All rights reserved.', 'string', true, 'Footer copyright text'),
    ('hero_title', 'Expert Financial Guidance for Your Success', 'string', true, 'Homepage hero title'),
    ('hero_subtitle', 'Professional financial services tailored to your personal and business needs.', 'string', true, 'Homepage hero subtitle'),
    ('about_text', 'With decades of combined experience, our team provides comprehensive accounting and tax services.', 'text', true, 'About section text'),
    ('meta_description', 'Professional financial services including tax preparation, business accounting, and financial consulting.', 'text', true, 'Default meta description for SEO');

-- Insert default email config
INSERT INTO email_config (smtp_host, smtp_port, use_tls, is_configured) VALUES
    ('smtp.gmail.com', 587, true, false);

-- Insert default service pages
INSERT INTO pages (slug, title, meta_title, meta_description, content, is_published, is_service_page, service_icon, service_order) VALUES
    ('tax-services', 'Tax Services', 'Tax Services | TEG Finance', 'Expert tax preparation and planning for individuals and businesses.',
     '<h2>Individual and Business Tax Services</h2><p>Our comprehensive tax services help you minimize your tax liability while ensuring full compliance with federal and state regulations.</p><h3>What We Offer</h3><ul><li>Individual Tax Preparation</li><li>Business Tax Returns</li><li>Tax Planning Strategies</li><li>IRS Representation</li><li>State and Local Tax Compliance</li></ul>',
     true, true, 'calculate', 1),

    ('business-registration', 'Business Registration', 'Business Registration | TEG Finance', 'Complete business formation and registration services.',
     '<h2>Start Your Business Right</h2><p>We guide you through the entire business formation process, from choosing the right entity type to filing all necessary paperwork.</p><h3>Services Include</h3><ul><li>Entity Selection Consulting</li><li>LLC Formation</li><li>Corporation Setup</li><li>EIN Registration</li><li>State Business Licenses</li></ul>',
     true, true, 'business', 2),

    ('accounting-bookkeeping', 'Accounting & Bookkeeping', 'Accounting Services | TEG Finance', 'Professional bookkeeping and accounting services for businesses of all sizes.',
     '<h2>Keep Your Books in Order</h2><p>Our bookkeeping services ensure accurate financial records so you can focus on growing your business.</p><h3>Our Services</h3><ul><li>Monthly Bookkeeping</li><li>Accounts Payable/Receivable</li><li>Bank Reconciliation</li><li>Payroll Processing</li><li>Financial Reporting</li></ul>',
     true, true, 'book', 3),

    ('financial-statements', 'Financial Statement Services', 'Financial Statements | TEG Finance', 'Preparation and analysis of financial statements for businesses.',
     '<h2>Clear Financial Picture</h2><p>We prepare accurate financial statements that give you insights into your business performance and satisfy lender requirements.</p><h3>Statement Services</h3><ul><li>Compilation Services</li><li>Review Engagements</li><li>Audit Services</li><li>Cash Flow Analysis</li><li>Financial Projections</li></ul>',
     true, true, 'assessment', 4),

    ('advisory-consulting', 'Advisory & Consulting', 'Business Consulting | TEG Finance', 'Strategic business advisory and consulting services.',
     '<h2>Strategic Business Guidance</h2><p>Beyond numbers, we provide strategic advice to help your business thrive and grow.</p><h3>Consulting Areas</h3><ul><li>Business Planning</li><li>Cash Flow Management</li><li>Succession Planning</li><li>M&A Advisory</li><li>Financial Analysis</li></ul>',
     true, true, 'trending_up', 5);

-- Insert default navigation items
INSERT INTO navigation_items (label, url, position, is_visible) VALUES
    ('Home', '/', 1, true),
    ('Services', '/services', 2, true),
    ('About', '/about', 3, true),
    ('Contact', '/contact', 4, true);

-- Link service pages to navigation (as children of Services)
DO $$
DECLARE
    services_nav_id UUID;
BEGIN
    SELECT id INTO services_nav_id FROM navigation_items WHERE label = 'Services';

    INSERT INTO navigation_items (label, url, parent_id, position, is_visible)
    SELECT title, '/services/' || slug, services_nav_id, service_order, true
    FROM pages WHERE is_service_page = true ORDER BY service_order;
END $$;

-- ============================================
-- FUNCTIONS AND TRIGGERS
-- ============================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply updated_at triggers
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_pages_updated_at
    BEFORE UPDATE ON pages
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_navigation_updated_at
    BEFORE UPDATE ON navigation_items
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_settings_updated_at
    BEFORE UPDATE ON site_settings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_email_config_updated_at
    BEFORE UPDATE ON email_config
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to clean expired sessions (run periodically)
CREATE OR REPLACE FUNCTION clean_expired_sessions()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM sessions WHERE expires_at < CURRENT_TIMESTAMP;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ language 'plpgsql';
