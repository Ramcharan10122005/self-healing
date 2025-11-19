# 🎬 Demonstration Guide - Self-Healing Process Manager

## 📋 Pre-Demo Setup Checklist

### 1. **Prepare Your Environment**
```bash
# Navigate to project directory
cd self-healing

# Ensure all files are present
ls -la *.py *.c *.sh

# Make sure scripts are executable
chmod +x heal.sh
chmod +x c_monitor_helper.py
```

### 2. **Configure Email (Optional but Recommended)**
```bash
# Edit email_config.txt
nano email_config.txt

# Set enabled=true
enabled=true

# Your credentials are already configured in email_notifier.py
# (sender_email, sender_password, receiver_email)
```

### 3. **Test Email Configuration**
```bash
# Test email sending
python3 email_notifier.py "Test Alert" "This is a test email from the system" "general"

# Check your inbox - you should receive the email
```

### 4. **Prepare Test Processes**
```bash
# Create/Edit process_list.txt
cat > process_list.txt << EOF
# process_name cpu_limit memory_limit_MB
gedit 80 200
firefox 90 500
EOF

# Or use any processes you want to monitor
```

### 5. **Start the System**
```bash
# Build and start all components
./heal.sh start

# Check status
./heal.sh status

# You should see:
# - c_monitor running
# - monitor.py running
# - gui.py running (if GUI is started)
```

---

## 🎯 Demo Flow - Step by Step

### **PART 1: Introduction & Overview (2 minutes)**

#### **What to Say:**
> "I've built a self-healing process manager that automatically monitors, detects, and recovers from process failures. Today I'll demonstrate 4 advanced features that make this production-ready."

#### **What to Show:**
1. Open the GUI:
   ```bash
   python3 gui.py
   ```
2. Show the 4 tabs:
   - **Processes** - Main monitoring view
   - **Anomalies** - Real-time anomaly detection
   - **Zombies** - Zombie process management
   - **Cooldown** - Restart limit tracking

3. Show the log file:
   ```bash
   tail -f healing.log
   ```

---

### **PART 2: Feature 1 - Email Notifications (3 minutes)**

#### **Demo Script:**

**Step 1: Show Email Configuration**
```bash
# Show the config file
cat email_config.txt

# Explain:
# "The system is configured to send emails for all critical events"
```

**Step 2: Trigger a Process Crash**
```bash
# Find a monitored process
ps aux | grep gedit

# Kill it to trigger crash detection
kill -9 <PID>

# Wait 5-10 seconds for detection and restart
```

**What Happens:**
- C monitor detects crash
- Process is restarted
- Email is sent to configured address
- Log entry is created

**Step 3: Show Email Received**
- Open your email inbox
- Show the received alert email
- Point out:
  - Subject: "[Self-Healing Monitor] Process Crash: gedit"
  - Timestamp
  - Process details (PID, reason)

**Step 4: Trigger Resource Violation**
```bash
# Create a CPU-intensive process (if you have one)
# Or show the log where a violation occurred

# Show in GUI: Processes tab
# Point out the CPU/Memory columns
```

**What to Say:**
> "When a process exceeds its CPU or memory limits, the system automatically kills it, restarts it, and sends an email alert. This ensures administrators are immediately notified of any issues."

---

### **PART 3: Feature 2 - Cooldown System (4 minutes)**

#### **Demo Script:**

**Step 1: Explain the Problem**
> "Without cooldown, a crashing process could restart infinitely, creating a loop. Our system prevents this."

**Step 2: Create a Test Scenario**
```bash
# Create a script that crashes immediately
cat > crash_test.sh << 'EOF'
#!/bin/bash
# This script will crash immediately
exit 1
EOF

chmod +x crash_test.sh

# Add to process_list.txt temporarily
echo "crash_test 50 100" >> process_list.txt
```

**Step 3: Show Cooldown Activation**
```bash
# Watch the log in real-time
tail -f healing.log

# The system will:
# 1. Detect crash
# 2. Restart (attempt 1)
# 3. Detect crash again
# 4. Restart (attempt 2)
# ... continue until 5 restarts
# 5. Enter cooldown mode
```

**Step 4: Show Cooldown in GUI**
- Switch to **Cooldown** tab
- Show the process in cooldown
- Point out:
  - Restart count: 5
  - In Cooldown: Yes
  - Cooldown Remaining: ~120 seconds

**Step 5: Show Email Alert**
- Check inbox for cooldown email
- Subject: "[Self-Healing Monitor] Cooldown Activated: crash_test"

**Step 6: Show Recovery**
```bash
# Wait 2 minutes (or manually reset)
# Or show in log when cooldown expires

# The system will reset and allow restarts again
```

**What to Say:**
> "After 5 restarts in 1 minute, the system enters a 2-minute cooldown. This prevents infinite loops while still allowing recovery. An email alert is sent when cooldown is activated."

---

### **PART 4: Feature 3 - Anomaly Detection (5 minutes)**

#### **Demo Script:**

**Step 1: Show Anomaly Detection Tab**
- Open GUI → **Anomalies** tab
- Explain: "The system continuously monitors for unusual behaviors"

**Step 2: Demonstrate Memory Leak Detection**

**Option A: Use a Real Process**
```bash
# Monitor a process that uses memory
# Watch the Anomalies tab in GUI
# The system will detect if memory increases steadily
```

**Option B: Simulate (if you have a test program)**
```python
# Create a simple memory leak program
cat > memory_leak.py << 'EOF'
import time
data = []
while True:
    data.append([0] * 1000000)  # Allocate 1MB
    time.sleep(1)
EOF

python3 memory_leak.py &
# Add to process_list.txt
```

**What Happens:**
- System detects steady memory increase
- Logs: "Anomaly: memory_leak detected"
- Sends email alert
- Automatically restarts the process

**Step 3: Demonstrate Fork Bomb Detection**

**Option A: Create Test Fork Bomb**
```bash
# WARNING: Be careful with this!
# Create a controlled fork bomb
cat > fork_test.sh << 'EOF'
#!/bin/bash
for i in {1..60}; do
    (while true; do sleep 1; done) &
done
wait
EOF

chmod +x fork_test.sh
./fork_test.sh &
```

**What Happens:**
- System detects >50 child processes
- Logs: "Anomaly: fork_bomb detected"
- Immediately kills the process
- Sends critical email alert

**Step 4: Show CPU Spike Detection**
```bash
# Create CPU-intensive task
yes > /dev/null &
# Or use stress-ng if available
stress-ng --cpu 1 --timeout 30s &
```

**What Happens:**
- System detects sudden CPU spike (3x average)
- Logs: "Anomaly: cpu_spike detected"
- Sends email alert
- Continues monitoring

**Step 5: Show Anomaly Email**
- Check inbox
- Show anomaly detection emails
- Point out different anomaly types

**What to Say:**
> "Unlike simple threshold monitoring, our system uses pattern detection. It can identify memory leaks by tracking trends, detect fork bombs by counting children, and catch CPU spikes by comparing to historical averages."

---

### **PART 5: Feature 4 - Zombie Process Management (3 minutes)**

#### **Demo Script:**

**Step 1: Show Zombie Tab**
- Open GUI → **Zombies** tab
- Explain: "Zombie processes are dead processes that haven't been properly cleaned up"

**Step 2: Create a Zombie Process (Demo)**
```bash
# Create a process that creates zombies
cat > zombie_creator.py << 'EOF'
import os
import time

def create_zombie():
    pid = os.fork()
    if pid == 0:
        # Child exits immediately
        os._exit(0)
    else:
        # Parent doesn't wait for child
        time.sleep(100)

for _ in range(5):
    create_zombie()
    time.sleep(1)
EOF

python3 zombie_creator.py &
```

**Step 3: Show Detection**
- Wait 5 minutes (or manually trigger)
- System scans for zombies every 5 minutes
- Check **Zombies** tab
- Shows zombie count and details

**Step 4: Show Cleanup**
- Click **"Cleanup Zombies"** button in GUI
- Or run manually:
  ```bash
  python3 zombie_manager.py cleanup
  ```
- Show results dialog

**Step 5: Show Email Alert**
- Check inbox for zombie detection email
- Subject: "[Self-Healing Monitor] Zombie Processes Detected: 5"

**What to Say:**
> "The system automatically scans for zombie processes every 5 minutes. When detected, it attempts to clean them up by killing their parent processes, and sends an alert. The GUI provides a one-click cleanup option."

---

### **PART 6: Integration Demo - All Features Working Together (3 minutes)**

#### **Demo Script:**

