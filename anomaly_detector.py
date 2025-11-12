#!/usr/bin/env python3
"""
Anomaly Detection System for Self-Healing Process Manager
Detects unusual process behaviors: fork bombs, memory leaks, CPU spikes, zombies
"""
import psutil
import time
from collections import deque

# Configuration
FORK_BOMB_THRESHOLD = 50  # Maximum child processes before considering fork bomb
MEMORY_LEAK_SAMPLES = 5  # Number of samples to check for memory leak
CPU_SPIKE_MULTIPLIER = 3  # CPU spike is 3x average
CPU_SPIKE_MIN = 80  # Minimum CPU to consider a spike
MEMORY_HISTORY_SIZE = 10  # Keep last N memory readings
CPU_HISTORY_SIZE = 5  # Keep last N CPU readings

# Historical data storage
_memory_history = {}  # {pid: deque([mem1, mem2, ...])}
_cpu_history = {}  # {pid: deque([cpu1, cpu2, ...])}

def detect_zombie_processes(pid: int) -> dict | None:
    """
    Detect if a process is a zombie
    
    Returns:
        Anomaly dict if zombie detected, None otherwise
    """
    try:
        proc = psutil.Process(pid)
        if proc.status() == psutil.STATUS_ZOMBIE:
            return {
                'type': 'zombie',
                'severity': 'medium',
                'pid': pid,
                'name': proc.name(),
                'ppid': proc.ppid(),
                'action': 'kill_parent_or_reap',
                'message': f'Process {pid} is a zombie process'
            }
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        pass
    except Exception:
        pass
    return None

def detect_fork_bomb(pid: int) -> dict | None:
    """
    Detect if a process has too many child processes (possible fork bomb)
    
    Returns:
        Anomaly dict if fork bomb detected, None otherwise
    """
    try:
        proc = psutil.Process(pid)
        children = proc.children(recursive=True)
        child_count = len(children)
        
        if child_count > FORK_BOMB_THRESHOLD:
            return {
                'type': 'fork_bomb',
                'severity': 'critical',
                'pid': pid,
                'name': proc.name(),
                'child_count': child_count,
                'threshold': FORK_BOMB_THRESHOLD,
                'action': 'kill_immediately',
                'message': f'Process {pid} has {child_count} child processes (possible fork bomb)'
            }
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    except Exception:
        pass
    return None

def detect_memory_leak(pid: int) -> dict | None:
    """
    Detect if a process shows memory leak pattern (steady increase)
    
    Returns:
        Anomaly dict if memory leak detected, None otherwise
    """
    try:
        proc = psutil.Process(pid)
        current_mem = proc.memory_info().rss / (1024 * 1024)  # MB
        
        # Initialize history if needed
        if pid not in _memory_history:
            _memory_history[pid] = deque(maxlen=MEMORY_HISTORY_SIZE)
        
        _memory_history[pid].append(current_mem)
        
        # Need at least MEMORY_LEAK_SAMPLES to detect pattern
        if len(_memory_history[pid]) >= MEMORY_LEAK_SAMPLES:
            recent = list(_memory_history[pid])[-MEMORY_LEAK_SAMPLES:]
            
            # Check if continuously increasing
            is_increasing = all(recent[i] < recent[i+1] for i in range(len(recent)-1))
            
            if is_increasing:
                increase = recent[-1] - recent[0]
                increase_pct = (increase / recent[0]) * 100 if recent[0] > 0 else 0
                
                return {
                    'type': 'memory_leak',
                    'severity': 'high',
                    'pid': pid,
                    'name': proc.name(),
                    'current_memory_mb': current_mem,
                    'increase_mb': increase,
                    'increase_percent': increase_pct,
                    'action': 'restart',
                    'message': f'Process {pid} shows memory leak pattern ({increase:.1f}MB increase)'
                }
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        # Clean up history if process is gone
        if pid in _memory_history:
            del _memory_history[pid]
    except Exception:
        pass
    return None

def detect_cpu_spike(pid: int) -> dict | None:
    """
    Detect sudden CPU spike (3x average)
    
    Returns:
        Anomaly dict if CPU spike detected, None otherwise
    """
    try:
        proc = psutil.Process(pid)
        current_cpu = proc.cpu_percent(interval=0.1)
        
        # Initialize history if needed
        if pid not in _cpu_history:
            _cpu_history[pid] = deque(maxlen=CPU_HISTORY_SIZE)
        
        _cpu_history[pid].append(current_cpu)
        
        # Need at least 3 readings to detect spike
        if len(_cpu_history[pid]) >= 3:
            recent = list(_cpu_history[pid])
            avg = sum(recent[:-1]) / (len(recent) - 1)  # Average of previous readings
            
            # Check for spike: current > 3x average AND > minimum threshold
            if current_cpu > avg * CPU_SPIKE_MULTIPLIER and current_cpu > CPU_SPIKE_MIN:
                return {
                    'type': 'cpu_spike',
                    'severity': 'medium',
                    'pid': pid,
                    'name': proc.name(),
                    'current_cpu': current_cpu,
                    'average_cpu': avg,
                    'multiplier': current_cpu / avg if avg > 0 else 0,
                    'action': 'investigate_or_restart',
                    'message': f'Process {pid} shows sudden CPU spike ({current_cpu:.1f}% vs {avg:.1f}% avg)'
                }
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        # Clean up history if process is gone
        if pid in _cpu_history:
            del _cpu_history[pid]
    except Exception:
        pass
    return None

def detect_anomalies(pid: int, process_name: str = "") -> list:
    """
    Run all anomaly detection checks on a process
    
    Args:
        pid: Process ID to check
        process_name: Optional process name for logging
    
    Returns:
        List of detected anomalies (empty if none)
    """
    anomalies = []
    
    # Check for zombie
    zombie = detect_zombie_processes(pid)
    if zombie:
        anomalies.append(zombie)
    
    # Check for fork bomb
    fork_bomb = detect_fork_bomb(pid)
    if fork_bomb:
        anomalies.append(fork_bomb)
    
    # Check for memory leak
    memory_leak = detect_memory_leak(pid)
    if memory_leak:
        anomalies.append(memory_leak)
    
    # Check for CPU spike
    cpu_spike = detect_cpu_spike(pid)
    if cpu_spike:
        anomalies.append(cpu_spike)
    
    return anomalies

def cleanup_history(pid: int) -> None:
    """Clean up historical data for a process"""
    if pid in _memory_history:
        del _memory_history[pid]
    if pid in _cpu_history:
        del _cpu_history[pid]

def get_anomaly_summary() -> dict:
    """Get summary of all detected anomalies"""
    return {
        'memory_tracked': len(_memory_history),
        'cpu_tracked': len(_cpu_history)
    }

if __name__ == '__main__':
    # Test anomaly detection
    import sys
    if len(sys.argv) >= 2:
        pid = int(sys.argv[1])
        anomalies = detect_anomalies(pid)
        if anomalies:
            print(f"Detected {len(anomalies)} anomaly(ies) for PID {pid}:")
            for anomaly in anomalies:
                print(f"  - {anomaly['type']}: {anomaly['message']}")
        else:
            print(f"No anomalies detected for PID {pid}")

