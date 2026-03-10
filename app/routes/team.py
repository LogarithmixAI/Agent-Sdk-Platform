from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.user_models import Team, TeamMember, User
from app.services.log_service import LogService
from datetime import datetime, timedelta

bp = Blueprint('team', __name__, url_prefix='/team')

log_service = LogService()

# ============================================
# TEAM DASHBOARD
# ============================================
@bp.route('/')
@login_required
def dashboard():
    """Team dashboard - view all teams"""
    owned_teams = Team.query.filter_by(owner_id=current_user.id).all()
    member_teams = Team.query.join(TeamMember).filter(
        TeamMember.user_id == current_user.id
    ).all()
    
    # Get stats for each team
    for team in owned_teams + member_teams:
        team.member_count = TeamMember.query.filter_by(team_id=team.id).count()
        team.role = TeamMember.query.filter_by(
            team_id=team.id, user_id=current_user.id
        ).first().role if team in member_teams else 'owner'
    
    return render_template('team/dashboard.html',
                         owned_teams=owned_teams,
                         member_teams=member_teams)

# ============================================
# CREATE TEAM
# ============================================
@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Create new team"""
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        
        # Check if team name already exists for user
        existing = Team.query.filter_by(owner_id=current_user.id, name=name).first()
        if existing:
            flash('You already have a team with this name.', 'danger')
            return redirect(url_for('team.create'))
        
        # Create team
        team = Team(
            name=name,
            owner_id=current_user.id,
            settings={'description': description}
        )
        db.session.add(team)
        db.session.flush()  # Get team.id
        
        # Add owner as team member with admin role
        member = TeamMember(
            user_id=current_user.id,
            team_id=team.id,
            role='admin',
            permissions=['view_logs', 'manage_members', 'manage_webhooks', 'delete_logs']
        )
        db.session.add(member)
        db.session.commit()
        
        flash(f'Team "{name}" created successfully!', 'success')
        
        # ✅ FIXED: Redirect using public_id, not id
        return redirect(url_for('team.view', public_id=team.public_id))
    
    return render_template('team/create.html')

# ============================================
# VIEW TEAM
# ============================================
@bp.route('/<public_id>')
@login_required
def view(public_id):
    """View team details"""
    team = Team.query.filter_by(public_id=public_id).first_or_404()
    
    # Check access
    membership = TeamMember.query.filter_by(
        team_id=team.id, user_id=current_user.id
    ).first()
    
    if not (team.owner_id == current_user.id or membership):
        flash('You do not have access to this team.', 'danger')
        return redirect(url_for('team.dashboard'))
    
    # Get all members with user details
    members = db.session.query(
        TeamMember, User
    ).join(
        User, TeamMember.user_id == User.id
    ).filter(
        TeamMember.team_id == team.id
    ).all()
    
    # Get pending invites (you can add an Invite model later)
    pending_invites = []
    
    # Get team logs summary
    logs_summary = get_team_logs_summary(team.id)
    
    user_role = membership.role if membership else 'owner'
    
    return render_template('team/view.html',
                         team=team,
                         members=members,
                         pending_invites=pending_invites,
                         logs_summary=logs_summary,
                         user_role=user_role,
                         is_owner=team.owner_id == current_user.id)

# ============================================
# ADD MEMBER
# ============================================
@bp.route('/<public_id>/add-member', methods=['POST'])
@login_required
def add_member(public_id):
    """Add member to team"""
    team = Team.query.filter_by(public_id=public_id).first_or_404()
    
    # Check permissions (only owner or admin)
    membership = TeamMember.query.filter_by(
        team_id=team.id, user_id=current_user.id
    ).first()
    
    if not (team.owner_id == current_user.id or 
            (membership and membership.role in ['admin'])):
        flash('You do not have permission to add members.', 'danger')
        return redirect(url_for('team.view', public_id=team.public_id))
    
    email = request.form.get('email')
    role = request.form.get('role', 'member')
    
    user = User.query.filter_by(email=email).first()
    if not user:
        flash('User not found with this email.', 'danger')
        return redirect(url_for('team.view', public_id=team.public_id))
    
    # Check if already member
    existing = TeamMember.query.filter_by(
        team_id=team.id, user_id=user.id
    ).first()
    
    if existing:
        flash('User is already a team member.', 'warning')
        return redirect(url_for('team.view', public_id=team.public_id))
    
    # Define permissions based on role
    permissions = {
        'admin': ['view_logs', 'manage_members', 'manage_webhooks', 'delete_logs'],
        'member': ['view_logs', 'create_webhooks'],
        'viewer': ['view_logs']
    }.get(role, ['view_logs'])
    
    # Add member
    member = TeamMember(
        user_id=user.id,
        team_id=team.id,
        role=role,
        permissions=permissions
    )
    db.session.add(member)
    db.session.commit()
    
    flash(f'{user.email} added to team as {role}.', 'success')
    return redirect(url_for('team.view', public_id=team.public_id))

# ============================================
# REMOVE MEMBER
# ============================================
@bp.route('/<public_id>/remove-member/<int:user_id>', methods=['POST'])
@login_required
def remove_member(public_id, user_id):
    """Remove member from team"""
    team = Team.query.filter_by(public_id=public_id).first_or_404()
    
    # Check permissions (only owner or admin)
    membership = TeamMember.query.filter_by(
        team_id=team.id, user_id=current_user.id
    ).first()
    
    if not (team.owner_id == current_user.id or 
            (membership and membership.role in ['admin'])):
        flash('You do not have permission to remove members.', 'danger')
        return redirect(url_for('team.view', public_id=team.public_id))
    
    # Cannot remove owner
    if user_id == team.owner_id:
        flash('Cannot remove the team owner.', 'danger')
        return redirect(url_for('team.view', public_id=team.public_id))
    
    member = TeamMember.query.filter_by(
        team_id=team.id, user_id=user_id
    ).first()
    
    if member:
        db.session.delete(member)
        db.session.commit()
        flash('Member removed from team.', 'success')
    
    return redirect(url_for('team.view', public_id=team.public_id))

# ============================================
# UPDATE MEMBER ROLE
# ============================================
@bp.route('/<public_id>/update-role/<int:user_id>', methods=['POST'])
@login_required
def update_role(public_id, user_id):
    """Update member role"""
    team = Team.query.filter_by(public_id=public_id).first_or_404()
    
    if team.owner_id != current_user.id:
        flash('Only team owner can change roles.', 'danger')
        return redirect(url_for('team.view', public_id=team.public_id))
    
    new_role = request.form.get('role')
    
    member = TeamMember.query.filter_by(
        team_id=team.id, user_id=user_id
    ).first()
    
    if member:
        member.role = new_role
        # Update permissions based on new role
        permissions = {
            'admin': ['view_logs', 'manage_members', 'manage_webhooks', 'delete_logs'],
            'member': ['view_logs', 'create_webhooks'],
            'viewer': ['view_logs']
        }.get(new_role, ['view_logs'])
        member.permissions = permissions
        db.session.commit()
        flash('Member role updated.', 'success')
    
    return redirect(url_for('team.view', public_id=team.public_id))

# ============================================
# LEAVE TEAM
# ============================================
@bp.route('/<public_id>/leave', methods=['POST'])
@login_required
def leave_team(public_id):
    """Leave a team"""
    team = Team.query.filter_by(public_id=public_id).first_or_404()
    
    if team.owner_id == current_user.id:
        flash('Team owner cannot leave. Transfer ownership or delete team.', 'danger')
        return redirect(url_for('team.view', public_id=team.public_id))
    
    member = TeamMember.query.filter_by(
        team_id=team.id, user_id=current_user.id
    ).first()
    
    if member:
        db.session.delete(member)
        db.session.commit()
        flash('You have left the team.', 'success')
    
    return redirect(url_for('team.dashboard'))

# ============================================
# DELETE TEAM
# ============================================
@bp.route('/<public_id>/delete', methods=['POST'])
@login_required
def delete_team(public_id):
    """Delete team"""
    team = Team.query.filter_by(public_id=public_id).first_or_404()
    
    if team.owner_id != current_user.id:
        flash('Only team owner can delete the team.', 'danger')
        return redirect(url_for('team.view', public_id=team.public_id))
    
    # Delete all members first
    TeamMember.query.filter_by(team_id=team.id).delete()
    
    # Delete team
    db.session.delete(team)
    db.session.commit()
    
    flash('Team deleted successfully.', 'success')
    return redirect(url_for('team.dashboard'))

# ============================================
# HELPER FUNCTION
# ============================================
def get_team_logs_summary(team_id):
    """Get logs summary for team"""
    # Get all team members' user IDs
    members = TeamMember.query.filter_by(team_id=team_id).all()
    user_ids = [m.user.public_id for m in members]
    
    # Get team owner's ID as well
    team = Team.query.get(team_id)
    if team.owner.public_id not in user_ids:
        user_ids.append(team.owner.public_id)
    
    # Get logs summary from log_service
    # This would need to be implemented in log_service
    return {
        'total_logs': 0,
        'last_24h': 0,
        'active_sources': 0
    }

@bp.route('/<public_id>/logs')
@login_required
def team_logs(public_id):
    """Dedicated team logs page"""
    team = Team.query.filter_by(public_id=public_id).first_or_404()
    
    # Verify access
    membership = TeamMember.query.filter_by(
        team_id=team.id, user_id=current_user.id
    ).first()
    
    if not (membership or team.owner_id == current_user.id):
        flash('You do not have access to this team.', 'danger')
        return redirect(url_for('team.dashboard'))
    
    # Get all team members
    members = TeamMember.query.filter_by(team_id=team.id).all()
    member_list = []
    for member in members:
        member_list.append({
            'user': member.user,
            'role': member.role
        })
    
    from app import mongo

    # Get all team member user IDs
    user_ids = [m.user.public_id for m in members]
    if team.owner.public_id not in user_ids:
        user_ids.append(team.owner.public_id)
    
    # Calculate stats
    stats = {
        'total_logs': 0,
        'last_24h': 0,
        'active_sources': 0,
        'avg_daily': 0,
        'projects': [],
        'environments': []
    }
    
    if mongo.db is not None:
        # Total logs
        stats['total_logs'] = mongo.db.logs.count_documents({
            'user_id': {'$in': user_ids}
        })
        
        # Last 24h
        day_ago = datetime.utcnow() - timedelta(days=1)
        stats['last_24h'] = mongo.db.logs.count_documents({
            'user_id': {'$in': user_ids},
            'received_at': {'$gte': day_ago}
        })
        
        # Distinct projects
        projects = mongo.db.logs.distinct('batch_meta.project', {
            'user_id': {'$in': user_ids}
        })
        stats['projects'] = [p for p in projects if p]
        
        # Distinct environments
        envs = mongo.db.logs.distinct('batch_meta.environment', {
            'user_id': {'$in': user_ids}
        })
        stats['environments'] = [e for e in envs if e]
    
    return render_template('team/logs.html',
                         team=team,
                         members=member_list,
                         stats=stats)


@bp.route('/api/team-logs')
@login_required
def api_team_logs():
    """API endpoint for team logs with filters"""
    team_public_id = request.args.get('team')
    member_id = request.args.get('member')
    days = int(request.args.get('days', 7))
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    
    team = Team.query.filter_by(public_id=team_public_id).first()
    if not team:
        return jsonify({'error': 'Team not found'}), 404
    
    # Verify access
    membership = TeamMember.query.filter_by(
        team_id=team.id, user_id=current_user.id
    ).first()
    
    if not (membership or team.owner_id == current_user.id):
        return jsonify({'error': 'Access denied'}), 403
    
    # Get user IDs to query
    if member_id and member_id != 'all':
        user_ids = [member_id]
    else:
        members = TeamMember.query.filter_by(team_id=team.id).all()
        user_ids = [m.user.public_id for m in members]
        if team.owner.public_id not in user_ids:
            user_ids.append(team.owner.public_id)
    
    # Build filters
    filters = {}
    if request.args.get('project'):
        filters['project'] = request.args.get('project')
    if request.args.get('environment'):
        filters['environment'] = request.args.get('environment')
    if request.args.get('severity'):
        filters['severity'] = request.args.get('severity')
    if request.args.get('event_type'):
        filters['event_type'] = request.args.get('event_type')
    
    # Date range
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    filters['start_date'] = start_date
    filters['end_date'] = end_date
    
    # Get logs
    result = log_service.get_logs_for_users(
        user_ids=user_ids,
        filters=filters,
        page=page,
        per_page=per_page
    )
    # Add usernames to logs
    for log in result.get('logs', []):
        user = User.query.filter_by(public_id=log.get('user_id')).first()
        log['username'] = user.username if user else 'Unknown'
    
    return jsonify(result)

@bp.route('/api/log/<log_id>')
@login_required
def get_log_detail(log_id):
    """Get detailed log information by ID (with team access check)"""
    from bson.objectid import ObjectId
    from app import mongo
    
    try:
        # Find the log
        log = mongo.db.logs.find_one({'_id': ObjectId(log_id)})
        
        if not log:
            return jsonify({'error': 'Log not found'}), 404
        
        # Check if user has access to this log (team member check)
        user_id = log.get('user_id')
        if not user_id:
            return jsonify({'error': 'Log has no user ID'}), 400
        
        # Find which team this log belongs to (if any)
        # For now, just check if user is in any team with the log owner
        from app.models.user_models import TeamMember, Team
        
        # Get user's teams
        user_teams = TeamMember.query.filter_by(user_id=current_user.id).all()
        team_ids = [t.team_id for t in user_teams]
        
        # Check if log owner is in any of user's teams
        owner_in_teams = TeamMember.query.filter(
            TeamMember.team_id.in_(team_ids),
            TeamMember.user_id == User.query.filter_by(public_id=user_id).first().id
        ).first() if team_ids else None
        
        # Allow access if user is the log owner or in same team
        if current_user.public_id != user_id and not owner_in_teams:
            return jsonify({'error': 'Access denied'}), 403
        
        # Convert ObjectId to string
        log['_id'] = str(log['_id'])
        
        # Add username
        user = User.query.filter_by(public_id=user_id).first()
        log['username'] = user.username if user else 'Unknown'
        
        return jsonify(log)
        
    except Exception as e:
        print(f"Error getting log detail: {e}")
        return jsonify({'error': str(e)}), 500