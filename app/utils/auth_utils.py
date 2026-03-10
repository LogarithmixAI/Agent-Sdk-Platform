from itsdangerous import URLSafeTimedSerializer
from flask import current_app, url_for
from flask_mail import Message
from app import mail
from threading import Thread
import pyotp
import qrcode
import io
import base64
from flask import render_template
from datetime import datetime, timedelta
import secrets

def generate_confirmation_token(email):
    """Generate email confirmation token"""
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(email, salt='email-confirm')

def confirm_token(token, expiration=3600):
    """Confirm email token"""
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = serializer.loads(
            token,
            salt='email-confirm',
            max_age=expiration
        )
    except:
        return False
    return email

def generate_reset_token(user_id):
    """Generate password reset token"""
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(user_id, salt='password-reset')

def verify_reset_token(token, expiration=3600):
    """Verify password reset token"""
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        user_id = serializer.loads(
            token,
            salt='password-reset',
            max_age=expiration
        )
    except:
        return None
    return user_id

def send_async_email(app, msg):
    """Send email asynchronously"""
    with app.app_context():
        try:
            mail.send(msg)
            print(f"✅ Email sent successfully to {msg.recipients}")
        except Exception as e:
            print(f"❌ Error sending email: {str(e)}")

def send_email(subject, recipients, text_body, html_body=None, sender=None):
    """Send email using Flask-Mail"""
    try:
        # Agar sender nahi diya to config se lo
        if not sender:
            sender = current_app.config.get('MAIL_DEFAULT_SENDER') or current_app.config.get('MAIL_USERNAME')
        
        # Sender ke saath message banao
        msg = Message(subject, recipients=recipients, sender=sender)
        msg.body = text_body
        msg.html = html_body
        
        # Send asynchronously
        Thread(target=send_async_email, args=(current_app._get_current_object(), msg)).start()
        return True, "Email queued for sending"
    except Exception as e:
        print(f"❌ Error in send_email: {str(e)}")
        return False, str(e)

def send_verification_email(user):
    """Send email verification link"""
    try:
        token = generate_confirmation_token(user.email)
        confirm_url = url_for('auth.confirm_email', token=token, _external=True)
        
        html_body = f'''
        <h1>Welcome to Agent SDK Platform!</h1>
        <p>Hi {user.full_name or user.username},</p>
        <p>Please verify your email address by clicking the link below:</p>
        <p><a href="{confirm_url}">Verify Email Address</a></p>
        <p>This link will expire in 1 hour.</p>
        <br>
        <p>If you didn't register for an account, please ignore this email.</p>
        '''
        
        text_body = f'''
        Welcome to Agent SDK Platform!
        
        Hi {user.full_name or user.username},
        
        Please verify your email address by clicking the link below:
        {confirm_url}
        
        This link will expire in 1 hour.
        
        If you didn't register for an account, please ignore this email.
        '''
        
        success, message = send_email(
            subject='Verify Your Email - Agent SDK Platform',
            recipients=[user.email],
            text_body=text_body,
            html_body=html_body
        )
        
        return success, message
        
    except Exception as e:
        print(f"❌ Error in send_verification_email: {str(e)}")
        return False, str(e)

def send_password_reset_email(user):
    """Send password reset email"""
    try:
        token = generate_reset_token(user.id)
        reset_url = url_for('auth.reset_password', token=token, _external=True)
        
        html_body = f'''
        <h1>Password Reset Request</h1>
        <p>Hi {user.full_name or user.username},</p>
        <p>We received a request to reset your password. Click the link below to set a new password:</p>
        <p><a href="{reset_url}">Reset Password</a></p>
        <p>This link will expire in 1 hour.</p>
        <br>
        <p>If you didn't request a password reset, please ignore this email or contact support.</p>
        '''
        
        text_body = f'''
        Password Reset Request
        
        Hi {user.full_name or user.username},
        
        We received a request to reset your password. Click the link below to set a new password:
        {reset_url}
        
        This link will expire in 1 hour.
        
        If you didn't request a password reset, please ignore this email or contact support.
        '''
        
        success, message = send_email(
            subject='Password Reset Request - Agent SDK Platform',
            recipients=[user.email],
            text_body=text_body,
            html_body=html_body
        )
        
        return success, message
        
    except Exception as e:
        print(f"❌ Error in send_password_reset_email: {str(e)}")
        return False, str(e)

def generate_2fa_secret():
    """Generate 2FA secret for user"""
    return pyotp.random_base32()

def get_2fa_uri(secret, username):
    """Get 2FA URI for QR code"""
    return pyotp.totp.TOTP(secret).provisioning_uri(
        name=username,
        issuer_name="Agent SDK Platform"
    )

def generate_2fa_qr(secret, username):
    """Generate 2FA QR code as base64 image"""
    uri = get_2fa_uri(secret, username)
    img = qrcode.make(uri)
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    return base64.b64encode(buffer.getvalue()).decode()

def verify_2fa_token(secret, token):
    """Verify 2FA token"""
    totp = pyotp.TOTP(secret)
    return totp.verify(token)

def rate_limit_key_func():
    """Generate rate limit key based on IP and endpoint"""
    from flask import request
    return f"rate_limit:{request.remote_addr}:{request.endpoint}"

def log_login_attempt(user, success, ip_address, user_agent):
    """Log login attempts for security monitoring"""
    from app.models.user_models import LoginLog
    from app import db
    
    log = LoginLog(
        user_id=user.id if user else None,
        email=user.email if user else 'unknown',
        success=success,
        ip_address=ip_address,
        user_agent=user_agent
    )
    db.session.add(log)
    db.session.commit()

def send_otp_email(user):
    """Send OTP verification email"""
    try:
        # Generate OTP
        otp = user.generate_otp()
        
        # Render email template
        html_body = render_template('email/otp_email.html', 
                                   name=user.full_name or user.username,
                                   otp=otp)
        
        text_body = f"""
        Agent SDK Platform - Email Verification
        
        Hello {user.full_name or user.username},
        
        Your OTP for email verification is: {otp}
        
        This OTP is valid for 10 minutes.
        
        Don't share this OTP with anyone.
        
        Thanks,
        Agent SDK Team
        """
        
        # Send email
        success, message = send_email(
            subject='Verify Your Email - Agent SDK Platform',
            recipients=[user.email],
            text_body=text_body,
            html_body=html_body
        )
        
        return success, message
        
    except Exception as e:
        print(f"Error sending OTP: {e}")
        return False, str(e)