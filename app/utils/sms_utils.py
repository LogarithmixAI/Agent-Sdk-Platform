import os
import os
from twilio.rest import Client  # ✅ IMPORT CLIENT FROM TWILIO
from flask import current_app
from datetime import datetime
import random

class SMSService:
    """SMS Service using Twilio"""
    
    def __init__(self):
        self.account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        self.auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.from_number = os.getenv('TWILIO_PHONE_NUMBER')
        self.client = None
        
        if self.account_sid and self.auth_token:
            self.client = Client(self.account_sid, self.auth_token)
    
    def send_otp(self, phone_number, otp):
        """Send OTP via SMS"""
        try:
            if not self.client:
                return False, "Twilio not configured"
            
            message = self.client.messages.create(
                body=f'🔐 Your Agent SDK OTP is: {otp}\nValid for 10 minutes.\nDon\'t share this code.',
                from_=self.from_number,
                to=phone_number
            )
            
            print(f"✅ SMS sent: {message.sid}")
            return True, "OTP sent successfully"
            
        except Exception as e:
            print(f"❌ SMS error: {str(e)}")
            return False, str(e)
    
    def send_verification_sms(self, phone_number, otp):
        """Send verification SMS with nice formatting"""
        try:
            if not self.client:
                return False, "Twilio not configured"
            
            message_body = f"""
🔐 Agent SDK Verification
            
Your verification code is: {otp}

This code will expire in 10 minutes.
Never share this code with anyone.

If you didn't request this, please ignore.
            """.strip()
            
            message = self.client.messages.create(
                body=message_body,
                from_=self.from_number,
                to=phone_number
            )
            
            return True, message.sid
            
        except Exception as e:
            return False, str(e)
    
    def send_custom_message(self, phone_number, message):
        """Send custom SMS message"""
        try:
            if not self.client:
                return False, "Twilio not configured"
            
            message = self.client.messages.create(
                body=message,
                from_=self.from_number,
                to=phone_number
            )
            
            return True, message.sid
            
        except Exception as e:
            return False, str(e)

# Create singleton instance
sms_service = SMSService()

def send_phone_otp(user):
    """Send OTP to user's phone"""
    try:
        # Generate 6-digit OTP
        otp = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        
        # Save OTP to user
        user.phone_otp_code = otp
        user.phone_otp_created_at = datetime.utcnow()
        user.phone_otp_attempts = 0
        from app import db
        db.session.commit()
        
        # Format phone number
        phone_number = f"{user.country_code}{user.phone}"
        
        # Send SMS
        success, message = sms_service.send_otp(phone_number, otp)
        
        if success:
            print(f"📱 OTP sent to {phone_number}")
            return True, "OTP sent successfully"
        else:
            return False, message
            
    except Exception as e:
        print(f"Error sending phone OTP: {e}")
        return False, str(e)

def verify_phone_otp(user, otp):
    """Verify phone OTP"""
    if not user.phone_otp_code or not user.phone_otp_created_at:
        return False, "No OTP generated"
    
    # Check expiration (10 minutes)
    from datetime import datetime, timedelta
    if datetime.utcnow() - user.phone_otp_created_at > timedelta(minutes=10):
        return False, "OTP expired"
    
    # Check attempts
    if user.phone_otp_attempts >= 3:
        return False, "Too many failed attempts"
    
    # Verify OTP
    if user.phone_otp_code == otp:
        user.phone_otp_code = None
        user.phone_otp_created_at = None
        user.phone_otp_attempts = 0
        user.phone_verified = True
        from app import db
        db.session.commit()
        return True, "Phone verified successfully"
    else:
        user.phone_otp_attempts += 1
        from app import db
        db.session.commit()
        return False, f"Invalid OTP. {3 - user.phone_otp_attempts} attempts remaining"