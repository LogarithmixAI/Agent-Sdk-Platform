from flask import Blueprint, request, jsonify, current_app, g
from flask_login import login_required
from app.services.log_service import LogService
from app.services.api_key_service import APIKeyService, APIKeyMiddleware
from app.services.queue_service import QueueService
from app.utils.validators import validate_log_batch
from app.decorators import rate_limit
from datetime import datetime
import uuid
import json

bp = Blueprint('api', __name__, url_prefix='/api/v1')

# Initialize services
log_service = LogService()
queue_service = QueueService()

@bp.before_request
def before_request():
    """Validate API key before processing request"""
    # Skip validation for public endpoints
    if request.endpoint in ['api.health', 'api.docs']:
        return
    
    # Authenticate using API key
    api_key, error = APIKeyMiddleware.authenticate_request(request)
    
    if error:
        return jsonify({
            'success': False,
            'error': error,
            'code': 'UNAUTHORIZED'
        }), 401
    
    # Store API key info in request context
    g.api_key = api_key
    g.user_id = api_key.user.public_id
    
    # Check rate limit
    from app.services.api_key_service import APIKeyRateLimiter
    rate_limiter = APIKeyRateLimiter()
    allowed, error = rate_limiter.check_rate_limit(api_key)
    
    if not allowed:
        return jsonify({
            'success': False,
            'error': error,
            'code': 'RATE_LIMITED'
        }), 429

        
@bp.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'version': '1.0.0'
    })

@bp.route('/logs', methods=['POST'])
def ingest_logs():
    """
    Ingest log batches from SDK
    Expected format matches the provided payload structure
    """
    try:
        # Get request data
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided',
                'code': 'INVALID_REQUEST'
            }), 400
        
        # Add request metadata
        data['ip'] = request.remote_addr
        data['received_at'] = datetime.utcnow().isoformat()
        
        # Validate the batch
        is_valid, errors = validate_log_batch(data)
        
        if not is_valid:
            return jsonify({
                'success': False,
                'error': 'Validation failed',
                'errors': errors,
                'code': 'VALIDATION_ERROR'
            }), 400
        
        # Check user quota
        user_id = g.user_id
        current_count = log_service.get_current_month_log_count(user_id)
        user = g.api_key.user
        
        if current_count + data['payload']['batch_meta']['event_count'] > user.monthly_log_limit:
            return jsonify({
                'success': False,
                'error': 'Monthly log limit exceeded',
                'code': 'QUOTA_EXCEEDED',
                'limit': user.monthly_log_limit,
                'current': current_count
            }), 429
        
        # Process the batch (async or sync based on load)
        # Process synchronously
        result = log_service.store_log_batch(
            data, 
            user_id=user_id,
            api_key_details={
                'id': g.api_key.id,
                'name': g.api_key.name
            }
        )
            
        return jsonify({
            'success': True,
            'message': 'Logs ingested successfully',
            'batch_id': result.get('id'),
            'event_count': result.get('event_count'),
            'storage': result.get('storage')
        }), 200
            
    except Exception as e:
        current_app.logger.error(f"Error ingesting logs: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'code': 'SERVER_ERROR'
        }), 500

@bp.route('/logs/batch', methods=['POST'])
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
        
        # Limit batch size
        if len(data) > 100:
            return jsonify({
                'success': False,
                'error': 'Too many batches. Maximum 100 per request.',
                'code': 'BATCH_TOO_LARGE'
            }), 400
        
        # Process all batches
        results = []
        errors = []
        
        for i, batch in enumerate(data):
            try:
                # Add metadata
                batch['ip'] = request.remote_addr
                batch['received_at'] = datetime.utcnow().isoformat()
                
                # Validate
                is_valid, validation_errors = validate_log_batch(batch)
                if not is_valid:
                    errors.append({
                        'index': i,
                        'errors': validation_errors
                    })
                    continue
                
                # Store
                result = log_service.store_log_batch(
                    batch,
                    user_id=g.user_id,
                    api_key_details={
                        'id': g.api_key.id,
                        'name': g.api_key.name
                    }
                )
                
                results.append({
                    'index': i,
                    'success': True,
                    'batch_id': result.get('id'),
                    'event_count': result.get('event_count')
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
        current_app.logger.error(f"Error processing batch: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'code': 'SERVER_ERROR'
        }), 500

@bp.route('/logs/status/<batch_id>', methods=['GET'])
def get_batch_status(batch_id):
    """Check status of async batch processing"""
    # In production, this would check a queue/database
    status = queue_service.get_batch_status(batch_id)
    
    if not status:
        return jsonify({
            'success': False,
            'error': 'Batch not found',
            'code': 'NOT_FOUND'
        }), 404
    
    return jsonify({
        'success': True,
        'batch_id': batch_id,
        'status': status['state'],
        'processed_at': status.get('processed_at'),
        'event_count': status.get('event_count')
    })

@bp.route('/logs/schema', methods=['GET'])
def get_schema():
    """Get the expected log schema for validation"""
    from app.models.log_models import LogSchema
    
    return jsonify({
        'schema': LogSchema.SCHEMA,
        'required_fields': LogSchema.REQUIRED_FIELDS,
        'version': '1.0.0'
    })

@bp.route('/logs/stats', methods=['GET'])
@login_required
def get_stats():
    """Get ingestion statistics for current period"""
    from datetime import datetime, timedelta
    
    # Get query parameters
    period = request.args.get('period', 'day')  # day, week, month
    end_date = datetime.utcnow()
    
    if period == 'day':
        start_date = end_date - timedelta(days=1)
    elif period == 'week':
        start_date = end_date - timedelta(days=7)
    elif period == 'month':
        start_date = end_date - timedelta(days=30)
    else:
        start_date = end_date - timedelta(days=1)
    
    # Get stats from database
    stats = log_service.get_ingestion_stats(
        user_id=g.user_id,
        start_date=start_date,
        end_date=end_date
    )
    
    return jsonify(stats)

# def should_process_async(data):
#     """Determine if batch should be processed asynchronously"""
#     # Check batch size
#     event_count = data.get('payload', {}).get('batch_meta', {}).get('event_count', 0)
    
#     # Async for large batches
#     if event_count > 50:
#         return True
    
#     # Check current system load (simplified)
#     import psutil
#     cpu_percent = psutil.cpu_percent(interval=0.1)
    
#     if cpu_percent > 70:  # High CPU load
#         return True
    
#     return False

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