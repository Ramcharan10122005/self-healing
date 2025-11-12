#!/usr/bin/env python3
"""
Cooldown Manager for Self-Healing Process Manager
Prevents infinite restart loops by tracking restart frequency and implementing cooldown periods
"""
import os
import time
import json
import fcntl
from datetime import datetime

STATE_FILE = 'cooldown_state.json'
LOG_FILE = 'healing.log'

# Configuration
MAX_RESTARTS = 5  # Maximum restarts allowed
COOLDOWN_WINDOW_SECONDS = 60  # Time window to count restarts (1 minute)
COOLDOWN_DURATION_SECONDS = 120  # Cooldown duration (2 minutes)

# In-memory cache (backed by file)
_restart_state = {}
_state_file_lock = None

def _load_state() -> dict:
    """Load restart state from file"""
    global _restart_state
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                _restart_state = json.load(f)
                # Convert string timestamps back to floats
                for process_name in _restart_state:
                    if 'last_restart' in _restart_state[process_name]:
                        _restart_state[process_name]['last_restart'] = float(_restart_state[process_name]['last_restart'])
                    if 'cooldown_until' in _restart_state[process_name]:
                        _restart_state[process_name]['cooldown_until'] = float(_restart_state[process_name]['cooldown_until'])
        except Exception:
            _restart_state = {}
    else:
        _restart_state = {}
    return _restart_state

def _save_state() -> None:
    """Save restart state to file"""
    try:
        # Use file locking to prevent race conditions
        with open(STATE_FILE, 'w') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            json.dump(_restart_state, f, indent=2)
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except Exception:
        pass

def _cleanup_old_entries() -> None:
    """Remove old entries that are no longer relevant"""
    now = time.time()
    to_remove = []
    
    for process_name, state in _restart_state.items():
        # Remove entries older than cooldown window
        if 'last_restart' in state:
            if now - state['last_restart'] > COOLDOWN_WINDOW_SECONDS * 2:
                # Check if in cooldown
                if 'cooldown_until' in state and state['cooldown_until'] > now:
                    continue  # Still in cooldown, keep it
                to_remove.append(process_name)
    
    for process_name in to_remove:
        del _restart_state[process_name]

def track_restart(process_name: str) -> None:
    """Track a restart attempt for a process"""
    _load_state()
    now = time.time()
    
    if process_name not in _restart_state:
        _restart_state[process_name] = {
            'count': 0,
            'restarts': []
        }
    
    # Add restart timestamp
    _restart_state[process_name]['restarts'].append(now)
    _restart_state[process_name]['last_restart'] = now
    
    # Keep only restarts within the window
    cutoff = now - COOLDOWN_WINDOW_SECONDS
    _restart_state[process_name]['restarts'] = [
        r for r in _restart_state[process_name]['restarts'] 
        if r > cutoff
    ]
    
    # Update count
    _restart_state[process_name]['count'] = len(_restart_state[process_name]['restarts'])
    
    _cleanup_old_entries()
    _save_state()

def is_in_cooldown(process_name: str) -> bool:
    """
    Check if a process is currently in cooldown
    
    Returns:
        True if process is in cooldown, False otherwise
    """
    _load_state()
    now = time.time()
    
    if process_name not in _restart_state:
        return False
    
    state = _restart_state[process_name]
    
    # Check if currently in cooldown
    if 'cooldown_until' in state and state['cooldown_until'] > now:
        return True
    
    # Check if should enter cooldown
    if 'restarts' in state and len(state['restarts']) >= MAX_RESTARTS:
        # Enter cooldown
        state['cooldown_until'] = now + COOLDOWN_DURATION_SECONDS
        _save_state()
        
        # Log cooldown activation
        try:
            with open(LOG_FILE, 'a') as f:
                ts = datetime.now().strftime('[%Y-%m-%d %H:%M:%S]')
                f.write(f"{ts} Cooldown activated {process_name} ({len(state['restarts'])} restarts in {COOLDOWN_WINDOW_SECONDS}s)\n")
        except Exception:
            pass
        
        return True
    
    return False

def reset_cooldown(process_name: str) -> None:
    """Reset cooldown for a process (e.g., after successful stable run)"""
    _load_state()
    if process_name in _restart_state:
        # Reset count but keep last_restart for tracking
        _restart_state[process_name]['restarts'] = []
        _restart_state[process_name]['count'] = 0
        if 'cooldown_until' in _restart_state[process_name]:
            del _restart_state[process_name]['cooldown_until']
        _save_state()

def get_restart_count(process_name: str) -> int:
    """Get current restart count for a process"""
    _load_state()
    if process_name in _restart_state:
        return _restart_state[process_name].get('count', 0)
    return 0

def get_cooldown_status(process_name: str) -> dict:
    """Get detailed cooldown status for a process"""
    _load_state()
    now = time.time()
    
    if process_name not in _restart_state:
        return {
            'in_cooldown': False,
            'restart_count': 0,
            'cooldown_remaining': 0
        }
    
    state = _restart_state[process_name]
    in_cooldown = 'cooldown_until' in state and state['cooldown_until'] > now
    
    return {
        'in_cooldown': in_cooldown,
        'restart_count': state.get('count', 0),
        'cooldown_remaining': max(0, int(state.get('cooldown_until', 0) - now)) if in_cooldown else 0
    }

def get_all_cooldown_status() -> dict:
    """Get cooldown status for all processes"""
    _load_state()
    result = {}
    for process_name in _restart_state:
        result[process_name] = get_cooldown_status(process_name)
    return result

if __name__ == '__main__':
    # Test cooldown system
    import sys
    if len(sys.argv) >= 2:
        action = sys.argv[1]
        process_name = sys.argv[2] if len(sys.argv) > 2 else 'test_process'
        
        if action == 'track':
            track_restart(process_name)
            print(f"Tracked restart for {process_name}")
        elif action == 'check':
            in_cooldown = is_in_cooldown(process_name)
            status = get_cooldown_status(process_name)
            print(f"Process: {process_name}")
            print(f"In cooldown: {in_cooldown}")
            print(f"Status: {status}")
        elif action == 'reset':
            reset_cooldown(process_name)
            print(f"Reset cooldown for {process_name}")

