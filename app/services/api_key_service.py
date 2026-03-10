from app.models.user_models import APIKey
from app import db
from datetime import datetime, timedelta
import secrets
import hashlib
import hmac
from flask import current_app
import ipaddress

class APIKeyService:
    """Service for managing API keys"""
    
    @staticmethod
    def generate_key_pair():
        """Generate a new API key pair (key_id and key_secret)"""
        # Generate key_id with prefix for identification
        key_id = 'sdk_' + secrets.token_urlsafe(32)
        
        # Generate secret
        key_secret = secrets.token_urlsafe(48)
        
        return key_id, key_secret
    
    @staticmethod
    def create_key(user_id, name, description='', permissions=None, 
                   allowed_domains=None, ip_whitelist=None, 
                   expires_at=None, rate_limit='60'):
        """Create a new API key for a user"""
        
        # Check if user has reached max keys
        from app.models.user_models import User
        user = User.query.get(user_id)
        
        if user.api_keys.count() >= user.max_api_keys:
            raise ValueError(f"Maximum number of API keys ({user.max_api_keys}) reached")
        
        # Generate key pair
        key_id, key_secret = APIKeyService.generate_key_pair()
        
        # Process allowed domains
        if allowed_domains and isinstance(allowed_domains, str):
            allowed_domains = [d.strip() for d in allowed_domains.split('\n') if d.strip()]
        
        # Process IP whitelist
        if ip_whitelist and isinstance(ip_whitelist, str):
            ip_whitelist = [ip.strip() for ip in ip_whitelist.split('\n') if ip.strip()]
        
        # Set default permissions if none provided
        if not permissions:
            permissions = ['read_logs', 'write_logs']
        
        # Create key
        api_key = APIKey(
            key_id=key_id,
            key_secret=key_secret,
            name=name,
            description=description,
            user_id=user_id,
            permissions=permissions,
            allowed_domains=allowed_domains or [],
            ip_whitelist=ip_whitelist or [],
            rate_limit=rate_limit,
            expires_at=expires_at
        )
        
        db.session.add(api_key)
        db.session.commit()
        
        return api_key
    
    @staticmethod
    def validate_key(key_id, key_secret, ip_address=None, domain=None):
        """Validate an API key and check permissions"""
        
        # Find key by key_id
        api_key = APIKey.query.filter_by(key_id=key_id).first()
        
        if not api_key:
            return None, "Invalid API key"
        
        # Check if key is active
        if not api_key.is_active:
            return None, "API key is deactivated"
        
        # Check expiration
        if api_key.expires_at and api_key.expires_at < datetime.utcnow():
            return None, "API key has expired"
        
        # Validate secret
        if not hmac.compare_digest(api_key.key_secret.encode(), key_secret.encode()):
            return None, "Invalid API key secret"
        
        # Check IP whitelist if configured
        if api_key.ip_whitelist and ip_address:
            if not APIKeyService._check_ip_whitelist(ip_address, api_key.ip_whitelist):
                return None, f"IP address {ip_address} not whitelisted"
        
        # Check domain whitelist if configured
        if api_key.allowed_domains and domain:
            if not APIKeyService._check_domain_whitelist(domain, api_key.allowed_domains):
                return None, f"Domain {domain} not whitelisted"
        
        # Update usage stats
        api_key.last_used_at = datetime.utcnow()
        api_key.last_used_ip = ip_address
        api_key.total_requests += 1
        db.session.commit()
        
        return api_key, None
    
    @staticmethod
    def _check_ip_whitelist(ip_address, whitelist):
        """Check if IP is in whitelist (supports CIDR notation)"""
        try:
            ip = ipaddress.ip_address(ip_address)
            for allowed in whitelist:
                try:
                    # Check if it's a CIDR range
                    if '/' in allowed:
                        network = ipaddress.ip_network(allowed, strict=False)
                        if ip in network:
                            return True
                    # Exact IP match
                    elif ip_address == allowed:
                        return True
                except:
                    continue
        except:
            return False
        return False
    
    @staticmethod
    def _check_domain_whitelist(domain, whitelist):
        """Check if domain is in whitelist (supports wildcards)"""
        domain = domain.lower()
        for allowed in whitelist:
            allowed = allowed.lower()
            
            # Exact match
            if domain == allowed:
                return True
            
            # Wildcard match (e.g., *.example.com)
            if allowed.startswith('*.'):
                base_domain = allowed[2:]
                if domain.endswith(base_domain) and domain.count('.') >= base_domain.count('.') + 1:
                    return True
        
        return False
    
    @staticmethod
    def revoke_key(key_id, user_id):
        """Revoke an API key"""
        api_key = APIKey.query.filter_by(key_id=key_id, user_id=user_id).first()
        if api_key:
            api_key.is_active = False
            db.session.commit()
            return True
        return False
    
    @staticmethod
    def delete_key(key_id, user_id):
        """Permanently delete an API key"""
        api_key = APIKey.query.filter_by(key_id=key_id, user_id=user_id).first()
        if api_key:
            db.session.delete(api_key)
            db.session.commit()
            return True
        return False
    
    @staticmethod
    def regenerate_secret(key_id, user_id):
        """Regenerate key secret (key rotation)"""
        try:
            api_key = APIKey.query.filter_by(key_id=key_id, user_id=user_id).first()
            if api_key:
                # Generate new secret
                new_secret = secrets.token_urlsafe(48)
                api_key.key_secret = new_secret
                db.session.commit()
                return new_secret
            return None
        except Exception as e:
            db.session.rollback()
            print(f"Error in regenerate_secret: {e}")
            return None
    
    @staticmethod
    def get_user_keys(user_id, include_inactive=False):
        """Get all API keys for a user"""
        query = APIKey.query.filter_by(user_id=user_id)
        if not include_inactive:
            query = query.filter_by(is_active=True)
        return query.order_by(APIKey.created_at.desc()).all()
    
    @staticmethod
    def check_permission(api_key, permission):
        """Check if key has specific permission"""
        if 'admin' in api_key.permissions:
            return True
        return permission in api_key.permissions
    
    @staticmethod
    def get_key_stats(key_id, user_id):
        """Get usage statistics for a specific key"""
        api_key = APIKey.query.filter_by(key_id=key_id, user_id=user_id).first()
        if not api_key:
            return None
        
        # Calculate usage stats
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Get today's usage from MongoDB
        from app.services.log_service import LogService
        log_service = LogService()
        today_count = log_service.get_key_usage_today(key_id, today_start)
        
        return {
            'total_requests': api_key.total_requests,
            'last_used': api_key.last_used_at,
            'last_ip': api_key.last_used_ip,
            'today_requests': today_count,
            'created_at': api_key.created_at,
            'expires_at': api_key.expires_at
        }

