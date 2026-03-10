from app import create_app
from app.config import config
import os

env = os.getenv('FLASK_ENV', 'production')
app = create_app(config[env])

if __name__ == '__main__':
    app.run()