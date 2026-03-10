from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, current_user, login_required
from app import db
import os
from app.models.user_models import User, APIKey
from app.form import (
    LoginForm, RegistrationForm, RequestPasswordResetForm,
    ResetPasswordForm, ChangePasswordForm, ProfileUpdateForm,
    TwoFactorForm
)
from app.utils.auth_utils import (
    send_verification_email, send_password_reset_email, confirm_token,
    verify_reset_token, generate_2fa_secret, generate_2fa_qr,
    verify_2fa_token, log_login_attempt, send_otp_email
)
from datetime import datetime
import pyotp

bp = Blueprint('auth', __name__, url_prefix='/auth')

@bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration with phone number"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        # Check if user exists
        existing = User.query.filter_by(email=form.email.data.lower()).first()
        if existing:
            flash('Email already registered. Please login.', 'info')
            return redirect(url_for('auth.login'))
        
        # Create user with phone
        full_phone = f"{form.country_code.data}{form.phone.data}"
        
        user = User(
            username=form.username.data,
            email=form.email.data.lower(),
            full_name=form.full_name.data,
            company_name=form.company_name.data,
            website_url=form.website_url.data,
            country_code=form.country_code.data,
            phone=form.phone.data,
            phone_verified=False,  # Will verify via OTP
            is_verified=False      # Will verify via email OTP
        )
        user.set_password(form.password.data)
        
        db.session.add(user)
        db.session.commit()
        
        # Send email OTP
        email_success, email_message = send_otp_email(user)
        
        # Send phone OTP (if SMS service available)
        # phone_success, phone_message = send_sms_otp(user)
        
        if email_success:
            session['verify_email'] = user.email
            flash(f'OTP sent to {user.email}. Please verify your email.', 'success')
            
            
            return redirect(url_for('auth.verify_otp', email=user.email))
        else:
            flash(f'Error sending OTP: {email_message}', 'danger')
            return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html', title='Register', form=form)
@bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login - Fixed auto-login issue"""
    
    # # 🔥 IMPORTANT: Session check and cleanup
    if current_user.is_authenticated:
        # Double-check if session is valid
        try:
            # Try to access user data to verify session
            _ = current_user.id
        except:
            # Invalid session - logout
            logout_user()
            session.clear()
        else:
            # Valid session - redirect to dashboard
            return redirect(url_for('dashboard.index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        
        # Log attempt details
        ip_address = request.remote_addr
        user_agent = request.user_agent.string
        
        if user and user.check_password(form.password.data):
            if not user.is_verified:
                flash('Please verify your email address before logging in.', 'warning')
                return redirect(url_for('auth.resend_verification', email=user.email))
            
            if not user.is_active:
                flash('Your account has been deactivated. Please contact support.', 'danger')
                return redirect(url_for('auth.login'))
            
            # ✅ Proper login with remember me
            login_user(user, remember=form.remember_me.data)
            
            # Update user info
            user.last_login = datetime.utcnow()
            user.last_login_ip = ip_address
            db.session.commit()
            
            # Log successful login
            log_login_attempt(user, True, ip_address, user_agent)
            
            flash(f'Welcome back, {user.full_name or user.username}!', 'success')
            
            # Check for 2FA
            if user.two_factor_enabled:
                session['2fa_required'] = True
                return redirect(url_for('auth.two_factor'))
            
            next_page = request.args.get('next')
            # Validate next_page to prevent open redirect
            if next_page and not next_page.startswith('/'):
                next_page = None
            return redirect(next_page) if next_page else redirect(url_for('dashboard.index'))
        else:
            # Log failed attempt
            log_login_attempt(user, False, ip_address, user_agent)
            flash('Invalid email or password.', 'danger')
    
    return render_template('auth/login.html', title='Login', form=form)
    
@bp.route('/logout')
@login_required
def logout():
    """User logout - Saari cookies remove karo"""
    
    # 1. User ko logout karo
    logout_user()
    
    # 2. Saari session data clear karo
    session.clear()
    
    # 3. Response banao
    response = redirect(url_for('auth.login'))
    
    # 4. 🔥 SAARI COOKIES DELETE KARO
    # Session cookie delete
    response.delete_cookie('session')  # Flask default session cookie
    response.delete_cookie('remember_token')  # Flask-Login remember cookie
    response.delete_cookie('permanent_session')  # Agar ho to
    
    # 5. Agar custom cookies ho to unhe bhi delete karo
    response.delete_cookie('user_preferences')
    response.delete_cookie('theme')
    response.delete_cookie('language')
    
    flash('You have been logged out successfully.', 'success')
    return response
@bp.route('/verify-phone', methods=['GET', 'POST'])
def verify_phone():
    """Verify phone number with OTP"""
    
    if 'phone_verify_email' not in session:
        flash('Session expired. Please try again.', 'warning')
        return redirect(url_for('auth.profile'))
    
    email = session['phone_verify_email']
    user = User.query.filter_by(email=email).first()
    
    if not user:
        session.pop('phone_verify_email', None)
        flash('User not found.', 'danger')
        return redirect(url_for('auth.profile'))
    
    if request.method == 'POST':
        otp = request.form.get('otp', '').strip()
        
        if not otp or len(otp) != 6 or not otp.isdigit():
            flash('Please enter a valid 6-digit OTP.', 'danger')
            return render_template('auth/verify_phone.html', phone=f"{user.country_code}{user.phone}")
        
        # Verify OTP
        from app.utils.sms_utils import verify_phone_otp
        success, message = verify_phone_otp(user, otp)
        
        if success:
            session.pop('phone_verify_email', None)
            flash('Phone number verified successfully!', 'success')
            return redirect(url_for('auth.profile'))
        else:
            flash(message, 'danger')
    
    return render_template('auth/verify_phone.html', phone=f"{user.country_code}{user.phone}")

@bp.route('/send-phone-otp', methods=['POST'])
def send_phone_otp_route():
    """Send OTP to phone"""
    
    if not current_user.is_authenticated:
        flash('Please login first.', 'warning')
        return redirect(url_for('auth.login'))
    
    # Send OTP
    from app.utils.sms_utils import send_phone_otp
    success, message = send_phone_otp(current_user)
    
    if success:
        session['phone_verify_email'] = current_user.email
        flash(f'OTP sent to {current_user.country_code}{current_user.phone}', 'success')
    else:
        flash(f'Error sending OTP: {message}', 'danger')
    
    return redirect(url_for('auth.verify_phone'))
    
@bp.route('/confirm-email/<token>')
def confirm_email(token):
    """Confirm email address"""
    email = confirm_token(token)
    if not email:
        flash('The confirmation link is invalid or has expired.', 'danger')
        return redirect(url_for('auth.login'))
    
    user = User.query.filter_by(email=email).first()
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('auth.login'))
    
    if user.is_verified:
        flash('Account already verified. Please login.', 'info')
    else:
        user.is_verified = True
        db.session.commit()
        flash('Your email has been verified! You can now login.', 'success')
    
    return redirect(url_for('auth.login'))

@bp.route('/resend-verification', methods=['GET', 'POST'])
def resend_verification():
    """Resend verification email"""
    
    # 📝 POST request - Form submit hua hai
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        
        print(f"📧 POST request received for email: {email}")  # Debug
        
        if not email:
            flash('Please enter an email address.', 'warning')
            return redirect(url_for('auth.resend_verification'))
        
        # User find karo
        from sqlalchemy import func
        user = User.query.filter(func.lower(User.email) == func.lower(email)).first()
        
        if not user:
            print(f"❌ User not found: {email}")
            flash(f'No account found with email: {email}', 'danger')
            return redirect(url_for('auth.resend_verification'))
        
        if user.is_verified:
            print(f"✅ User already verified: {email}")
            flash('This account is already verified. Please login.', 'info')
            return redirect(url_for('auth.login'))
        
        # Send verification email
        try:
            send_verification_email(user)
            print(f"✅ Verification email sent to: {email}")
            
            # Success page dikhao - template mein success message ke saath
            return render_template('auth/resend_verification.html', email_sent=True, email=email)
            
        except Exception as e:
            print(f"❌ Error sending email: {e}")
            flash(f'Error sending email: {str(e)}', 'danger')
            return redirect(url_for('auth.resend_verification'))
    
    # 👁️ GET request - Form dikhao
    email = request.args.get('email', '')
    return render_template('auth/resend_verification.html', email=email, email_sent=False)

    
@bp.route('/reset-password-request', methods=['GET', 'POST'])
def reset_password_request():
    """Request password reset"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    form = RequestPasswordResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        if user:
            send_password_reset_email(user)

            flash('Check your email for instructions to reset your password.', 'info')
        else:
            # Don't reveal if email exists
            flash('If an account exists with this email, you will receive reset instructions.', 'info')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/reset_password_request.html', title='Reset Password', form=form)

@bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Reset password with token"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    user_id = verify_reset_token(token)
    if not user_id:
        flash('The password reset link is invalid or has expired.', 'danger')
        return redirect(url_for('auth.reset_password_request'))
    
    user = User.query.get(user_id)
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('auth.login'))
    
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash('Your password has been reset. You can now login.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/reset_password.html', title='Reset Password', form=form)

@bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """View and edit user profile"""
    form = ProfileUpdateForm()
    
    if form.validate_on_submit():
        current_user.full_name = form.full_name.data
        current_user.company_name = form.company_name.data
        current_user.website_url = form.website_url.data
        current_user.phone = form.phone.data
        db.session.commit()
        flash('Your profile has been updated.', 'success')
        return redirect(url_for('auth.profile'))
    
    # Pre-populate form
    form.full_name.data = current_user.full_name
    form.company_name.data = current_user.company_name
    form.website_url.data = current_user.website_url
    form.phone.data = current_user.phone
    
    # Get recent activity (you'll need to implement this)
    recent_activity = []

    if current_user.last_login:
        recent_activity.append({
            'icon': 'sign-in-alt',
            'title': f'Logged in from {current_user.last_login_ip or "unknown location"}',
            'time': current_user.last_login.strftime('%Y-%m-%d %H:%M')
        })
    
    # 2. API key activities (last 3)
    for key in current_user.api_keys.order_by(APIKey.created_at.desc()).limit(3):
        recent_activity.append({
            'icon': 'key',
            'title': f'Created API key "{key.name}"',
            'time': key.created_at.strftime('%Y-%m-%d %H:%M')
        })
    
    return render_template('auth/profile.html', title='Profile', form=form, recent_activity=recent_activity)

@bp.route('/deactivate', methods=['POST'])
@login_required
def deactivate_account():
    """Deactivate user account"""
    try:
        # Don't allow deactivation if user is admin or has active subscription
        if current_user.is_admin:
            flash('Admin accounts cannot be deactivated.', 'danger')
            return redirect(url_for('auth.profile'))
        
        # Deactivate account
        current_user.is_active = False
        db.session.commit()
        
        # Logout user
        logout_user()
        session.clear()
        
        flash('Your account has been deactivated. You can reactivate by contacting support.', 'info')
        return redirect(url_for('main.index'))
        
    except Exception as e:
        flash(f'Error deactivating account: {str(e)}', 'danger')
        return redirect(url_for('auth.profile'))

