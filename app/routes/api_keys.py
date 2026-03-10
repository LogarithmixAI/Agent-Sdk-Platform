from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.models.user_models import APIKey
from app.forms.api_key_forms import CreateAPIKeyForm, EditAPIKeyForm, RevokeKeyForm
from app.services.api_key_service import APIKeyService
from datetime import datetime
import json

bp = Blueprint('api_keys', __name__, url_prefix='/api-keys')

@bp.route('/')
@login_required
def manage_keys():
    """API key management dashboard"""
    keys = APIKeyService.get_user_keys(current_user.id, include_inactive=True)
    
    # Calculate usage stats for each key
    key_stats = {}
    for key in keys:
        key_stats[key.key_id] = {
            'total_requests': key.total_requests,
            'last_used': key.last_used_at,
            'is_active': key.is_active,
            'expires_at': key.expires_at
        }
    
    return render_template('api_keys/manage.html', 
                         title='API Keys', 
                         keys=keys,
                         key_stats=key_stats,
                         max_keys=current_user.max_api_keys)

@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_key():
    """Create a new API key"""
    
    # Check if user has reached max keys
    if current_user.api_keys.count() >= current_user.max_api_keys:
        flash(f'You have reached the maximum number of API keys ({current_user.max_api_keys}).', 'warning')
        return redirect(url_for('api_keys.manage_keys'))
    
    form = CreateAPIKeyForm()
    
    if form.validate_on_submit():
        try:
            # Handle expiration
            expires_at = None
            if not form.never_expire.data and form.expires_at.data:
                expires_at = form.expires_at.data
            
            # Create key
            api_key = APIKeyService.create_key(
                user_id=current_user.id,
                name=form.name.data,
                description=form.description.data,
                permissions=form.permissions.data,
                allowed_domains=form.allowed_domains.data,
                ip_whitelist=form.ip_whitelist.data,
                expires_at=expires_at,
                rate_limit=form.rate_limit.data
            )
            
            flash('API key created successfully!', 'success')
            
            # Show the key secret only once
            return render_template('api_keys/show_key.html', 
                                 key_id=api_key.key_id,
                                 key_secret=api_key.key_secret,
                                 key_name=api_key.name)
        
        except ValueError as e:
            flash(str(e), 'danger')
        except Exception as e:
            flash(f'Error creating API key: {str(e)}', 'danger')
    
    return render_template('api_keys/create.html', title='Create API Key', form=form)

