import requests
import hmac
import hashlib
import json
from datetime import datetime
from flask import current_app
from app import db
from app.models.user_models import Webhook
from app.models.webhook_models import WebhookDelivery

class WebhookService:
    
    @staticmethod
    def trigger(event_type, payload, user_id=None, team_id=None):
        """Trigger webhooks for an event"""
        
        # Find matching webhooks
        query = Webhook.query.filter_by(is_active=True)
        
        if user_id:
            query = query.filter_by(user_id=user_id)
        
        # Filter by event type
        webhooks = query.all()
        matching = []
        
        for webhook in webhooks:
            if '*' in webhook.events or event_type in webhook.events:
                matching.append(webhook)
        
        # Send to each webhook asynchronously
        for webhook in matching:
            WebhookService._send_async(webhook, event_type, payload)
    
    @staticmethod
    def _send_async(webhook, event_type, payload):
        """Send webhook asynchronously"""
        from threading import Thread
        
        thread = Thread(
            target=WebhookService._send,
            args=(webhook, event_type, payload)
        )
        thread.daemon = True
        thread.start()
    
    @staticmethod
    def _send(webhook, event_type, payload):
        """Send webhook with retry logic"""
        from app import create_app
        
        # Create app context for database operations
        app = create_app()
        with app.app_context():
            webhook = Webhook.query.get(webhook.id)
            
            # Prepare payload
            webhook_payload = {
                'event': event_type,
                'timestamp': datetime.utcnow().isoformat(),
                'data': payload
            }
            
            # Sign payload
            signature = hmac.new(
                webhook.secret.encode(),
                json.dumps(webhook_payload).encode(),
                hashlib.sha256
            ).hexdigest()
            
            headers = {
                'Content-Type': 'application/json',
                'X-Webhook-Signature': signature,
                'User-Agent': 'AgentSDK-Webhook/1.0'
            }
            
            # Send with retries
            for attempt in range(webhook.retry_count):
                try:
                    response = requests.post(
                        webhook.url,
                        json=webhook_payload,
                        headers=headers,
                        timeout=webhook.timeout
                    )
                    
                    # Log delivery
                    delivery = WebhookDelivery(
                        webhook_id=webhook.id,
                        event_type=event_type,
                        payload=webhook_payload,
                        response_status=response.status_code,
                        response_body=response.text[:500],
                        success=200 <= response.status_code < 300,
                        attempt=attempt + 1
                    )
                    db.session.add(delivery)
                    
                    if 200 <= response.status_code < 300:
                        webhook.total_delivered += 1
                        webhook.last_triggered_at = datetime.utcnow()
                        db.session.commit()
                        return
                    else:
                        webhook.total_failed += 1
                        webhook.last_error = f"HTTP {response.status_code}"
                        db.session.commit()
                        
                except Exception as e:
                    error_msg = str(e)
                    delivery = WebhookDelivery(
                        webhook_id=webhook.id,
                        event_type=event_type,
                        payload=webhook_payload,
                        error=error_msg,
                        success=False,
                        attempt=attempt + 1
                    )
                    db.session.add(delivery)
                    webhook.total_failed += 1
                    webhook.last_error = error_msg
                    db.session.commit()
    
    @staticmethod
    def send_test(webhook):
        """Send test webhook"""
        test_payload = {
            'test': True,
            'message': 'This is a test webhook from Agent SDK Platform',
            'timestamp': datetime.utcnow().isoformat()
        }
        
        try:
            WebhookService._send(webhook, 'test', test_payload)
            return True, "Test webhook sent"
        except Exception as e:
            return False, str(e)
    
    @staticmethod
    def get_delivery_history(webhook_id, limit=10):
        """Get webhook delivery history"""
        from app.models.webhook_models import WebhookDelivery
        
        deliveries = WebhookDelivery.query.filter_by(
            webhook_id=webhook_id
        ).order_by(
            WebhookDelivery.created_at.desc()
        ).limit(limit).all()
        
        return deliveries