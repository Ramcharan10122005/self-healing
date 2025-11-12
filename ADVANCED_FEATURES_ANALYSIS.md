# Advanced Features Analysis - Email, Cooldown, & Anomaly Detection

## 📊 Current Project Architecture Overview

### Existing Components:
1. **C Monitor (`c_monitor.c`)** - Daemon for crash detection and restart
2. **Python Monitor (`monitor.py`)** - Resource limit monitoring (CPU/Memory)
3. **GUI (`gui.py`)** - Tkinter interface for process management
4. **Shell Script (`heal.sh`)** - Orchestration script
5. **Logging System** - Centralized `healing.log` file

### Current Event Flow:
```
Process Event → Detection → Log Action → Restart (if needed)
```

---

## ✅ Feature 1: Email Notification System

### 🎯 How It Fits With Your Project

#### **Current State:**
- Events are logged to `healing.log` file
- GUI displays log entries in real-time
- No external notification mechanism exists

#### **Integration Points:**

**A. Where to Add Email Notifications:**

1. **In `monitor.py` (Python Monitor)** - Resource violations:
   ```python
   # Current: Line 246-254 (CPU violation)
   if cpu > limits['cpu']:
       log_action('Killed', name, pid, f'due to high CPU usage...')
       kill_process(pid)
       # ADD: send_email("CPU Violation", f"{name} exceeded CPU limit")
       new_pid = start_process(name)
   
   # Current: Line 255-263 (Memory violation)
   elif mem > limits['mem']:
       log_action('Killed', name, pid, f'due to high memory usage...')
       kill_process(pid)
       # ADD: send_email("Memory Violation", f"{name} exceeded memory limit")
       new_pid = start_process(name)
   ```

2. **In `c_monitor.c` (C Monitor)** - Crash detection:
   ```c
   // Current: Line 608 (Crash detected)
   log_action("Detected crash", processes[i].name, processes[i].pid, "");
   // ADD: Call Python script or C function to send email
   
   // Current: Line 613 (Restart successful)
   log_action("Restarted", processes[i].name, processes[i].pid, "after crash signal");
   // ADD: send_email("Process Restarted", f"{name} was restarted after crash")
   ```

3. **In `c_monitor.c`** - Restart failures:
   ```c
   // Current: Line 615 (Restart failed)
   log_action("Restart failed", processes[i].name, 0, "unable to start process");
   // ADD: send_email("CRITICAL: Restart Failed", f"{name} could not be restarted")
   ```

#### **Architecture Decision:**

**Option A: Python-Based Email (Recommended)**
- Create `email_notifier.py` module
- Both C and Python monitors call this module
- C monitor calls Python script via `system()` or `popen()`
- **Pros:** Easy to implement, Python has excellent email libraries
- **Cons:** Requires Python dependency for C monitor

**Option B: C-Based Email (Complex)**
- Implement SMTP in C using libcurl or similar
- **Pros:** No Python dependency
- **Cons:** More complex, less maintainable

**Option C: Hybrid Approach (Best)**
- Python module handles all email logic
- C monitor calls: `python3 email_notifier.py "subject" "message"`
- Python monitor imports and calls directly
- **Pros:** Single source of truth, flexible

#### **What Needs to Be Done:**

1. **Create `email_notifier.py`:**
   ```python
   # New file: email_notifier.py
   - send_email(subject, message) function
   - Configuration loading (from config file or environment)
   - Error handling (network failures, invalid credentials)
   - Rate limiting (don't spam emails)
   ```

2. **Create `email_config.txt` (or use environment variables):**
   ```
   smtp_server=smtp.gmail.com
   smtp_port=465
   sender_email=yourmail@gmail.com
   sender_password=your_app_password
   receiver_email=admin@gmail.com
   enable_email=true
   ```

3. **Modify `monitor.py`:**
   - Import email_notifier
   - Add email calls after critical events
   - Add try/except to handle email failures gracefully

