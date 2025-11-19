# Live Demo Script - Self-Healing Process Manager

## Pre-Demo Setup (Do this before class)
```bash
cd /home/ramcharan/Desktop/OS/project/p1
./heal.sh stop  # Clean slate
./heal.sh start # Start fresh
```

## Demo Script (Follow this during presentation)

### 1. Show System Status (1 minute)
```bash
# Terminal 1
./heal.sh status
```
**Say:** "All three components are running - C monitor, Python monitor, and GUI"

### 2. Open GUI and Show Dashboard (1 minute)
```bash
# The GUI should already be open, if not:
python3 gui.py &
```
**Say:** "Here's our real-time dashboard showing process status, resource usage, and live logs"

### 3. Add a Process to Monitor (2 minutes)
**In GUI:**
1. Click "Add process"
2. Enter: `gedit` (Process name)
3. Enter: `80` (CPU limit %)
4. Enter: `200` (Memory limit MB)
5. Click "Save"

**Say:** "Now we're monitoring gedit with 80% CPU and 200MB memory limits"

### 4. Demonstrate Process Monitoring (2 minutes)
**In GUI:**
- Show gedit appears in the process table
- Point out the real-time updates
- Show the log entries

**Say:** "The system is now actively monitoring gedit. You can see it in the process table with live resource usage."

### 5. Simulate Process Crash (2 minutes)
**Terminal 2:**
```bash
# Start gedit manually
gedit &

# Find its PID
ps aux | grep gedit

# Kill it (replace XXXX with actual PID)
kill -9 XXXX
```

**In GUI:**
- Show the crash detection in logs
- Show gedit being restarted automatically
- Point out the new PID

**Say:** "I just killed gedit, but watch - the system detected the crash and automatically restarted it with a new PID."

### 6. Simulate Resource Violation (3 minutes)
**Terminal 2:**
```bash
# Install stress-ng if not available

sudo apt install stress-ng

# Start CPU stress test
stress-ng --cpu 1 --timeout 30s &
```

**In GUI:**
1. Add process: `stress-ng` with CPU limit `10` and memory `100`
2. Watch it get killed for exceeding CPU limit
3. Show the restart in logs

**Say:** "Now I'm running a CPU-intensive process with a low limit. Watch as the system detects the resource violation, kills the process, and restarts it."

### 7. Show Process Management Features (1 minute)
**In GUI:**
- Click on a process in the table
- Click "Force restart" to manually restart
- Show "Remove process" functionality
- Point out the live log updates

**Say:** "The GUI also provides manual control - you can force restart processes or remove them from monitoring."

### 8. Show Log Details (1 minute)
**In GUI:**
- Scroll through the log
- Point out different types of entries:
  - Process starts
  - Crash detections
  - Resource violations
  - Restarts

**Say:** "Everything is logged with timestamps, so you have a complete audit trail of all system actions."

## Backup Demo (If live demo fails)

### Screenshots to Show:
1. System architecture diagram
2. GUI dashboard with processes
3. Log file with various entries
4. Terminal showing status

### Key Points to Emphasize:
- **Automatic Recovery**: No manual intervention needed
- **Resource Management**: Prevents runaway processes
- **Real-time Monitoring**: Live updates and logging
- **Easy Configuration**: Simple text file setup
- **Modular Design**: Separate components for different tasks

## Troubleshooting During Demo

**If GUI doesn't open:**
```bash
python3 gui.py
```

**If processes don't restart:**
```bash
./heal.sh restart
```

**If you need to show logs manually:**
```bash
tail -f healing.log
```

**If system seems stuck:**
```bash
./heal.sh stop
./heal.sh start
```

## Closing Points

1. **Real-world Application**: This solves actual operational problems
2. **System Programming**: Demonstrates OS concepts in practice
3. **Multi-language Integration**: C, Python, and shell scripting
4. **User Experience**: Both programmatic and GUI interfaces
5. **Extensibility**: Easy to add new features and processes

## Questions to Expect

**Q: "What if a process needs specific arguments?"**
A: "The current version uses the process name, but we could extend it to support command-line arguments in the config file."

**Q: "How do you handle process dependencies?"**
A: "That's a great extension - we could add dependency management to ensure processes start in the correct order."

**Q: "What about security?"**
A: "The system runs with user permissions. For production, you'd want proper access controls and input validation."

**Q: "How would you scale this?"**
A: "We could extend it with distributed monitoring, database logging, and web-based dashboards for larger systems."


