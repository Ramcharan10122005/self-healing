#!/bin/bash
set -e

C_MONITOR_SRC="c_monitor.c"
C_MONITOR_BIN="c_monitor"
PY_MONITOR="monitor.py"
GUI="gui.py"
PID_FILE="selfhealer.pid"
LOG_FILE="healing.log"
PROCESS_LIST="process_list.txt"

color() { printf "\033[%sm%s\033[0m\n" "$1" "$2"; }
info() { color "34" "[INFO] $1"; }
ok() { color "32" "[OK] $1"; }
warn() { color "33" "[WARN] $1"; }
err() { color "31" "[ERR ] $1"; }

exists() { command -v "$1" >/dev/null 2>&1; }

stop_all() {
    if [ -f "$PID_FILE" ]; then
        while read -r pid comp; do
            if kill -0 "$pid" 2>/dev/null; then
                info "Stopping $comp (PID $pid)"; kill "$pid" || true; sleep 1; kill -9 "$pid" || true;
            fi
        done < "$PID_FILE"
        rm -f "$PID_FILE"
    fi
    pkill -f "$C_MONITOR_BIN" 2>/dev/null || true
    pkill -f "$PY_MONITOR" 2>/dev/null || true
    pkill -f "$GUI" 2>/dev/null || true
}

check_deps() {
    exists gcc || { err "gcc not found"; exit 1; }
    exists python3 || { err "python3 not found"; exit 1; }
    python3 -c 'import psutil' 2>/dev/null || { err "psutil missing (pip3 install psutil)"; exit 1; }
    python3 -c 'import tkinter' 2>/dev/null || { err "tkinter missing (sudo apt-get install python3-tk)"; exit 1; }
    ok "Dependencies OK"
}

ensure_process_list() {
    if [ ! -f "$PROCESS_LIST" ]; then
        info "Creating default $PROCESS_LIST"
        cat > "$PROCESS_LIST" <<EOF
# Self-Healing Process Manager
# process_name cpu_limit memory_limit_MB
# gedit 80 200
# firefox 90 500
EOF
    fi
}

build() {
    info "Compiling C monitor"
    gcc -o "$C_MONITOR_BIN" "$C_MONITOR_SRC" -Wall -Wextra
    ok "Compiled $C_MONITOR_BIN"
}

start_c_monitor() {
    info "Starting C monitor"
    ./"$C_MONITOR_BIN" --no-daemon & echo "$! c_monitor" >> "$PID_FILE"
}

start_python_monitor() {
    info "Starting Python monitor"
    python3 "$PY_MONITOR" & echo "$! python_monitor" >> "$PID_FILE"
}

start_gui() {
    info "Starting GUI"
    python3 "$GUI" & echo "$! gui" >> "$PID_FILE"
}

status() {
    if [ -f "$PID_FILE" ]; then
        while read -r pid comp; do
            if kill -0 "$pid" 2>/dev/null; then ok "$comp (PID $pid) running"; else warn "$comp (PID $pid) not running"; fi
        done < "$PID_FILE"
    else
        warn "No PID file"
    fi
    [ -f "$LOG_FILE" ] && tail -n 10 "$LOG_FILE" || true
}

case "${1:-start}" in
    start)
        check_deps; ensure_process_list; stop_all; build; start_c_monitor; sleep 1; start_python_monitor; sleep 1; start_gui; ok "All components started"; status ;;
    stop)
        stop_all; ok "Stopped" ;;
    restart)
        stop_all; "$0" start ;;
    status)
        status ;;
    monitor)
        check_deps; ensure_process_list; stop_all; build; start_c_monitor; sleep 1; start_python_monitor; ok "Monitors started" ;;
    gui)
        start_gui ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|monitor|gui}"; exit 1 ;;
esac


