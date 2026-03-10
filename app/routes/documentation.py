from flask import Blueprint, render_template, jsonify, request, abort, redirect, url_for
from flask_login import login_required, current_user

bp = Blueprint('documentation', __name__, url_prefix='/docs')

DOCS_STRUCTURE = {
    'getting-started': {
        'title': 'Getting Started',
        'icon': 'rocket',
        'pages': [
            {'id': 'introduction', 'title': 'Introduction'},
            {'id': 'quick-start', 'title': 'Quick Start Guide'},
            {'id': 'installation', 'title': 'Installation'},
            {'id': 'configuration', 'title': 'Configuration'},
            {'id': 'first-project', 'title': 'Your First Project'}
        ]
    },
    'sdk-integration': {
        'title': 'SDK Integration',
        'icon': 'code-slash',
        'pages': [
            {'id': 'javascript-sdk', 'title': 'JavaScript SDK'},
            {'id': 'python-sdk', 'title': 'Python SDK'},
            {'id': 'react-sdk', 'title': 'React SDK'},
            {'id': 'vue-sdk', 'title': 'Vue.js SDK'},
            {'id': 'angular-sdk', 'title': 'Angular SDK'},
            {'id': 'node-sdk', 'title': 'Node.js SDK'}
        ]
    },
    'api-reference': {
        'title': 'API Reference',
        'icon': 'gear',
        'pages': [
            {'id': 'authentication', 'title': 'Authentication'},
            {'id': 'endpoints', 'title': 'API Endpoints'},
            {'id': 'events', 'title': 'Event Types'},
            {'id': 'batch-processing', 'title': 'Batch Processing'},
            {'id': 'webhooks', 'title': 'Webhooks'},
            {'id': 'rate-limits', 'title': 'Rate Limits'},
            {'id': 'errors', 'title': 'Error Handling'}
        ]
    },
    'guides': {
        'title': 'Guides',
        'icon': 'book',
        'pages': [
            {'id': 'best-practices', 'title': 'Best Practices'},
            {'id': 'data-privacy', 'title': 'Data Privacy'},
            {'id': 'performance', 'title': 'Performance'},
            {'id': 'custom-events', 'title': 'Custom Events'},
            {'id': 'user-tracking', 'title': 'User Tracking'},
            {'id': 'error-tracking', 'title': 'Error Tracking'}
        ]
    },
    'dashboard': {
        'title': 'Dashboard',
        'icon': 'graph-up',
        'pages': [
            {'id': 'overview', 'title': 'Overview'},
            {'id': 'analytics', 'title': 'Analytics'},
            {'id': 'filters', 'title': 'Filters'},
            {'id': 'exports', 'title': 'Exports'},
            {'id': 'alerts', 'title': 'Alerts'}
        ]
    },
    'account': {
        'title': 'Account',
        'icon': 'person',
        'pages': [
            {'id': 'profile', 'title': 'Profile'},
            {'id': 'api-keys', 'title': 'API Keys'},
            {'id': 'team', 'title': 'Team'},
            {'id': 'billing', 'title': 'Billing'},
            {'id': 'security', 'title': 'Security'}
        ]
    }
}

