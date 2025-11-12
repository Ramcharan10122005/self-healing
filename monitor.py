#!/usr/bin/env python3
import psutil
import time
import os
import signal
import subprocess
from datetime import datetime

# Import new feature modules
try:
    from email_notifier import send_violation_email, send_restart_failed_email, send_anomaly_email, send_zombie_email
except ImportError:
    # Fallback if modules not available
    def send_violation_email(*args, **kwargs): return False
    def send_restart_failed_email(*args, **kwargs): return False
    def send_anomaly_email(*args, **kwargs): return False
    def send_zombie_email(*args, **kwargs): return False

try:
    from cooldown_manager import is_in_cooldown, track_restart, reset_cooldown, get_cooldown_status
except ImportError:
    def is_in_cooldown(*args, **kwargs): return False
    def track_restart(*args, **kwargs): pass
    def reset_cooldown(*args, **kwargs): pass
    def get_cooldown_status(*args, **kwargs): return {'in_cooldown': False}

try:
    from anomaly_detector import detect_anomalies, cleanup_history
except ImportError:
    def detect_anomalies(*args, **kwargs): return []
    def cleanup_history(*args, **kwargs): pass

try:
    from zombie_manager import scan_zombies, get_zombie_count, cleanup_zombies
except ImportError:
    def scan_zombies(*args, **kwargs): return []
    def get_zombie_count(*args, **kwargs): return 0
    def cleanup_zombies(*args, **kwargs): return {}

PROCESS_LIST_FILE = 'process_list.txt'
LOG_FILE = 'healing.log'
ZOMBIE_CHECK_INTERVAL = 300  # Check for zombies every 5 minutes
last_zombie_check = 0


def log_action(action: str, process_name: str, pid: int | None, reason: str) -> None:
    try:
        ts = datetime.now().strftime('[%Y-%m-%d %H:%M]')
        with open(LOG_FILE, 'a') as f:
            f.write(f"{ts} {action} {process_name} (PID {pid if pid else 0}) {reason}\n")
    except Exception:
        pass


def read_process_list() -> dict:
    processes = {}
    if not os.path.exists(PROCESS_LIST_FILE):
        return processes
    with open(PROCESS_LIST_FILE, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if len(parts) >= 3:
                # Last two parts are cpu_limit and mem_limit
                # Everything before that is the process name/command
                try:
                    cpu_limit = int(parts[-2])
                    mem_limit = int(parts[-1])
                    name = ' '.join(parts[:-2])  # Everything except last two
                    # Extract just the executable name (first word) for process matching
                    process_name = parts[0]
                    processes[process_name] = {'cpu': cpu_limit, 'mem': mem_limit, 'full_cmd': name}
                except (ValueError, IndexError):
                    # Skip invalid lines
                    continue
    return processes


def find_pid_by_name(name: str) -> int | None:
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'status']):
        try:
            # Skip zombies and stopped processes
            if proc.info.get('status') in ['zombie', 'stopped']:
                continue
            if proc.info['name'] == name or (proc.info['cmdline'] and name in ' '.join(proc.info['cmdline'])):
                # Verify process is actually responsive
                pid = proc.info['pid']
                p = psutil.Process(pid)
                # Try to get status to ensure it's not a zombie
                status = p.status()
                if status != psutil.STATUS_ZOMBIE and status != psutil.STATUS_STOPPED:
                    return pid
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
        except Exception:
            continue
    return None


def get_usage(pid: int) -> tuple[float, float] | tuple[None, None]:
    try:
        p = psutil.Process(pid)
        cpu = p.cpu_percent(interval=0.5)  # short sample
        mem_mb = p.memory_info().rss / (1024 * 1024)
        return cpu, mem_mb
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return None, None


