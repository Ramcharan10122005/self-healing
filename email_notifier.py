#!/usr/bin/env python3
"""
Email Notification System for Self-Healing Process Manager
Sends email alerts for critical events (crashes, violations, anomalies)
"""
import smtplib
import os
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

CONFIG_FILE = 'email_config.txt'
LOG_FILE = 'healing.log'
LAST_EMAIL_TIME = {}  # Rate limiting: {event_type: timestamp}
MIN_EMAIL_INTERVAL = 60  # Minimum seconds between same-type emails

def load_config() -> dict:
    """Load email configuration from file or environment variables"""
    config = {
        'enabled': False,
        'smtp_server': 'smtp.gmail.com',
        'smtp_port': 465,
        'sender_email': 'kundenaramcharan@gmail.com',
        'sender_password': 'eyjl oedy unjk fpue',
        'receiver_email': '202311047@diu.iiitvadodara.ac.in',
        'use_ssl': True
    }
    
    # Try to load from file
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        if key == 'enabled':
                            config['enabled'] = value.lower() in ('true', '1', 'yes')
                        elif key == 'smtp_server':
                            config['smtp_server'] = value
                        elif key == 'smtp_port':
                            config['smtp_port'] = int(value)
                        elif key == 'sender_email':
                            config['sender_email'] = value
                        elif key == 'sender_password':
                            config['sender_password'] = value
                        elif key == 'receiver_email':
                            config['receiver_email'] = value
                        elif key == 'use_ssl':
                            config['use_ssl'] = value.lower() in ('true', '1', 'yes')
        except Exception:
            pass
    
    # Override with environment variables if present
    config['enabled'] = os.getenv('EMAIL_ENABLED', str(config['enabled'])).lower() in ('true', '1', 'yes')
    config['smtp_server'] = os.getenv('EMAIL_SMTP_SERVER', config['smtp_server'])
    config['smtp_port'] = int(os.getenv('EMAIL_SMTP_PORT', str(config['smtp_port'])))
    config['sender_email'] = os.getenv('EMAIL_SENDER', config['sender_email'])
    config['sender_password'] = os.getenv('EMAIL_PASSWORD', config['sender_password'])
    config['receiver_email'] = os.getenv('EMAIL_RECEIVER', config['receiver_email'])
    
    return config

def should_send_email(event_type: str) -> bool:
    """Check if email should be sent (rate limiting)"""
    now = time.time()
    if event_type not in LAST_EMAIL_TIME:
        LAST_EMAIL_TIME[event_type] = 0
    
    if now - LAST_EMAIL_TIME[event_type] >= MIN_EMAIL_INTERVAL:
        LAST_EMAIL_TIME[event_type] = now
        return True
    return False

def send_email(subject: str, message: str, event_type: str = 'general') -> bool:
    """
    Send email notification
    
    Args:
        subject: Email subject line
        message: Email body message
        event_type: Type of event (for rate limiting): 'crash', 'violation', 'anomaly', 'cooldown', 'general'
    
    Returns:
        True if email sent successfully, False otherwise
    """
    config = load_config()
    
    # Check if email is enabled
    if not config['enabled']:
        return False
    
    # Check required fields
    if not config['sender_email'] or not config['receiver_email']:
        return False
    
    # Rate limiting
    if not should_send_email(event_type):
        return False
    
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = config['sender_email']
        msg['To'] = config['receiver_email']
        msg['Subject'] = f"[Self-Healing Monitor] {subject}"
        
        # Add timestamp to message
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        body = f"""
Self-Healing Process Manager Alert

Time: {timestamp}

{message}

---
This is an automated alert from the Self-Healing Process Manager.
"""
        msg.attach(MIMEText(body, 'plain'))
        
        # Send email
        if config['use_ssl']:
            server = smtplib.SMTP_SSL(config['smtp_server'], config['smtp_port'])
        else:
            server = smtplib.SMTP(config['smtp_server'], config['smtp_port'])
            server.starttls()
        
        if config['sender_password']:
            server.login(config['sender_email'], config['sender_password'])
        
        server.sendmail(config['sender_email'], config['receiver_email'], msg.as_string())
        server.quit()
        
        # Log email sent
        try:
            with open(LOG_FILE, 'a') as f:
                f.write(f"[{timestamp}] Email sent: {subject}\n")
        except Exception:
            pass
        
        return True
    except Exception as e:
        # Log error but don't break monitoring
        try:
            with open(LOG_FILE, 'a') as f:
                f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Email failed: {str(e)}\n")
        except Exception:
            pass
        return False

def send_crash_email(process_name: str, pid: int, reason: str = "") -> bool:
    """Send email for process crash"""
    subject = f"Process Crash: {process_name}"
    message = f"Process '{process_name}' (PID {pid}) has crashed.\n"
    if reason:
        message += f"Reason: {reason}\n"
    message += "The system will attempt to restart the process."
    return send_email(subject, message, 'crash')

def send_violation_email(process_name: str, pid: int, violation_type: str, value: float, limit: float) -> bool:
    """Send email for resource violation"""
    subject = f"Resource Violation: {process_name}"
    message = f"Process '{process_name}' (PID {pid}) has exceeded its {violation_type} limit.\n"
    message += f"Current: {value:.1f}\n"
    message += f"Limit: {limit}\n"
    message += "The process has been killed and will be restarted."
    return send_email(subject, message, 'violation')

def send_restart_failed_email(process_name: str, reason: str = "") -> bool:
    """Send email for restart failure"""
    subject = f"CRITICAL: Restart Failed - {process_name}"
    message = f"Process '{process_name}' could not be restarted.\n"
    if reason:
        message += f"Reason: {reason}\n"
    message += "Manual intervention may be required."
    return send_email(subject, message, 'general')

def send_cooldown_email(process_name: str, restart_count: int) -> bool:
    """Send email when cooldown is activated"""
    subject = f"Cooldown Activated: {process_name}"
    message = f"Process '{process_name}' has been restarted {restart_count} times in a short period.\n"
    message += "The system has entered cooldown mode and will not restart the process for 2 minutes.\n"
    message += "This prevents infinite restart loops."
    return send_email(subject, message, 'cooldown')

def send_anomaly_email(process_name: str, pid: int, anomaly_type: str, details: str = "") -> bool:
    """Send email for detected anomaly"""
    subject = f"Anomaly Detected: {process_name}"
    message = f"An anomaly has been detected for process '{process_name}' (PID {pid}).\n"
    message += f"Anomaly Type: {anomaly_type}\n"
    if details:
        message += f"Details: {details}\n"
    message += "Appropriate action has been taken."
    return send_email(subject, message, 'anomaly')

def send_zombie_email(zombie_count: int, details: str = "") -> bool:
    """Send email for zombie process detection"""
    subject = f"Zombie Processes Detected: {zombie_count}"
    message = f"{zombie_count} zombie process(es) detected on the system.\n"
    if details:
        message += f"Details: {details}\n"
    message += "The system will attempt to clean up these processes."
    return send_email(subject, message, 'anomaly')

if __name__ == '__main__':
    # Test email sending (if config exists)
    import sys
    if len(sys.argv) >= 3:
        subject = sys.argv[1]
        message = sys.argv[2]
        event_type = sys.argv[3] if len(sys.argv) > 3 else 'general'
        result = send_email(subject, message, event_type)
        print("Email sent successfully" if result else "Email failed or disabled")

