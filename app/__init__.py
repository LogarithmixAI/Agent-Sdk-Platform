from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_mail import Mail
from flask_pymongo import PyMongo
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv
import os
from datetime import datetime
import markdown
import bleach

# Load environment variables
load_dotenv()

# Initialize extensions
db = SQLAlchemy()
mongo = PyMongo()
login_manager = LoginManager()
migrate = Migrate()
mail = Mail()
csrf = CSRFProtect()

# Initialize services
from app.services.queue_service import QueueService
from app.services.websocket_service import socketio
from app.services.log_service import LogService

queue_service = QueueService()
log_service = LogService()  # Create instance

def create_app(config_class=None):
    app = Flask(__name__, 
                template_folder='templates',
                static_folder='static')
    
    @app.template_filter('markdown')
    def markdown_filter(text):
        return markdown.markdown(text, extensions=['extra', 'codehilite'])
    # Load configuration
    if config_class:
        app.config.from_object(config_class)
    else:
        from app.config import config
        env = os.getenv('FLASK_ENV', 'development')
        app.config.from_object(config[env])
    
    # Initialize extensions with app
    db.init_app(app)
    mongo.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    csrf.init_app(app)
    
    # Initialize services with app context
    queue_service.init_app(app)
    log_service.init_app(app)  # Important: Initialize log service here
    socketio.init_app(app, cors_allowed_origins="*")
    
    # Configure login
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    
    # Create logs directory if it doesn't exist
    os.makedirs(app.config['LOGS_STORAGE_PATH'], exist_ok=True)
    
    @app.template_filter('markdown')
    def markdown_filter(text):
        """Convert markdown to safe HTML"""
        # Markdown to HTML
        html = markdown.markdown(
            text,
            extensions=[
                'extra',           # Tables, footnotes, etc.
                'codehilite',      # Code highlighting
                'toc',             # Table of contents
                'tables'
            ]
        )
        
        # Allowed HTML tags (security)
        allowed_tags = [
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'p', 'br', 'hr',
            'ul', 'ol', 'li',
            'strong', 'em', 'b', 'i', 'u',
            'code', 'pre',
            'a', 'img',
            'blockquote',
            'table', 'thead', 'tbody', 'tr', 'th', 'td',
            'div', 'span'
        ]
        
        allowed_attrs = {
            'a': ['href', 'title', 'target'],
            'img': ['src', 'alt', 'title'],
            'code': ['class'],
            'pre': ['class'],
            'div': ['class'],
            'span': ['class']
        }
        
        # Clean HTML (remove dangerous tags)
        clean_html = bleach.clean(
            html,
            tags=allowed_tags,
            attributes=allowed_attrs,
            strip=True
        )
        
        return clean_html
    
    # Register template filters
    @app.template_filter('timesince')
    def timesince_filter(dt, default="just now"):
        """
        Returns string representing "time since" e.g.
        3 days ago, 5 hours ago etc.
        """
        if dt is None:
            return default
        
        if isinstance(dt, str):
            try:
                dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
            except:
                return default
        
        now = datetime.utcnow()
        diff = now - dt
        
        periods = [
            (diff.days // 365, 'year', 'years'),
            (diff.days // 30, 'month', 'months'),
            (diff.days // 7, 'week', 'weeks'),
            (diff.days, 'day', 'days'),
            (diff.seconds // 3600, 'hour', 'hours'),
            ((diff.seconds % 3600) // 60, 'minute', 'minutes'),
            (diff.seconds % 60, 'second', 'seconds')
        ]
        
        for period, singular, plural in periods:
            if period:
                return f"{period} {singular if period == 1 else plural} ago"
        
        return default
    
    # Import models to ensure they're registered with SQLAlchemy
    from app.models import user_models
    
    # Set up user loader for Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        return user_models.User.query.get(int(user_id))
    
    # Register blueprints
    from app.routes import auth, dashboard, api_keys, logs, documentation, api, main, team, webhooks
    app.register_blueprint(team.bp)
    app.register_blueprint(webhooks.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(api_keys.bp)
    app.register_blueprint(logs.bp)
    app.register_blueprint(documentation.bp)
    app.register_blueprint(api.bp)
    
    # Create database tables and indexes
    with app.app_context():
        db.create_all()
        
        # Create MongoDB indexes if connected
        try:
            from app.models.log_models import LogModel
            LogModel.create_indexes()
        except Exception as e:
            app.logger.warning(f"Could not create MongoDB indexes: {e}")
    
    return app