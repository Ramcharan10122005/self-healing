# Self-Healing Process Manager

Linux project combining C daemon, Python resource monitor, Bash orchestrator, and Tkinter GUI.

## Files
- `c_monitor.c`: Daemon to detect crashes and restart processes listed in `process_list.txt`.
- `monitor.py`: Uses psutil to enforce CPU/memory limits; restarts when exceeded.
- `heal.sh`: Orchestrates build and start; one command to run all.
- `gui.py`: Tkinter UI showing process status and live `healing.log`.
- `process_list.txt`: `process_name cpu_limit memory_limit_MB`.
- `healing.log`: Appended by monitors.

## Quick start
```bash
chmod +x heal.sh
./heal.sh start
```

## Example config
```
gedit 80 200
firefox 90 500
```

## Notes
- Requires: gcc, python3, psutil, tkinter.
- GUI refreshes every few seconds; monitors append to `healing.log`.
