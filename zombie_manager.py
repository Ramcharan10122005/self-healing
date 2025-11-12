#!/usr/bin/env python3
"""
Zombie Process Manager for Self-Healing Process Manager
Detects, reports, and manages zombie processes
"""
import psutil
import os
import signal
import time
from datetime import datetime

LOG_FILE = 'healing.log'

def scan_zombies() -> list:
    """
    Scan all processes and return zombie information
    
    Returns:
        List of zombie process dictionaries
    """
    zombies = []
    try:
        for proc in psutil.process_iter(['pid', 'name', 'ppid', 'status', 'create_time']):
            try:
                if proc.info['status'] == psutil.STATUS_ZOMBIE:
                    pid = proc.info['pid']
                    ppid = proc.info['ppid']
                    
                    # Try to get parent name
                    parent_name = "unknown"
                    try:
                        parent = psutil.Process(ppid)
                        parent_name = parent.name()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                    
                    # Calculate zombie age
                    age = time.time() - proc.info['create_time'] if 'create_time' in proc.info else 0
                    
                    zombies.append({
                        'pid': pid,
                        'name': proc.info['name'],
                        'ppid': ppid,
                        'parent_name': parent_name,
                        'age_seconds': age,
                        'age_formatted': f"{int(age)}s"
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
            except Exception:
                continue
    except Exception:
        pass
    
    return zombies

def get_zombie_count() -> int:
    """Get count of zombie processes"""
    return len(scan_zombies())

def reap_zombie(pid: int) -> bool:
    """
    Attempt to reap a zombie by killing its parent (if safe)
    
    Args:
        pid: PID of zombie process
    
    Returns:
        True if successful, False otherwise
    """
    try:
        proc = psutil.Process(pid)
        if proc.status() != psutil.STATUS_ZOMBIE:
            return False
        
        ppid = proc.ppid()
        
        # Don't kill critical processes
        if ppid == 1:  # init process - will auto-reap
            return True
        
        # Check if parent is still alive
        try:
            parent = psutil.Process(ppid)
            parent_name = parent.name()
            
            # Don't kill system processes
            critical_processes = ['systemd', 'init', 'kernel']
            if any(crit in parent_name.lower() for crit in critical_processes):
                return False
            
            # Kill parent to force zombie reaping
            parent.terminate()
            time.sleep(0.5)
            if parent.is_running():
                parent.kill()
            
            # Log action
            try:
                with open(LOG_FILE, 'a') as f:
                    ts = datetime.now().strftime('[%Y-%m-%d %H:%M:%S]')
                    f.write(f"{ts} Reaped zombie {pid} by killing parent {ppid} ({parent_name})\n")
            except Exception:
                pass
            
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # Parent already dead, zombie should be reaped by init
            return True
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return False
    except Exception:
        return False
    
    return False

def cleanup_zombies() -> dict:
    """
    Clean up all zombie processes (attempt to reap)
    
    Returns:
        Dictionary with cleanup results
    """
    zombies = scan_zombies()
    results = {
        'total': len(zombies),
        'reaped': 0,
        'failed': 0,
        'skipped': 0
    }
    
    for zombie in zombies:
        pid = zombie['pid']
        ppid = zombie['ppid']
        
        # Skip if parent is init (will auto-reap)
        if ppid == 1:
            results['skipped'] += 1
            continue
        
        if reap_zombie(pid):
            results['reaped'] += 1
        else:
            results['failed'] += 1
    
    # Log summary
    try:
        with open(LOG_FILE, 'a') as f:
            ts = datetime.now().strftime('[%Y-%m-%d %H:%M:%S]')
            f.write(f"{ts} Zombie cleanup: {results['reaped']} reaped, {results['failed']} failed, {results['skipped']} skipped\n")
    except Exception:
        pass
    
    return results

def get_zombie_report() -> dict:
    """
    Generate comprehensive zombie report
    
    Returns:
        Dictionary with zombie statistics and details
    """
    zombies = scan_zombies()
    
    # Group by parent
    by_parent = {}
    for z in zombies:
        ppid = z['ppid']
        if ppid not in by_parent:
            by_parent[ppid] = []
        by_parent[ppid].append(z)
    
    # Find problematic parents
    problematic_parents = {k: v for k, v in by_parent.items() if len(v) > 3}
    
    # Calculate statistics
    total_age = sum(z['age_seconds'] for z in zombies)
    avg_age = total_age / len(zombies) if zombies else 0
    oldest_age = max((z['age_seconds'] for z in zombies), default=0)
    
    return {
        'total_zombies': len(zombies),
        'unique_parents': len(by_parent),
        'problematic_parents': len(problematic_parents),
        'average_age_seconds': avg_age,
        'oldest_age_seconds': oldest_age,
        'zombies': zombies,
        'by_parent': by_parent
    }

if __name__ == '__main__':
    # Test zombie management
    import sys
    if len(sys.argv) >= 2:
        action = sys.argv[1]
        
        if action == 'scan':
            zombies = scan_zombies()
            print(f"Found {len(zombies)} zombie process(es):")
            for z in zombies:
                print(f"  PID {z['pid']}: {z['name']} (parent: {z['ppid']} - {z['parent_name']}, age: {z['age_formatted']})")
        elif action == 'cleanup':
            results = cleanup_zombies()
            print(f"Cleanup results: {results}")
        elif action == 'report':
            report = get_zombie_report()
            print(f"Zombie Report:")
            print(f"  Total zombies: {report['total_zombies']}")
            print(f"  Unique parents: {report['unique_parents']}")
            print(f"  Problematic parents: {report['problematic_parents']}")
            print(f"  Average age: {report['average_age_seconds']:.1f}s")
            print(f"  Oldest zombie: {report['oldest_age_seconds']:.1f}s")

