from flask import Blueprint, render_template, jsonify, request, current_app
from flask_login import login_required, current_user
from app.services.log_service import LogService
from app.services.api_key_service import APIKeyService
from app.models.user_models import User
from datetime import datetime, timedelta
from app import db
import json

bp = Blueprint('dashboard', __name__)
log_service = LogService()
@bp.route('/')
@bp.route('/dashboard')
@login_required
def index():
    """Main dashboard view"""
    
    
    # Get date range (default: last 7 days)
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=7)
    
    # Get dashboard stats
    stats = log_service.get_dashboard_stats(
        current_user.public_id,
        start_date,
        end_date
    )
    
    # Get recent activity
    recent_logs = log_service.get_recent_logs(
        current_user.public_id,
        limit=10
    )
    
    # Get projects list
    projects = log_service.get_project_list(current_user.public_id)
    
    # Get API keys count
    api_keys = APIKeyService.get_user_keys(current_user.id)
    
    # Usage percentage
    usage_percentage = min(
        round((stats.get('total_events', 0) / current_user.monthly_log_limit) * 100, 1),
        100
    ) if current_user.monthly_log_limit > 0 else 0
    
    return render_template(
        'dashboard/main.html',
        title='Dashboard',
        stats=stats,
        recent_logs=recent_logs,
        projects=projects,
        api_keys=api_keys,
        usage_percentage=usage_percentage,
        user=current_user,
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d')
    )

@bp.route('/api/dashboard/stats')
@login_required
def api_stats():
    
    # Get date range from query params
    days = int(request.args.get('days', 7))
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    stats = log_service.get_dashboard_stats(
        current_user.public_id,
        start_date,
        end_date
    )
    
    return jsonify(stats)

@bp.route('/api/dashboard/timeseries')
@login_required
def api_timeseries():
    
    # Get date range from query params
    days = int(request.args.get('days', 7))
    interval = request.args.get('interval', 'day')  # hour, day, week
    
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    data = log_service.get_timeseries_data(
        current_user.public_id,
        start_date,
        end_date,
        interval
    )
    
    return jsonify(data)

@bp.route('/api/dashboard/events-by-type')
@login_required
def api_events_by_type():
    
    days = int(request.args.get('days', 7))
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    data = log_service.get_events_by_type(
        current_user.public_id,
        start_date,
        end_date
    )
    
    return jsonify(data)

@bp.route('/api/dashboard/severity-distribution')
@login_required
def api_severity_distribution():
    
    days = int(request.args.get('days', 7))
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    data = log_service.get_severity_distribution(
        current_user.public_id,
        start_date,
        end_date
    )
    
    return jsonify(data)

@bp.route('/api/dashboard/top-pages')
@login_required
def api_top_pages():
    
    days = int(request.args.get('days', 7))
    limit = int(request.args.get('limit', 10))
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    data = log_service.get_top_pages(
        current_user.public_id,
        start_date,
        end_date,
        limit
    )
    
    return jsonify(data)

@bp.route('/api/dashboard/recent-errors')
@login_required
def api_recent_errors():
    
    limit = int(request.args.get('limit', 10))
    
    data = log_service.get_recent_errors(
        current_user.public_id,
        limit
    )
    
    return jsonify(data)

@bp.route('/profile/update-usage')
@login_required
def update_usage():
    
    current_count = log_service.get_current_month_log_count(current_user.public_id)
    percentage = min(round((current_count / current_user.monthly_log_limit) * 100, 1), 100)
    
    return jsonify({
        'current': current_count,
        'limit': current_user.monthly_log_limit,
        'percentage': percentage
    })