class APIKeyMiddleware:
    """Middleware for API key authentication in Flask routes"""
    
    @staticmethod
    def authenticate_request(request):
        """Extract and validate API key from request"""
        
        # ============================================
        # STEP 1: Try multiple header formats
        # ============================================
        api_key = None
        
        # Try X-API-KEY header (Agent SDK format)
        api_key = request.headers.get('X-API-KEY')
        
        # Try X-API-Key (alternative case)
        if not api_key:
            api_key = request.headers.get('X-API-Key')
        
        # Try Authorization header (Bearer format)
        if not api_key:
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                api_key = auth_header[7:]
            elif auth_header.startswith('ApiKey '):
                api_key = auth_header[7:]
        
        # Try query parameter
        if not api_key:
            api_key = request.args.get('api_key')
        
        if not api_key:
            return None, "No API key provided"
        
        # ============================================
        # STEP 2: Parse key_id and secret
        # ============================================
        # Agent SDK sends both key_id and secret in X-API-KEY
        if ':' in api_key:
            key_id, key_secret = api_key.split(':', 1)
        else:
            # If no colon, assume it's just the key_id
            key_id = api_key
            key_secret = None
        
        # Get client info
        ip_address = request.remote_addr
        domain = request.host
        
        # ============================================
        # STEP 3: Validate key
        # ============================================
        # Pass key_secret for direct validation, or None for signature validation
        api_key_obj, error = APIKeyService.validate_key(
            key_id, 
            key_secret, 
            ip_address, 
            domain
        )
        
        if error:
            return None, error
        
        # Store the key secret in request context for signature verification
        g.key_secret = api_key_obj.key_secret
        
        return api_key_obj, None

class APIKeyRateLimiter:
    """Simple rate limiter without Redis"""
    
    def __init__(self):
        # Simple in-memory rate limiting
        self._rate_limits = {}
        from collections import defaultdict
        import time
        self._rate_limits = defaultdict(list)
    
    def check_rate_limit(self, api_key):
        """Simple in-memory rate limiting"""
        if api_key.rate_limit == 'unlimited':
            return True, None
        
        limit = int(api_key.rate_limit)
        key = f"rate_limit:{api_key.key_id}"
        now = time.time()
        minute_ago = now - 60
        
        # Clean old requests
        self._rate_limits[key] = [t for t in self._rate_limits[key] if t > minute_ago]
        
        if len(self._rate_limits[key]) >= limit:
            return False, f"Rate limit exceeded. Max {limit} requests per minute."
        
        self._rate_limits[key].append(now)
        return True, None