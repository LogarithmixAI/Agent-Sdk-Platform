# Agent SDK Platform

A professional dashboard platform for website log tracking and analytics.

## Features
- User authentication and management
- API key generation and management
- Log data visualization dashboard
- Multi-user support with data isolation
- Professional analytics interface

## Technology Stack
- **Backend**: Flask (Python)
- **User Database**: SQLite (dev) / PostgreSQL (prod)
- **Logs Database**: MongoDB (primary) / Local files (dev/test)
- **Frontend**: Bootstrap 5, Chart.js/Plotly
- **Authentication**: Flask-Login + JWT

## Installation

1. Clone the repository
2. Create virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate