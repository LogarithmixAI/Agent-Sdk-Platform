from app import mongo
from app.models.log_models import LogModel, EventModel
from app.services.file_storage_service import FileStorageService
from flask import current_app
from datetime import datetime, timedelta
from bson import ObjectId
import pandas as pd
import json

class LogService:
    """Main service for handling log operations with actual payload structure"""
    
    def __init__(self):
        self.file_storage = FileStorageService()
        self.storage_type = current_app.config.get('STORAGE_TYPE', 'file')
    
    def store_log_batch(self, request_data, user_id=None, api_key_details=None):
        """
        Store a batch of logs from the Agent SDK
        
        Args:
            request_data: The complete request data (includes ip, api_key, payload)
            user_id: User ID derived from API key validation
            api_key_details: Additional API key information
        """
        
        # Prepare log for storage
        log_entry = LogModel.prepare_log(request_data, user_id, api_key_details)
        
        # Store based on environment
        if self.storage_type == 'mongodb' and current_app.config.get('MONGO_URI'):
            # Store in MongoDB
            result = mongo.db.logs.insert_one(log_entry)
            
            # Update user's log count
            from app.models.user_models import User
            user = User.query.filter_by(public_id=user_id).first()
            if user:
                # Increment by actual event count
                event_count = len(log_entry.get('events', []))
                user.total_logs += event_count
                from app import db
                db.session.commit()
            
            return {
                'success': True, 
                'id': str(result.inserted_id),
                'event_count': len(log_entry.get('events', [])),
                'storage': 'mongodb'
            }

        else:
            # Store in file system (development)
            # Save the complete request for debugging
            filename = f"batch_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{ObjectId()}.json"
            file_path = f"{current_app.config['LOGS_STORAGE_PATH']}/json/{filename}"
            
            # Convert datetime objects to string for JSON serialization
            def datetime_converter(o):
                if isinstance(o, datetime):
                    return o.isoformat()
                raise TypeError(f'Object of type {o.__class__.__name__} is not JSON serializable')
            
            with open(file_path, 'w') as f:
                json.dump(log_entry, f, default=datetime_converter, indent=2)
            
            return {
                'success': True, 
                'file': filename,
                'event_count': len(log_entry.get('events', [])),
                'storage': 'file'
            }
    
    def get_logs(self, user_id, filters=None, page=1, per_page=20):
        """
        Retrieve logs with filtering and pagination
        Supports filtering by:
        - project, environment, severity, event_type, date range, trace_id, instance_id
        """
        
        if self.storage_type == 'mongodb':
            # Build query
            query = {'user_id': user_id}
            
            if filters:
                # Filter by project
                if filters.get('project'):
                    query['batch_meta.project'] = filters['project']
                
                # Filter by environment
                if filters.get('environment'):
                    query['batch_meta.environment'] = filters['environment']
                
                # Filter by date range
                if filters.get('start_date') or filters.get('end_date'):
                    query['received_at'] = {}
                    if filters.get('start_date'):
                        query['received_at']['$gte'] = filters['start_date']
                    if filters.get('end_date'):
                        query['received_at']['$lte'] = filters['end_date']
                
                # Filter by trace_id (using processed_events)
                if filters.get('trace_id'):
                    query['processed_events.trace_id'] = filters['trace_id']
                
                # Filter by instance_id
                if filters.get('instance_id'):
                    query['processed_events.instance_id'] = filters['instance_id']
                
                # Filter by severity
                if filters.get('severity'):
                    query['processed_events.event_severity'] = filters['severity']
                
                # Filter by event_type
                if filters.get('event_type'):
                    query['processed_events.event_type'] = filters['event_type']
            
            # Pagination
            skip = (page - 1) * per_page
            
            # Execute query
            cursor = mongo.db.logs.find(query).sort('received_at', -1).skip(skip).limit(per_page)
            
            # Convert ObjectId to string and prepare for response
            logs = []
            for log in cursor:
                log['_id'] = str(log['_id'])
                # Convert datetime objects to ISO format strings
                if isinstance(log.get('received_at'), datetime):
                    log['received_at'] = log['received_at'].isoformat()
                if isinstance(log.get('processed_at'), datetime):
                    log['processed_at'] = log['processed_at'].isoformat() if log.get('processed_at') else None
                logs.append(log)
            
            # Get total count
            total = mongo.db.logs.count_documents(query)
            
            return {
                'logs': logs,
                'total': total,
                'page': page,
                'per_page': per_page,
                'total_pages': (total + per_page - 1) // per_page,
                'filters': filters
            }

        else:
            # For file storage, read from JSON files
            import glob
            import os
            
            log_files = glob.glob(f"{current_app.config['LOGS_STORAGE_PATH']}/json/batch_*.json")
            log_files.sort(reverse=True)  # Most recent first
            
            # Paginate files
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            selected_files = log_files[start_idx:end_idx]
            
            logs = []
            for file_path in selected_files:
                with open(file_path, 'r') as f:
                    log_data = json.load(f)
                    logs.append(log_data)
            
            return {
                'logs': logs,
                'total': len(log_files),
                'page': page,
                'per_page': per_page,
                'total_pages': (len(log_files) + per_page - 1) // per_page
            }
    
    def get_events_aggregated(self, user_id, filters=None):
        
        """
        Get aggregated event data for dashboards
        This flattens the events array for analytics
        """
        pipeline = [
            {'$match': {'user_id': user_id}},
            {'$unwind': '$processed_events'},
            {'$match': self._build_event_match(filters)},
            {
                '$group': {
                    '_id': {
                        'event_type': '$processed_events.event_type',
                        'severity': '$processed_events.event_severity',
                        'date': {'$dateToString': {'format': '%Y-%m-%d', 'date': '$received_at'}}
                    },
                    'count': {'$sum': 1},
                    'unique_instances': {'$addToSet': '$processed_events.instance_id'},
                    'unique_traces': {'$addToSet': '$processed_events.trace_id'}
                }
            },
            {'$sort': {'_id.date': -1}}
        ]
        
        result = list(mongo.db.logs.aggregate(pipeline))
        
        # Format the result
        formatted = {
            'by_type': {},
            'by_severity': {},
            'by_date': {},
            'totals': {
                'total_events': 0,
                'unique_instances': 0,
                'unique_traces': 0
            }
        }
        
        for item in result:
            event_type = item['_id']['event_type'] or 'unknown'
            severity = item['_id']['severity'] or 'unknown'
            date = item['_id']['date']
            
            # Aggregate by type
            if event_type not in formatted['by_type']:
                formatted['by_type'][event_type] = 0
            formatted['by_type'][event_type] += item['count']
            
            # Aggregate by severity
            if severity not in formatted['by_severity']:
                formatted['by_severity'][severity] = 0
            formatted['by_severity'][severity] += item['count']
            
            # Aggregate by date
            if date not in formatted['by_date']:
                formatted['by_date'][date] = 0
            formatted['by_date'][date] += item['count']
            
            # Update totals
            formatted['totals']['total_events'] += item['count']
            formatted['totals']['unique_instances'] += len(item['unique_instances'])
            formatted['totals']['unique_traces'] += len(item['unique_traces'])
        
        return formatted
    
    def _build_event_match(self, filters):
        """Build match condition for event aggregation"""
        match = {}
        if not filters:
            return match
        
        if filters.get('event_type'):
            match['processed_events.event_type'] = filters['event_type']
        
        if filters.get('severity'):
            match['processed_events.event_severity'] = filters['severity']
        
        if filters.get('project'):
            match['batch_meta.project'] = filters['project']
        
        if filters.get('environment'):
            match['batch_meta.environment'] = filters['environment']
        
        if filters.get('start_date') or filters.get('end_date'):
            match['received_at'] = {}
            if filters.get('start_date'):
                match['received_at']['$gte'] = filters['start_date']
            if filters.get('end_date'):
                match['received_at']['$lte'] = filters['end_date']
        
        return match
    
    def get_project_list(self, user_id):
        """Get list of unique projects for a user"""
        projects = mongo.db.logs.distinct('batch_meta.project', {'user_id': user_id})
        return [p for p in projects if p]  # Filter out None/empty
    
    def get_error_rate(self, user_id, hours=24):
        """Calculate error rate for the last X hours"""
        since = datetime.utcnow() - timedelta(hours=hours)
        
        pipeline = [
            {
                '$match': {
                    'user_id': user_id,
                    'received_at': {'$gte': since}
                }
            },
            {'$unwind': '$processed_events'},
            {
                '$group': {
                    '_id': None,
                    'total': {'$sum': 1},
                    'errors': {
                        '$sum': {
                            '$cond': [
                                {'$eq': ['$processed_events.event_severity', 'HIGH']},
                                1,
                                0
                            ]
                        }
                    }
                }
            }
        ]
        
        result = list(mongo.db.logs.aggregate(pipeline))
        if result:
            total = result[0]['total']
            errors = result[0]['errors']
            return {
                'total_events': total,
                'errors': errors,
                'error_rate': (errors / total * 100) if total > 0 else 0,
                'period_hours': hours
            }
        
        return {
            'total_events': 0,
            'errors': 0,
            'error_rate': 0,
            'period_hours': hours
        }
    
    def get_current_month_log_count(self, user_id):
        """Get log count for current month (for quota checking)"""
        if self.storage_type == 'mongodb':
            start_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            query = {
                'user_id': user_id,
                'received_at': {'$gte': start_of_month}
            }
            
            # Sum up event counts from batches
            pipeline = [
                {'$match': query},
                {
                    '$group': {
                        '_id': None,
                        'total_events': {'$sum': '$batch_meta.event_count'}
                    }
                }
            ]
            
            result = list(mongo.db.logs.aggregate(pipeline))
            return result[0]['total_events'] if result else 0
        return 0