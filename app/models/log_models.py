from app import mongo
from datetime import datetime
from bson import ObjectId, json_util
import json

class LogSchema:
    """Schema definition for logs stored in MongoDB - matching Agent SDK payload"""
    
    COLLECTION_NAME = 'logs'
    
    # Complete schema matching the incoming payload
    SCHEMA = {
        # Top-level fields from the incoming request
        'ip': {'type': str, 'required': True},
        'api_key': {'type': str, 'required': True, 'index': True},
        'received_at': {'type': datetime, 'required': True},
        
        # User ID (added by server after API key validation)
        'user_id': {'type': str, 'required': True, 'index': True},
        
        # Batch metadata
        'batch_meta': {
            'type': dict,
            'required': True,
            'schema': {
                'environment': {'type': str, 'required': True},
                'event_count': {'type': int, 'required': True},
                'project': {'type': str, 'required': True},
                'schema_version': {'type': str, 'required': True},
                'sdk_version': {'type': str, 'required': True},
                'sent_at': {'type': str, 'required': True}  # ISO format string
            }
        },
        
        # Events array - the core data
        'events': {'type': list, 'required': True},
        
        # Flattened events for easier querying (processed version)
        'processed_events': {'type': list, 'required': False},
        
        # Processing metadata
        'processed': {'type': bool, 'default': False},
        'processed_at': {'type': datetime, 'required': False}
    }

class LogModel:
    """Wrapper class for log operations with the actual payload structure"""
    
    @staticmethod
    def create_indexes():
        """Create necessary indexes for logs collection based on query patterns"""
        collection = mongo.db.logs
        
        # Indexes for common queries
        collection.create_index([('user_id', 1), ('received_at', -1)])
        collection.create_index([('api_key', 1), ('received_at', -1)])
        collection.create_index([('batch_meta.project', 1), ('received_at', -1)])
        collection.create_index([('batch_meta.environment', 1), ('received_at', -1)])
        
        # Indexes for event-level queries (using dotted notation)
        collection.create_index([('processed_events.meta.trace_id', 1)])
        collection.create_index([('processed_events.identity.instance_id', 1)])
        collection.create_index([('processed_events.event.type', 1)])
        collection.create_index([('processed_events.event.severity', 1)])
        collection.create_index([('processed_events.event.category', 1)])
        
        # Compound indexes for dashboard queries
        collection.create_index([
            ('user_id', 1),
            ('processed_events.event.severity', 1),
            ('received_at', -1)
        ])
        
        # TTL index for automatic data expiration (optional)
        # collection.create_index('received_at', expireAfterSeconds=7776000)  # 90 days
    
    @staticmethod
    def prepare_log(data, user_id=None, api_key_details=None):
        """
        Prepare log data for storage with the actual payload structure
        This flattens events for easier querying while preserving original structure
        """
        log_entry = {
            'ip': data.get('ip'),
            'api_key': data.get('api_key'),
            'received_at': datetime.utcnow(),
            'user_id': user_id,
            'batch_meta': data.get('payload', {}).get('batch_meta', {}),
            'events': data.get('payload', {}).get('events', []),
            'processed': False
        }
        
        # Process events for easier querying (flattened version)
        processed_events = []
        for event_item in log_entry['events']:
            processed_event = {
                'trace_id': event_item.get('meta', {}).get('trace_id'),
                'timestamp': event_item.get('meta', {}).get('timestamp'),
                'environment': event_item.get('meta', {}).get('environment'),
                'project': event_item.get('meta', {}).get('project'),
                'sdk_version': event_item.get('meta', {}).get('sdk_version'),
                
                # Identity fields
                'instance_id': event_item.get('identity', {}).get('instance_id'),
                'hostname': event_item.get('identity', {}).get('hostname'),
                'os': event_item.get('identity', {}).get('os'),
                'os_version': event_item.get('identity', {}).get('os_version'),
                'app_version': event_item.get('identity', {}).get('app_version'),
                'python_version': event_item.get('identity', {}).get('python_version'),
                'region': event_item.get('identity', {}).get('region'),
                
                # Event fields
                'event_type': event_item.get('event', {}).get('type'),
                'event_category': event_item.get('event', {}).get('category'),
                'event_severity': event_item.get('event', {}).get('severity'),
                'event_status': event_item.get('event', {}).get('status'),
                'event_data': event_item.get('event', {}).get('data', {}),
                'event_metrics': event_item.get('event', {}).get('metrics', {})
            }
            processed_events.append(processed_event)
        
        log_entry['processed_events'] = processed_events
        
        return log_entry
    
    @staticmethod
    def extract_event_types(log_entry):
        """Extract unique event types from a log batch"""
        event_types = set()
        for event_item in log_entry.get('events', []):
            event_type = event_item.get('event', {}).get('type')
            if event_type:
                event_types.add(event_type)
        return list(event_types)
    
    @staticmethod
    def extract_severity_levels(log_entry):
        """Extract severity levels from a log batch"""
        severities = set()
        for event_item in log_entry.get('events', []):
            severity = event_item.get('event', {}).get('severity')
            if severity:
                severities.add(severity)
        return list(severities)

class EventModel:
    """Helper class for querying individual events"""
    
    @staticmethod
    def get_events_by_trace_id(trace_id, user_id=None):
        """Retrieve all events with a specific trace ID"""
        query = {'processed_events.trace_id': trace_id}
        if user_id:
            query['user_id'] = user_id
        
        return mongo.db.logs.find(query)
    
    @staticmethod
    def get_events_by_instance(instance_id, user_id=None, limit=100):
        """Retrieve events from a specific instance"""
        query = {'processed_events.instance_id': instance_id}
        if user_id:
            query['user_id'] = user_id
        
        return mongo.db.logs.find(query).sort('received_at', -1).limit(limit)
    
    @staticmethod
    def get_errors_by_severity(user_id, severity='HIGH', start_date=None, end_date=None):
        """Get error logs by severity level"""
        query = {
            'user_id': user_id,
            'processed_events.event_severity': severity,
            'processed_events.event_type': 'LOG'
        }
        
        if start_date or end_date:
            query['received_at'] = {}
            if start_date:
                query['received_at']['$gte'] = start_date
            if end_date:
                query['received_at']['$lte'] = end_date
        
        return mongo.db.logs.find(query).sort('received_at', -1)