@bp.route('/delete', methods=['POST'])
@login_required
def delete_account():
    """Permanently delete user account"""
    try:
        # Don't allow deletion if user is admin
        if current_user.is_admin:
            flash('Admin accounts cannot be deleted.', 'danger')
            return redirect(url_for('auth.profile'))
        
        # Store user id for logging
        user_id = current_user.id
        user_email = current_user.email
        
        # Delete user's API keys first
        for key in current_user.api_keys:
            db.session.delete(key)
        
        # Delete user's webhooks
        for webhook in current_user.webhooks:
            db.session.delete(webhook)
        
        # Delete team memberships
        for team_member in current_user.teams:
            db.session.delete(team_member)
        
        # Delete login logs
        from app.models.user_models import LoginLog
        LoginLog.query.filter_by(user_id=user_id).delete()
        
        # Finally delete the user
        db.session.delete(current_user)
        db.session.commit()
        
        # Logout user
        logout_user()
        session.clear()
        
        print(f"User {user_email} deleted their account")
        flash('Your account has been permanently deleted.', 'success')
        return redirect(url_for('main.index'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting account: {str(e)}', 'danger')
        return redirect(url_for('auth.profile'))

@bp.route('/reactivate', methods=['GET', 'POST'])
def reactivate_account():
    """Reactivate deactivated account"""
    if request.method == 'POST':
        email = request.form.get('email', '').lower().strip()
        user = User.query.filter_by(email=email).first()
        
        if user and not user.is_active:
            # Send reactivation email
            token = generate_confirmation_token(user.email)
            reactivate_url = url_for('auth.confirm_reactivation', token=token, _external=True)
            
            send_email(
                subject='Reactivate Your Account - Agent SDK Platform',
                recipients=[user.email],
                text_body=f'Click the link to reactivate your account: {reactivate_url}',
                html_body=f'<h1>Reactivate Account</h1><p>Click <a href="{reactivate_url}">here</a> to reactivate.</p>'
            )
            
            flash('Reactivation email sent. Please check your inbox.', 'success')
            return redirect(url_for('auth.login'))
        else:
            flash('No inactive account found with that email.', 'danger')
    
    return render_template('auth/reactivate.html', title='Reactivate Account')

@bp.route('/confirm-reactivation/<token>')
def confirm_reactivation(token):
    """Confirm account reactivation"""
    email = confirm_token(token)
    if not email:
        flash('The reactivation link is invalid or has expired.', 'danger')
        return redirect(url_for('auth.login'))
    
    user = User.query.filter_by(email=email).first()
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('auth.login'))
    
    if user.is_active:
        flash('Account is already active.', 'info')
    else:
        user.is_active = True
        db.session.commit()
        flash('Your account has been reactivated. You can now login.', 'success')
    
    return redirect(url_for('auth.login'))

@bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Change user password"""
    form = ChangePasswordForm()
    
    if form.validate_on_submit():
        if current_user.check_password(form.current_password.data):
            current_user.set_password(form.new_password.data)
            db.session.commit()
            flash('Your password has been changed.', 'success')
            return redirect(url_for('auth.profile'))
        else:
            flash('Current password is incorrect.', 'danger')
    
    return render_template('auth/change_password.html', title='Change Password', form=form)
    

@bp.route('/two-factor/setup', methods=['GET', 'POST'])
@login_required
def two_factor_setup():
    """Setup two-factor authentication"""
    if not current_user.two_factor_secret:
        current_user.two_factor_secret = generate_2fa_secret()
        db.session.commit()
    
    qr_code = generate_2fa_qr(current_user.two_factor_secret, current_user.email)
    
    if request.method == 'POST':
        token = request.form.get('token')
        if verify_2fa_token(current_user.two_factor_secret, token):
            current_user.two_factor_enabled = True
            db.session.commit()
            flash('Two-factor authentication has been enabled.', 'success')
            return redirect(url_for('auth.profile'))
        else:
            flash('Invalid verification code.', 'danger')
    
    return render_template('auth/two_factor_setup.html', 
                         title='Setup 2FA', 
                         secret=current_user.two_factor_secret,
                         qr_code=qr_code)

@bp.route('/two-factor/disable', methods=['POST'])
@login_required
def two_factor_disable():
    """Disable two-factor authentication"""
    current_user.two_factor_enabled = False
    current_user.two_factor_secret = None
    db.session.commit()
    flash('Two-factor authentication has been disabled.', 'success')
    return redirect(url_for('auth.profile'))

@bp.route('/two-factor', methods=['GET', 'POST'])
def two_factor():
    """Two-factor authentication verification"""
    if not session.get('2fa_required'):
        return redirect(url_for('dashboard.index'))
    
    form = TwoFactorForm()
    if form.validate_on_submit():
        user = current_user
        if verify_2fa_token(user.two_factor_secret, form.token.data):
            session['2fa_verified'] = True
            session.pop('2fa_required', None)
            flash('Two-factor authentication successful.', 'success')
            return redirect(url_for('dashboard.index'))
        else:
            flash('Invalid authentication code.', 'danger')
    
    return render_template('auth/two_factor.html', title='Two-Factor Authentication', form=form)

@bp.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    """OTP verification page"""
    # Get email from session or query param
    email = session.get('verify_email') or request.args.get('email')
    
    if not email:
        flash('Email not found. Please register again.', 'danger')
        return redirect(url_for('auth.register'))
    
    user = User.query.filter_by(email=email).first()
    
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('auth.register'))
    
    if request.method == 'POST':
        otp = request.form.get('otp', '').strip()
        
        if not otp or len(otp) != 6 or not otp.isdigit():
            flash('Please enter a valid 6-digit OTP.', 'danger')
            return render_template('auth/verify_otp.html', email=email)
        
        success, message = user.verify_otp(otp)
        
        if success:
            session.pop('verify_email', None)
            flash('Email verified successfully! You can now login.', 'success')
            return redirect(url_for('auth.login'))
        else:
            flash(message, 'danger')
            
            # If too many attempts, redirect to register
            if 'Too many attempts' in message:
                return redirect(url_for('auth.register'))
    
    return render_template('auth/verify_otp.html', email=email)

@bp.route('/resend-otp', methods=['POST'])
def resend_otp():
    """Resend OTP code"""
    email = request.form.get('email')
    
    if not email:
        flash('Email not provided.', 'danger')
        return redirect(url_for('auth.register'))
    
    user = User.query.filter_by(email=email).first()
    
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('auth.register'))
    
    # Check if user is already verified
    if user.is_verified:
        flash('Email already verified. Please login.', 'info')
        return redirect(url_for('auth.login'))
    
    # Resend OTP
    success, message = send_otp_email(user)
    
    if success:
        flash(f'New OTP sent to {email}. Valid for 10 minutes.', 'success')
    else:
        flash(f'Error sending OTP: {message}', 'danger')
    
    return redirect(url_for('auth.verify_otp', email=email))