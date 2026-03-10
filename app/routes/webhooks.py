from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.user_models import Webhook
from app.services.webhook_service import WebhookService
import secrets
from datetime import datetime

bp = Blueprint('webhooks', __name__, url_prefix='/webhooks')

# ============================================
# LIST WEBHOOKS
# ============================================
@bp.route('/')
@login_required
def list_webhooks():
    """List all webhooks for current user"""
    webhooks = Webhook.query.filter_by(user_id=current_user.id).all()
    return render_template('webhooks/list.html', webhooks=webhooks)

# ============================================
# CREATE WEBHOOK
# ============================================
@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Create new webhook"""
    if request.method == 'POST':
        url = request.form.get('url')
        description = request.form.get('description')
        events = request.form.getlist('events')  # ['log.created', 'error.detected']
        
        if not events:
            events = ['*']  # All events
        
        # Create webhook
        webhook = Webhook(
            user_id=current_user.id,
            url=url,
            description=description,
            events=events,
            secret=secrets.token_urlsafe(32)
        )
        db.session.add(webhook)
        db.session.commit()
        
        flash('Webhook created successfully!', 'success')
        return redirect(url_for('webhooks.view', webhook_id=webhook.id))
    
    # Get available event types
    event_types = [
        {'id': 'log.created', 'name': 'Log Created', 'description': 'When a new log is created'},
        {'id': 'log.batch', 'name': 'Batch Processed', 'description': 'When a batch of logs is processed'},
        {'id': 'error.detected', 'name': 'Error Detected', 'description': 'When an error is detected'},
        {'id': 'anomaly.found', 'name': 'Anomaly Found', 'description': 'When an anomaly is detected'},
        {'id': 'alert.triggered', 'name': 'Alert Triggered', 'description': 'When an alert is triggered'},
        {'id': 'user.login', 'name': 'User Login', 'description': 'When a user logs in'},
        {'id': 'api.key_created', 'name': 'API Key Created', 'description': 'When an API key is created'},
    ]
    
    return render_template('webhooks/create.html', event_types=event_types)

# ============================================
# VIEW WEBHOOK
# ============================================
@bp.route('/<int:webhook_id>')
@login_required
def view(webhook_id):
    """View webhook details"""
    webhook = Webhook.query.get_or_404(webhook_id)
    
    if webhook.user_id != current_user.id:
        flash('You do not have access to this webhook.', 'danger')
        return redirect(url_for('webhooks.list_webhooks'))
    
    # Get delivery history (last 10)
    deliveries = WebhookService.get_delivery_history(webhook_id, limit=10)
    
    return render_template('webhooks/view.html',
                         webhook=webhook,
                         deliveries=deliveries)

# ============================================
# EDIT WEBHOOK
# ============================================
@bp.route('/<int:webhook_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(webhook_id):
    """Edit webhook"""
    webhook = Webhook.query.get_or_404(webhook_id)
    
    if webhook.user_id != current_user.id:
        flash('You do not have access to this webhook.', 'danger')
        return redirect(url_for('webhooks.list_webhooks'))
    
    if request.method == 'POST':
        webhook.url = request.form.get('url')
        webhook.description = request.form.get('description')
        webhook.events = request.form.getlist('events')
        webhook.is_active = request.form.get('is_active') == 'on'
        
        db.session.commit()
        flash('Webhook updated successfully!', 'success')
        return redirect(url_for('webhooks.view', webhook_id=webhook.id))
    
    event_types = [
        {'id': 'log.created', 'name': 'Log Created'},
        {'id': 'log.batch', 'name': 'Batch Processed'},
        {'id': 'error.detected', 'name': 'Error Detected'},
        {'id': 'anomaly.found', 'name': 'Anomaly Found'},
        {'id': 'alert.triggered', 'name': 'Alert Triggered'},
    ]
    
    return render_template('webhooks/edit.html',
                         webhook=webhook,
                         event_types=event_types)

# ============================================
# TEST WEBHOOK
# ============================================
@bp.route('/<int:webhook_id>/test', methods=['POST'])
@login_required
def test(webhook_id):
    """Test webhook"""
    webhook = Webhook.query.get_or_404(webhook_id)
    
    if webhook.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Send test payload
    success, message = WebhookService.send_test(webhook)
    
    if success:
        flash('Webhook test successful!', 'success')
    else:
        flash(f'Webhook test failed: {message}', 'danger')
    
    return redirect(url_for('webhooks.view', webhook_id=webhook_id))

# ============================================
# REGENERATE SECRET
# ============================================
@bp.route('/<int:webhook_id>/regenerate-secret', methods=['POST'])
@login_required
def regenerate_secret(webhook_id):
    """Regenerate webhook secret"""
    webhook = Webhook.query.get_or_404(webhook_id)
    
    if webhook.user_id != current_user.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('webhooks.list_webhooks'))
    
    webhook.secret = secrets.token_urlsafe(32)
    db.session.commit()
    
    flash('Webhook secret regenerated successfully!', 'success')
    return redirect(url_for('webhooks.view', webhook_id=webhook_id))

# ============================================
# DELETE WEBHOOK
# ============================================
@bp.route('/<int:webhook_id>/delete', methods=['POST'])
@login_required
def delete(webhook_id):
    """Delete webhook"""
    webhook = Webhook.query.get_or_404(webhook_id)
    
    if webhook.user_id != current_user.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('webhooks.list_webhooks'))
    
    db.session.delete(webhook)
    db.session.commit()
    
    flash('Webhook deleted successfully!', 'success')
    return redirect(url_for('webhooks.list_webhooks'))