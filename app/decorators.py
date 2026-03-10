from functools import wraps
from flask import abort, flash, redirect, url_for, request
from flask_login import current_user
from flask import current_app
import time

def login_required(f):
    """Enhanced login required decorator with account verification check"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        
        if not current_user.is_verified:
            flash('Please verify your email address before accessing this page.', 'warning')
            return redirect(url_for('auth.resend_verification'))
        
        if not current_user.is_active:
            flash('Your account has been deactivated. Please contact support.', 'danger')
            return redirect(url_for('auth.logout'))
        
        # Update last activity
        from datetime import datetime
        current_user.last_activity = datetime.utcnow()
        from app import db
        db.session.commit()
        
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Admin only decorator"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def subscription_required(tier='pro'):
    """Check if user has required subscription tier"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('auth.login', next=request.url))
            
            tiers = {'free': 0, 'pro': 1, 'enterprise': 2}
            if tiers.get(current_user.subscription_tier, 0) < tiers.get(tier, 1):
                flash(f'This feature requires {tier} subscription. Please upgrade your plan.', 'warning')
                return redirect(url_for('dashboard.billing'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def check_log_limit(f):
    """Check if user has not exceeded monthly log limit"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from app.services.log_service import LogService
        
        log_service = LogService()
        current_count = log_service.get_current_month_log_count(current_user.public_id)
        
        if current_count >= current_user.monthly_log_limit:
            flash('You have exceeded your monthly log limit. Please upgrade your plan.', 'warning')
            return redirect(url_for('dashboard.billing'))
        
        return f(*args, **kwargs)
    return decorated_function

def rate_limit(limit=100, per=60):
    """Rate limiting decorator"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from flask import request, g
            import time
            from collections import defaultdict
            
            # Simple in-memory rate limiting (use Redis in production)
            if not hasattr(g, 'rate_limits'):
                g.rate_limits = defaultdict(list)
            
            key = f"{request.remote_addr}:{request.endpoint}"
            now = time.time()
            
            # Clean old requests
            g.rate_limits[key] = [t for t in g.rate_limits[key] if t > now - per]
            
            if len(g.rate_limits[key]) >= limit:
                abort(429, description=f"Rate limit exceeded. Max {limit} requests per {per} seconds.")
            
            g.rate_limits[key].append(now)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def two_factor_required(f):
    """Require 2FA if enabled for user"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.is_authenticated and current_user.two_factor_enabled:
            from flask import session
            if not session.get('2fa_verified', False):
                return redirect(url_for('auth.two_factor'))
        return f(*args, **kwargs)
    return decorated_function