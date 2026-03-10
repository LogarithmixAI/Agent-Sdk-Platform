# Add these methods to the LogService class
from app import mongo
from app.models.log_models import LogModel, LogSchema
from app.services.file_storage_service import FileStorageService
from flask import current_app
from datetime import datetime, timedelta
from bson import ObjectId
import pandas as pd
import json
import os

class LogService:
    """Main service for handling log operations"""
    
    def __init__(self):
        self.file_storage = FileStorageService()
        # self.storage_type = current_app.config.get('STORAGE_TYPE', 'file')
        self.storage_type = None  # Will be set in init_app
        self._initialized = False
        self.mongo = None
    
    def init_app(self, app):
        """Initialize with app context"""
        self.storage_type = app.config.get('STORAGE_TYPE', 'file')
        self.file_storage.init_app(app)
        
        # ✅ Initialize MongoDB if configured
        if self.storage_type == 'mongodb':
            try:
                from app import mongo as app_mongo
                self.mongo = app_mongo
                print("✅ MongoDB client initialized in LogService")
            except Exception as e:
                print(f"⚠️ Failed to initialize MongoDB: {e}")
                self.mongo = None
                self.storage_type = 'file'  # Fallback to file
        
        self._initialized = True

    def _get_default_stats(self):
        """Return default statistics when no data is available"""
        return {
            'total_events': 0,
            'unique_instances': 0,
            'unique_traces': 0,
            'errors': 0,
            'error_rate': 0,
            'growth': 0,
            'by_type': {},
            'by_severity': {},
            'projects': {},
            'period': {}
        }

    def _ensure_initialized(self):
        """Check if service is initialized"""
        if not self._initialized:
            from flask import current_app
            try:
                if current_app:
                    self.init_app(current_app)
                else:
                    raise RuntimeError("LogService not initialized. Call init_app() first.")
            except RuntimeError:
                raise RuntimeError("LogService not initialized. Call init_app() with app context.")

    def get_project_list(self, user_id):
        """Get list of unique projects for a user"""
        self._ensure_initialized()
        
        if self.storage_type == 'mongodb':
            try:
                projects = self.mongo.db.logs.distinct('batch_meta.project', {'user_id': user_id})
                return [p for p in projects if p]  # Filter out None/empty
            except Exception as e:
                print(f"Error getting project list: {e}")
                return []
        return []

    def get_project_stats(self, user_id, project, start_date, end_date):
        """Get statistics for a specific project"""
        self._ensure_initialized()
        
        if self.storage_type == 'mongodb':
            try:
                pipeline = [
                    {
                        '$match': {
                            'user_id': user_id,
                            'batch_meta.project': project,
                            'received_at': {'$gte': start_date, '$lte': end_date}
                        }
                    },
                    {'$unwind': '$processed_events'},
                    {
                        '$group': {
                            '_id': {
                                'date': {'$dateToString': {'format': '%Y-%m-%d', 'date': '$received_at'}},
                                'type': '$processed_events.event_type',
                                'severity': '$processed_events.event_severity'
                            },
                            'count': {'$sum': 1}
                        }
                    },
                    {'$sort': {'_id.date': 1}}
                ]
                
                results = list(self.mongo.db.logs.aggregate(pipeline))
                
                # Format results
                by_date = {}
                by_type = {}
                by_severity = {}
                
                for item in results:
                    date = item['_id']['date']
                    event_type = item['_id']['type'] or 'unknown'
                    severity = item['_id']['severity'] or 'unknown'
                    count = item['count']
                    
                    # By date
                    if date not in by_date:
                        by_date[date] = 0
                    by_date[date] += count
                    
                    # By type
                    if event_type not in by_type:
                        by_type[event_type] = 0
                    by_type[event_type] += count
                    
                    # By severity
                    if severity not in by_severity:
                        by_severity[severity] = 0
                    by_severity[severity] += count
                
                return {
                    'project': project,
                    'period': {
                        'start': start_date.isoformat(),
                        'end': end_date.isoformat()
                    },
                    'total_events': sum(by_date.values()),
                    'by_date': by_date,
                    'by_type': by_type,
                    'by_severity': by_severity
                }
            except Exception as e:
                print(f"Error getting project stats: {e}")
                return {
                    'project': project,
                    'total_events': 0,
                    'by_date': {},
                    'by_type': {},
                    'by_severity': {}
                }
        
        return {
            'project': project,
            'total_events': 0,
            'by_date': {},
            'by_type': {},
            'by_severity': {}
        }
    
    def store_log_batch(self, request_data, user_id=None, api_key_details=None):
        """Store a batch of logs from the Agent SDK"""
        
        # Prepare log for storage
        log_entry = LogModel.prepare_log(request_data, user_id, api_key_details)
        
        # Store based on environment
        if self.storage_type == 'mongodb' and current_app.config.get('MONGO_URI'):
            # Store in MongoDB
            result = mongo.db.logs.insert_one(log_entry)
            
            # Update user's log count
            from app.models.user_models import User
            from app import db
            user = User.query.filter_by(public_id=user_id).first()
            if user:
                # Increment by actual event count
                event_count = len(log_entry.get('events', []))
                user.total_logs += event_count
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
            logs_path = current_app.config.get('LOGS_STORAGE_PATH', './logs_data')
        
            # ✅ USER-SPECIFIC DIRECTORY - SECURE!
            user_dir = os.path.join(logs_path, 'json', f"user_{user_id}")
            os.makedirs(user_dir, exist_ok=True)
            filename = f"batch_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
            file_path = os.path.join(user_dir, filename)
            
            # Convert datetime objects to string for JSON serialization
            def datetime_converter(o):
                if isinstance(o, datetime):
                    return o.isoformat()
                raise TypeError(f'Object of type {o.__class__.__name__} is not JSON serializable')
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(log_entry, f, default=datetime_converter, indent=2)
            
            return {
                'success': True, 
                'file': filename,
                'event_count': len(log_entry.get('events', [])),
                'storage': 'file'
            }

    def get_logs(self, user_id, filters=None, page=1, per_page=50):
        """Retrieve logs with filtering and pagination - Supports both MongoDB and File storage"""
        
        print(f"\n🔍 Getting logs for user: {user_id}")
        print(f"📋 Storage type: {self.storage_type}")
        
        # ============================================
        # CASE 1: MONGODB STORAGE
        # ============================================
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
        # ============================================
        # CASE 2: FILE STORAGE (YOUR ACTUAL STORAGE)
        # ============================================
        print("📁 Using FILE storage")
        
        try:
            import glob
            import json
            import os
            from flask import current_app
            
            # Get logs path from config
            logs_path = current_app.config.get('LOGS_STORAGE_PATH', './logs_data')
            user_dir = os.path.join(logs_path, 'json', f"user_{user_id}")
            
            print(f"📁 Looking in: {user_dir}")
            
            # Check if directory exists
            if not os.path.exists(user_dir):
                print(f"⚠️ Directory not found: {user_dir}")
                return {
                    'logs': [],
                    'total': 0,
                    'page': page,
                    'per_page': per_page,
                    'total_pages': 0
                }
            
            # Get all JSON files
            pattern = os.path.join(user_dir, "*.json")
            log_files = glob.glob(pattern)
            log_files.sort(reverse=True)  # Newest first
            
            print(f"📄 Found {len(log_files)} log files")
            
            # Apply filters (basic implementation)
            filtered_files = []
            start_date = None
            end_date = None
            
            if filters:
                start_date = filters.get('start_date')
                end_date = filters.get('end_date')
            
            for file_path in log_files:
                include = True
                
                # Date filtering by filename (which contains timestamp)
                if start_date or end_date:
                    try:
                        # Extract timestamp from filename (format: batch_YYYYMMDD_HHMMSS.json)
                        filename = os.path.basename(file_path)
                        if filename.startswith('batch_'):
                            date_str = filename.replace('batch_', '').replace('.json', '')
                            try:
                                file_date = datetime.strptime(date_str, '%Y%m%d_%H%M%S')
                                
                                if start_date and file_date < start_date:
                                    include = False
                                if end_date and file_date > end_date:
                                    include = False
                            except:
                                pass
                    except:
                        pass
                
                if include:
                    filtered_files.append(file_path)
            
            print(f"📊 After filters: {len(filtered_files)} files")
            
            # Pagination
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            selected_files = filtered_files[start_idx:end_idx]
            
            # Read and format logs
            logs = []
            for file_path in selected_files:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # Extract filename for ID
                    filename = os.path.basename(file_path)
                    
                    # Format log for frontend
                    formatted_log = {
                        '_id': filename,
                        'received_at': data.get('received_at'),
                        'batch_meta': data.get('batch_meta', {}),
                        'events': data.get('events', []),
                        'event_count': len(data.get('events', []))
                    }
                    
                    # Add first event info for preview
                    events = data.get('events', [])
                    if events:
                        first_event = events[0]
                        formatted_log['first_event_type'] = first_event.get('event', {}).get('type', 'unknown')
                        formatted_log['first_event_severity'] = first_event.get('event', {}).get('severity', 'INFO')
                    
                    logs.append(formatted_log)
                    
                except Exception as e:
                    print(f"❌ Error reading {file_path}: {e}")
            
            print(f"✅ Returning {len(logs)} logs")
            
            return {
                'logs': logs,
                'total': len(filtered_files),
                'page': page,
                'per_page': per_page,
                'total_pages': (len(filtered_files) + per_page - 1) // per_page
            }
            
        except Exception as e:
            print(f"❌ File storage error: {e}")
            return {
                'logs': [],
                'total': 0,
                'page': page,
                'per_page': per_page,
                'total_pages': 0
            }

    def get_logs_for_users(self, user_ids, filters=None, page=1, per_page=50):
        """
        Get logs for multiple users (for team access)
        
        Args:
            user_ids: List of user public_ids
            filters: Dictionary of filters (project, environment, dates)
            page: Page number
            per_page: Items per page
        
        Returns:
            Dictionary with logs, total count, pagination info
        """
        self._ensure_initialized()
        
        print(f"\n🔍 GET_LOGS_FOR_USERS:")
        print(f"  User IDs: {[uid[:8] for uid in user_ids]}")
        print(f"  Storage type: {self.storage_type}")
        
        if (self.storage_type == 'mongodb' and 
            self.mongo is not None and 
            hasattr(self.mongo, 'db') and 
            self.mongo.db is not None):
            
            try:
                # Build query for multiple users
                query = {'user_id': {'$in': user_ids}}
                
                # Apply filters
                if filters:
                    if filters.get('project'):
                        query['payload.batch_meta.project'] = filters['project']
                    if filters.get('environment'):
                        query['payload.batch_meta.environment'] = filters['environment']
                    if filters.get('start_date') or filters.get('end_date'):
                        query['received_at'] = {}
                        if filters.get('start_date'):
                            query['received_at']['$gte'] = filters['start_date']
                        if filters.get('end_date'):
                            query['received_at']['$lte'] = filters['end_date']
                
                print(f"  MongoDB Query: {query}")
                
                # Count total documents
                total = self.mongo.db.logs.count_documents(query)
                print(f"  Total logs: {total}")
                
                # Pagination
                skip = (page - 1) * per_page
                
                # Get logs
                cursor = self.mongo.db.logs.find(query).sort('received_at', -1).skip(skip).limit(per_page)
                
                logs = []
                for log in cursor:
                    log['_id'] = str(log['_id'])
                    
                    # Format for frontend
                    formatted_log = {
                        '_id': log['_id'],
                        'user_id': log.get('user_id'),  # 👈 USER ID ADD KARO
                        'received_at': log.get('received_at'),
                        'batch_meta': log.get('batch_meta', {}),
                        'events': log.get('events', []),
                        'event_count': len(log.get('events', [])),
                        'processed_events': log.get('processed_events', []),
                        'api_key': log.get('api_key'),
                        'ip': log.get('ip')
                    }
                    
                    # Add first event info for preview
                    events = log.get('events', [])
                    if events:
                        first_event = events[0]
                        formatted_log['first_event_type'] = first_event.get('event', {}).get('type', 'unknown')
                        formatted_log['first_event_severity'] = first_event.get('event', {}).get('severity', 'INFO')
                    
                    logs.append(formatted_log)
                
                print(f"  Returning {len(logs)} logs")
                
                return {
                    'logs': logs,
                    'total': total,
                    'page': page,
                    'per_page': per_page,
                    'total_pages': (total + per_page - 1) // per_page
                }
            
            except Exception as e:
                print(f"❌ Error in get_logs_for_users: {e}")
                import traceback
                traceback.print_exc()
                return {
                    'logs': [], 
                    'total': 0, 
                    'page': page, 
                    'per_page': per_page, 
                    'total_pages': 0,
                    'error': str(e)
                }
    
        print("⚠️ MongoDB not available, returning empty")
        return {
            'logs': [], 
            'total': 0, 
            'page': page, 
            'per_page': per_page, 
            'total_pages': 0
        }

    def get_distinct_values_for_users(self, user_ids, field):
        """Get distinct values for a field across multiple users"""
        self._ensure_initialized()
        
        if (self.storage_type == 'mongodb' and 
            self.mongo is not None and 
            hasattr(self.mongo, 'db') and 
            self.mongo.db is not None):
            try:
                values = self.mongo.db.logs.distinct(
                    field, 
                    {'user_id': {'$in': user_ids}}
                )
                return [v for v in values if v]
            except Exception as e:
                print(f"Error: {e}")
                return []
        return []

    def get_current_month_log_count(self, user_id):
        """Get log count for current month (for quota checking) - Supports both storages"""
        self._ensure_initialized()
        from datetime import datetime
        # ============================================
        # CASE 1: MONGODB
        # ============================================
        if self.storage_type == 'mongodb' and hasattr(self, 'mongo') and self.mongo:
            try:
                start_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                count = self.mongo.db.logs.count_documents({
                    'user_id': user_id,
                    'received_at': {'$gte': start_of_month}
                })
                return count
            except Exception as e:
                print(f"Error getting month count: {e}")
                return 0
        
        # ============================================
        # CASE 2: FILE STORAGE
        # ============================================
        try:
            import glob
            import os
            from flask import current_app
            from datetime import datetime
            
            logs_path = current_app.config.get('LOGS_STORAGE_PATH', './logs_data')
            user_dir = os.path.join(logs_path, 'json', f"user_{user_id}")
            
            if not os.path.exists(user_dir):
                return 0
            
            # Get all files
            pattern = os.path.join(user_dir, "*.json")
            files = glob.glob(pattern)
            
            # Count files from this month
            current_month = datetime.utcnow().strftime('%Y%m')
            count = 0
            
            for file_path in files:
                filename = os.path.basename(file_path)
                if filename.startswith('batch_') and filename[6:12] == current_month:
                    count += 1
            
            # Each file is one batch, but we want event count
            # You might want to read files to count actual events
            return count  # Returns number of batches this month
            
        except Exception as e:
            print(f"Error getting file count: {e}")
            return 0

    def get_analytics(self, user_id, period='day', date=None):
        """Get analytics for dashboard"""
        if not date:
            date = datetime.utcnow()
        
        if period == 'day':
            start_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=1)
        elif period == 'week':
            start_date = date - timedelta(days=date.weekday())
            start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=7)
        elif period == 'month':
            start_date = date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            next_month = date.month + 1 if date.month < 12 else 1
            year = date.year if date.month < 12 else date.year + 1
            end_date = datetime(year, next_month, 1)
        
        # Get logs for the period
        filters = {
            'start_date': start_date,
            'end_date': end_date
        }
        
        result = self.get_logs(user_id, filters, page=1, per_page=10000)
        
        if not result['logs']:
            return {
                'total_events': 0,
                'unique_visitors': 0,
                'unique_sessions': 0,
                'events_by_type': {},
                'events_by_page': {},
                'countries': {},
                'browsers': {},
                'devices': {}
            }
        
        # Convert to DataFrame for analysis
        df = pd.DataFrame(result['logs'])
        
        analytics = {
            'total_events': len(df),
            'unique_visitors': df['visitor_id'].nunique() if 'visitor_id' in df else 0,
            'unique_sessions': df['session_id'].nunique() if 'session_id' in df else 0,
            'events_by_type': df['event_type'].value_counts().to_dict() if 'event_type' in df else {},
            'events_by_page': df['page_url'].value_counts().head(10).to_dict() if 'page_url' in df else {},
            'countries': df['country'].value_counts().to_dict() if 'country' in df else {},
            'browsers': df['browser'].value_counts().to_dict() if 'browser' in df else {},
            'devices': df['device'].value_counts().to_dict() if 'device' in df else {}
        }
        
        return analytics

    def get_dashboard_stats(self, user_id, start_date, end_date):
        """Get comprehensive dashboard statistics"""
        
        print(f"\n📊 Getting dashboard stats for user: {user_id}")
        
        if (self.storage_type == 'mongodb' and 
            self.mongo is not None and 
            hasattr(self.mongo, 'db') and 
            self.mongo.db is not None):
            
            try:
                pipeline = [
                    {
                        '$match': {
                            'user_id': user_id,
                            'received_at': {'$gte': start_date, '$lte': end_date}
                        }
                    },
                    {
                        '$facet': {
                            'totals': [
                                {'$unwind': '$processed_events'},
                                {'$count': 'total_events'}
                            ],
                            'unique_instances': [
                                {'$unwind': '$processed_events'},
                                {
                                    '$group': {
                                        '_id': '$processed_events.instance_id'
                                    }
                                },
                                {'$count': 'count'}
                            ],
                            'unique_traces': [
                                {'$unwind': '$processed_events'},
                                {
                                    '$group': {
                                        '_id': '$processed_events.trace_id'
                                    }
                                },
                                {'$count': 'count'}
                            ],
                            'errors': [
                                {'$unwind': '$processed_events'},
                                {
                                    '$match': {
                                        '$or': [
                                            {'processed_events.event_severity': 'HIGH'},
                                            {'processed_events.event_status': 'FAILURE'}
                                        ]
                                    }
                                },
                                {'$count': 'count'}
                            ],
                            'by_type': [
                                {'$unwind': '$processed_events'},
                                {
                                    '$group': {
                                        '_id': '$processed_events.event_type',
                                        'count': {'$sum': 1}
                                    }
                                }
                            ],
                            'by_severity': [
                                {'$unwind': '$processed_events'},
                                {
                                    '$group': {
                                        '_id': '$processed_events.event_severity',
                                        'count': {'$sum': 1}
                                    }
                                }
                            ],
                            'projects': [
                                {
                                    '$group': {
                                        '_id': '$batch_meta.project',
                                        'count': {'$sum': 1}
                                    }
                                }
                            ]
                        }
                    }
                ]
                
                result = list(self.mongo.db.logs.aggregate(pipeline))
                
                if result and result[0]:
                    data = result[0]
                    
                    # Get values with fallbacks
                    totals = data.get('totals', [{}])[0]
                    total_events = totals.get('total_events', 0)
                    
                    unique_instances = data.get('unique_instances', [{}])[0].get('count', 0)
                    unique_traces = data.get('unique_traces', [{}])[0].get('count', 0)
                    errors = data.get('errors', [{}])[0].get('count', 0)
                    
                    # Calculate error rate
                    error_rate = round((errors / max(total_events, 1)) * 100, 2)
                    
                    print(f"✅ Stats calculated:")
                    print(f"   Total events: {total_events}")
                    print(f"   Unique instances: {unique_instances}")
                    print(f"   Errors: {errors}")
                    print(f"   Error rate: {error_rate}%")
                    
                    return {
                        'total_events': total_events,
                        'unique_instances': unique_instances,
                        'unique_traces': unique_traces,
                        'errors': errors,
                        'error_rate': error_rate,
                        'growth': 0,
                        'by_type': {
                            item['_id'] or 'unknown': item['count'] 
                            for item in data.get('by_type', [])
                        },
                        'by_severity': {
                            item['_id'] or 'unknown': item['count'] 
                            for item in data.get('by_severity', [])
                        },
                        'projects': {
                            item['_id'] or 'unknown': item['count'] 
                            for item in data.get('projects', [])
                        },
                        'period': {
                            'start': start_date.isoformat(),
                            'end': end_date.isoformat(),
                            'days': (end_date - start_date).days
                        }
                    }
                
            except Exception as e:
                print(f"❌ Dashboard stats error: {e}")
                import traceback
                traceback.print_exc()
        
        return self._get_default_stats()    

    def get_timeseries_data(self, user_id, start_date, end_date, interval='day'):
        """Get time series data for charts"""
        
        if (self.storage_type == 'mongodb' and 
            self.mongo is not None and 
            hasattr(self.mongo, 'db') and 
            self.mongo.db is not None):
            
            try:
                # Date format based on interval
                date_format = {
                    'hour': '%Y-%m-%d %H:00',
                    'day': '%Y-%m-%d',
                    'week': '%Y-%W',
                    'month': '%Y-%m'
                }.get(interval, '%Y-%m-%d')
                
                pipeline = [
                    {
                        '$match': {
                            'user_id': user_id,
                            'received_at': {'$gte': start_date, '$lte': end_date}
                        }
                    },
                    {'$unwind': '$processed_events'},
                    {
                        '$group': {
                            '_id': {
                                'date': {'$dateToString': {'format': date_format, 'date': '$received_at'}},
                                'type': '$processed_events.event_type'
                            },
                            'count': {'$sum': 1}
                        }
                    },
                    {'$sort': {'_id.date': 1}}
                ]
                results = list(self.mongo.db.logs.aggregate(pipeline))
                
                # Format for chart.js
                dates = sorted(set(item['_id']['date'] for item in results))
                event_types = sorted(set(item['_id']['type'] for item in results if item['_id']['type']))
                
                datasets = []
                colors = ['#36A2EB', '#FF6384', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40']
                
                for i, event_type in enumerate(event_types):
                    data = []
                    for date in dates:
                        count = next(
                            (item['count'] for item in results 
                            if item['_id']['date'] == date and item['_id']['type'] == event_type),
                            0
                        )
                        data.append(count)
                    
                    datasets.append({
                        'label': event_type or 'Unknown',
                        'data': data,
                        'borderColor': colors[i % len(colors)],
                        'backgroundColor': colors[i % len(colors)] + '20',
                        'tension': 0.4
                    })
                
                return {
                    'labels': dates,
                    'datasets': datasets
                }
                
            except Exception as e:
                print(f"❌ Timeseries error: {e}")
        
        return {'labels': [], 'datasets': []}


    def get_events_by_type(self, user_id, start_date, end_date):
        """Get event type distribution for pie chart"""
        
        if self.storage_type == 'mongodb':
            pipeline = [
                {
                    '$match': {
                        'user_id': user_id,
                        'received_at': {'$gte': start_date, '$lte': end_date}
                    }
                },
                {'$unwind': '$processed_events'},
                {
                    '$group': {
                        '_id': '$processed_events.event_type',
                        'count': {'$sum': 1}
                    }
                },
                {'$sort': {'count': -1}}
            ]
            
            results = list(self.mongo.db.logs.aggregate(pipeline))
            
            return {
                'labels': [r['_id'] or 'Unknown' for r in results],
                'data': [r['count'] for r in results],
                'total': sum(r['count'] for r in results)
            }
        
        return {'labels': [], 'data': [], 'total': 0}

    def get_severity_distribution(self, user_id, start_date, end_date):
        """Get severity distribution"""
        print(f'severtiy distribution : {self.storage_type == 'mongodb' and self.mongo is not None}')
        if (self.storage_type == 'mongodb' and self.mongo is not None):
            try:
                pipeline = [
                    {
                        '$match': {
                            'user_id': user_id,
                            'received_at': {'$gte': start_date, '$lte': end_date}
                        }
                    },
                    {'$unwind': '$processed_events'},
                    {
                        '$group': {
                            '_id': '$processed_events.event_severity',
                            'count': {'$sum': 1}
                        }
                    }
                ]
                
                results = list(self.mongo.db.logs.aggregate(pipeline))
                
                colors = {
                    'HIGH': '#dc3545',
                    'MEDIUM': '#ffc107',
                    'LOW': '#28a745',
                    'INFO': '#17a2b8'
                }
                
                return {
                    'labels': [r['_id'] or 'UNKNOWN' for r in results],
                    'data': [r['count'] for r in results],
                    'colors': [colors.get(r['_id'], '#6c757d') for r in results],
                    'total': sum(r['count'] for r in results)
                }
                
            except Exception as e:
                print(f"Error: {e}")
        
        return {'labels': [], 'data': [], 'colors': [], 'total': 0}

    def get_top_pages(self, user_id, start_date, end_date, limit=10):
        """Get top pages by event count"""
        
        if (self.storage_type == 'mongodb' and 
            self.mongo is not None and 
            hasattr(self.mongo, 'db') and 
            self.mongo.db is not None):
            
            try:
                pipeline = [
                    {
                        '$match': {
                            'user_id': user_id,
                            'received_at': {'$gte': start_date, '$lte': end_date}
                        }
                    },
                    {'$unwind': '$processed_events'},
                    # Sirf INCOMING_REQUEST type ke events filter karo
                    {
                        '$match': {
                            'processed_events.event_type': 'INCOMING_REQUEST'
                        }
                    },
                    {
                        '$group': {
                            '_id': '$processed_events.event_data.path',  # ✅ SAHI PATH
                            'count': {'$sum': 1},
                            'last_seen': {'$max': '$received_at'}
                        }
                    },
                    {'$match': {'_id': {'$ne': None, '$ne': ''}}},
                    {'$sort': {'count': -1}},
                    {'$limit': limit}
                ]
                
                results = list(self.mongo.db.logs.aggregate(pipeline))
                
                pages = []
                for r in results:
                    pages.append({
                        'url': r['_id'] or '/',
                        'count': r['count'],
                        'last_seen': r['last_seen'].isoformat() if r['last_seen'] else None
                    })
                
                print(f"📊 Top pages found: {pages}")
                return pages
                
            except Exception as e:
                print(f"❌ Error in get_top_pages: {e}")
                import traceback
                traceback.print_exc()
                return []
        
        return []

    def get_recent_logs(self, user_id, limit=10):
        """Get most recent logs"""
        
        if self.storage_type == 'mongodb':
            cursor = self.mongo.db.logs.find(
                {'user_id': user_id}
            ).sort('received_at', -1).limit(limit)
            
            logs = []
            for log in cursor:
                # Get first event for preview
                events = log.get('events', [])
                first_event = events[0] if events else {}
                
                logs.append({
                    'id': str(log['_id']),
                    'received_at': log['received_at'].isoformat() if log.get('received_at') else None,
                    'project': log.get('batch_meta', {}).get('project'),
                    'environment': log.get('batch_meta', {}).get('environment'),
                    'event_count': len(events),
                    'first_event_type': first_event.get('event', {}).get('type'),
                    'first_event_severity': first_event.get('event', {}).get('severity')
                })
            
            return logs
        
        return []

    def get_recent_errors(self, user_id, limit=10):
        """Get most recent error logs"""
        
        if self.storage_type == 'mongodb':
            pipeline = [
                {'$match': {'user_id': user_id}},
                {'$unwind': '$processed_events'},
                {'$match': {'processed_events.event_severity': 'HIGH'}},
                {'$sort': {'received_at': -1}},
                {'$limit': limit},
                {
                    '$project': {
                        'timestamp': '$received_at',
                        'message': '$processed_events.event_data.message',
                        'type': '$processed_events.event_type',
                        'trace_id': '$processed_events.trace_id',
                        'instance_id': '$processed_events.instance_id',
                        'project': '$batch_meta.project'
                    }
                }
            ]
            
            results = list(self.mongo.db.logs.aggregate(pipeline))
            
            return [{
                'timestamp': r['timestamp'].isoformat() if r.get('timestamp') else None,
                'message': r.get('message', 'Unknown error')[:100] + '...' if r.get('message') else 'Unknown error',
                'type': r.get('type', 'ERROR'),
                'trace_id': r.get('trace_id'),
                'instance_id': r.get('instance_id'),
                'project': r.get('project')
            } for r in results]
        
        return []

    def get_total_events(self, user_id, start_date, end_date):
        """Get total events in date range"""
        
        if self.storage_type == 'mongodb':
            pipeline = [
                {
                    '$match': {
                        'user_id': user_id,
                        'received_at': {'$gte': start_date, '$lte': end_date}
                    }
                },
                {'$unwind': '$processed_events'},
                {'$count': 'total'}
            ]
            
            result = list(self.mongo.db.logs.aggregate(pipeline))
            return result[0]['total'] if result else 0
        
        return 0

    def _calculate_growth(self, current, previous):
        """Calculate growth percentage"""
        if previous == 0:
            return 100 if current > 0 else 0
        return round(((current - previous) / previous) * 100, 1)

    def get_distinct_values(self, user_id, field):
        """Get distinct values for a field"""
        self._ensure_initialized()
        
        if self.storage_type == 'mongodb':
            try:
                values = self.mongo.db.logs.distinct(field, {'user_id': user_id})
                return [v for v in values if v]  # Filter out None/empty
            except:
                return []
        return []

    def get_log_by_id(self, user_id, log_id):
        """Get a specific log by ID"""
        self._ensure_initialized()
        
        if self.storage_type == 'mongodb':
            from bson.objectid import ObjectId
            
            try:
                log = self.mongo.db.logs.find_one({
                    '_id': ObjectId(log_id),
                    'user_id': user_id
                })
                
                if log:
                    log['_id'] = str(log['_id'])
                    if log.get('received_at'):
                        log['received_at'] = log['received_at'].isoformat()
                
                return log
            except:
                return None
        return None

    def get_events_by_batch(self, user_id, log_id):
        """Get all events from a specific batch"""
        self._ensure_initialized()
        
        log = self.get_log_by_id(user_id, log_id)
        if log:
            return log.get('events', [])
        return []

    def get_project_stats(self, user_id, project, start_date, end_date):
        """Get statistics for a specific project"""
        self._ensure_initialized()
        
        if self.storage_type == 'mongodb':
            pipeline = [
                {
                    '$match': {
                        'user_id': user_id,
                        'batch_meta.project': project,
                        'received_at': {'$gte': start_date, '$lte': end_date}
                    }
                },
                {'$unwind': '$processed_events'},
                {
                    '$group': {
                        '_id': {
                            'date': {'$dateToString': {'format': '%Y-%m-%d', 'date': '$received_at'}},
                            'type': '$processed_events.event_type',
                            'severity': '$processed_events.event_severity'
                        },
                        'count': {'$sum': 1}
                    }
                },
                {'$sort': {'_id.date': 1}}
            ]
            
            results = list(self.mongo.db.logs.aggregate(pipeline))
            
            # Format results
            by_date = {}
            by_type = {}
            by_severity = {}
            
            for item in results:
                date = item['_id']['date']
                event_type = item['_id']['type'] or 'unknown'
                severity = item['_id']['severity'] or 'unknown'
                count = item['count']
                
                # By date
                if date not in by_date:
                    by_date[date] = 0
                by_date[date] += count
                
                # By type
                if event_type not in by_type:
                    by_type[event_type] = 0
                by_type[event_type] += count
                
                # By severity
                if severity not in by_severity:
                    by_severity[severity] = 0
                by_severity[severity] += count
            
            return {
                'project': project,
                'period': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                },
                'total_events': sum(by_date.values()),
                'by_date': by_date,
                'by_type': by_type,
                'by_severity': by_severity
            }
        
        return {
            'project': project,
            'total_events': 0,
            'by_date': {},
            'by_type': {},
            'by_severity': {}
        }

    def search_logs(self, user_id, query, limit=50):
        """Search logs by text query"""
        self._ensure_initialized()
        
        if self.storage_type == 'mongodb':
            # Text search implementation
            # This is a simple version - you might want to use MongoDB text indexes
            pipeline = [
                {'$match': {'user_id': user_id}},
                {'$unwind': '$processed_events'},
                {
                    '$match': {
                        '$or': [
                            {'processed_events.trace_id': {'$regex': query, '$options': 'i'}},
                            {'processed_events.instance_id': {'$regex': query, '$options': 'i'}},
                            {'batch_meta.project': {'$regex': query, '$options': 'i'}}
                        ]
                    }
                },
                {'$limit': limit},
                {
                    '$project': {
                        'log_id': '$_id',
                        'timestamp': '$received_at',
                        'project': '$batch_meta.project',
                        'environment': '$batch_meta.environment',
                        'trace_id': '$processed_events.trace_id',
                        'event_type': '$processed_events.event_type'
                    }
                }
            ]
            
            results = list(self.mongo.db.logs.aggregate(pipeline))
            
            # Format results
            for r in results:
                r['_id'] = str(r['_id'])
                if r.get('timestamp'):
                    r['timestamp'] = r['timestamp'].isoformat()
            
            return results
        
        return []

    def get_key_usage_today(self, key_id, start_of_day):
        """Get API key usage count for today from MongoDB"""
        
        if (self.storage_type == 'mongodb' and 
            self.mongo is not None and 
            hasattr(self.mongo, 'db') and 
            self.mongo.db is not None):
            
            try:
                # Count documents with this API key and received_at >= today
                count = self.mongo.db.logs.count_documents({
                    'api_key': key_id,
                    'received_at': {'$gte': start_of_day}
                })
                return count
            except Exception as e:
                print(f"Error getting key usage today: {e}")
                return 0
        
        # Agar MongoDB nahi hai to file storage se count karo
        elif self.storage_type == 'file':
            try:
                import glob
                import os
                import json
                from flask import current_app
                
                logs_path = current_app.config.get('LOGS_STORAGE_PATH', './logs_data')
                pattern = f"{logs_path}/json/**/*.json"
                files = glob.glob(pattern, recursive=True)
                
                count = 0
                for file_path in files:
                    try:
                        with open(file_path, 'r') as f:
                            data = json.load(f)
                            if data.get('api_key') == key_id:
                                received_at = data.get('received_at')
                                if received_at and received_at >= start_of_day.isoformat():
                                    count += 1
                    except:
                        continue
                return count
            except Exception as e:
                print(f"Error in file count: {e}")
                return 0
        
        return 0