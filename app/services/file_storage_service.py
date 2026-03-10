import os
import json
import csv
from datetime import datetime
from flask import current_app
import uuid

class FileStorageService:
    """Service for storing logs in local files (development/testing)"""
    
    def __init__(self, base_path="./logs_data"):
        self.base_path = base_path
        self._ensure_directories()
    
    def init_app(self, app):
        """Initialize with app context - call this after app is created"""
        if not self.base_path:
            self.base_path = app.config.get('LOGS_STORAGE_PATH', './logs_data')
        self._ensure_directories()
        self._initialized = True
        return self
        
    def _ensure_directories(self):
        """Create necessary directories if they don't exist"""
        os.makedirs(self.base_path, exist_ok=True)
        os.makedirs(os.path.join(self.base_path, 'json'), exist_ok=True)
        os.makedirs(os.path.join(self.base_path, 'csv'), exist_ok=True)
        os.makedirs(os.path.join(self.base_path, 'failed'), exist_ok=True)
    
    def _get_user_path(self, user_id, format_type='json'):
        """Get path for user's log file"""
        return os.path.join(self.base_path, format_type, f"user_{user_id}")
    
    def _get_daily_file(self, user_id, format_type='json'):
        """Get daily log file path"""
        date_str = datetime.utcnow().strftime('%Y-%m-%d')
        user_dir = self._get_user_path(user_id, format_type)
        os.makedirs(user_dir, exist_ok=True)
        return os.path.join(user_dir, f"{date_str}.{format_type}")
    
    def store_log_json(self, log_entry, user_id):
        """Store a single log entry in JSON file"""
        file_path = self._get_daily_file(user_id, 'json')
        
        # Read existing logs
        logs = []
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                try:
                    logs = json.load(f)
                except json.JSONDecodeError:
                    logs = []
        
        # Add new log
        if 'timestamp' in log_entry and isinstance(log_entry['timestamp'], datetime):
            log_entry['timestamp'] = log_entry['timestamp'].isoformat()
        logs.append(log_entry)
        
        # Write back
        with open(file_path, 'w') as f:
            json.dump(logs, f, indent=2)
        
        return True
    
    def store_log_csv(self, log_entry, user_id):
        """Store log in CSV format (good for testing/analysis)"""
        file_path = self._get_daily_file(user_id, 'csv')
        
        # Prepare flat log entry for CSV
        flat_entry = {
            'id': str(uuid.uuid4()),
            'timestamp': log_entry.get('timestamp', datetime.utcnow().isoformat()),
            'event_type': log_entry.get('event_type', 'unknown'),
            'page_url': log_entry.get('page_url', ''),
            'visitor_id': log_entry.get('visitor_id', ''),
            'session_id': log_entry.get('session_id', ''),
            'ip_address': log_entry.get('ip_address', ''),
            'country': log_entry.get('country', ''),
            'browser': log_entry.get('browser', ''),
            'os': log_entry.get('os', ''),
            'device': log_entry.get('device', ''),
        }
        
        # Add event data as JSON string
        if 'event_data' in log_entry:
            flat_entry['event_data'] = json.dumps(log_entry['event_data'])
        
        # Write to CSV
        file_exists = os.path.exists(file_path)
        with open(file_path, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=flat_entry.keys())
            if not file_exists:
                writer.writeheader()
            writer.writerow(flat_entry)
        
        return True
    
    def get_user_logs(self, user_id, start_date=None, end_date=None, limit=1000):
        """Retrieve logs for a user from JSON files"""
        logs = []
        user_dir = self._get_user_path(user_id, 'json')
        
        if not os.path.exists(user_dir):
            return logs
        
        for filename in os.listdir(user_dir):
            if not filename.endswith('.json'):
                continue
            
            # Filter by date if needed
            if start_date or end_date:
                file_date = filename.replace('.json', '')
                try:
                    file_date = datetime.strptime(file_date, '%Y-%m-%d').date()
                    if start_date and file_date < start_date:
                        continue
                    if end_date and file_date > end_date:
                        continue
                except:
                    pass
            
            file_path = os.path.join(user_dir, filename)
            with open(file_path, 'r') as f:
                try:
                    file_logs = json.load(f)
                    logs.extend(file_logs)
                    if len(logs) >= limit:
                        break
                except:
                    continue
        
        return logs[:limit]
    
    def store_failed_log(self, log_entry, error):
        """Store logs that failed validation/processing for debugging"""
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename = f"failed_{timestamp}_{uuid.uuid4().hex[:8]}.json"
        file_path = os.path.join(self.base_path, 'failed', filename)
        
        failed_entry = {
            'log': log_entry,
            'error': str(error),
            'failed_at': datetime.utcnow().isoformat()
        }
        
        with open(file_path, 'w') as f:
            json.dump(failed_entry, f, indent=2)