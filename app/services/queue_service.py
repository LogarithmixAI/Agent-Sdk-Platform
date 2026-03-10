# app/services/queue_service.py - Simplified without Redis
from datetime import datetime
import uuid
import json

class QueueService:
    """Simple queue service without Redis"""
    
    def __init__(self):
        self.in_memory_queue = []
    
    def init_app(self, app):
        """Simple initialization"""
        self.app = app
        print("QueueService running in simple mode (without Redis)")
    
    def enqueue(self, task_name, data=None):
        """Simple in-memory queue"""
        task_id = str(uuid.uuid4())
        
        self.in_memory_queue.append({
            'task_id': task_id,
            'task_name': task_name,
            'data': data,
            'enqueued_at': datetime.utcnow().isoformat()
        })
        
        # Process immediately for now
        self._process_task(task_id, task_name, data)
        
        return {
            'task_id': task_id,
            'status': 'processed'
        }
    
    def _process_task(self, task_id, task_name, data):
        """Process task immediately"""
        print(f"Processing task: {task_name} with ID: {task_id}")
        
        if task_name == 'process_log_batch':
            from app.services.log_service import LogService
            log_service = LogService()
            
            try:
                result = log_service.store_log_batch(
                    data['data'],
                    user_id=data['user_id'],
                    api_key_details=data.get('api_key_details')
                )
                
                # Store result
                self._store_result(task_id, 'COMPLETED', result)
                
            except Exception as e:
                self._store_result(task_id, 'FAILED', {'error': str(e)})
    
    def _store_result(self, task_id, state, result):
        """Store task result in memory"""
        # In production, you might want to store in database
        print(f"Task {task_id} {state}: {result}")
    
    def get_batch_status(self, batch_id):
        """Return simple status"""
        return {
            'state': 'COMPLETED',
            'processed_at': datetime.utcnow().isoformat(),
            'message': 'Processing completed (simple mode)'
        }
    
    def get_queue_stats(self):
        """Return basic stats"""
        return {
            'mode': 'simple',
            'queued': len(self.in_memory_queue)
        }