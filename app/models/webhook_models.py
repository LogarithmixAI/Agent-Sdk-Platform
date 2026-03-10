from app import db
from datetime import datetime

class WebhookDelivery(db.Model):
    __tablename__ = 'webhook_deliveries'
    
    id = db.Column(db.Integer, primary_key=True)
    webhook_id = db.Column(db.Integer, db.ForeignKey('webhooks.id'), nullable=False)
    event_type = db.Column(db.String(50))
    payload = db.Column(db.JSON)
    response_status = db.Column(db.Integer)
    response_body = db.Column(db.Text)
    error = db.Column(db.Text)
    success = db.Column(db.Boolean, default=False)
    attempt = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    webhook = db.relationship('Webhook', backref='deliveries')