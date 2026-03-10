from flask import Blueprint, render_template, request, jsonify, current_app, send_file, session
from flask_login import login_required, current_user
from app.services.log_service import LogService
from app.services.api_key_service import APIKeyService
from datetime import datetime, timedelta
from app.models.user_models import Team, TeamMember
import csv
import io
import json

log_service = LogService()

bp = Blueprint('logs', __name__, url_prefix='/logs')

@bp.route('/')
@login_required
def view_logs():
    """Main logs viewer - personal or team based on 'team' parameter"""
    
    team_public_id = request.args.get('team')
    team_info = None
    
    if team_public_id:
        # Team logs mode
        team = Team.query.filter_by(public_id=team_public_id).first()
        
        if not team:
            flash('Team not found.', 'danger')
            return redirect(url_for('logs.view_logs'))
        
        # Verify team access
        membership = TeamMember.query.filter_by(
            team_id=team.id, 
            user_id=current_user.id
        ).first()
        
        if not (membership or team.owner_id == current_user.id):
            flash('You do not have access to this team.', 'danger')
            return redirect(url_for('logs.view_logs'))
        
        team_info = {
            'id': team_public_id,
            'name': team.name,
            'mode': 'team'
        }
        session['current_team'] = team_public_id
    else:
        # Personal logs mode
        team_info = {
            'mode': 'personal'
        }
        session.pop('current_team', None)
    
    return render_template('logs/viewer.html', 
                         title='Logs Viewer',
                         team_info=team_info)


@bp.route('/api/logs')
@login_required
def get_logs():
    """API endpoint for logs - personal or team based on team parameter"""
    
    # Get team from query param or session
    team_public_id = request.args.get('team') or session.get('current_team')
    
    # ============================================
    # BUILD FILTERS
    # ============================================
    filters = {}
    
    if request.args.get('project'):
        filters['project'] = request.args.get('project')
    if request.args.get('environment'):
        filters['environment'] = request.args.get('environment')
    if request.args.get('severity'):
        filters['severity'] = request.args.get('severity')
    if request.args.get('start_date'):
        try:
            filters['start_date'] = datetime.fromisoformat(
                request.args.get('start_date').replace('Z', '+00:00')
            )
        except:
            pass
    if request.args.get('end_date'):
        try:
            filters['end_date'] = datetime.fromisoformat(
                request.args.get('end_date').replace('Z', '+00:00')
            )
        except:
            pass
    
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    
    # ============================================
    # DETERMINE LOGS TYPE
    # ============================================
    if team_public_id:
        # TEAM LOGS MODE
        from app.models.user_models import Team, TeamMember
        
        team = Team.query.filter_by(public_id=team_public_id).first()
        if not team:
            return jsonify({'error': 'Team not found'}), 404
        
        # Verify access
        membership = TeamMember.query.filter_by(
            team_id=team.id, 
            user_id=current_user.id
        ).first()
        
        if not (membership or team.owner_id == current_user.id):
            return jsonify({'error': 'Access denied'}), 403
        
        # Get all team members
        members = TeamMember.query.filter_by(team_id=team.id).all()
        user_ids = [m.user.public_id for m in members]
        
        # Add team owner
        if team.owner.public_id not in user_ids:
            user_ids.append(team.owner.public_id)
        
        # Get logs for all team members
        result = log_service.get_logs_for_users(
            user_ids=user_ids,
            filters=filters,
            page=page,
            per_page=per_page
        )
        
        # Add team info to response
        result['mode'] = 'team'
        result['team'] = {
            'id': team_public_id,
            'name': team.name,
            'member_count': len(user_ids)
        }
        
    else:
        # PERSONAL LOGS MODE
        result = log_service.get_logs(
            user_id=current_user.public_id,
            filters=filters,
            page=page,
            per_page=per_page
        )
        result['mode'] = 'personal'
    
    return jsonify(result)

@bp.route('/api/filters')
@login_required
def get_filter_options():
    """Get available filter options"""
    
    # Get team if specified
    team_public_id = request.args.get('team') or session.get('current_team')
    
    if team_public_id:
        # Team mode - get projects from all team members
        from app.models.user_models import Team, TeamMember
        
        team = Team.query.filter_by(public_id=team_public_id).first()
        if team:
            members = TeamMember.query.filter_by(team_id=team.id).all()
            user_ids = [m.user.public_id for m in members]
            if team.owner.public_id not in user_ids:
                user_ids.append(team.owner.public_id)
            
            # Get distinct values from multiple users
            projects = log_service.get_distinct_values_for_users(
                user_ids, 'batch_meta.project'
            )
            environments = log_service.get_distinct_values_for_users(
                user_ids, 'batch_meta.environment'
            )
        else:
            projects = []
            environments = []
    else:
        # Personal mode
        projects = log_service.get_distinct_values(
            current_user.public_id, 'batch_meta.project'
        )
        environments = log_service.get_distinct_values(
            current_user.public_id, 'batch_meta.environment'
        )
    
    event_types = log_service.get_distinct_values(
        current_user.public_id, 'processed_events.event_type'
    )
    severities = ['HIGH', 'MEDIUM', 'LOW', 'INFO']
    
    return jsonify({
        'projects': projects,
        'environments': environments,
        'event_types': event_types,
        'severities': severities
    })