def kill_process(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
        time.sleep(1)
        try:
            os.kill(pid, 0)
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
    except OSError:
        pass


def find_active_display() -> str:
    """Find active DISPLAY by checking running X processes"""
    # First check environment
    if 'DISPLAY' in os.environ and os.environ['DISPLAY']:
        return os.environ['DISPLAY']
    
    # Try to find from /tmp/.X11-unix
    try:
        result = subprocess.run(['ls', '/tmp/.X11-unix/'], 
                              stdout=subprocess.PIPE, 
                              stderr=subprocess.DEVNULL, 
                              timeout=1)
        if result.returncode == 0:
            for line in result.stdout.decode().split('\n'):
                if line.startswith('X'):
                    disp_num = line[1:]  # Remove 'X' prefix
                    if disp_num.isdigit() or '.' in disp_num:
                        return f":{disp_num}"
    except Exception:
        pass
    
    # Try to read from session file
    uid = os.getuid()
    session_file = f"/run/user/{uid}/.x11_display"
    if os.path.exists(session_file):
        try:
            with open(session_file, 'r') as f:
                disp = f.read().strip()
                if disp:
                    return disp
        except Exception:
            pass
    
    # Default fallback
    return ':0'

def get_gui_env_from_process() -> dict:
    """Get GUI environment from running user processes"""
    env = {}
    try:
        uid = os.getuid()
        # Get environment from any GUI process
        result = subprocess.run(['ps', 'e', '-u', str(uid)], 
                              stdout=subprocess.PIPE, 
                              stderr=subprocess.DEVNULL, 
                              timeout=2)
        if result.returncode == 0:
            for line in result.stdout.decode().split('\n'):
                if 'DISPLAY=' in line or 'XAUTHORITY=' in line or 'DBUS_SESSION_BUS_ADDRESS=' in line:
                    # Parse environment variables
                    parts = line.split()
                    for part in parts:
                        if '=' in part:
                            key, val = part.split('=', 1)
                            if key in ['DISPLAY', 'XAUTHORITY', 'DBUS_SESSION_BUS_ADDRESS', 'XDG_RUNTIME_DIR']:
                                env[key] = val
                    if env:
                        break
    except Exception:
        pass
    return env

def start_process(name: str) -> int | None:
    try:
        # Ensure GUI apps can open windows by providing session env
        env = os.environ.copy()
        
        # First try to get GUI env from running processes
        gui_env = get_gui_env_from_process()
        env.update(gui_env)
        
        # Then set defaults/fallbacks
        if 'DISPLAY' not in env or not env['DISPLAY']:
            env['DISPLAY'] = find_active_display()
        if 'DBUS_SESSION_BUS_ADDRESS' not in env:
            env['DBUS_SESSION_BUS_ADDRESS'] = f"unix:path=/run/user/{os.getuid()}/bus"
        # Add more GUI-related fallbacks for Xorg/Wayland environments
        env.setdefault('XDG_RUNTIME_DIR', f"/run/user/{os.getuid()}")
        if 'WAYLAND_DISPLAY' not in env and os.path.exists(f"{env['XDG_RUNTIME_DIR']}/wayland-0"):
            env['WAYLAND_DISPLAY'] = 'wayland-0'
        if 'XAUTHORITY' not in env:
            home = os.path.expanduser('~')
            xa = os.path.join(home, '.Xauthority')
            if os.path.exists(xa):
                env['XAUTHORITY'] = xa
        
        # Use start_new_session=True to detach from terminal but keep GUI access
        proc = subprocess.Popen([name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, 
                               env=env, start_new_session=True)
        return proc.pid
    except Exception:
        # Fallback: try shell invocation so PATH and desktop launchers can help
        try:
            env = os.environ.copy()
            env['DISPLAY'] = find_active_display()
            if 'DBUS_SESSION_BUS_ADDRESS' not in env:
                env['DBUS_SESSION_BUS_ADDRESS'] = f"unix:path=/run/user/{os.getuid()}/bus"
            env.setdefault('XDG_RUNTIME_DIR', f"/run/user/{os.getuid()}")
            if 'WAYLAND_DISPLAY' not in env and os.path.exists(f"{env['XDG_RUNTIME_DIR']}/wayland-0"):
                env['WAYLAND_DISPLAY'] = 'wayland-0'
            if 'XAUTHORITY' not in env:
                home = os.path.expanduser('~')
                xa = os.path.join(home, '.Xauthority')
                if os.path.exists(xa):
                    env['XAUTHORITY'] = xa
            proc = subprocess.Popen(name, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, 
                                  env=env, start_new_session=True)
            return proc.pid
        except Exception:
            # Last resort: try launching via desktop entry (gtk-launch/gio)
            try:
                desktop_id = f"{name}.desktop"
                # Try gtk-launch if available
                if subprocess.call(['which', 'gtk-launch'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
                    proc = subprocess.Popen(['gtk-launch', desktop_id], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
                    return proc.pid
                # Try gio launch by locating a desktop file
                applications_dirs = ['/usr/share/applications', os.path.expanduser('~/.local/share/applications')]
                desktop_path = None
                for d in applications_dirs:
                    cand = os.path.join(d, desktop_id)
                    if os.path.exists(cand):
                        desktop_path = cand
                        break
                if desktop_path:
                    proc = subprocess.Popen(['gio', 'launch', desktop_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
                    return proc.pid
            except Exception:
                pass
            log_action('Start failed', name, 0, 'unable to exec command')
            return None


def main() -> None:
    global last_zombie_check
    log_action('Resource Monitor', 'monitor.py', os.getpid(), 'started')
    
    while True:
        processes = read_process_list()
        
        # Periodic zombie check
        current_time = time.time()
        if current_time - last_zombie_check >= ZOMBIE_CHECK_INTERVAL:
            try:
                zombie_count = get_zombie_count()
                if zombie_count > 0:
                    zombies = scan_zombies()
                    log_action('Zombie Alert', 'system', 0, f'{zombie_count} zombie process(es) detected')
                    send_zombie_email(zombie_count, f"Found {zombie_count} zombie processes")
                    # Attempt cleanup
                    cleanup_results = cleanup_zombies()
                    if cleanup_results.get('reaped', 0) > 0:
                        log_action('Zombie Cleanup', 'system', 0, f"Reaped {cleanup_results['reaped']} zombie(s)")
            except Exception:
                pass
            last_zombie_check = current_time
        
        for name, limits in processes.items():
            pid = find_pid_by_name(name)
            if pid is None:
                # Process not running - don't start it here
                # C monitor handles all process starting/restarting
                # Python monitor only handles resource limit monitoring
                continue
            
            # Process exists - run anomaly detection first
            try:
                anomalies = detect_anomalies(pid, name)
                if anomalies:
                    # Handle anomalies
                    for anomaly in anomalies:
                        log_action('Anomaly', name, pid, f"{anomaly['type']}: {anomaly['message']}")
                        send_anomaly_email(name, pid, anomaly['type'], anomaly.get('message', ''))
                        
                        # Take action based on anomaly type
                        if anomaly['type'] == 'fork_bomb':
                            # Critical - kill immediately
                            log_action('Killed', name, pid, f"fork bomb detected ({anomaly.get('child_count', 0)} children)")
                            kill_process(pid)
                            cleanup_history(pid)
                            continue  # Skip resource checks
                        elif anomaly['type'] == 'memory_leak':
                            # High severity - restart
                            log_action('Killed', name, pid, f"memory leak detected ({anomaly.get('increase_mb', 0):.1f}MB increase)")
                            kill_process(pid)
                            cleanup_history(pid)
                            # Will restart below (if not in cooldown)
                        elif anomaly['type'] == 'zombie':
                            # Medium - try to reap
                            log_action('Zombie', name, pid, 'zombie process detected')
                            cleanup_history(pid)
                            continue  # Skip resource checks
                        elif anomaly['type'] == 'cpu_spike':
                            # Medium - log and continue monitoring
                            log_action('CPU Spike', name, pid, f"CPU spike: {anomaly.get('current_cpu', 0):.1f}%")
                            # Continue to resource checks
            except Exception:
                pass  # Don't break monitoring if anomaly detection fails
            
            # Process exists - check resource usage
            # Python monitor only handles resource limit monitoring
            # C monitor handles crash detection and restarting
            cpu, mem = get_usage(pid)
            if cpu is None or mem is None:
                # Process doesn't exist or is inaccessible - skip (C monitor will handle it)
                cleanup_history(pid)  # Clean up tracking data
                continue
            
            # Check resource limits
            if cpu > limits['cpu']:
                # Check cooldown before restarting
                if is_in_cooldown(name):
                    log_action('Cooldown', name, pid, 'too many restarts, cooling down')
                    continue
                
                log_action('Killed', name, pid, f'due to high CPU usage ({cpu:.1f}% > {limits["cpu"]}%)')
                kill_process(pid)
                log_action('Stopped', name, pid, 'terminated by monitor')
                
                # Track restart attempt
                track_restart(name)
                
                # Check cooldown again (might have been activated by track_restart)
                if is_in_cooldown(name):
                    log_action('Cooldown', name, 0, 'cooldown activated after restart tracking')
                    send_restart_failed_email(name, 'Process entered cooldown due to excessive restarts')
                    continue
                
                new_pid = start_process(name)
                if new_pid:
                    log_action('Restarted', name, new_pid, 'after high CPU usage')
                    send_violation_email(name, pid, 'CPU', cpu, limits['cpu'])
                else:
                    log_action('Restart failed', name, 0, 'unable to restart after CPU kill')
                    send_restart_failed_email(name, 'Unable to restart after CPU violation')
            elif mem > limits['mem']:
                # Check cooldown before restarting
                if is_in_cooldown(name):
                    log_action('Cooldown', name, pid, 'too many restarts, cooling down')
                    continue
                
                log_action('Killed', name, pid, f'due to high memory usage ({mem:.1f}MB > {limits["mem"]}MB)')
                kill_process(pid)
                log_action('Stopped', name, pid, 'terminated by monitor')
                
                # Track restart attempt
                track_restart(name)
                
                # Check cooldown again (might have been activated by track_restart)
                if is_in_cooldown(name):
                    log_action('Cooldown', name, 0, 'cooldown activated after restart tracking')
                    send_restart_failed_email(name, 'Process entered cooldown due to excessive restarts')
                    continue
                
                new_pid = start_process(name)
                if new_pid:
                    log_action('Restarted', name, new_pid, 'after high memory usage')
                    send_violation_email(name, pid, 'Memory', mem, limits['mem'])
                else:
                    log_action('Restart failed', name, 0, 'unable to restart after memory kill')
                    send_restart_failed_email(name, 'Unable to restart after memory violation')
            else:
                # Process is healthy - reset cooldown if it was in cooldown
                # (This allows recovery after cooldown period)
                status = get_cooldown_status(name)
                if status.get('in_cooldown', False):
                    # Check if cooldown period has expired
                    if status.get('cooldown_remaining', 0) <= 0:
                        reset_cooldown(name)
                        log_action('Cooldown Reset', name, pid, 'process stable, cooldown reset')
        
        time.sleep(5)


if __name__ == '__main__':
    main()