def get_html_content(page_id):
    """Return detailed HTML content with Bootstrap classes"""
    
    contents = {
        'introduction': '''
<div class="mb-5">
    <h1 class="display-4 fw-bold mb-4">Welcome to Agent SDK Platform</h1>
    <p class="lead fs-4">The complete observability platform for modern applications</p>
    <p class="text-muted">Agent SDK helps you monitor, debug, and optimize your applications with real-time log tracking and powerful analytics.</p>
</div>

<div class="row g-4 mb-5">
    <div class="col-md-4">
        <div class="card h-100 border-0 shadow-sm">
            <div class="card-body">
                <div class="feature-icon mb-3">
                    <i class="bi bi-lightning-charge-fill fs-1 text-primary"></i>
                </div>
                <h3 class="h5 fw-bold">Real-time Tracking</h3>
                <p class="text-muted small">Monitor logs as they happen with sub-second latency. Get instant visibility into errors and performance issues.</p>
                <ul class="list-unstyled small mt-3">
                    <li><i class="bi bi-check-circle-fill text-success me-2"></i>Live log streaming</li>
                    <li><i class="bi bi-check-circle-fill text-success me-2"></i>Instant alerts</li>
                    <li><i class="bi bi-check-circle-fill text-success me-2"></i>Real-time dashboards</li>
                </ul>
            </div>
        </div>
    </div>
    
    <div class="col-md-4">
        <div class="card h-100 border-0 shadow-sm">
            <div class="card-body">
                <div class="feature-icon mb-3">
                    <i class="bi bi-graph-up-arrow fs-1 text-success"></i>
                </div>
                <h3 class="h5 fw-bold">Advanced Analytics</h3>
                <p class="text-muted small">Deep insights into user behavior, system performance, and business metrics with customizable dashboards.</p>
                <ul class="list-unstyled small mt-3">
                    <li><i class="bi bi-check-circle-fill text-success me-2"></i>Custom charts</li>
                    <li><i class="bi bi-check-circle-fill text-success me-2"></i>Trend analysis</li>
                    <li><i class="bi bi-check-circle-fill text-success me-2"></i>User journeys</li>
                </ul>
            </div>
        </div>
    </div>
    
    <div class="col-md-4">
        <div class="card h-100 border-0 shadow-sm">
            <div class="card-body">
                <div class="feature-icon mb-3">
                    <i class="bi bi-code-square fs-1 text-warning"></i>
                </div>
                <h3 class="h5 fw-bold">Multi-language Support</h3>
                <p class="text-muted small">SDKs for all major frameworks and languages. Easy integration with minimal code changes.</p>
                <ul class="list-unstyled small mt-3">
                    <li><i class="bi bi-check-circle-fill text-success me-2"></i>JavaScript/TypeScript</li>
                    <li><i class="bi bi-check-circle-fill text-success me-2"></i>Python/Django/Flask</li>
                    <li><i class="bi bi-check-circle-fill text-success me-2"></i>React/Vue/Angular</li>
                </ul>
            </div>
        </div>
    </div>
</div>

<div class="row g-4 mb-5">
    <div class="col-md-6">
        <div class="card border-0 bg-light">
            <div class="card-body p-4">
                <h3 class="h5 fw-bold mb-3"><i class="bi bi-people-fill me-2 text-primary"></i>Team Collaboration</h3>
                <p class="small text-muted">Share insights and work together seamlessly</p>
                <div class="row mt-3">
                    <div class="col-6">
                        <div class="text-center">
                            <h4 class="h3 fw-bold text-primary">5+</h4>
                            <small class="text-muted">Team members</small>
                        </div>
                    </div>
                    <div class="col-6">
                        <div class="text-center">
                            <h4 class="h3 fw-bold text-primary">3</h4>
                            <small class="text-muted">Permission levels</small>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="col-md-6">
        <div class="card border-0 bg-light">
            <div class="card-body p-4">
                <h3 class="h5 fw-bold mb-3"><i class="bi bi-shield-check me-2 text-success"></i>Enterprise Security</h3>
                <p class="small text-muted">Bank-level security for your data</p>
                <div class="mt-3">
                    <span class="badge bg-success me-2">SOC2</span>
                    <span class="badge bg-success me-2">GDPR</span>
                    <span class="badge bg-success me-2">HIPAA</span>
                    <span class="badge bg-success me-2">Encryption</span>
                </div>
            </div>
        </div>
    </div>
</div>

<div class="mb-5">
    <h2 class="h3 fw-bold mb-4"><i class="bi bi-diagram-3 me-2 text-primary"></i>How It Works</h2>
    
    <div class="row g-4">
        <div class="col-md-3">
            <div class="text-center">
                <div class="bg-primary text-white rounded-circle d-inline-flex align-items-center justify-content-center mb-3" style="width: 60px; height: 60px;">
                    <span class="h4 fw-bold mb-0">1</span>
                </div>
                <h4 class="h6 fw-bold">Sign Up</h4>
                <small class="text-muted">Create free account</small>
            </div>
        </div>
        <div class="col-md-3">
            <div class="text-center">
                <div class="bg-primary text-white rounded-circle d-inline-flex align-items-center justify-content-center mb-3" style="width: 60px; height: 60px;">
                    <span class="h4 fw-bold mb-0">2</span>
                </div>
                <h4 class="h6 fw-bold">Get API Key</h4>
                <small class="text-muted">Generate from dashboard</small>
            </div>
        </div>
        <div class="col-md-3">
            <div class="text-center">
                <div class="bg-primary text-white rounded-circle d-inline-flex align-items-center justify-content-center mb-3" style="width: 60px; height: 60px;">
                    <span class="h4 fw-bold mb-0">3</span>
                </div>
                <h4 class="h6 fw-bold">Install SDK</h4>
                <small class="text-muted">npm install / pip install</small>
            </div>
        </div>
        <div class="col-md-3">
            <div class="text-center">
                <div class="bg-primary text-white rounded-circle d-inline-flex align-items-center justify-content-center mb-3" style="width: 60px; height: 60px;">
                    <span class="h4 fw-bold mb-0">4</span>
                </div>
                <h4 class="h6 fw-bold">Start Tracking</h4>
                <small class="text-muted">View analytics</small>
            </div>
        </div>
    </div>
</div>

<div class="mb-5">
    <h2 class="h3 fw-bold mb-4"><i class="bi bi-table me-2 text-primary"></i>Use Cases</h2>
    
    <div class="table-responsive">
        <table class="table table-hover align-middle">
            <thead class="table-light">
                <tr>
                    <th>Use Case</th>
                    <th>Description</th>
                    <th>Key Features</th>
                    <th>Benefit</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td><span class="badge bg-danger">Error Monitoring</span></td>
                    <td>Real-time error tracking with full context</td>
                    <td>Stack traces, user sessions, browser info</td>
                    <td>99.9% error reduction</td>
                </tr>
                <tr>
                    <td><span class="badge bg-primary">User Analytics</span></td>
                    <td>Track user behavior and journeys</td>
                    <td>Click maps, funnels, retention</td>
                    <td>2x conversion rate</td>
                </tr>
                <tr>
                    <td><span class="badge bg-success">Performance</span></td>
                    <td>Monitor app speed and responsiveness</td>
                    <td>Load times, API latency, resource usage</td>
                    <td>40% faster apps</td>
                </tr>
            </tbody>
        </table>
    </div>
</div>

<div class="bg-primary text-white p-5 rounded-4 mb-5">
    <div class="row align-items-center">
        <div class="col-md-8">
            <h3 class="h4 fw-bold mb-2">Ready to get started?</h3>
            <p class="mb-md-0 opacity-75">Join thousands of developers using Agent SDK</p>
        </div>
        <div class="col-md-4 text-md-end">
            <a href="/register" class="btn btn-light btn-lg px-4">
                <i class="bi bi-person-plus me-2"></i>Sign Up Free
            </a>
        </div>
    </div>
</div>
        ''',
        
        'quick-start': '''
<div class="mb-4">
    <h1 class="fw-bold mb-3">Quick Start Guide</h1>
    <p class="lead">Get up and running with Agent SDK in 5 minutes ⚡</p>
</div>

<div class="alert alert-info d-flex align-items-center mb-4">
    <i class="bi bi-info-circle-fill fs-4 me-3"></i>
    <div>Already have an account? <a href="/login" class="alert-link">Login here</a></div>
</div>

<div class="row g-4 mb-5">
    <div class="col-md-6">
        <div class="card shadow-sm h-100">
            <div class="card-header bg-white py-3">
                <h5 class="mb-0 fw-bold"><i class="bi bi-filetype-js me-2 text-primary"></i>JavaScript</h5>
            </div>
            <div class="card-body">
                <h6 class="fw-bold mb-3">1. Install SDK</h6>
                <pre class="bg-dark text-light p-3 rounded"><code class="language-bash">npm install @agent-sdk/javascript</code></pre>
                
                <h6 class="fw-bold mb-3 mt-4">2. Initialize</h6>
                <pre class="bg-dark text-light p-3 rounded"><code class="language-javascript">import AgentSDK from '@agent-sdk/javascript';

const agent = new AgentSDK({
    apiKey: process.env.AGENT_API_KEY,
    project: 'my-app',
    environment: process.env.NODE_ENV
});</code></pre>
                
                <h6 class="fw-bold mb-3 mt-4">3. Track Events</h6>
                <pre class="bg-dark text-light p-3 rounded"><code class="language-javascript">// Track page views
agent.track('page_view', {
    page: window.location.pathname,
    user_id: getUserId()
});

// Track custom events
agent.track('button_click', {
    button_id: 'signup',
    button_text: 'Sign Up'
});</code></pre>
            </div>
        </div>
    </div>
    
    <div class="col-md-6">
        <div class="card shadow-sm h-100">
            <div class="card-header bg-white py-3">
                <h5 class="mb-0 fw-bold"><i class="bi bi-filetype-py me-2 text-success"></i>Python</h5>
            </div>
            <div class="card-body">
                <h6 class="fw-bold mb-3">1. Install SDK</h6>
                <pre class="bg-dark text-light p-3 rounded"><code class="language-bash">pip install agent-sdk-python</code></pre>
                
                <h6 class="fw-bold mb-3 mt-4">2. Initialize</h6>
                <pre class="bg-dark text-light p-3 rounded"><code class="language-python">from agent_sdk import AgentSDK

agent = AgentSDK(
    api_key=os.getenv('AGENT_API_KEY'),
    project='my-app',
    environment=os.getenv('ENV')
)</code></pre>
                
                <h6 class="fw-bold mb-3 mt-4">3. Track Events</h6>
                <pre class="bg-dark text-light p-3 rounded"><code class="language-python"># Track user actions
agent.track('user_action', {
    'action': 'login',
    'user_id': user.id,
    'method': 'google'
})

# Track API calls
agent.track('api_request', {
    'endpoint': '/users',
    'duration_ms': 234,
    'status': 200
})</code></pre>
            </div>
        </div>
    </div>
</div>

<div class="card shadow-sm mb-5">
    <div class="card-header bg-white py-3">
        <h5 class="mb-0 fw-bold"><i class="bi bi-check2-circle me-2 text-success"></i>Quick Checklist</h5>
    </div>
    <div class="card-body">
        <div class="row g-3">
            <div class="col-md-6">
                <div class="form-check">
                    <input class="form-check-input" type="checkbox" id="check1">
                    <label class="form-check-label" for="check1">
                        SDK installed successfully
                    </label>
                </div>
                <div class="form-check">
                    <input class="form-check-input" type="checkbox" id="check2">
                    <label class="form-check-label" for="check2">
                        API key configured
                    </label>
                </div>
                <div class="form-check">
                    <input class="form-check-input" type="checkbox" id="check3">
                    <label class="form-check-label" for="check3">
                        First event tracked
                    </label>
                </div>
            </div>
            <div class="col-md-6">
                <div class="form-check">
                    <input class="form-check-input" type="checkbox" id="check4">
                    <label class="form-check-label" for="check4">
                        Dashboard verified
                    </label>
                </div>
                <div class="form-check">
                    <input class="form-check-input" type="checkbox" id="check5">
                    <label class="form-check-label" for="check5">
                        Error tracking setup
                    </label>
                </div>
                <div class="form-check">
                    <input class="form-check-input" type="checkbox" id="check6">
                    <label class="form-check-label" for="check6">
                        Team invited
                    </label>
                </div>
            </div>
        </div>
    </div>
</div>

<div class="row g-4">
    <div class="col-md-4">
        <div class="card bg-light border-0">
            <div class="card-body text-center">
                <i class="bi bi-youtube fs-1 text-danger mb-3"></i>
                <h6 class="fw-bold">Video Tutorial</h6>
                <p class="small text-muted">Watch our 2-minute setup guide</p>
                <a href="#" class="btn btn-outline-danger btn-sm">Watch Now</a>
            </div>
        </div>
    </div>
    <div class="col-md-4">
        <div class="card bg-light border-0">
            <div class="card-body text-center">
                <i class="bi bi-github fs-1 text-dark mb-3"></i>
                <h6 class="fw-bold">Example Projects</h6>
                <p class="small text-muted">Check out sample apps on GitHub</p>
                <a href="#" class="btn btn-outline-dark btn-sm">View Code</a>
            </div>
        </div>
    </div>
    <div class="col-md-4">
        <div class="card bg-light border-0">
            <div class="card-body text-center">
                <i class="bi bi-chat-dots fs-1 text-primary mb-3"></i>
                <h6 class="fw-bold">Need Help?</h6>
                <p class="small text-muted">Join our community forum</p>
                <a href="#" class="btn btn-outline-primary btn-sm">Ask Now</a>
            </div>
        </div>
    </div>
</div>
        ''',
        
        'javascript-sdk': '''
<div class="mb-4">
    <h1 class="fw-bold mb-3">JavaScript SDK</h1>
    <p class="lead">Complete guide for browser and Node.js applications</p>
</div>

<div class="row mb-4">
    <div class="col-md-3">
        <div class="card bg-light border-0 text-center">
            <div class="card-body">
                <h2 class="h1 fw-bold text-primary">10k+</h2>
                <small class="text-muted">Weekly downloads</small>
            </div>
        </div>
    </div>
    <div class="col-md-3">
        <div class="card bg-light border-0 text-center">
            <div class="card-body">
                <h2 class="h1 fw-bold text-success">99.9%</h2>
                <small class="text-muted">Uptime SLA</small>
            </div>
        </div>
    </div>
    <div class="col-md-3">
        <div class="card bg-light border-0 text-center">
            <div class="card-body">
                <h2 class="h1 fw-bold text-warning">5ms</h2>
                <small class="text-muted">Avg latency</small>
            </div>
        </div>
    </div>
    <div class="col-md-3">
        <div class="card bg-light border-0 text-center">
            <div class="card-body">
                <h2 class="h1 fw-bold text-info">100+</h2>
                <small class="text-muted">Contributors</small>
            </div>
        </div>
    </div>
</div>

<ul class="nav nav-tabs mb-4" id="sdkTab" role="tablist">
    <li class="nav-item" role="presentation">
        <button class="nav-link active" id="browser-tab" data-bs-toggle="tab" data-bs-target="#browser" type="button">Browser</button>
    </li>
    <li class="nav-item" role="presentation">
        <button class="nav-link" id="node-tab" data-bs-toggle="tab" data-bs-target="#node" type="button">Node.js</button>
    </li>
    <li class="nav-item" role="presentation">
        <button class="nav-link" id="typescript-tab" data-bs-toggle="tab" data-bs-target="#typescript" type="button">TypeScript</button>
    </li>
</ul>

<div class="tab-content mb-5" id="sdkTabContent">
    <div class="tab-pane fade show active" id="browser" role="tabpanel">
        <div class="card shadow-sm">
            <div class="card-body">
                <h5 class="fw-bold mb-3">Browser Installation</h5>
                <pre class="bg-dark text-light p-3 rounded"><code class="language-bash">npm install @agent-sdk/javascript</code></pre>
                
                <h5 class="fw-bold mb-3 mt-4">CDN (Quick Start)</h5>
                <pre class="bg-dark text-light p-3 rounded"><code class="language-html">&lt;script src="https://cdn.agentsdk.com/sdk/latest/agent.min.js"&gt;&lt;/script&gt;
&lt;script&gt;
    const agent = new AgentSDK({
        apiKey: 'your-key',
        project: 'my-app'
    });
&lt;/script&gt;</code></pre>
                
                <h5 class="fw-bold mb-3 mt-4">Browser Events</h5>
                <pre class="bg-dark text-light p-3 rounded"><code class="language-javascript">// Page view tracking
window.addEventListener('load', () => {
    agent.track('page_view', {
        url: window.location.href,
        title: document.title,
        referrer: document.referrer,
        screen: `${window.screen.width}x${window.screen.height}`
    });
});

// Click tracking
document.addEventListener('click', (e) => {
    const target = e.target.closest('button, a');
    if (target) {
        agent.track('click', {
            element: target.tagName,
            text: target.innerText.slice(0, 50),
            href: target.href,
            id: target.id
        });
    }
});

// Form tracking
document.addEventListener('submit', (e) => {
    agent.track('form_submit', {
        formId: e.target.id,
        formName: e.target.name,
        action: e.target.action
    });
});</code></pre>
            </div>
        </div>
    </div>
    
    <div class="tab-pane fade" id="node" role="tabpanel">
        <div class="card shadow-sm">
            <div class="card-body">
                <h5 class="fw-bold mb-3">Node.js Installation</h5>
                <pre class="bg-dark text-light p-3 rounded"><code class="language-bash">npm install @agent-sdk/node</code></pre>
                
                <h5 class="fw-bold mb-3 mt-4">Express Middleware</h5>
                <pre class="bg-dark text-light p-3 rounded"><code class="language-javascript">const express = require('express');
const { agentMiddleware } = require('@agent-sdk/node');

const app = express();

// Add tracking middleware
app.use(agentMiddleware({
    apiKey: process.env.AGENT_API_KEY,
    project: 'my-api'
}));

// Your routes
app.get('/api/users', (req, res) => {
    // Auto-tracked by middleware
    res.json({ users: [] });
});</code></pre>
                
                <h5 class="fw-bold mb-3 mt-4">Manual Tracking</h5>
                <pre class="bg-dark text-light p-3 rounded"><code class="language-javascript">const AgentSDK = require('@agent-sdk/node');
const agent = new AgentSDK({
    apiKey: process.env.AGENT_API_KEY,
    project: 'my-api'
});

// Track API calls
app.get('/api/orders', async (req, res) => {
    const start = Date.now();
    try {
        const orders = await db.getOrders();
        agent.track('api_call', {
            endpoint: '/orders',
            method: 'GET',
            duration: Date.now() - start,
            status: 200
        });
        res.json(orders);
    } catch (error) {
        agent.error(error, {
            endpoint: '/orders',
            method: 'GET'
        });
        res.status(500).json({ error: error.message });
    }
});</code></pre>
            </div>
        </div>
    </div>
    
    <div class="tab-pane fade" id="typescript" role="tabpanel">
        <div class="card shadow-sm">
            <div class="card-body">
                <h5 class="fw-bold mb-3">TypeScript Support</h5>
                <pre class="bg-dark text-light p-3 rounded"><code class="language-typescript">import AgentSDK, { Event, Config } from '@agent-sdk/javascript';

interface UserEvent extends Event {
    data: {
        userId: string;
        action: 'login' | 'logout' | 'signup';
        metadata?: Record<string, any>;
    };
}

const config: Config = {
    apiKey: process.env.AGENT_API_KEY!,
    project: 'my-app',
    environment: process.env.NODE_ENV as 'production' | 'development'
};

const agent = new AgentSDK(config);

// Type-safe tracking
agent.track<UserEvent>('user_action', {
    userId: '123',
    action: 'login',
    metadata: { source: 'google' }
});</code></pre>
            </div>
        </div>
    </div>
</div>

<h3 class="h4 fw-bold mb-3">Configuration Options</h3>
<div class="table-responsive mb-5">
    <table class="table table-bordered">
        <thead class="table-light">
            <tr>
                <th>Option</th>
                <th>Type</th>
                <th>Default</th>
                <th>Description</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td><code>apiKey</code></td>
                <td>string</td>
                <td>required</td>
                <td>Your API key (format: key_id:key_secret)</td>
            </tr>
            <tr>
                <td><code>project</code></td>
                <td>string</td>
                <td>required</td>
                <td>Project name for grouping logs</td>
            </tr>
            <tr>
                <td><code>environment</code></td>
                <td>string</td>
                <td>'production'</td>
                <td>production/staging/development</td>
            </tr>
            <tr>
                <td><code>batchSize</code></td>
                <td>number</td>
                <td>10</td>
                <td>Events per batch</td>
            </tr>
            <tr>
                <td><code>flushInterval</code></td>
                <td>number</td>
                <td>5000</td>
                <td>Flush interval in ms</td>
            </tr>
            <tr>
                <td><code>maxQueueSize</code></td>
                <td>number</td>
                <td>100</td>
                <td>Max queued events</td>
            </tr>
        </tbody>
    </table>
</div>
        ''',
        
        'api-keys': '''
<div class="mb-4">
    <h1 class="fw-bold mb-3">API Keys</h1>
    <p class="lead">Secure access management for your applications</p>
</div>

<div class="alert alert-warning d-flex align-items-center mb-4">
    <i class="bi bi-shield-lock-fill fs-4 me-3"></i>
    <div><strong>Security Note:</strong> Never expose your API keys in client-side code or public repositories.</div>
</div>

<div class="row g-4 mb-5">
    <div class="col-md-4">
        <div class="card h-100 border-0 shadow-sm">
            <div class="card-body text-center">
                <div class="bg-primary bg-opacity-10 text-primary rounded-circle d-inline-flex align-items-center justify-content-center mb-3" style="width: 64px; height: 64px;">
                    <i class="bi bi-key fs-1"></i>
                </div>
                <h5 class="fw-bold">Key ID</h5>
                <p class="small text-muted">Public identifier for your key</p>
                <code class="bg-light p-2 d-block">sdk_live_2xK3pQ...</code>
            </div>
        </div>
    </div>
    
    <div class="col-md-4">
        <div class="card h-100 border-0 shadow-sm">
            <div class="card-body text-center">
                <div class="bg-success bg-opacity-10 text-success rounded-circle d-inline-flex align-items-center justify-content-center mb-3" style="width: 64px; height: 64px;">
                    <i class="bi bi-shield-check fs-1"></i>
                </div>
                <h5 class="fw-bold">Key Secret</h5>
                <p class="small text-muted">Keep this secret! Shown only once</p>
                <code class="bg-light p-2 d-block">••••••••••••••••</code>
            </div>
        </div>
    </div>
    
    <div class="col-md-4">
        <div class="card h-100 border-0 shadow-sm">
            <div class="card-body text-center">
                <div class="bg-info bg-opacity-10 text-info rounded-circle d-inline-flex align-items-center justify-content-center mb-3" style="width: 64px; height: 64px;">
                    <i class="bi bi-clock-history fs-1"></i>
                </div>
                <h5 class="fw-bold">Expiration</h5>
                <p class="small text-muted">Set expiry for temporary access</p>
                <span class="badge bg-info">30 days</span>
            </div>
        </div>
    </div>
</div>

<h3 class="h4 fw-bold mb-3">Creating API Keys</h3>
<div class="card shadow-sm mb-5">
    <div class="card-body">
        <div class="row align-items-center">
            <div class="col-md-8">
                <pre class="bg-dark text-light p-3 rounded mb-0"><code class="language-bash"># Generate new API key
curl -X POST https://api.agentsdk.com/v1/api-keys \
  -H "Authorization: Bearer YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Production App",
    "permissions": ["read", "write"],
    "expires_in": "90d"
  }'</code></pre>
            </div>
            <div class="col-md-4">
                <div class="bg-light p-3 rounded">
                    <h6 class="fw-bold mb-2">Response</h6>
                    <pre class="small mb-0"><code>{
  "key_id": "sdk_live_2xK3pQ...",
  "key_secret": "9f8a7g6h5j4k3l2...",
  "created_at": "2026-02-24T10:30:00Z"
}</code></pre>
                </div>
            </div>
        </div>
    </div>
</div>

<h3 class="h4 fw-bold mb-3">Permission Levels</h3>
<div class="row g-4 mb-5">
    <div class="col-md-3">
        <div class="card border-0 bg-light">
            <div class="card-body">
                <h6 class="fw-bold text-primary">Read Only</h6>
                <small class="text-muted d-block mb-2">View logs and analytics</small>
                <code>read_logs</code>
            </div>
        </div>
    </div>
    <div class="col-md-3">
        <div class="card border-0 bg-light">
            <div class="card-body">
                <h6 class="fw-bold text-success">Write Only</h6>
                <small class="text-muted d-block mb-2">Send logs only</small>
                <code>write_logs</code>
            </div>
        </div>
    </div>
    <div class="col-md-3">
        <div class="card border-0 bg-light">
            <div class="card-body">
                <h6 class="fw-bold text-warning">Admin</h6>
                <small class="text-muted d-block mb-2">Full access</small>
                <code>admin</code>
            </div>
        </div>
    </div>
    <div class="col-md-3">
        <div class="card border-0 bg-light">
            <div class="card-body">
                <h6 class="fw-bold text-danger">Custom</h6>
                <small class="text-muted d-block mb-2">Combination of scopes</small>
                <code>read_logs,write_logs</code>
            </div>
        </div>
    </div>
</div>

<h3 class="h4 fw-bold mb-3">Rate Limits</h3>
<div class="card shadow-sm mb-5">
    <div class="card-body">
        <div class="table-responsive">
            <table class="table table-hover">
                <thead>
                    <tr>
                        <th>Tier</th>
                        <th>Requests/minute</th>
                        <th>Batch size</th>
                        <th>Data retention</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><span class="badge bg-secondary">Free</span></td>
                        <td>60</td>
                        <td>100 events</td>
                        <td>7 days</td>
                    </tr>
                    <tr>
                        <td><span class="badge bg-primary">Pro</span></td>
                        <td>300</td>
                        <td>500 events</td>
                        <td>30 days</td>
                    </tr>
                    <tr>
                        <td><span class="badge bg-success">Enterprise</span></td>
                        <td>Custom</td>
                        <td>Custom</td>
                        <td>1 year+</td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
</div>
        '''
    }
    
    return contents.get(page_id, '''
<div class="alert alert-warning d-flex align-items-center">
    <i class="bi bi-exclamation-triangle-fill fs-4 me-3"></i>
    <div>
        <h5 class="alert-heading mb-1">Content Coming Soon</h5>
        <p class="mb-0">This documentation page is being written. Check back later!</p>
    </div>
</div>
    ''')