@bp.route('/<key_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_key(key_id):
    """Edit an existing API key"""
    api_key = APIKey.query.filter_by(key_id=key_id, user_id=current_user.id).first()
    
    if not api_key:
        flash('API key not found.', 'danger')
        return redirect(url_for('api_keys.manage_keys'))
    
    form = EditAPIKeyForm(obj=api_key)
    
    if form.validate_on_submit():
        api_key.name = form.name.data
        api_key.description = form.description.data
        api_key.is_active = form.is_active.data
        api_key.permissions = form.permissions.data
        db.session.commit()
        
        flash('API key updated successfully.', 'success')
        return redirect(url_for('api_keys.manage_keys'))
    
    # Pre-populate form
    form.name.data = api_key.name
    form.description.data = api_key.description
    form.is_active.data = api_key.is_active
    form.permissions.data = api_key.permissions
    
    return render_template('api_keys/edit.html', 
                         title='Edit API Key', 
                         form=form, 
                         key=api_key)

@bp.route('/<key_id>/revoke', methods=['GET', 'POST'])
@login_required
def revoke_key(key_id):
    """Revoke an API key"""
    api_key = APIKey.query.filter_by(key_id=key_id, user_id=current_user.id).first()
    
    if not api_key:
        flash('API key not found.', 'danger')
        return redirect(url_for('api_keys.manage_keys'))
    
    form = RevokeKeyForm()
    
    if form.validate_on_submit():
        if APIKeyService.revoke_key(key_id, current_user.id):
            flash(f'API key "{api_key.name}" has been revoked.', 'success')
        else:
            flash('Error revoking API key.', 'danger')
        
        return redirect(url_for('api_keys.manage_keys'))
    
    return render_template('api_keys/revoke.html', 
                         title='Revoke API Key', 
                         form=form, 
                         key=api_key)

@bp.route('/<key_id>/delete', methods=['POST'])
@login_required
def delete_key(key_id):
    """Permanently delete an API key"""
    api_key = APIKey.query.filter_by(key_id=key_id, user_id=current_user.id).first()
    
    if not api_key:
        flash('API key not found.', 'danger')
        return redirect(url_for('api_keys.manage_keys'))
    
    if APIKeyService.delete_key(key_id, current_user.id):
        flash(f'API key "{api_key.name}" has been permanently deleted.', 'success')
    else:
        flash('Error deleting API key.', 'danger')
    
    return redirect(url_for('api_keys.manage_keys'))

@bp.route('/<path:key_id>/regenerate', methods=['POST'])
@login_required
def regenerate_key(key_id):
    """Regenerate API key secret with better path handling"""
    
    # Clean the key_id - remove any extra slashes
    key_id = key_id.strip().strip('/')
    print(key_id)
    # Log for debugging
    current_app.logger.info(f"Regenerate request for key: {key_id}")
    
    # Validate key_id format
    if not key_id or len(key_id) < 10:
        flash('Invalid API key ID.', 'danger')
        return redirect(url_for('api_keys.manage_keys'))
    
    # Find the key
    api_key = APIKey.query.filter_by(key_id=key_id, user_id=current_user.id).first()
    
    if not api_key:
        current_app.logger.warning(f"Key not found: {key_id}")
        flash('API key not found.', 'danger')
        return redirect(url_for('api_keys.manage_keys'))
    
    # Check if key is active
    if not api_key.is_active:
        flash('Cannot regenerate an inactive key. Please activate it first.', 'warning')
        return redirect(url_for('api_keys.manage_keys'))
    
    try:
        # Regenerate secret
        new_secret = APIKeyService.regenerate_secret(key_id, current_user.id)
        
        if new_secret:
            current_app.logger.info(f"Key regenerated successfully: {key_id}")
            flash('API key secret regenerated successfully.', 'success')
            
            return render_template('api_keys/show_key.html', 
                                 key_id=api_key.key_id,
                                 key_secret=new_secret,
                                 key_name=api_key.name,
                                 regenerated=True)
        else:
            flash('Error regenerating API key.', 'danger')
    except Exception as e:
        current_app.logger.error(f"Error regenerating key: {str(e)}")
        flash(f'Error: {str(e)}', 'danger')
    
    return redirect(url_for('api_keys.manage_keys'))

@bp.route('/<key_id>/stats')
@login_required
def key_stats(key_id):
    """Get usage statistics for a specific key"""
    api_key = APIKey.query.filter_by(key_id=key_id, user_id=current_user.id).first()
    
    if not api_key:
        return jsonify({'error': 'Key not found'}), 404
    
    stats = APIKeyService.get_key_stats(key_id, current_user.id)
    
    # Format for JSON response
    if stats:
        stats['last_used'] = stats['last_used'].isoformat() if stats['last_used'] else None
        stats['created_at'] = stats['created_at'].isoformat()
        stats['expires_at'] = stats['expires_at'].isoformat() if stats['expires_at'] else None
    
    return jsonify(stats)

@bp.route('/check-limit')
@login_required
def check_limit():
    """Check if user has reached API key limit"""
    current_count = current_user.api_keys.count()
    max_keys = current_user.max_keys
    
    return jsonify({
        'current': current_count,
        'max': max_keys,
        'can_create': current_count < max_keys
    })

@bp.route('/api-docs')
@login_required
def api_documentation():
    """API documentation for key usage"""
    return render_template('api_keys/api_docs.html', title='API Documentation')