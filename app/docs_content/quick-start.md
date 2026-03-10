# Quick Start Guide

Get up and running with Agent SDK in 5 minutes.

## 📦 Installation

### JavaScript/Node.js
npm install @agent-sdk/javascript

### Python
pip install agent-sdk-python

## 🔑 Configuration

### 1. Get Your API Key
1. Log in to your dashboard
2. Navigate to API Keys section
3. Click Create New Key
4. Copy your key ID and secret

### 2. Initialize the SDK

#### JavaScript
import AgentSDK from '@agent-sdk/javascript';

const agent = new AgentSDK({
    apiKey: 'your-key-id:your-key-secret',
    project: 'my-web-app',
    environment: 'production',
    debug: false,
    batchSize: 10,
    flushInterval: 5000
});

#### Python
from agent_sdk import AgentSDK

agent = AgentSDK(
    api_key='your-key-id:your-key-secret',
    project='my-python-app',
    environment='production'
)

## 🎯 Track Your First Event

### JavaScript
// Track a page view
agent.track('page_view', {
    page: '/home',
    user_id: 'user-123',
    referrer: document.referrer
});

// Track a button click
agent.track('button_click', {
    button_id: 'signup',
    button_text: 'Sign Up',
    page: window.location.pathname
});

### Python
# Track a user action
agent.track('user_action', {
    'action': 'login',
    'user_id': 'user-123',
    'method': 'google'
});

## 🔍 View Your Data

1. Go to your dashboard
2. Navigate to Logs Viewer
3. Apply filters to see your events
4. Create custom charts and reports

## ⚡ Advanced Features

### Batch Events
agent.batch([
    {
        type: 'page_view',
        data: { page: '/home' }
    },
    {
        type: 'api_call',
        data: { endpoint: '/users', duration: 234 }
    }
]);

### Error Tracking
try {
    JSON.parse(invalidData);
} catch (error) {
    agent.error(error, {
        component: 'DataParser',
        severity: 'high'
    });
}

### User Identification
agent.identify('user-123', {
    email: 'user@example.com',
    name: 'John Doe',
    plan: 'premium'
});

## ✅ Checklist

- SDK installed
- API key configured
- First event tracked
- Dashboard verified
- Error tracking set up