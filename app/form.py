from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField, TextAreaField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError, Regexp, Optional, URL
from wtforms.widgets import ListWidget, CheckboxInput
from app.models.user_models import User
import re

class LoginForm(FlaskForm):
    """User login form"""
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class RegistrationForm(FlaskForm):
    """User registration form with phone number"""
    username = StringField('Username', validators=[
        DataRequired(),
        Length(min=3, max=20),
        Regexp('^[A-Za-z][A-Za-z0-9_.]*$', 0,
               'Username must start with a letter and contain only letters, numbers, dots, or underscores')
    ])
    email = StringField('Email', validators=[DataRequired(), Email()])
    
    # ✅ Add phone fields
    country_code = SelectField('Country Code', choices=[
        ('+1', '🇺🇸 +1 (USA)'),
        ('+44', '🇬🇧 +44 (UK)'),
        ('+91', '🇮🇳 +91 (India)'),
        ('+61', '🇦🇺 +61 (Australia)'),
        ('+81', '🇯🇵 +81 (Japan)'),
        ('+86', '🇨🇳 +86 (China)'),
        ('+49', '🇩🇪 +49 (Germany)'),
        ('+33', '🇫🇷 +33 (France)'),
        ('+7', '🇷🇺 +7 (Russia)'),
        ('+55', '🇧🇷 +55 (Brazil)'),
        ('+27', '🇿🇦 +27 (South Africa)'),
        ('+971', '🇦🇪 +971 (UAE)'),
    ], default='+91')
    
    phone = StringField('Mobile Number', validators=[
        DataRequired(),
        Length(min=10, max=15),
        Regexp('^[0-9]+$', 0, 'Phone number must contain only digits')
    ])
    
    full_name = StringField('Full Name', validators=[Length(max=100)])
    company_name = StringField('Company Name', validators=[Length(max=100)])
    website_url = StringField('Website URL', validators=[Length(max=200), Optional(), URL()])
    
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=8, message='Password must be at least 8 characters long'),
        Regexp('^(?=.*[A-Za-z])(?=.*\\d)(?=.*[@$!%*#?&])[A-Za-z\\d@$!%*#?&]', 0,
               'Password must contain at least one letter, one number, and one special character')
    ])
    password2 = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])
    accept_tos = BooleanField('I accept the Terms of Service and Privacy Policy', validators=[DataRequired()])
    submit = SubmitField('Register')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError('Please use a different username.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user is not None:
            raise ValidationError('Please use a different email address.')
    
    def validate_phone(self, phone):
        # Check if phone already exists with same country code
        from app.models.user_models import User
        user = User.query.filter_by(phone=phone.data, country_code=self.country_code.data).first()
        if user is not None:
            raise ValidationError('This phone number is already registered.')

class RequestPasswordResetForm(FlaskForm):
    """Request password reset form"""
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Request Password Reset')

class ResetPasswordForm(FlaskForm):
    """Reset password form"""
    password = PasswordField('New Password', validators=[
        DataRequired(),
        Length(min=8),
        Regexp('^(?=.*[A-Za-z])(?=.*\\d)(?=.*[@$!%*#?&])[A-Za-z\\d@$!%*#?&]', 0,
               'Password must contain at least one letter, one number, and one special character')
    ])
    password2 = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField('Reset Password')

class ChangePasswordForm(FlaskForm):
    """Change password form (for authenticated users)"""
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[
        DataRequired(),
        Length(min=8),
        Regexp('^(?=.*[A-Za-z])(?=.*\\d)(?=.*[@$!%*#?&])[A-Za-z\\d@$!%*#?&]', 0,
               'Password must contain at least one letter, one number, and one special character')
    ])
    confirm_password = PasswordField('Confirm New Password', validators=[
        DataRequired(),
        EqualTo('new_password', message='Passwords must match')
    ])
    submit = SubmitField('Change Password')

class ProfileUpdateForm(FlaskForm):
    """Update user profile form"""
    full_name = StringField('Full Name', validators=[Length(max=100)])
    company_name = StringField('Company Name', validators=[Length(max=100)])
    website_url = StringField('Website URL', validators=[Length(max=200)])
    phone = StringField('Phone Number', validators=[Length(max=20)])
    submit = SubmitField('Update Profile')

class TwoFactorForm(FlaskForm):
    """Two-factor authentication form"""
    token = StringField('Authentication Code', validators=[DataRequired(), Length(min=6, max=6)])
    submit = SubmitField('Verify')