from flask import Blueprint, request, jsonify, current_app, g
from flask_login import login_required
from app import csrf
from app.services.log_service import LogService 
from app.services.api_key_service import APIKeyService, APIKeyMiddleware
from app.utils.validators import validate_log_batch, verify_signature, ip_allowed
from app.models.user_models import APIKey
from datetime import datetime, timezone
from app import db
import hmac
import hashlib
import json
import ipaddress

log_service = LogService()

bp = Blueprint('api', __name__, url_prefix='/api')

# Replay protection cache
REPLAY_CACHE = set()
MAX_CACHE_SIZE = 10000

    
# @bp.before_request
# def before_request():
#     """Validate API key before processing request"""
#     # Skip validation for public endpoints
#     if request.endpoint in ['api.health', 'api.docs']:
#         return
    
#     # Authenticate using API key
#     api_key, error = APIKeyMiddleware.authenticate_request(request)
    
#     if error:
#         return jsonify({
#             'success': False,
#             'error': error,
#             'code': 'UNAUTHORIZED'
#         }), 401
    
#     # Store API key info in request context
#     g.api_key = api_key
#     g.user_id = api_key.user.public_id
#     g.key_secret = api_key.key_secret
    
#     # Check rate limit
#     from app.services.api_key_service import APIKeyRateLimiter
#     rate_limiter = APIKeyRateLimiter()
#     allowed, error = rate_limiter.check_rate_limit(api_key)
    
#     if not allowed:
#         return jsonify({
#             'success': False,
#             'error': error,
#             'code': 'RATE_LIMITED'
#         }), 429

def clean_replay_cache():
    """Clean old entries from replay cache"""
    if len(REPLAY_CACHE) > MAX_CACHE_SIZE:
        # Remove oldest 20%
        to_remove = len(REPLAY_CACHE) - MAX_CACHE_SIZE + 2000
        for _ in range(to_remove):
            REPLAY_CACHE.pop()

# ============================================
# 🎯 MAIN LOG INGESTION ENDPOINT - AS PER AGENT SDK
# ============================================
@bp.route('/logs', methods=['POST'])
@csrf.exempt
def ingest_logs():
    """Agent SDK Log Ingestion - Proper validation"""
    try:
        # ============================================
        # STEP 1: Extract headers
        # ============================================
        key_id = request.headers.get('X-API-KEY')        # Sirf key_id
        timestamp = request.headers.get('X-TIMESTAMP')
        signature = request.headers.get('X-SIGNATURE')
        client_ip = request.remote_addr
        
        print(f"🆔 Key ID: {key_id}")
        print(f"⏰ Timestamp: {timestamp}")
        print(f"🔏 Signature: {signature[:20]}...")
        
        # Validate required headers
        if not all([key_id, timestamp, signature]):
            missing = []
            if not key_id: missing.append('X-API-KEY')
            if not timestamp: missing.append('X-TIMESTAMP')
            if not signature: missing.append('X-SIGNATURE')
            
            return jsonify({
                'success': False,
                'error': f'Missing headers: {", ".join(missing)}',
                'code': 'MISSING_HEADERS'
            }), 400
        
        # ============================================
        # STEP 2: Get API key from database using key_id
        # ============================================
        api_key = APIKey.query.filter_by(key_id=key_id).first()
        
        if not api_key:
            return jsonify({
                'success': False,
                'error': 'Invalid API key',
                'code': 'INVALID_API_KEY'
            }), 401
        
        # Check if API key is active
        if not api_key.is_active:
            return jsonify({
                'success': False,
                'error': 'API key is deactivated',
                'code': 'KEY_DEACTIVATED'
            }), 401
        
        # Check expiration
        if api_key.expires_at and api_key.expires_at < datetime.utcnow():
            return jsonify({
                'success': False,
                'error': 'API key has expired',
                'code': 'KEY_EXPIRED'
            }), 401
        
        # ============================================
        # STEP 3: IP whitelist validation
        # ============================================
        if api_key.ip_whitelist and len(api_key.ip_whitelist) > 0:
            if not ip_allowed(client_ip, api_key.ip_whitelist):
                return jsonify({
                    'success': False,
                    'error': f'IP address {client_ip} not allowed',
                    'code': 'IP_NOT_ALLOWED'
                }), 403
        
        # ============================================
        # STEP 4: Get raw body
        # ============================================
        body_bytes = request.get_data()
        body_str = body_bytes.decode('utf-8')
        
        # ============================================
        # STEP 5: Verify signature using stored SECRET
        # ============================================
        # 🔐 IMPORTANT: api_key.key_secret is the actual secret stored in DB
        if not verify_signature(
            api_key.key_secret,  # 👈 Secret from database
            timestamp,
            signature,
            body_str
        ):  

            print('verification failed.')
            print(api_key.key_secret)
            return jsonify({
                'success': False,
                'error': 'Invalid signature',
                'code': 'INVALID_SIGNATURE'
            }), 401
        
        # ============================================
        # STEP 6: Timestamp freshness check (5 minutes)
        # ============================================
        try:
            ts = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            
            if abs((now - ts).total_seconds()) > 300:  # 5 minutes
                return jsonify({
                    'success': False,
                    'error': 'Timestamp expired',
                    'code': 'TIMESTAMP_EXPIRED'
                }), 401

        except Exception as e:
            return jsonify({
                'success': False,
                'error': 'Invalid timestamp format',
                'code': 'INVALID_TIMESTAMP'
            }), 400
        
        # ============================================
        # STEP 7: Domain validation (if configured)
        # ============================================
        if api_key.allowed_domains and len(api_key.allowed_domains) > 0:
            from urllib.parse import urlparse
            origin = request.headers.get('Origin') or request.headers.get('Referer')
            if origin:
                domain = urlparse(origin).netloc
                if not any(domain.endswith(allowed_domain.lstrip('*.')) 
                          for allowed_domain in api_key.allowed_domains):
                    return jsonify({
                        'success': False,
                        'error': f'Domain {domain} not allowed',
                        'code': 'DOMAIN_NOT_ALLOWED'
                    }), 403
        
        # ============================================
        # STEP 8: Parse payload
        # ============================================
        try:
            payload = json.loads(body_str)
        except Exception as e:
            return jsonify({
                'success': False,
                'error': 'Invalid JSON payload',
                'code': 'INVALID_JSON'
            }), 400
        
        # ============================================
        # STEP 9: Check user quota
        # ============================================
        user = api_key.user
        event_count = payload.get('batch_meta', {}).get('event_count', 0)
        
        # Validate event count matches actual events
        events = payload.get('events', [])
        if len(events) != event_count:
            return jsonify({
                'success': False,
                'error': f'Event count mismatch: meta says {event_count}, got {len(events)}',
                'code': 'COUNT_MISMATCH'
            }), 400
        
        # Check monthly limit
        current_count = log_service.get_current_month_log_count(user.public_id)
        
        if current_count + event_count > user.monthly_log_limit:
            return jsonify({
                'success': False,
                'error': 'Monthly log limit exceeded',
                'code': 'QUOTA_EXCEEDED',
                'limit': user.monthly_log_limit,
                'current': current_count
            }), 429
        
        # ============================================
        # STEP 10: Prepare and store logs
        # ============================================
        log_entry = {
            'ip': client_ip,
            'api_key': key_id,
            'received_at': datetime.utcnow().isoformat(),
            'payload': payload,
            'user_id': user.public_id
        }
        
        # Store logs
        result = log_service.store_log_batch(
            log_entry,
            user_id=user.public_id,
            api_key_details={
                'id': api_key.id,
                'name': api_key.name
            }
        )
        
        # Update API key usage
        api_key.last_used_at = datetime.utcnow()
        api_key.last_used_ip = client_ip
        api_key.total_requests += 1
        print(f"api_key_request : {api_key.total_requests}")
        # db.session.commit()

        try:
            db.session.commit()
        except Exception as e:
            print(f"Commit failed: {e}")
        
        # ============================================
        # 🔔 WEBHOOK TRIGGER - YAHAN LAGAO
        # ============================================
        from app.services.webhook_service import WebhookService
        
        # Trigger for new logs
        WebhookService.trigger(
            event_type='log.created',
            payload={
                'batch_id': result.get('id'),
                'event_count': event_count,
                'project': payload.get('batch_meta', {}).get('project'),
                'environment': payload.get('batch_meta', {}).get('environment')
            },
            user_id=user.id,
            team_id=None  # Optional: team ID if applicable
        )
        
        # If error detected, trigger error event
        if has_high_severity_events(payload):
            WebhookService.trigger(
                event_type='error.detected',
                payload={
                    'errors': extract_errors(payload),
                    'batch_id': result.get('id')
                },
                user_id=user.id
            )
        
        return jsonify({
            'success': True,
            'message': 'Logs received successfully',
            'batch_id': result.get('id', ''),
            'event_count': event_count,
            'storage': result.get('storage', 'file')
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error ingesting logs: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'code': 'SERVER_ERROR'
        }), 500


