// Main JavaScript for Agent SDK Platform
console.log('Agent SDK Platform loaded');

// Auto-hide alerts after 5 seconds
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(function() {
        const alerts = document.querySelectorAll('.alert');
        alerts.forEach(function(alert) {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);
});

// Add CSRF token to all AJAX requests
const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');

if (csrfToken) {
    document.addEventListener('htmx:configRequest', function(evt) {
        evt.detail.headers['X-CSRFToken'] = csrfToken;
    });
}

// Simple Custom Alert Function
function showMessage(message, type = 'info') {
    // Create alert element
    const alertDiv = document.createElement('div');
    alertDiv.className = `custom-message message-${type}`;
    alertDiv.innerHTML = `
        <div class="message-content">
            <span class="message-icon">${getIcon(type)}</span>
            <span class="message-text">${message}</span>
            <button class="message-close" onclick="this.parentElement.parentElement.remove()">&times;</button>
        </div>
    `;
    
    // Add to page
    document.body.appendChild(alertDiv);
    
    // Auto remove after 3 seconds
    setTimeout(() => {
        alertDiv.remove();
    }, 3000);
}

function getIcon(type) {
    switch(type) {
        case 'success': return '✅';
        case 'error': return '❌';
        case 'warning': return '⚠️';
        case 'info': return 'ℹ️';
        default: return '📢';
    }
}

// Override default alert (optional)
window.alert = function(message) {
    showMessage(message, 'info');
};

window.confirm = function(message) {
    // Custom confirm can also be implemented
    return window.confirm(message); // Keep default for now
};