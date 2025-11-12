#!/usr/bin/env python3
"""
Helper script for C monitor to call Python features
Allows C monitor to use email notifications and cooldown system
"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    if len(sys.argv) < 2:
        return 1
    
    action = sys.argv[1]
    
    if action == 'email_crash':
        # Usage: python3 c_monitor_helper.py email_crash <process_name> <pid> [reason]
        if len(sys.argv) < 4:
            return 1
        from email_notifier import send_crash_email
        process_name = sys.argv[2]
        pid = int(sys.argv[3])
        reason = sys.argv[4] if len(sys.argv) > 4 else ""
        send_crash_email(process_name, pid, reason)
        return 0
    
    elif action == 'email_restart_failed':
        # Usage: python3 c_monitor_helper.py email_restart_failed <process_name> [reason]
        if len(sys.argv) < 3:
            return 1
        from email_notifier import send_restart_failed_email
        process_name = sys.argv[2]
        reason = sys.argv[3] if len(sys.argv) > 3 else ""
        send_restart_failed_email(process_name, reason)
        return 0
    
    elif action == 'check_cooldown':
        # Usage: python3 c_monitor_helper.py check_cooldown <process_name>
        # Returns: 0 if not in cooldown, 1 if in cooldown
        if len(sys.argv) < 3:
            return 0  # Default to not in cooldown
        from cooldown_manager import is_in_cooldown
        process_name = sys.argv[2]
        return 1 if is_in_cooldown(process_name) else 0
    
    elif action == 'track_restart':
        # Usage: python3 c_monitor_helper.py track_restart <process_name>
        if len(sys.argv) < 3:
            return 1
        from cooldown_manager import track_restart
        process_name = sys.argv[2]
        track_restart(process_name)
        return 0
    
    elif action == 'check_cooldown_after_track':
        # Usage: python3 c_monitor_helper.py check_cooldown_after_track <process_name>
        # Tracks restart and checks if cooldown was activated
        if len(sys.argv) < 3:
            return 0
        from cooldown_manager import track_restart, is_in_cooldown
        process_name = sys.argv[2]
        track_restart(process_name)
        return 1 if is_in_cooldown(process_name) else 0
    
    return 1

if __name__ == '__main__':
    sys.exit(main())

