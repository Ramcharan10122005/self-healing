# Self-Healing Process Manager - Class Presentation Guide

## 🎯 **Presentation Overview (15-20 minutes)**

### **1. Introduction & Problem Statement (2-3 minutes)**
**Hook:** "What happens when critical processes crash on a server? Manual intervention? Downtime? Lost revenue?"

**Problem:**
- Critical processes can crash unexpectedly
- Manual monitoring and restart is time-consuming
- Resource leaks (CPU/memory) can bring down systems
- Need automated process management

**Solution:** A self-healing process manager that automatically detects crashes and resource violations, then restarts processes.

---

### **2. System Architecture (3-4 minutes)**

**Show the diagram:**
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   C Monitor     │    │ Python Monitor  │    │   GUI (Tkinter) │
│   (Daemon)      │    │ (Resource Mgmt) │    │   (Dashboard)   │
│                 │    │                 │    │                 │
│ • Crash detect  │    │ • CPU monitoring│    │ • Live status   │
│ • Auto restart  │    │ • Memory limits │    │ • Process mgmt  │
│ • Process list  │    │ • Kill & restart│    │ • Log viewer    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │   heal.sh       │
                    │ (Orchestrator)  │
                    │                 │
                    │ • Build system  │
                    │ • Start/stop    │
                    │ • Status check  │
                    └─────────────────┘
```

**Key Components:**
1. **C Monitor (Daemon)**: Low-level crash detection and restart
2. **Python Monitor**: Resource monitoring with psutil
3. **GUI**: Real-time dashboard with Tkinter
4. **Shell Script**: Orchestration and management

---

### **3. Live Demo (8-10 minutes)**

#### **Demo Setup:**
```bash
# Terminal 1: Start the system
cd /home/ramcharan/Desktop/OS/project/p1
./heal.sh start
```

#### **Demo Scenarios:**

**A. Show System Status (1 minute)**
- Run `./heal.sh status`
- Show all components running
- Open GUI to show dashboard

**B. Add a Process to Monitor (2 minutes)**
- Open GUI
- Click "Add process"
- Add: `gedit 80 200` (80% CPU, 200MB memory limit)
- Show process appears in table

**C. Simulate Process Crash (2 minutes)**
- Start gedit manually: `gedit &`
- Kill it: `kill -9 <pid>`
- Show in GUI/log that it was detected and restarted
- Point out the healing.log entries

**D. Simulate Resource Violation (3 minutes)**
- Add a CPU-intensive process: `stress-ng --cpu 1 --timeout 30s &`
- Add it to process list with low CPU limit (e.g., 10%)
- Show Python monitor detecting high CPU usage
- Show process being killed and restarted
- Explain the graceful termination (SIGTERM → SIGKILL)

**E. Show Real-time Monitoring (2 minutes)**
- Point out live updates in GUI
- Show log scrolling in real-time
- Demonstrate process management features

---

### **4. Technical Deep Dive (3-4 minutes)**

#### **C Monitor (Daemon)**
```c
// Key features:
- Daemonization with fork()
- Process list parsing
- Crash detection with kill(pid, 0)
- Automatic restart with execvp()
- Signal handling (SIGTERM/SIGINT)
```

#### **Python Monitor (Resource Management)**
```python
# Key features:
- psutil for system monitoring
- CPU/memory threshold enforcement
- Process discovery by name
- Graceful termination sequence
- Comprehensive logging
```

#### **GUI (User Interface)**
```python
# Key features:
- Real-time process table
- Live log viewer
- Process management (add/remove/restart)
- Auto-refresh every 3 seconds
- Modern Tkinter interface
```

---

### **5. Key Features & Benefits (2-3 minutes)**

#### **Features:**
- ✅ **Automatic Crash Recovery**: Detects and restarts crashed processes
- ✅ **Resource Management**: Enforces CPU and memory limits
- ✅ **Real-time Monitoring**: Live dashboard with process status
- ✅ **Comprehensive Logging**: Detailed audit trail of all actions
- ✅ **Easy Configuration**: Simple text file for process definitions
- ✅ **Cross-platform**: Works on Linux/Unix systems
- ✅ **Modular Design**: Separate components for different responsibilities

#### **Benefits:**
- **Zero Downtime**: Automatic recovery from failures
- **Resource Efficiency**: Prevents runaway processes
- **Operational Simplicity**: One command to start everything
- **Visibility**: Real-time monitoring and logging
- **Flexibility**: Easy to add/remove monitored processes

---

### **6. Code Quality & Best Practices (2 minutes)**

#### **C Programming:**
- Proper error handling
- Signal management
- Memory safety
- Daemon best practices

#### **Python Programming:**
- Type hints
- Exception handling
- Clean separation of concerns
- Modern Python features

#### **System Integration:**
- Process management
- File I/O and logging
- Cross-language communication
- Shell scripting

---

### **7. Q&A & Discussion (3-5 minutes)**

**Potential Questions:**
- "How does it handle processes that don't exist?"
- "What about processes that need specific arguments?"
- "How do you handle dependencies between processes?"
- "What about security considerations?"
- "How would you scale this for production?"

**Answers:**
- Process discovery by name matching
- Could extend to support command-line arguments
- Could add dependency management
- Security: proper permissions, input validation
- Scaling: distributed monitoring, database logging

---

## 🎬 **Demo Script**

### **Opening (30 seconds)**
"Today I'll demonstrate a self-healing process manager I built for my OS project. This system automatically monitors processes, detects crashes and resource violations, and restarts them without human intervention."

### **Architecture Overview (1 minute)**
"Let me show you the system architecture. We have four main components working together..."

### **Live Demo (8 minutes)**
"Now let's see it in action. I'll start the system and demonstrate various failure scenarios..."

### **Technical Details (2 minutes)**
"The system uses C for low-level daemon functionality, Python for resource monitoring, and Tkinter for the user interface..."

### **Closing (1 minute)**
"This demonstrates how we can build robust, self-healing systems using standard OS concepts and programming techniques. The modular design makes it easy to extend and maintain."

---

## 📋 **Pre-Demo Checklist**

- [ ] Test all components work (`./heal.sh start`)
- [ ] Verify GUI opens correctly
- [ ] Prepare example processes to add
- [ ] Test crash simulation scenarios
- [ ] Check log file has recent entries
- [ ] Have backup terminal windows ready
- [ ] Prepare process_list.txt with examples

---

## 🛠 **Troubleshooting**

**If something goes wrong:**
- `./heal.sh stop` to stop everything
- `./heal.sh start` to restart
- Check `healing.log` for errors
- Verify dependencies: `gcc`, `python3`, `psutil`, `tkinter`

**Common issues:**
- Permission denied: `chmod +x heal.sh`
- Missing dependencies: Install with package manager
- GUI not opening: Check display settings
- Process not found: Verify process name in PATH

---

## 💡 **Presentation Tips**

1. **Start with the problem** - Make it relatable
2. **Show, don't just tell** - Live demos are powerful
3. **Explain the "why"** - Not just the "what"
4. **Keep it interactive** - Ask questions, engage audience
5. **Have backup plans** - Screenshots if live demo fails
6. **End with impact** - What did we learn? What's next?

---

## 🎯 **Key Takeaways for Audience**

- **Process Management**: Understanding how OS manages processes
- **System Programming**: C daemons, Python system monitoring
- **User Interface**: Building practical GUIs with Tkinter
- **System Integration**: Combining multiple languages and tools
- **Real-world Application**: Solving actual operational problems
- **Best Practices**: Error handling, logging, modular design