@bp.route('/api/logs/<log_id>')
@login_required
def get_log_detail(log_id):
    """Get detailed view of a specific log batch"""
    
    log_detail = log_service.get_log_by_id(
        user_id=current_user.public_id,
        log_id=log_id
    )
    
    if not log_detail:
        return jsonify({'error': 'Log not found'}), 404
    
    return jsonify(log_detail)

@bp.route('/api/logs/<log_id>/events')
@login_required
def get_log_events(log_id):
    """Get events from a specific log batch"""
    
    events = log_service.get_events_by_batch(
        user_id=current_user.public_id,
        log_id=log_id
    )
    
    return jsonify({
        'events': events,
        'count': len(events)
    })

@bp.route('/api/stats/summary')
@login_required
def get_stats_summary():
    """Get summary statistics for logs"""
    
    period = request.args.get('period', '24h')
    
    # Calculate date range based on period
    end_date = datetime.utcnow()
    
    if period == '24h':
        start_date = end_date - timedelta(hours=24)
    elif period == '7d':
        start_date = end_date - timedelta(days=7)
    elif period == '30d':
        start_date = end_date - timedelta(days=30)
    else:
        start_date = end_date - timedelta(days=7)
    
    # Get stats
    stats = log_service.get_dashboard_stats(
        user_id=current_user.public_id,
        start_date=start_date,
        end_date=end_date
    )
    
    return jsonify(stats)

@bp.route('/export')
@login_required
def export_logs():
    """Export logs as CSV or JSON"""
    format_type = request.args.get('format', 'json')
    project = request.args.get('project')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    limit = int(request.args.get('limit', 1000))
    
    # Build filters
    filters = {}
    if project:
        filters['project'] = project
    if start_date:
        try:
            filters['start_date'] = datetime.fromisoformat(start_date)
        except:
            pass
    if end_date:
        try:
            filters['end_date'] = datetime.fromisoformat(end_date)
        except:
            pass
    
    # Get logs
    result = log_service.get_logs(
        user_id=current_user.public_id,
        filters=filters,
        page=1,
        per_page=limit
    )
    
    logs = result.get('logs', [])
    
    if format_type == 'csv':
        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Timestamp', 'Project', 'Environment', 'Event Count', 'Events'])
        
        # Write data
        for log in logs:
            writer.writerow([
                log.get('received_at', ''),
                log.get('batch_meta', {}).get('project', ''),
                log.get('batch_meta', {}).get('environment', ''),
                len(log.get('events', [])),
                json.dumps(log.get('events', [])[:1])  # First event as sample
            ])
        
        # Create response
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'logs_export_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.csv'
        )
    
    else:
        # Return JSON
        return send_file(
            io.BytesIO(json.dumps(logs, indent=2).encode('utf-8')),
            mimetype='application/json',
            as_attachment=True,
            download_name=f'logs_export_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.json'
        )

@bp.route('/api/search')
@login_required
def search_logs():
    """Search logs by text"""
    query = request.args.get('q', '')
    if len(query) < 3:
        return jsonify({'logs': []})
    
    # Implement search logic here
    # This would need to be added to log_service
    results = log_service.search_logs(
        user_id=current_user.public_id,
        query=query,
        limit=50
    )
    
    return jsonify({'logs': results})

@bp.route('/api/projects/<project>/stats')
@login_required
def get_project_stats(project):
    """Get statistics for a specific project"""
    
    period = request.args.get('period', '7d')
    
    # Calculate date range
    end_date = datetime.utcnow()
    if period == '24h':
        start_date = end_date - timedelta(hours=24)
    elif period == '7d':
        start_date = end_date - timedelta(days=7)
    elif period == '30d':
        start_date = end_date - timedelta(days=30)
    else:
        start_date = end_date - timedelta(days=7)
    
    # Get project stats
    stats = log_service.get_project_stats(
        user_id=current_user.public_id,
        project=project,
        start_date=start_date,
        end_date=end_date
    )
    
    return jsonify(stats)