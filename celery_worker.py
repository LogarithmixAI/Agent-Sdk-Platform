#!/usr/bin/env python
"""Celery worker for async task processing"""
from app import create_app
from app.services.queue_service import queue_service
import os

# Create Flask app context
app = create_app()
app.app_context().push()

# Get Celery instance
celery = queue_service.celery_app

if __name__ == '__main__':
    celery.start()