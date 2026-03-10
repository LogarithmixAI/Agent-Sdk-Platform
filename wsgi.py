from app import create_app
from app.config import config
import os
import sys

env = os.getenv('FLASK_ENV', 'production')
print(f"🚀 Starting app in {env} mode")

try:
    app = create_app(config[env])
    print("✅ App created successfully")
except Exception as e:
    print(f"❌ Failed to create app: {e}")
    print("\n📋 Environment variables:")
    print(f"MONGO_URI: {os.getenv('MONGO_URI', 'NOT SET')}")
    print(f"DATABASE_URL: {os.getenv('DATABASE_URL', 'NOT SET')}")
    print(f"STORAGE_TYPE: {os.getenv('STORAGE_TYPE', 'NOT SET')}")
    sys.exit(1)

if __name__ == '__main__':
    app.run()
