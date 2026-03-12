import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key-change-in-production')
    
    # SQL Database (User data)
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///instance/users.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # MongoDB (Logs data)
    MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/agent_sdk_logs_dev')
    
    # Local file storage for testing
    LOGS_STORAGE_PATH = os.getenv('LOGS_STORAGE_PATH', './logs_data')
    
    # Security
    BCRYPT_LOG_ROUNDS = 13
    TOKEN_EXPIRATION_DAYS = 30
    
    # Email
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')

    #brevo api_key for email
    BREVO_API_KEY = os.getenv('BREVO_API_KEY')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER')
    
    # API Settings
    API_RATE_LIMIT = int(os.getenv('API_RATE_LIMIT', 100))
    API_KEY_LENGTH = int(os.getenv('API_KEY_LENGTH', 32))
    
    # Pagination
    ITEMS_PER_PAGE = 20

class DevelopmentConfig(Config):
    DEBUG = True
    # Use file storage for logs in development
    STORAGE_TYPE= 'mongodb'
    MONGO_URI = os.getenv('MONGO_URI')
    LOGS_STORAGE_PATH = './logs_data'


class ProductionConfig(Config):
    DEBUG = False
    # Use MongoDB for logs in production
    STORAGE_TYPE = 'mongodb'
    # Ensure MongoDB URI is set
    MONGO_URI = os.getenv('MONGO_URI')
    if not MONGO_URI:
        raise ValueError("MONGO_URI must be set in production")

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    MONGO_URI = 'mongodb://localhost:27017/agent_sdk_logs_test'
    WTF_CSRF_ENABLED = False
    STORAGE_TYPE = 'file'

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}