@bp.route('/')
@bp.route('/<path:page>')
def index(page='introduction'):
    current_page = None
    for section in DOCS_STRUCTURE.values():
        for p in section['pages']:
            if p['id'] == page:
                current_page = p
                break
    
    if not current_page:
        return redirect(url_for('documentation.index', page='introduction'))
    
    content = get_html_content(page)
    
    return render_template(
        'documentation/bootstrap_docs.html',
        title=f"{current_page['title']} - Documentation",
        structure=DOCS_STRUCTURE,
        current_page=current_page,
        content=content,
        user=current_user if current_user.is_authenticated else None
    )

@bp.route('/api/search')
def search():
    query = request.args.get('q', '').lower()
    if len(query) < 3:
        return jsonify({'results': []})
    
    results = []
    for section_id, section in DOCS_STRUCTURE.items():
        for page in section['pages']:
            if query in page['title'].lower():
                results.append({
                    'title': page['title'],
                    'section': section['title'],
                    'url': url_for('documentation.index', page=page['id']),
                    'type': 'page'
                })
    
    return jsonify({'results': results[:10]})

@bp.route('/api/feedback', methods=['POST'])
def feedback():
    try:
        data = request.get_json()
        page = data.get('page')
        helpful = data.get('helpful')
        print(f"Feedback for {page}: {'👍' if helpful else '👎'}")
        return jsonify({'success': True, 'message': 'Thank you for your feedback!'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500