**Step 1: Create a Complex Scenario**
```bash
# Add a problematic process
echo "problematic_app 50 100" >> process_list.txt

# This process will:
# 1. Crash repeatedly (trigger cooldown)
# 2. Use too much memory (trigger anomaly)
# 3. Create zombie processes
```

**Step 2: Show Real-Time Monitoring**
- Open GUI
- Show all 4 tabs updating in real-time
- Point out:
  - **Processes**: Shows status, CPU, Memory, Cooldown
  - **Anomalies**: Shows detected issues
  - **Zombies**: Shows zombie count
  - **Cooldown**: Shows restart tracking

**Step 3: Show Log File**
```bash
tail -50 healing.log
```

**Point out entries:**
- Crash detection
- Anomaly detection
- Cooldown activation
- Email notifications
- Zombie cleanup

**Step 4: Show Email Inbox**
- Show multiple emails received:
  - Crash alerts
  - Violation alerts
  - Anomaly alerts
  - Cooldown alerts
  - Zombie alerts

**What to Say:**
> "All features work together seamlessly. When a process has issues, the system detects anomalies first, then monitors resources, applies cooldown if needed, cleans up zombies, and sends comprehensive email alerts. Everything is logged and visible in the GUI."

---

## 🎤 Presentation Talking Points

### **Opening (30 seconds)**
> "I've built a production-ready self-healing process manager with 4 advanced features: email notifications, cooldown system, anomaly detection, and zombie management. Let me demonstrate each feature."

### **Feature 1 - Email (30 seconds)**
> "The system sends real-time email alerts for all critical events - crashes, violations, anomalies, and cooldowns. This ensures administrators are immediately notified."

### **Feature 2 - Cooldown (45 seconds)**
> "To prevent infinite restart loops, the system tracks restart frequency. After 5 restarts in 1 minute, it enters a 2-minute cooldown period and sends an alert. This is production-grade reliability."

### **Feature 3 - Anomaly Detection (60 seconds)**
> "Unlike simple threshold monitoring, our system uses intelligent pattern detection. It can identify memory leaks by tracking trends, detect fork bombs by counting child processes, and catch CPU spikes by comparing to historical data. Each anomaly triggers appropriate action and email alerts."

### **Feature 4 - Zombie Management (30 seconds)**
> "The system automatically scans for zombie processes every 5 minutes, attempts cleanup, and sends alerts. The GUI provides visibility and one-click cleanup."

### **Integration (30 seconds)**
> "All features work together seamlessly. The system provides complete visibility through the GUI, comprehensive logging, and real-time email alerts. This makes it production-ready for real-world deployment."

---

## 📊 Expected Demo Outcomes

### **What Should Happen:**

1. **Email Notifications:**
   - ✅ Receive emails for crashes
   - ✅ Receive emails for violations
   - ✅ Receive emails for anomalies
   - ✅ Receive emails for cooldown
   - ✅ Receive emails for zombies

2. **Cooldown System:**
   - ✅ Process restarts 5 times
   - ✅ Cooldown activates
   - ✅ Email sent
   - ✅ GUI shows cooldown status
   - ✅ System waits 2 minutes

3. **Anomaly Detection:**
   - ✅ Memory leak detected
   - ✅ Fork bomb detected
   - ✅ CPU spike detected
   - ✅ Appropriate actions taken
   - ✅ Emails sent

4. **Zombie Management:**
   - ✅ Zombies detected
   - ✅ Cleanup attempted
   - ✅ Email sent
   - ✅ GUI shows zombie count

---

## 🔧 Troubleshooting During Demo

### **Issue: Emails Not Sending**

**Quick Fix:**
```bash
# Test email manually
python3 email_notifier.py "Test" "Test message" "general"

# Check if enabled
grep enabled email_config.txt

# Enable if needed
sed -i 's/enabled=false/enabled=true/' email_config.txt
```

### **Issue: Cooldown Not Activating**

**Quick Fix:**
```bash
# Manually trigger multiple restarts
for i in {1..6}; do
    killall gedit 2>/dev/null
    sleep 2
done

# Check cooldown state
python3 cooldown_manager.py check gedit
```

### **Issue: Anomalies Not Detecting**

**Quick Fix:**
```bash
# Manually test anomaly detection
python3 anomaly_detector.py <PID>

# Check if process is being monitored
ps aux | grep <process_name>
```

### **Issue: Zombies Not Showing**

**Quick Fix:**
```bash
# Manually scan for zombies
python3 zombie_manager.py scan

# Force cleanup
python3 zombie_manager.py cleanup
```