4. **Modify `c_monitor.c`:**
   - Add function to call Python email script
   - Integrate at crash detection points
   - Handle email script failures silently (don't break monitoring)

5. **Update `heal.sh`:**
   - Add email configuration check on startup
   - Optional: Test email sending

#### **Integration Flow:**
```
Event Detected → Log Action → Send Email (async/non-blocking) → Continue Monitoring
```

---

## ✅ Feature 2: Restart Limit + Cooldown System

### 🎯 How It Fits With Your Project

#### **Current State:**
- Processes restart immediately on crash/violation
- No tracking of restart frequency
- Risk of infinite restart loops

#### **Problem Scenario:**
```
Process crashes → Restart → Crashes again → Restart → Crashes → ...
(Every 2-3 seconds, infinite loop)
```

#### **Integration Points:**

**A. Where to Add Cooldown Logic:**

1. **In `c_monitor.c` - Crash Restart Logic:**
   ```c
   // Current: Line 604-616 (Crash restart)
   if (should_restart) {
       // ADD: Check cooldown before restarting
       if (is_in_cooldown(processes[i].name)) {
           log_action("Cooldown", processes[i].name, 0, "too many failures, cooling down");
           continue; // Skip restart
       }
       
       // Increment restart count
       increment_restart_count(processes[i].name);
       
       // Restart process
       processes[i].pid = start_process(processes[i].name);
   }
   ```

2. **In `monitor.py` - Resource Violation Restart:**
   ```python
   # Current: Line 246-254 (CPU violation restart)
   if cpu > limits['cpu']:
       # ADD: Check cooldown
       if is_in_cooldown(name):
           log_action('Cooldown', name, pid, 'too many restarts, cooling down')
           continue
       
       # Increment restart count
       increment_restart_count(name)
       
       kill_process(pid)
       new_pid = start_process(name)
   ```

#### **Data Structure Needed:**

**Option A: In-Memory Dictionary (Python)**
```python
# In monitor.py
restart_tracking = {
    'process_name': {
        'count': 0,
        'last_restart': timestamp,
        'cooldown_until': timestamp
    }
}
```

**Option B: Persistent File (Both C and Python)**
```c
// File: restart_state.txt
// Format: process_name restart_count last_restart_timestamp cooldown_until
```

**Option C: Shared State File (Recommended)**
- Both monitors read/write to same file
- Use file locking to prevent race conditions
- Format: JSON or simple text

#### **What Needs to Be Done:**

1. **Create `cooldown_manager.py`:**
   ```python
   # New file: cooldown_manager.py
   - track_restart(process_name) function
   - is_in_cooldown(process_name) function
   - reset_cooldown(process_name) function
   - load_state() / save_state() for persistence
   ```

2. **Modify `monitor.py`:**
   - Import cooldown_manager
   - Check cooldown before every restart
   - Track restart counts
   - Send email when cooldown activated

3. **Modify `c_monitor.c`:**
   - Add restart tracking structure
   - Check cooldown before restart
   - Persist state to file (or call Python script)

4. **Configuration:**
   ```python
   # In config or constants
   MAX_RESTARTS = 5
   COOLDOWN_WINDOW_SECONDS = 60  # 1 minute
   COOLDOWN_DURATION_SECONDS = 120  # 2 minutes cooldown
   ```

#### **Cooldown Logic Flow:**
```
Restart Attempted
    │
    ├─ Check: restart_count > MAX_RESTARTS in last COOLDOWN_WINDOW?
    │   │
    │   ├─ YES → Enter cooldown
    │   │   ├─ Log: "Cooldown activated"
    │   │   ├─ Send email alert
    │   │   ├─ Set cooldown_until = now + COOLDOWN_DURATION
    │   │   └─ Skip restart
    │   │
    │   └─ NO → Allow restart
    │       ├─ Increment restart_count
    │       ├─ Update last_restart timestamp
    │       └─ Proceed with restart
    │
    └─ After COOLDOWN_DURATION expires:
        ├─ Reset restart_count
        └─ Allow restarts again
```

#### **Edge Cases to Handle:**
- Process restarts successfully after cooldown → reset counter
- System reboot → reset all counters
- Multiple monitors running → use file locking
- Clock changes → use relative timestamps

---

## ✅ Feature 3: Anomaly Detection (Rule-Based)

### 🎯 How It Fits With Your Project

#### **Current State:**
- Simple threshold checking (CPU > limit, Memory > limit)
- No pattern detection
- No advanced behavior analysis

#### **Integration Points:**

**A. Where to Add Anomaly Detection:**

1. **In `monitor.py` - Main Loop:**
   ```python
   # Current: Line 225-264 (Main monitoring loop)
   def main():
       while True:
           processes = read_process_list()
           for name, limits in processes.items():
               pid = find_pid_by_name(name)
               if pid:
                   # ADD: Anomaly detection before resource checks
                   anomalies = detect_anomalies(pid, name)
                   if anomalies:
                       handle_anomalies(pid, name, anomalies)
                       continue  # Skip normal resource checks
                   
                   # Existing resource checks...
   ```

2. **New Module: `anomaly_detector.py`:**
   ```python
   # New file: anomaly_detector.py
   - detect_anomalies(pid, name) → returns list of anomalies
   - detect_zombie_processes()
   - detect_fork_bomb(pid)
   - detect_memory_leak(pid, history)
   - detect_rapid_crashes(name)
   ```

#### **Anomaly Types & Implementation:**

**1. Zombie Process Detection:**
```python
def detect_zombies(pid):
    proc = psutil.Process(pid)
    if proc.status() == psutil.STATUS_ZOMBIE:
        return {
            'type': 'zombie',
            'severity': 'medium',
            'action': 'kill_parent_or_reap'
        }
```

**2. Fork Bomb Detection:**
```python
def detect_fork_bomb(pid):
    proc = psutil.Process(pid)
    children = proc.children(recursive=True)
    if len(children) > 50:  # Threshold
        return {
            'type': 'fork_bomb',
            'severity': 'critical',
            'child_count': len(children),
            'action': 'kill_immediately'
        }
```

**3. Memory Leak Detection:**
```python
# Need to track memory history
memory_history = {}  # {pid: [mem1, mem2, mem3, ...]}

def detect_memory_leak(pid):
    if pid not in memory_history:
        memory_history[pid] = []
    
    current_mem = get_memory_usage(pid)
    memory_history[pid].append(current_mem)
    
    # Keep last 10 readings
    if len(memory_history[pid]) > 10:
        memory_history[pid] = memory_history[pid][-10:]
    
    # Check if continuously increasing
    if len(memory_history[pid]) >= 5:
        recent = memory_history[pid][-5:]
        if all(recent[i] < recent[i+1] for i in range(len(recent)-1)):
            return {
                'type': 'memory_leak',
                'severity': 'high',
                'trend': 'increasing',
                'action': 'restart'
            }
```

**4. Rapid Crash Detection:**
```python
# Integrate with cooldown system
def detect_rapid_crashes(name):
    # Use restart tracking from cooldown_manager
    if is_in_cooldown(name):
        return {
            'type': 'rapid_crashes',
            'severity': 'critical',
            'action': 'cooldown_already_active'
        }
```

**5. Sudden CPU Spike Detection:**
```python
cpu_history = {}  # Track CPU over time

def detect_cpu_spike(pid):
    current_cpu = get_cpu_usage(pid)
    if pid not in cpu_history:
        cpu_history[pid] = []
    
    cpu_history[pid].append(current_cpu)
    if len(cpu_history[pid]) > 5:
        cpu_history[pid] = cpu_history[pid][-5:]
    
    # Check for sudden spike (e.g., 3x average)
    if len(cpu_history[pid]) >= 3:
        avg = sum(cpu_history[pid][:-1]) / (len(cpu_history[pid]) - 1)
        if current_cpu > avg * 3 and current_cpu > 80:
            return {
                'type': 'cpu_spike',
                'severity': 'medium',
                'current': current_cpu,
                'average': avg,
                'action': 'investigate_or_restart'
            }
```

#### **What Needs to Be Done:**

1. **Create `anomaly_detector.py`:**
   - Implement all detection functions
   - Return structured anomaly objects
   - Track historical data (memory, CPU trends)

2. **Create `anomaly_handler.py`:**
   - Handle each anomaly type
   - Execute appropriate actions (kill, restart, log, email)
   - Integrate with existing systems

3. **Modify `monitor.py`:**
   - Import anomaly detector
   - Run detection before resource checks
   - Handle anomalies appropriately

4. **Add Configuration:**
   ```python
   ANOMALY_CONFIG = {
       'fork_bomb_threshold': 50,
       'memory_leak_samples': 5,
       'cpu_spike_multiplier': 3,
       'enable_anomaly_detection': True
   }
   ```

5. **Update GUI:**
   - Add "Anomalies" tab or section
   - Display detected anomalies
   - Show anomaly history

#### **Anomaly Detection Flow:**
```
Monitor Loop
    │
    ├─ For each process:
    │   │
    │   ├─ Run Anomaly Detection
    │   │   ├─ Check for zombies
    │   │   ├─ Check for fork bomb
    │   │   ├─ Check for memory leak
    │   │   ├─ Check for CPU spike
    │   │   └─ Check for rapid crashes
    │   │
    │   ├─ If anomalies found:
    │   │   ├─ Log anomaly
    │   │   ├─ Send email alert
    │   │   ├─ Execute action (kill/restart/investigate)
    │   │   └─ Skip normal resource checks
    │   │
    │   └─ If no anomalies:
    │       └─ Continue with normal resource limit checks
```

---

## 🏗️ Overall Architecture Integration

### **How All Three Features Work Together:**

```
┌─────────────────────────────────────────────────────────┐
│                    Monitoring Loop                       │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │   Anomaly Detection           │
        │   (Feature 3)                 │
        └───────────────────────────────┘
                        │
        ┌───────────────┴───────────────┐
        │                               │
        ▼                               ▼
    Anomaly Found                  No Anomaly
        │                               │
        ▼                               ▼
    Handle Anomaly              Resource Check
    (kill/restart)              (CPU/Memory)
        │                               │
        └───────────────┬───────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │   Cooldown Check               │
        │   (Feature 2)                  │
        └───────────────────────────────┘
                        │
        ┌───────────────┴───────────────┐
        │                               │
        ▼                               ▼
    In Cooldown                    Not in Cooldown
        │                               │
        ▼                               ▼
    Skip Restart                  Proceed Restart
    Send Email                    Track Restart
        │                           Send Email
        │                               │
        └───────────────┬───────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │   Email Notification           │
        │   (Feature 1)                  │
        └───────────────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │   Log Action                  │
        │   (Existing)                  │
        └───────────────────────────────┘
```

---

## 📋 Implementation Checklist

### **Phase 1: Email Notifications**
- [ ] Create `email_notifier.py` module
- [ ] Create `email_config.txt` configuration file
- [ ] Add email calls to `monitor.py` (CPU/Memory violations)
- [ ] Add email calls to `c_monitor.c` (crashes, restart failures)
- [ ] Test email sending with various events
- [ ] Add error handling (network failures, invalid config)
- [ ] Add rate limiting (prevent email spam)

### **Phase 2: Cooldown System**
- [ ] Create `cooldown_manager.py` module
- [ ] Design restart state storage (file-based)
- [ ] Add cooldown checks to `monitor.py`
- [ ] Add cooldown checks to `c_monitor.c`
- [ ] Integrate with email system (cooldown alerts)
- [ ] Test infinite restart loop prevention
- [ ] Add configuration for thresholds

### **Phase 3: Anomaly Detection**
- [ ] Create `anomaly_detector.py` module
- [ ] Implement zombie detection
- [ ] Implement fork bomb detection
- [ ] Implement memory leak detection
- [ ] Implement CPU spike detection
- [ ] Implement rapid crash detection
- [ ] Create `anomaly_handler.py` for actions
- [ ] Integrate with monitoring loop
- [ ] Add anomaly display to GUI
- [ ] Test each anomaly type

### **Phase 4: Integration & Testing**
- [ ] Test all features together
- [ ] Verify email notifications work
- [ ] Verify cooldown prevents loops
- [ ] Verify anomaly detection catches issues
- [ ] Update documentation
- [ ] Update GUI with new features
- [ ] Create demo scenarios

---

## 🎯 Presentation Points

### **Slide 1: Advanced Features Overview**
- ✅ Email notifications for all critical events
- ✅ Restart limit prevents infinite loops
- ✅ Cooldown mechanism for unstable processes
- ✅ Rule-based anomaly detection
- ✅ Production-ready reliability features

### **Slide 2: Email Notification System**
- Real-time alerts for:
  - Process crashes
  - Resource violations (CPU/Memory)
  - Restart failures
  - Anomaly detection
- Configurable SMTP settings
- Rate limiting to prevent spam

### **Slide 3: Cooldown & Restart Limits**
- Prevents infinite restart loops
- Configurable thresholds (5 restarts/minute)
- Automatic cooldown activation
- Email alerts when cooldown activated
- Automatic recovery after cooldown period

### **Slide 4: Anomaly Detection**
- Detects dangerous process behaviors:
  - Fork bombs (too many child processes)
  - Memory leaks (steady memory increase)
  - Zombie processes
  - Sudden CPU spikes
  - Rapid crash patterns
- Automatic response to anomalies
- Pattern-based detection (not just thresholds)

### **Slide 5: System Architecture**
- Multi-layered protection:
  1. Anomaly detection (first line)
  2. Resource monitoring (second line)
  3. Cooldown system (safety net)
  4. Email notifications (alerting)
- All features work together seamlessly

---

## ⚠️ Important Considerations

### **1. Performance Impact:**
- Anomaly detection adds CPU overhead
- Email sending should be async/non-blocking
- Cooldown checks are lightweight (file I/O)

### **2. Reliability:**
- Email failures shouldn't break monitoring
- Cooldown state should persist across restarts
- Anomaly detection should handle edge cases

### **3. Configuration:**
- All thresholds should be configurable
- Email settings should be easy to configure
- Default values should be sensible

### **4. Testing:**
- Test each feature independently
- Test features together
- Test edge cases (network failures, file locks, etc.)
- Create reproducible test scenarios

### **5. Security:**
- Email passwords should be stored securely
- Consider using environment variables
- Don't log sensitive information

---

## 🚀 Next Steps

1. **Review this analysis** - Understand integration points
2. **Prioritize features** - Decide which to implement first
3. **Design data structures** - Plan state management
4. **Create configuration files** - Define settings format
5. **Implement incrementally** - One feature at a time
6. **Test thoroughly** - Verify each feature works
7. **Update documentation** - Document new features
8. **Prepare demo** - Create scenarios for presentation

---

**This analysis provides a complete roadmap for implementing these advanced features while maintaining your existing architecture and ensuring all components work together seamlessly.**

