from flask import Blueprint, render_template, jsonify
from flask_login import current_user

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    """Landing page"""
    return render_template('index.html', title='Agent SDK Platform')

@bp.route('/features')
def features():
    """Features page"""
    return render_template('features.html', title='Features')

@bp.route('/pricing')
def pricing():
    """Pricing page"""
    return render_template('pricing.html', title='Pricing')

@bp.route('/about')
def about():
    """About page"""
    return render_template('about.html', title='About Us')

@bp.route('/contact')
def contact():
    """Contact page"""
    return render_template('contact.html', title='Contact')

@bp.route('/health', methods=['GET'])
def health():
    """Health check endpoint for monitoring"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'version': '1.0.0'
    })