@bp.route('/logs/batch', methods=['POST'])
@csrf.exempt
def ingest_batch():
    """Ingest multiple log batches in one request"""
    try:
        data = request.get_json()
        
        if not data or not isinstance(data, list):
            return jsonify({
                'success': False,
                'error': 'Expected array of log batches',
                'code': 'INVALID_REQUEST'
            }), 400
        
        if len(data) > 100:
            return jsonify({
                'success': False,
                'error': 'Too many batches. Maximum 100 per request.',
                'code': 'BATCH_TOO_LARGE'
            }), 400
        
        results = []
        errors = []
        
        for i, batch in enumerate(data):
            try:
                # Add metadata
                batch['ip'] = request.remote_addr
                batch['received_at'] = datetime.utcnow().isoformat()
                
                # Call main ingest function
                response = ingest_logs()  # Reuse main logic
                results.append({
                    'index': i,
                    'success': True,
                    'batch_id': response.json.get('batch_id')
                })
                
            except Exception as e:
                errors.append({
                    'index': i,
                    'error': str(e)
                })
        
        return jsonify({
            'success': len(errors) == 0,
            'processed': len(results),
            'failed': len(errors),
            'results': results,
            'errors': errors if errors else None
        }), 207 if errors else 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Endpoint not found',
        'code': 'NOT_FOUND'
    }), 404

@bp.errorhandler(405)
def method_not_allowed(error):
    return jsonify({
        'success': False,
        'error': 'Method not allowed',
        'code': 'METHOD_NOT_ALLOWED'
    }), 405

@bp.errorhandler(500)
def internal_error(error):
    current_app.logger.error(f"Internal server error: {str(error)}")
    return jsonify({
        'success': False,
        'error': 'Internal server error',
        'code': 'SERVER_ERROR'
    }), 500

@bp.route('/logs/schema', methods=['GET'])
def get_schema():
    """Get the expected log schema for validation"""
    return jsonify({
        'schema': {
            'batch_meta': {
                'environment': 'string',
                'event_count': 'integer',
                'project': 'string',
                'schema_version': 'string',
                'sdk_version': 'string',
                'sent_at': 'ISO timestamp'
            },
            'events': 'array of event objects'
        },
        'required_fields': ['batch_meta', 'events'],
        'version': '1.0.0'
    })
