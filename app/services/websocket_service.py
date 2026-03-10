from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_login import current_user
from flask import request
import json
from datetime import datetime

# Initialize SocketIO
socketio = SocketIO(cors_allowed_origins="*")

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    if current_user.is_authenticated:
        # Join user's personal room
        join_room(f"user_{current_user.public_id}")
        emit('connected', {
            'status': 'connected',
            'user_id': current_user.public_id,
            'timestamp': datetime.utcnow().isoformat()
        })

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    if current_user.is_authenticated:
        leave_room(f"user_{current_user.public_id}")

@socketio.on('subscribe_project')
def handle_subscribe(data):
    """Subscribe to real-time updates for a project"""
    if not current_user.is_authenticated:
        return
    
    project = data.get('project')
    if project:
        room = f"project_{current_user.public_id}_{project}"
        join_room(room)
        emit('subscribed', {'project': project})

@socketio.on('unsubscribe_project')
def handle_unsubscribe(data):
    """Unsubscribe from project updates"""
    if not current_user.is_authenticated:
        return
    
    project = data.get('project')
    if project:
        room = f"project_{current_user.public_id}_{project}"
        leave_room(room)

class RealtimeService:
    """Service for sending real-time updates via WebSocket"""
    
    @staticmethod
    def send_new_log(user_id, log_data):
        """Send new log notification to user"""
        socketio.emit('new_log', {
            'type': 'new_log',
            'data': {
                'id': log_data.get('id'),
                'project': log_data.get('project'),
                'event_count': log_data.get('event_count'),
                'timestamp': log_data.get('timestamp')
            },
            'timestamp': datetime.utcnow().isoformat()
        }, room=f"user_{user_id}")
    
    @staticmethod
    def send_error_alert(user_id, error_data):
        """Send error alert to user"""
        socketio.emit('error_alert', {
            'type': 'error_alert',
            'data': {
                'message': error_data.get('message'),
                'severity': error_data.get('severity'),
                'project': error_data.get('project'),
                'count': error_data.get('count', 1)
            },
            'timestamp': datetime.utcnow().isoformat()
        }, room=f"user_{user_id}")
    
    @staticmethod
    def send_project_stats(user_id, project, stats):
        """Send updated project statistics"""
        socketio.emit('project_stats', {
            'type': 'project_stats',
            'project': project,
            'data': stats,
            'timestamp': datetime.utcnow().isoformat()
        }, room=f"project_{user_id}_{project}")
    
    @staticmethod
    def send_quota_alert(user_id, usage):
        """Send quota usage alert"""
        socketio.emit('quota_alert', {
            'type': 'quota_alert',
            'data': {
                'current': usage['current'],
                'limit': usage['limit'],
                'percentage': usage['percentage']
            },
            'timestamp': datetime.utcnow().isoformat()
        }, room=f"user_{user_id}")