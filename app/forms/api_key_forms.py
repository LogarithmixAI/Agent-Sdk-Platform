from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, BooleanField, SelectField, SelectMultipleField, DateTimeField
from wtforms.validators import DataRequired, Length, Optional, URL, ValidationError
from wtforms.widgets import ListWidget, CheckboxInput
import re

class MultiCheckboxField(SelectMultipleField):
    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()

class CreateAPIKeyForm(FlaskForm):
    """Form for creating new API keys"""
    name = StringField('Key Name', validators=[
        DataRequired(),
        Length(min=3, max=100, message='Key name must be between 3 and 100 characters')
    ])
    description = TextAreaField('Description', validators=[Optional(), Length(max=500)])
    
    # Permissions
    permissions = MultiCheckboxField('Permissions', choices=[
        ('read_logs', 'Read Logs'),
        ('write_logs', 'Write Logs'),
        ('delete_logs', 'Delete Logs'),
        ('manage_webhooks', 'Manage Webhooks'),
        ('view_analytics', 'View Analytics'),
        ('admin', 'Full Access')
    ], validators=[DataRequired()])
    
    # Security settings
    allowed_domains = TextAreaField('Allowed Domains (one per line)', 
                                   validators=[Optional()],
                                   description='Restrict key usage to specific domains')
    
    ip_whitelist = TextAreaField('IP Whitelist (one per line)',
                                validators=[Optional()],
                                description='Restrict key usage to specific IP addresses')
    
    # Expiration
    never_expire = BooleanField('Never expire', default=True)
    expires_at = DateTimeField('Expiration Date', validators=[Optional()], format='%Y-%m-%dT%H:%M')
    
    # Rate limits
    rate_limit = SelectField('Rate Limit', choices=[
        ('60', '60 requests per minute'),
        ('300', '300 requests per minute'),
        ('1000', '1000 requests per minute'),
        ('5000', '5000 requests per minute'),
        ('unlimited', 'Unlimited')
    ], default='60')
    
    def validate_allowed_domains(self, field):
        if field.data:
            domains = [d.strip() for d in field.data.split('\n') if d.strip()]
            for domain in domains:
                # Simple domain validation
                if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9-_.]+\.[a-zA-Z]{2,}$', domain):
                    raise ValidationError(f'Invalid domain format: {domain}')
    
    def validate_ip_whitelist(self, field):
        if field.data:
            ips = [ip.strip() for ip in field.data.split('\n') if ip.strip()]
            for ip in ips:
                # Simple IP validation
                if not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip):
                    raise ValidationError(f'Invalid IP address format: {ip}')

class EditAPIKeyForm(FlaskForm):
    """Form for editing existing API keys"""
    name = StringField('Key Name', validators=[
        DataRequired(),
        Length(min=3, max=100)
    ])
    
    # ✅ ADD THIS DESCRIPTION FIELD
    description = TextAreaField('Description', validators=[Optional(), Length(max=500)])
    
    is_active = BooleanField('Active')
    
    permissions = MultiCheckboxField('Permissions', choices=[
        ('read_logs', 'Read Logs'),
        ('write_logs', 'Write Logs'),
        ('delete_logs', 'Delete Logs'),
        ('manage_webhooks', 'Manage Webhooks'),
        ('view_analytics', 'View Analytics'),
        ('admin', 'Full Access')
    ])
    
    allowed_domains = TextAreaField('Allowed Domains (one per line)',
                                   validators=[Optional()])
    
    ip_whitelist = TextAreaField('IP Whitelist (one per line)',
                                validators=[Optional()])
    
    rate_limit = SelectField('Rate Limit', choices=[
        ('60', '60 requests per minute'),
        ('300', '300 requests per minute'),
        ('1000', '1000 requests per minute'),
        ('5000', '5000 requests per minute'),
        ('unlimited', 'Unlimited')
    ], default='60')
    
    # Optional expiration editing (you can add if needed)
    expires_at = DateTimeField('Expiration Date', validators=[Optional()], format='%Y-%m-%dT%H:%M')

class RevokeKeyForm(FlaskForm):
    """Form for revoking API keys"""
    confirmation = BooleanField('I understand that this action cannot be undone', 
                                validators=[DataRequired()])