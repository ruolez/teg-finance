import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Tuple, Optional

from backend import database as db

logger = logging.getLogger(__name__)


def get_smtp_connection():
    config = db.get_email_config()

    if not config or not config.get('is_configured'):
        return None, None

    try:
        if config.get('use_tls'):
            server = smtplib.SMTP(config['smtp_host'], config['smtp_port'])
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(config['smtp_host'], config['smtp_port'])

        if config.get('smtp_username') and config.get('smtp_password'):
            server.login(config['smtp_username'], config['smtp_password'])

        return server, config
    except Exception as e:
        logger.error(f"SMTP connection failed: {e}")
        return None, None


def send_email(to: str, subject: str, body_html: str, body_text: str = None) -> Tuple[bool, Optional[str]]:
    server, config = get_smtp_connection()

    if not server:
        return False, "Email not configured"

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"{config.get('from_name', 'TEG Finance')} <{config['from_email']}>"
        msg['To'] = to

        # Plain text version
        if body_text:
            part1 = MIMEText(body_text, 'plain')
            msg.attach(part1)

        # HTML version
        part2 = MIMEText(body_html, 'html')
        msg.attach(part2)

        server.sendmail(config['from_email'], to, msg.as_string())
        server.quit()

        return True, None
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        try:
            server.quit()
        except:
            pass
        return False, str(e)


def send_contact_notification(submission: dict) -> Tuple[bool, Optional[str]]:
    config = db.get_email_config()

    if not config or not config.get('is_configured') or not config.get('recipient_email'):
        logger.warning("Email not configured for contact notifications")
        return False, "Email not configured"

    subject = f"New Contact Form Submission: {submission.get('subject', 'No Subject')}"

    body_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #16A085; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; background: #f9f9f9; }}
            .field {{ margin-bottom: 15px; }}
            .label {{ font-weight: bold; color: #16A085; }}
            .value {{ margin-top: 5px; }}
            .footer {{ padding: 20px; text-align: center; font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>New Contact Form Submission</h2>
            </div>
            <div class="content">
                <div class="field">
                    <div class="label">Name:</div>
                    <div class="value">{submission.get('name', 'N/A')}</div>
                </div>
                <div class="field">
                    <div class="label">Email:</div>
                    <div class="value">{submission.get('email', 'N/A')}</div>
                </div>
                <div class="field">
                    <div class="label">Phone:</div>
                    <div class="value">{submission.get('phone', 'N/A') or 'Not provided'}</div>
                </div>
                <div class="field">
                    <div class="label">Service Interest:</div>
                    <div class="value">{submission.get('service_interest', 'N/A') or 'Not specified'}</div>
                </div>
                <div class="field">
                    <div class="label">Subject:</div>
                    <div class="value">{submission.get('subject', 'N/A') or 'No subject'}</div>
                </div>
                <div class="field">
                    <div class="label">Message:</div>
                    <div class="value">{submission.get('message', 'N/A')}</div>
                </div>
            </div>
            <div class="footer">
                This email was sent from your website contact form.
            </div>
        </div>
    </body>
    </html>
    """

    body_text = f"""
New Contact Form Submission

Name: {submission.get('name', 'N/A')}
Email: {submission.get('email', 'N/A')}
Phone: {submission.get('phone', 'N/A') or 'Not provided'}
Service Interest: {submission.get('service_interest', 'N/A') or 'Not specified'}
Subject: {submission.get('subject', 'N/A') or 'No subject'}

Message:
{submission.get('message', 'N/A')}

---
This email was sent from your website contact form.
    """

    return send_email(config['recipient_email'], subject, body_html, body_text)


def send_password_reset_email(email: str, token: str) -> Tuple[bool, Optional[str]]:
    # Note: In production, use HTTPS and proper domain
    reset_url = f"http://localhost/admin/reset-password?token={token}"

    subject = "Password Reset Request - TEG Finance Admin"

    body_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #16A085; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 30px; background: #f9f9f9; text-align: center; }}
            .button {{ display: inline-block; padding: 15px 30px; background: #16A085; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
            .footer {{ padding: 20px; text-align: center; font-size: 12px; color: #666; }}
            .warning {{ color: #dc3545; font-size: 13px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>Password Reset Request</h2>
            </div>
            <div class="content">
                <p>You have requested to reset your password for the TEG Finance admin panel.</p>
                <p>Click the button below to reset your password:</p>
                <a href="{reset_url}" class="button">Reset Password</a>
                <p class="warning">This link will expire in 1 hour.</p>
                <p>If you did not request this password reset, please ignore this email.</p>
            </div>
            <div class="footer">
                <p>TEG Finance Admin Panel</p>
            </div>
        </div>
    </body>
    </html>
    """

    body_text = f"""
Password Reset Request

You have requested to reset your password for the TEG Finance admin panel.

Click the link below to reset your password:
{reset_url}

This link will expire in 1 hour.

If you did not request this password reset, please ignore this email.

---
TEG Finance Admin Panel
    """

    return send_email(email, subject, body_html, body_text)


def send_test_email() -> Tuple[bool, Optional[str]]:
    config = db.get_email_config()

    if not config or not config.get('recipient_email'):
        return False, "Recipient email not configured"

    subject = "Test Email - TEG Finance Admin"

    body_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
            .container { max-width: 600px; margin: 0 auto; padding: 20px; }
            .header { background: #16A085; color: white; padding: 20px; text-align: center; }
            .content { padding: 30px; background: #f9f9f9; text-align: center; }
            .success { color: #28a745; font-size: 48px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>Email Configuration Test</h2>
            </div>
            <div class="content">
                <div class="success">✓</div>
                <h3>Success!</h3>
                <p>Your email configuration is working correctly.</p>
                <p>Contact form submissions will be sent to this email address.</p>
            </div>
        </div>
    </body>
    </html>
    """

    body_text = """
Email Configuration Test

Success!

Your email configuration is working correctly.
Contact form submissions will be sent to this email address.
    """

    return send_email(config['recipient_email'], subject, body_html, body_text)
