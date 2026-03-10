from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import uuid
import secrets

class User(UserMixin, db.Model):
    """User account model - stored in SQL database"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(50), unique=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(200), nullable=False)
    
    # Profile information
    full_name = db.Column(db.String(100))
    company_name = db.Column(db.String(100))
    website_url = db.Column(db.String(200))
    phone = db.Column(db.String(20))
    avatar = db.Column(db.String(200), default='default-avatar.png')
    
    # Account status
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    
    # Subscription
    subscription_tier = db.Column(db.String(20), default='free')  # free, pro, enterprise
    subscription_status = db.Column(db.String(20), default='active')
    subscription_expires = db.Column(db.DateTime, nullable=True)
    
    # Usage limits based on subscription
    monthly_log_limit = db.Column(db.Integer, default=10000)  # 10k logs/month for free tier
    api_rate_limit = db.Column(db.Integer, default=100)  # requests per minute
    max_api_keys = db.Column(db.Integer, default=5)  # max number of API keys
    
    # Statistics
    total_logs = db.Column(db.BigInteger, default=0)
    total_sessions = db.Column(db.BigInteger, default=0)
    last_login = db.Column(db.DateTime)
    last_activity = db.Column(db.DateTime)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    api_keys = db.relationship('APIKey', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    webhooks = db.relationship('Webhook', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    teams = db.relationship('TeamMember', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    
    # Authentication fields
    two_factor_enabled = db.Column(db.Boolean, default=False)
    two_factor_secret = db.Column(db.String(100), nullable=True)
    last_login_ip = db.Column(db.String(45))
    login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)
    
    # Email verification
    email_verified_at = db.Column(db.DateTime, nullable=True)
    verification_sent_at = db.Column(db.DateTime, nullable=True)

    # Phone fields - add karo
    phone = db.Column(db.String(20), nullable=True)
    phone_verified = db.Column(db.Boolean, default=False)
    phone_otp_code = db.Column(db.String(6), nullable=True)
    phone_otp_created_at = db.Column(db.DateTime, nullable=True)
    phone_otp_attempts = db.Column(db.Integer, default=0)
    
    # Country code for international numbers
    country_code = db.Column(db.String(5), default='+91')  # Default India

    # OTP fields for verification
    otp_code = db.Column(db.String(6), nullable=True)
    otp_created_at = db.Column(db.DateTime, nullable=True)
    otp_attempts = db.Column(db.Integer, default=0)
    otp_verified = db.Column(db.Boolean, default=False)
    
    # Security
    password_changed_at = db.Column(db.DateTime, nullable=True)
    force_password_change = db.Column(db.Boolean, default=False)
    
    # API and rate limiting
    api_calls_today = db.Column(db.Integer, default=0)
    last_api_call = db.Column(db.DateTime, nullable=True)

    def get_sessions_count(self):
        """
        Get unique sessions (instances) count for this user
        Returns: integer count of unique instance_ids
        """
        from app import mongo
        
        if mongo is None or not hasattr(mongo, 'db') or mongo.db is None:
            return 0
        
        try:
            # Using distinct to get unique instance_ids
            unique_instances = mongo.db.logs.distinct(
                'processed_events.instance_id', 
                {'user_id': self.public_id}
            )
            return len(unique_instances)
            
        except Exception:
            return 0


    def get_projects_count(self):
        """
        Get unique projects count for this user
        Returns: integer count of unique projects
        """
        from app import mongo
        
        if mongo is None or not hasattr(mongo, 'db') or mongo.db is None:
            return 0
        
        try:
            # Get distinct projects from batch_meta
            projects = mongo.db.logs.distinct(
                'batch_meta.project', 
                {'user_id': self.public_id}
            )
            
            # Filter out None/empty values
            valid_projects = [p for p in projects if p]
            return len(valid_projects)
            
        except Exception:
            return 0

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def get_id(self):
        return str(self.id)
    
    def increment_log_count(self):
        self.total_logs += 1
        db.session.commit()
    
    def check_log_limit(self):
        """Check if user has exceeded monthly log limit"""
        # Get current month's log count from MongoDB
        from app.services.log_service import get_current_month_log_count
        current_count = get_current_month_log_count(self.public_id)
        return current_count < self.monthly_log_limit
    
    def to_dict(self):
        return {
            'public_id': self.public_id,
            'email': self.email,
            'username': self.username,
            'full_name': self.full_name,
            'company_name': self.company_name,
            'website_url': self.website_url,
            'subscription_tier': self.subscription_tier,
            'total_logs': self.total_logs,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def lock_account(self, minutes=30):
        """Lock account for specified minutes"""
        self.locked_until = datetime.utcnow() + timedelta(minutes=minutes)
        db.session.commit()
    
    def is_locked(self):
        """Check if account is locked"""
        if self.locked_until and self.locked_until > datetime.utcnow():
            return True
        return False
    
    def increment_login_attempts(self):
        """Increment failed login attempts"""
        self.login_attempts += 1
        if self.login_attempts >= 5:
            self.lock_account()
        db.session.commit()
    
    def reset_login_attempts(self):
        """Reset failed login attempts"""
        self.login_attempts = 0
        self.locked_until = None
        db.session.commit()

    def generate_otp(self):
    
        """Generate 6-digit OTP"""
        import random
        self.otp_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        self.otp_created_at = datetime.utcnow()
        self.otp_attempts = 0
        db.session.commit()
        return self.otp_code
    
    def verify_otp(self, otp):
        """Verify OTP code"""
        # Check if OTP exists and not expired (10 minutes)
        if not self.otp_code or not self.otp_created_at:
            return False, "No OTP generated"
        
        # Check expiration (10 minutes)
        if datetime.utcnow() - self.otp_created_at > timedelta(minutes=10):
            return False, "OTP expired"
        
        # Check attempts (max 3)
        if self.otp_attempts >= 3:
            return False, "Too many failed attempts"
        
        # Verify OTP
        if self.otp_code == otp:
            self.otp_code = None
            self.otp_created_at = None
            self.otp_attempts = 0
            self.is_verified = True
            db.session.commit()
            return True, "OTP verified successfully"
        else:
            self.otp_attempts += 1
            db.session.commit()
            return False, f"Invalid OTP. {3 - self.otp_attempts} attempts remaining"

    def generate_phone_otp(self):
        """Generate 6-digit OTP for phone"""
        import random
        self.phone_otp_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        self.phone_otp_created_at = datetime.utcnow()
        self.phone_otp_attempts = 0
        db.session.commit()
        return self.phone_otp_code
    
    def verify_phone_otp(self, otp):
        """Verify phone OTP"""
        if not self.phone_otp_code or not self.phone_otp_created_at:
            return False, "No OTP generated"
        
        if datetime.utcnow() - self.phone_otp_created_at > timedelta(minutes=10):
            return False, "OTP expired"
        
        if self.phone_otp_attempts >= 3:
            return False, "Too many failed attempts"
        
        if self.phone_otp_code == otp:
            self.phone_otp_code = None
            self.phone_otp_created_at = None
            self.phone_otp_attempts = 0
            self.phone_verified = True
            db.session.commit()
            return True, "Phone verified successfully"
        else:
            self.phone_otp_attempts += 1
            db.session.commit()
            return False, f"Invalid OTP. {3 - self.phone_otp_attempts} attempts remaining"

# class APIKey(db.Model):
#     """API Key model for SDK access - stored in SQL database"""
#     __tablename__ = 'api_keys'
    
#     id = db.Column(db.Integer, primary_key=True)
#     key_id = db.Column(db.String(50), unique=True, default=lambda: 'ak_' + secrets.token_urlsafe(32))
#     key_secret = db.Column(db.String(100), default=lambda: secrets.token_urlsafe(48))
#     name = db.Column(db.String(100), nullable=False)  # e.g., "Production", "Development"
    
#     # Foreign keys
#     user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
#     # Permissions
#     permissions = db.Column(db.JSON, default=lambda: ['read', 'write'])  # read, write, admin
#     allowed_domains = db.Column(db.JSON, default=list)  # List of allowed domains for CORS
#     ip_whitelist = db.Column(db.JSON, default=list)  # List of allowed IPs
    
#     # Usage tracking
#     last_used_at = db.Column(db.DateTime)
#     last_used_ip = db.Column(db.String(45))
#     total_requests = db.Column(db.BigInteger, default=0)
    
#     # Status
#     is_active = db.Column(db.Boolean, default=True)
#     expires_at = db.Column(db.DateTime, nullable=True)
    
#     # Timestamps
#     created_at = db.Column(db.DateTime, default=datetime.utcnow)

#     # Additional fields for Phase 4
#     description = db.Column(db.Text, nullable=True)
#     rate_limit = db.Column(db.String(20), default='60')  # '60', '300', '1000', '5000', 'unlimited'
    
#     # Statistics
#     total_requests = db.Column(db.BigInteger, default=0)
#     last_used_at = db.Column(db.DateTime, nullable=True)
#     last_used_ip = db.Column(db.String(45), nullable=True)
    
#     # Security
#     allowed_domains = db.Column(db.JSON, default=list)
#     ip_whitelist = db.Column(db.JSON, default=list)
    
#     def is_valid(self):
#         """Check if API key is valid and not expired"""
#         if not self.is_active:
#             return False
#         if self.expires_at and self.expires_at < datetime.utcnow():
#             return False
#         return True
    
#     def record_usage(self, ip_address):
#         """Record API key usage"""
#         self.last_used_at = datetime.utcnow()
#         self.last_used_ip = ip_address
#         self.total_requests += 1
#         db.session.commit()
    
#     def regenerate_secret(self):
#         """Regenerate key secret (key rotation)"""
#         self.key_secret = secrets.token_urlsafe(48)
#         db.session.commit()
#         return self.key_secret
    
#     def to_dict(self, include_secret=False):
#         data = {
#             'key_id': self.key_id,
#             'name': self.name,
#             'permissions': self.permissions,
#             'allowed_domains': self.allowed_domains,
#             'is_active': self.is_active,
#             'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
#             'total_requests': self.total_requests,
#             'expires_at': self.expires_at.isoformat() if self.expires_at else None,
#             'created_at': self.created_at.isoformat()
#         }
#         if include_secret:
#             data['key_secret'] = self.key_secret
#         return data
        
#     def __repr__(self):
#         return f'<APIKey {self.name} - {self.key_id[:8]}...>'

class Webhook(db.Model):
    """Webhook configuration for real-time log forwarding"""
    __tablename__ = 'webhooks'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    events = db.Column(db.JSON, default=['*'])  # Event types to send, ['*'] for all
    secret = db.Column(db.String(100), default=lambda: secrets.token_urlsafe(32))
    
    # Configuration
    is_active = db.Column(db.Boolean, default=True)
    retry_count = db.Column(db.Integer, default=3)
    timeout = db.Column(db.Integer, default=5)  # seconds
    
    # Statistics
    total_delivered = db.Column(db.Integer, default=0)
    total_failed = db.Column(db.Integer, default=0)
    last_triggered_at = db.Column(db.DateTime)
    last_error = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class TeamMember(db.Model):
    """Team collaboration model"""
    __tablename__ = 'team_members'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    role = db.Column(db.String(20), default='member')  # owner, admin, member, viewer
    permissions = db.Column(db.JSON, default=['view_logs'])
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

class Team(db.Model):
    """Team model for collaboration"""
    __tablename__ = 'teams'
    
    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(50), unique=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    settings = db.Column(db.JSON, default={})
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    owner = db.relationship('User', foreign_keys=[owner_id], backref='owned_teams')
    members = db.relationship('TeamMember', backref='team', lazy='dynamic', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'public_id': self.public_id,
            'name': self.name,
            'owner': self.owner.username if self.owner else None,
            'created_at': self.created_at.isoformat()
        }


class LoginLog(db.Model):
    """Log of login attempts for security monitoring"""
    __tablename__ = 'login_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    email = db.Column(db.String(120))
    success = db.Column(db.Boolean, default=False)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<LoginLog {self.email} {"success" if self.success else "failed"}>'

class APIKey(db.Model):
    __tablename__ = 'api_keys'
    
    id = db.Column(db.Integer, primary_key=True)
    key_id = db.Column(db.String(50), unique=True, nullable=False)
    key_secret = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Permissions and restrictions
    permissions = db.Column(db.JSON, default=list)
    allowed_domains = db.Column(db.JSON, default=list)
    ip_whitelist = db.Column(db.JSON, default=list)
    
    # Usage tracking
    last_used_at = db.Column(db.DateTime)
    last_used_ip = db.Column(db.String(45))
    total_requests = db.Column(db.BigInteger, default=0)
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    expires_at = db.Column(db.DateTime)
    rate_limit = db.Column(db.String(20), default='60')
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)