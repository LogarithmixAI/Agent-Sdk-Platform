import re
import ipaddress
import hmac
import hashlib
import json
from datetime import datetime
from typing import Tuple, List, Dict, Any

# ============================================
# 🔐 SIGNATURE VERIFICATION FUNCTION
# ============================================
def verify_signature(secret, timestamp, signature, body_str):
    """
    Verify HMAC-SHA256 signature as per Agent SDK requirements
    
    Args:
        secret: API key secret
        timestamp: X-Timestamp header value
        signature: X-Signature header value
        body_str: Raw request body as string
    
    Returns:
        bool: True if signature is valid, False otherwise
    """
    try:
        # Create message = timestamp + body
        message = timestamp + json.dumps(body_str, sort_keys=True)
        
        # Compute expected signature
        expected = hmac.new(
            secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Constant-time comparison to prevent timing attacks
        return hmac.compare_digest(signature, expected)
        
    except Exception as e:
        print(f"Signature verification error: {e}")
        return False


# ============================================
# 🌐 IP ALLOWLIST CHECK FUNCTION
# ============================================
def ip_allowed(client_ip, whitelist):
    """
    Check if IP address is in whitelist (supports CIDR notation)
    
    Args:
        client_ip: Client IP address string
        whitelist: List of allowed IPs/CIDR ranges
    
    Returns:
        bool: True if IP is allowed
    """
    try:
        ip_obj = ipaddress.ip_address(client_ip)
        
        for rule in whitelist:
            if '/' in rule:  # CIDR notation (e.g., 192.168.1.0/24)
                network = ipaddress.ip_network(rule, strict=False)
                if ip_obj in network:
                    return True
            else:  # Exact IP match
                if client_ip == rule:
                    return True
    except Exception as e:
        print(f"IP validation error: {e}")
    
    return False


# ============================================
# 📦 LOG BATCH VALIDATION FUNCTIONS
# ============================================
def validate_log_batch(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate log batch structure as per Agent SDK format
    """
    errors = []
    
    # Check required fields
    required_fields = ['ip', 'api_key', 'received_at', 'payload']
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: {field}")
    
    if errors:
        return False, errors
    
    # Validate payload structure
    payload = data.get('payload', {})
    
    # Check batch_meta
    batch_meta = payload.get('batch_meta', {})
    required_meta = ['environment', 'event_count', 'project', 'schema_version', 'sdk_version', 'sent_at']
    
    for field in required_meta:
        if field not in batch_meta:
            errors.append(f"Missing batch_meta field: {field}")
    
    # Validate event_count matches actual events
    events = payload.get('events', [])
    expected_count = batch_meta.get('event_count', 0)
    
    if len(events) != expected_count:
        errors.append(
            f"Event count mismatch: batch_meta says {expected_count}, "
            f"but received {len(events)} events"
        )
    
    # Validate each event
    for idx, event_item in enumerate(events):
        event_errors = validate_event(event_item, idx)
        errors.extend(event_errors)
    
    return len(errors) == 0, errors


def validate_event(event_item: Dict[str, Any], index: int) -> List[str]:
    """Validate a single event as per Agent SDK format"""
    errors = []
    prefix = f"Event {index}: "
    
    # Check required sections
    required_sections = ['event', 'identity', 'meta']
    for section in required_sections:
        if section not in event_item:
            errors.append(prefix + f"Missing section: {section}")
            return errors
    
    # Validate event section
    event = event_item.get('event', {})
    required_event_fields = ['type', 'category', 'severity', 'status', 'data']
    
    for field in required_event_fields:
        if field not in event:
            errors.append(prefix + f"Missing event field: {field}")
    
    # Validate severity
    valid_severities = ['HIGH', 'MEDIUM', 'LOW', 'INFO']
    severity = event.get('severity')
    if severity and severity not in valid_severities:
        errors.append(prefix + f"Invalid severity: {severity}. Must be one of {valid_severities}")
    
    # Validate status
    valid_statuses = ['SUCCESS', 'FAILURE', 'PENDING', 'SKIPPED']
    status = event.get('status')
    if status and status not in valid_statuses:
        errors.append(prefix + f"Invalid status: {status}")
    
    # Validate identity section
    identity = event_item.get('identity', {})
    required_identity = ['instance_id', 'hostname', 'os', 'process_id']
    
    for field in required_identity:
        if field not in identity:
            errors.append(prefix + f"Missing identity field: {field}")
    
    # Validate meta section
    meta = event_item.get('meta', {})
    required_meta = ['timestamp', 'trace_id', 'environment', 'project']
    
    for field in required_meta:
        if field not in meta:
            errors.append(prefix + f"Missing meta field: {field}")
    
    # Validate timestamp
    try:
        timestamp = meta.get('timestamp')
        if timestamp:
            datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        errors.append(prefix + f"Invalid timestamp: {meta.get('timestamp')}")
    
    # Validate trace_id format (UUID)
    trace_id = meta.get('trace_id')
    if trace_id:
        uuid_pattern = re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            re.IGNORECASE
        )
        if not uuid_pattern.match(trace_id):
            errors.append(prefix + f"Invalid trace_id format: {trace_id}")
    
    return errors


def sanitize_log_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize log data before storage (remove sensitive info)"""
    sensitive_patterns = [
        r'password.*?=.*?[&\s]',
        r'token.*?=.*?[&\s]',
        r'api[_-]key.*?=.*?[&\s]',
        r'secret.*?=.*?[&\s]',
        r'auth.*?=.*?[&\s]'
    ]
    
    def sanitize_value(value):
        if isinstance(value, str):
            for pattern in sensitive_patterns:
                if re.search(pattern, value, re.IGNORECASE):
                    return '[REDACTED]'
        return value
    
    def recursive_sanitize(obj):
        if isinstance(obj, dict):
            return {k: recursive_sanitize(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [recursive_sanitize(item) for item in obj]
        else:
            return sanitize_value(obj)
    
    return recursive_sanitize(data)