### **Issue: GUI Not Updating**

**Quick Fix:**
```bash
# Restart GUI
pkill -f gui.py
python3 gui.py &

# Check if monitors are running
./heal.sh status
```

---

## 📝 Demo Checklist

### **Before Demo:**
- [ ] Email configured and tested
- [ ] All processes in process_list.txt are valid
- [ ] System is running (`./heal.sh status`)
- [ ] GUI is open and visible
- [ ] Log file is accessible (`tail -f healing.log`)
- [ ] Email inbox is open
- [ ] Test scripts prepared (if needed)

### **During Demo:**
- [ ] Show GUI with all 4 tabs
- [ ] Demonstrate email notifications
- [ ] Demonstrate cooldown system
- [ ] Demonstrate anomaly detection
- [ ] Demonstrate zombie management
- [ ] Show integration of all features
- [ ] Show log file entries
- [ ] Show received emails

### **After Demo:**
- [ ] Clean up test processes
- [ ] Stop the system (`./heal.sh stop`)
- [ ] Answer questions
- [ ] Show code if requested

---

## 🎬 Quick Demo Script (5-Minute Version)

If you have limited time, follow this condensed version:

1. **Show GUI** (30s)
   - Open GUI, show 4 tabs
   - Explain each feature briefly

2. **Trigger Crash** (1 min)
   - Kill a process
   - Show restart in GUI
   - Show email received

3. **Show Cooldown** (1 min)
   - Explain the concept
   - Show cooldown tab
   - Show email for cooldown

4. **Show Anomaly Detection** (1.5 min)
   - Show anomalies tab
   - Explain detection types
   - Show email for anomaly

5. **Show Zombie Management** (1 min)
   - Show zombies tab
   - Explain automatic cleanup
   - Show email for zombies

6. **Summary** (30s)
   - Show log file
   - Show all emails received
   - Emphasize production-ready features

---

## 💡 Pro Tips for a Great Demo

1. **Practice First:** Run through the demo at least once before presenting
2. **Have Backup:** Prepare screenshots/videos in case something doesn't work
3. **Explain While Showing:** Don't just show - explain what's happening
4. **Highlight Integration:** Emphasize how features work together
5. **Show Real Impact:** Use real processes if possible, not just test scripts
6. **Be Prepared for Questions:** Know your code - be ready to explain implementation
7. **Keep It Simple:** Don't overcomplicate - focus on key features
8. **Show the Code:** If time permits, briefly show key implementation files

---

## 📧 Email Templates You'll See

### **Crash Email:**
```
Subject: [Self-Healing Monitor] Process Crash: gedit

Process 'gedit' (PID 12345) has crashed.
Reason: crash signal detected
The system will attempt to restart the process.
```

### **Violation Email:**
```
Subject: [Self-Healing Monitor] Resource Violation: firefox

Process 'firefox' (PID 12346) has exceeded its CPU limit.
Current: 95.2
Limit: 90
The process has been killed and will be restarted.
```

### **Cooldown Email:**
```
Subject: [Self-Healing Monitor] Cooldown Activated: problematic_app

Process 'problematic_app' has been restarted 5 times in a short period.
The system has entered cooldown mode and will not restart the process for 2 minutes.
This prevents infinite restart loops.
```

### **Anomaly Email:**
```
Subject: [Self-Healing Monitor] Anomaly Detected: memory_leak_app

An anomaly has been detected for process 'memory_leak_app' (PID 12347).
Anomaly Type: memory_leak
Details: Process shows memory leak pattern (15.3MB increase)
Appropriate action has been taken.
```

### **Zombie Email:**
```
Subject: [Self-Healing Monitor] Zombie Processes Detected: 3

3 zombie process(es) detected on the system.
The system will attempt to clean up these processes.
```

---

## 🎯 Key Points to Emphasize

1. **Production-Ready:** Not just a prototype - includes error handling, logging, safety checks
2. **Intelligent Detection:** Pattern-based anomaly detection, not just thresholds
3. **Prevents Problems:** Cooldown prevents infinite loops, zombie cleanup prevents resource leaks
4. **Complete Visibility:** GUI, logs, and emails provide full system awareness
5. **Automatic Recovery:** System handles issues automatically without manual intervention
6. **Real-World Applicable:** Features address actual production problems

---

**Good luck with your demonstration! 🚀**

