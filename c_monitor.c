

#define _POSIX_C_SOURCE 200809L
#define _DEFAULT_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <signal.h>
#include <string.h>
#include <time.h>
#include <errno.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <pwd.h>

#define MAX_LINE_LENGTH 256
#define MAX_PROCESS_NAME 128
#define LOG_FILE "healing.log"
#define PROCESS_LIST_FILE "process_list.txt"
#define HELPER_SCRIPT "c_monitor_helper.py"

// Forward declarations
static pid_t find_pid_by_name(const char* process_name);
static int check_cooldown(const char* process_name);
static void track_restart_c(const char* process_name);
static int check_cooldown_after_track(const char* process_name);
static void send_email_crash(const char* process_name, pid_t pid, const char* reason);
static void send_email_restart_failed(const char* process_name, const char* reason);

typedef struct {
    char name[MAX_PROCESS_NAME];
    int cpu_limit;
    int memory_limit_mb;
    pid_t pid;
    int is_running;
    int we_killed_it;  // Track if we killed this process (resource limits)
    int exited_normally;  // Track if process exited normally (don't restart)
} ProcessInfo;

static void log_action(const char* action, const char* process_name, pid_t pid, const char* reason) {
    FILE* log_file = fopen(LOG_FILE, "a");
    if (log_file) {
        time_t now = time(NULL);
        struct tm* tm_info = localtime(&now);
        fprintf(log_file, "[%04d-%02d-%02d %02d:%02d] %s %s (PID %d) %s\n",
                tm_info->tm_year + 1900, tm_info->tm_mon + 1, tm_info->tm_mday,
                tm_info->tm_hour, tm_info->tm_min,
                action, process_name, pid, reason ? reason : "");
        fclose(log_file);
    }
}

static int check_process_exists(pid_t pid) {
    if (pid <= 0) return 0;
    
    // First check if PID exists
    if (kill(pid, 0) != 0) return 0;
    
    // Check if process is actually running (not zombie) by reading /proc/PID/stat
    char stat_path[64];
    snprintf(stat_path, sizeof(stat_path), "/proc/%d/stat", (int)pid);
    FILE* f = fopen(stat_path, "r");
    if (!f) return 0;  // Process doesn't exist or can't access
    
    char state;
    // Format: pid comm state ...
    // We need to skip pid and comm (which may contain spaces), then read state
    int scanned = fscanf(f, "%*d %*s %c", &state);
    fclose(f);
    
    if (scanned != 1) return 0;
    
    // State 'Z' means zombie, 'T' means stopped - we want only running processes
    // States: R (running), S (sleeping), D (disk sleep), Z (zombie), T (stopped)
    return (state != 'Z' && state != 'T');
}

// Parse exit signal from /proc/PID/stat for a zombie process
// Returns: signal number if killed by signal, 0 if normal exit, -1 if error
// In /proc/PID/stat, for a zombie: exit_code field contains:
// - Exit value (0-255) if process exited normally
// - Signal number if process was killed by signal
static int get_exit_signal(pid_t pid) {
    char stat_path[64];
    snprintf(stat_path, sizeof(stat_path), "/proc/%d/stat", (int)pid);
    
    FILE* f = fopen(stat_path, "r");
    if (!f) return -1;
    
    // Read entire line to handle comm field with spaces
    char line[512];
    if (!fgets(line, sizeof(line), f)) {
        fclose(f);
        return -1;
    }
    fclose(f);
    
    // Find comm field boundaries (in parentheses)
    char* comm_start = strchr(line, '(');
    if (!comm_start) return -1;
    char* comm_end = strrchr(comm_start, ')');
    if (!comm_end || comm_end[1] != ' ') return -1;
    
    // Parse fields after comm: state ppid pgrp ... exit_code
    // exit_code is the last field (field 52 in modern kernels)
    // We'll parse by counting fields after comm
    char* after_comm = comm_end + 2; // Skip ") "
    
    // Count to exit_code: it's the last numeric field
    // Simpler: parse backwards or use a more robust method
    // Let's count fields: state(1), ppid(2), ... exit_code(last)
    // Actually, let's just parse the last field which is exit_code
    
    // Find the last space-separated field (exit_code)
    char* last_space = strrchr(after_comm, ' ');
    if (!last_space) return -1;
    
    unsigned long exit_code = strtoul(last_space + 1, NULL, 10);
    
    // Also get state (first field after comm)
    char state;
    if (sscanf(after_comm, "%c", &state) != 1) return -1;
    if (state != 'Z') return -1; // Not a zombie
    
    // exit_code interpretation for zombie:
    // - If 0: normal exit with exit code 0
    // - If 1-31: killed by signal (signal number) - direct signal number
    // - If 128-159: killed by signal (exit_code - 128 = signal number) - shell exit status format
    // - If > 31 and < 128: normal exit with that exit value
    // - If > 159: normal exit with that exit value
    
    // Check if it's a direct signal number (1-31)
    if (exit_code > 0 && exit_code <= 31) {
        return (int)exit_code; // Killed by signal
    }
    
    // Check if it's in shell exit status format (128 + signal)
    if (exit_code >= 128 && exit_code <= 159) {
        int signal = (int)(exit_code - 128);
        if (signal >= 1 && signal <= 31) {
            return signal; // Killed by signal
        }
    }
    
    // exit_code is 0 or other value - normal exit
    return 0; // Normal exit
}

// Check if process should be restarted based on exit signal
// Returns: 1 if should restart (crash signals), 0 if should NOT restart (normal exit, SIGTERM, SIGKILL)
// Crash signals: SIGSEGV(11), SIGABRT(6), SIGBUS(7), SIGFPE(8), SIGILL(4)
// Normal exit: exit(0) or window close - no signal
// Normal kill: SIGTERM(15), SIGKILL(9) - don't restart
static int should_restart_on_exit(pid_t pid, const char* process_name) {
    if (pid <= 0) return 0;
    
    char stat_path[64];
    snprintf(stat_path, sizeof(stat_path), "/proc/%d/stat", (int)pid);
    
    // Check immediately first (no delay) - critical to catch zombie before reaping
    // Then check multiple times quickly to catch zombie state and read exit signal
    for (int i = 0; i < 30; i++) {
        if (i > 0) {
            usleep(2 * 1000); // 2ms between checks - very fast
        }
        
        FILE* f = fopen(stat_path, "r");
        if (!f) {
            // Process gone - try to read exit signal from status file as fallback
            // Sometimes the stat file disappears before we can read it
            if (i >= 1) {
                // Try reading from /proc/PID/status which might still exist briefly
                char status_path[64];
                snprintf(status_path, sizeof(status_path), "/proc/%d/status", (int)pid);
                FILE* status_f = fopen(status_path, "r");
                if (status_f) {
                    char line[256];
                    while (fgets(line, sizeof(line), status_f)) {
                        // Look for signal information in status file
                        if (strncmp(line, "State:", 6) == 0) {
                            // State shows how process exited
                        }
                    }
                    fclose(status_f);
                }
                
                // Check if new instance exists
                if (i >= 2) {
                    pid_t new_pid = find_pid_by_name(process_name);
                    if (new_pid > 0 && new_pid != pid) {
                        return 0; // New instance exists, don't restart
                    }
                }
            }
            continue;
        }
        
        // Check if zombie or try to read exit signal
        char state;
        int scanned = fscanf(f, "%*d %*s %c", &state);
        fclose(f);
        
        if (scanned >= 1) {
            if (state == 'Z') {
                // Found zombie - get exit signal immediately
                int signal = get_exit_signal(pid);
                
                if (signal < 0) {
                    // Error reading signal - try again on next iteration
                    continue;
                }
                
                if (signal == 0) {
                    // Normal exit (exit_code is exit value, not signal)
                    log_action("Exit detected", process_name, pid, "normal exit (exit code 0)");
                    return 0; // Don't restart
                }
                
                // Process was killed by a signal
                // Log the signal for debugging
                const char* signal_name = "unknown";
                if (signal == 11) signal_name = "SIGSEGV";
                else if (signal == 6) signal_name = "SIGABRT";
                else if (signal == 7) signal_name = "SIGBUS";
                else if (signal == 8) signal_name = "SIGFPE";
                else if (signal == 4) signal_name = "SIGILL";
                else if (signal == 15) signal_name = "SIGTERM";
                else if (signal == 9) signal_name = "SIGKILL";
                
                log_action("Exit signal detected", process_name, pid, signal_name);
                
                // Check if it's a crash signal that should trigger restart
                if (signal == 11 || signal == 6 || signal == 7 || signal == 8 || signal == 4) {
                    // SIGSEGV(11), SIGABRT(6), SIGBUS(7), SIGFPE(8), SIGILL(4) - crash signals
                    return 1; // Restart on crash signal
                }
                
                // Other signals (SIGTERM=15, SIGKILL=9, etc.) - don't restart
                return 0; // Don't restart on normal kill signals
            } else if (state == 'R' || state == 'S' || state == 'D') {
                // Process is still running - continue checking
                continue;
            }
            // Other states (T=stopped, etc.) - continue checking
        }
    }
    
    // Process disappeared without becoming zombie
    // This usually means:
    // 1. Normal exit - parent reaped it immediately (very common for GUI apps)
    // 2. Killed with SIGKILL - no zombie state
    // 3. Killed with SIGTERM - might not become zombie if parent reaps quickly
    // 
    // Since we can't detect the signal in this case, we must be conservative:
    // Only restart if we're CERTAIN it was a crash signal.
    // If we're uncertain, assume normal exit (don't restart).
    
    log_action("Exit detected", process_name, pid, "process disappeared without zombie state (assumed normal exit)");
    
    // Check if new instance exists
    pid_t new_pid = find_pid_by_name(process_name);
    if (new_pid > 0 && new_pid != pid) {
        return 0; // New instance exists, don't restart
    }
    
    // Process gone without zombie - assume normal exit (don't restart)
    // This is the safe default: only restart on confirmed crash signals
    return 0; // Don't restart - we didn't confirm a crash signal
}

// Find an existing process PID by exact name using pgrep, but verify it's actually running
static pid_t find_pid_by_name(const char* process_name) {
    char cmd[256];
    snprintf(cmd, sizeof(cmd), "pgrep -x %s 2>/dev/null", process_name);
    FILE* fp = popen(cmd, "r");
    if (!fp) return 0;
    
    char buf[32];
    while (fgets(buf, sizeof(buf), fp) != NULL) {
        pid_t pid = (pid_t)strtol(buf, NULL, 10);
        if (pid > 0 && check_process_exists(pid)) {
            // Found a running (non-zombie) process
            pclose(fp);
            return pid;
        }
    }
    pclose(fp);
    return 0;
}

// Try to get DISPLAY from user's active session
static char* get_user_display(void) {
    static char display[64] = {0};
    
    // First check if already set in environment
    const char* env_disp = getenv("DISPLAY");
    if (env_disp && *env_disp) {
        strncpy(display, env_disp, sizeof(display) - 1);
        display[sizeof(display) - 1] = '\0';
        return display;
    }
    
    // Try to read from user's session (check common session files)
    uid_t uid = getuid();
    char session_file[256];
    snprintf(session_file, sizeof(session_file), "/run/user/%d/.x11_display", (int)uid);
    FILE* f = fopen(session_file, "r");
    if (f) {
        if (fgets(display, sizeof(display), f)) {
            char* nl = strchr(display, '\n');
            if (nl) *nl = '\0';
            fclose(f);
            return display;
        }
        fclose(f);
    }
    
    // Default fallback to most common display
    strncpy(display, ":0", sizeof(display) - 1);
    display[sizeof(display) - 1] = '\0';
    return display;
}

// Find actual DISPLAY by checking X processes
static char* find_active_display(void) {
    static char display[64] = {0};
    FILE* fp;
    char line[256];
    
    // Try to find DISPLAY from running X processes
    fp = popen("ps aux | grep -E '[X]org|[X]wayland' | head -1", "r");
    if (fp) {
        if (fgets(line, sizeof(line), fp)) {
            // Try to extract display from process args
            char* disp_ptr = strstr(line, " :");
            if (disp_ptr) {
                sscanf(disp_ptr, " :%63s", display);
                if (display[0]) {
                    char full_disp[64];
                    snprintf(full_disp, sizeof(full_disp), ":%s", display);
                    strncpy(display, full_disp, sizeof(display) - 1);
                    pclose(fp);
                    return display;
                }
            }
        }
        pclose(fp);
    }
    
    // Check /tmp/.X11-unix for active displays
    fp = popen("ls /tmp/.X11-unix/ 2>/dev/null | grep -o 'X[0-9]*' | head -1 | sed 's/X/:/'", "r");
    if (fp) {
        if (fgets(display, sizeof(display), fp)) {
            char* nl = strchr(display, '\n');
            if (nl) *nl = '\0';
            if (display[0]) {
                pclose(fp);
                return display;
            }
        }
        pclose(fp);
    }
    
    return get_user_display();
}

// Get GUI environment from a running process of the same user
static void get_gui_env_from_process(void) {
    FILE* fp;
    char line[512];
    char cmd[256];
    uid_t uid = getuid();
    
    // Try to get env from any GUI process (like gedit, firefox, etc.)
    snprintf(cmd, sizeof(cmd), "ps e -u %d 2>/dev/null | grep -E '(DISPLAY|XAUTHORITY|DBUS)' | head -1", (int)uid);
    fp = popen(cmd, "r");
    if (fp) {
        if (fgets(line, sizeof(line), fp)) {
            // Parse environment variables from ps output
            char* disp_ptr = strstr(line, "DISPLAY=");
            if (disp_ptr) {
                char disp_val[64];
                if (sscanf(disp_ptr, "DISPLAY=%63s", disp_val) == 1) {
                    setenv("DISPLAY", disp_val, 1);
                }
            }
            char* xauth_ptr = strstr(line, "XAUTHORITY=");
            if (xauth_ptr) {
                char xauth_val[256];
                if (sscanf(xauth_ptr, "XAUTHORITY=%255s", xauth_val) == 1) {
                    setenv("XAUTHORITY", xauth_val, 1);
                }
            }
            char* dbus_ptr = strstr(line, "DBUS_SESSION_BUS_ADDRESS=");
            if (dbus_ptr) {
                char dbus_val[256];
                if (sscanf(dbus_ptr, "DBUS_SESSION_BUS_ADDRESS=%255s", dbus_val) == 1) {
                    setenv("DBUS_SESSION_BUS_ADDRESS", dbus_val, 1);
                }
            }
        }
        pclose(fp);
    }
}

static pid_t start_process(const char* process_name) {
    pid_t pid = fork();
    if (pid == 0) {
        // Child: exec process with full GUI environment
        
        // First, ensure HOME is set (needed before reading XAUTHORITY)
        if (!getenv("HOME")) {
            struct passwd* pw = getpwuid(getuid());
            if (pw && pw->pw_dir) {
                setenv("HOME", pw->pw_dir, 1);
            }
        }
        
        // Try to get GUI env from running processes first
        get_gui_env_from_process();
        
        // Then set defaults/fallbacks
        if (!getenv("DISPLAY")) {
            char* disp = find_active_display();
            setenv("DISPLAY", disp, 1);
        }
        
        if (!getenv("DBUS_SESSION_BUS_ADDRESS")) {
            char dbus_addr[128];
            snprintf(dbus_addr, sizeof(dbus_addr), "unix:path=/run/user/%d/bus", (int)getuid());
            setenv("DBUS_SESSION_BUS_ADDRESS", dbus_addr, 1);
        }
        if (!getenv("XDG_RUNTIME_DIR")) {
            char xdg[128];
            snprintf(xdg, sizeof(xdg), "/run/user/%d", (int)getuid());
            setenv("XDG_RUNTIME_DIR", xdg, 1);
        }
        if (!getenv("WAYLAND_DISPLAY")) {
            char wl_path[160];
            snprintf(wl_path, sizeof(wl_path), "%s/wayland-0", getenv("XDG_RUNTIME_DIR") ? getenv("XDG_RUNTIME_DIR") : "/run/user/0");
            if (access(wl_path, F_OK) == 0) {
                setenv("WAYLAND_DISPLAY", "wayland-0", 1);
            }
        }
        if (!getenv("XAUTHORITY")) {
            const char* home = getenv("HOME");
            if (home) {
                char xa[256];
                snprintf(xa, sizeof(xa), "%s/.Xauthority", home);
                if (access(xa, F_OK) == 0) setenv("XAUTHORITY", xa, 1);
            }
        }
        
        // Create new session for GUI access
        setsid();
        
        // Try direct exec
        char* const args[] = {(char*)process_name, NULL};
        execvp(process_name, args);
        
        _exit(127); // exec failed
    } else if (pid > 0) {
        // Give the child a brief moment to exec, then verify it exists
        usleep(200 * 1000);
        if (kill(pid, 0) == 0) {
        return pid;
        } else {
            log_action("Failed to start", process_name, pid, "exec failed");
            return -1;
        }
    } else {
        log_action("Failed to start", process_name, 0, "fork() failed");
        return -1;
    }
}

static void daemonize(void) {
    pid_t pid = fork();
    if (pid < 0) exit(EXIT_FAILURE);
    if (pid > 0) exit(EXIT_SUCCESS);
    if (setsid() < 0) exit(EXIT_FAILURE);
    pid = fork();
    if (pid < 0) exit(EXIT_FAILURE);
    if (pid > 0) exit(EXIT_SUCCESS);
    umask(0);
    if (chdir("/") < 0) {
        // Ignore chdir error in daemon
    }
    close(STDIN_FILENO);
    close(STDOUT_FILENO);
    close(STDERR_FILENO);
}

static int parse_process_list(ProcessInfo* processes, int max_processes, ProcessInfo* old_processes, int old_count) {
    FILE* file = fopen(PROCESS_LIST_FILE, "r");
    if (!file) {
        return 0;
    }
    int count = 0;
    char line[MAX_LINE_LENGTH];
    while (fgets(line, sizeof(line), file) && count < max_processes) {
        if (line[0] == '#' || line[0] == '\n') continue;
        char name[MAX_PROCESS_NAME];
        int cpu_limit, mem_limit;
        if (sscanf(line, "%127s %d %d", name, &cpu_limit, &mem_limit) == 3) {
            strncpy(processes[count].name, name, MAX_PROCESS_NAME - 1);
            processes[count].name[MAX_PROCESS_NAME - 1] = '\0';
            processes[count].cpu_limit = cpu_limit;
            processes[count].memory_limit_mb = mem_limit;
            
            // Preserve PID from old process list if name matches
            processes[count].pid = 0;
            processes[count].is_running = 0;
            processes[count].we_killed_it = 0;
            processes[count].exited_normally = 0;
            
            // Try to find matching process in old list
            for (int i = 0; i < old_count; i++) {
                if (strcmp(old_processes[i].name, processes[count].name) == 0) {
                    // Preserve PID and state if process still exists
                    if (old_processes[i].pid > 0 && check_process_exists(old_processes[i].pid)) {
                        processes[count].pid = old_processes[i].pid;
                        processes[count].is_running = old_processes[i].is_running;
                        processes[count].we_killed_it = old_processes[i].we_killed_it;
                        processes[count].exited_normally = 0;  // Reset if process is running
                    } else {
                        // Process doesn't exist - preserve exit status
                        processes[count].exited_normally = old_processes[i].exited_normally;
                    }
                    break;
                }
            }
            
            count++;
        }
    }
    fclose(file);
    return count;
}

static void handle_signal(int sig) {
    if (sig == SIGTERM || sig == SIGINT) {
        log_action("Daemon", "c_monitor", getpid(), "shutting down");
        exit(EXIT_SUCCESS);
    }
}

// Helper function to call Python helper script
static int call_helper_script(const char* action, const char* arg1, const char* arg2) {
    char cmd[512];
    if (arg2) {
        snprintf(cmd, sizeof(cmd), "python3 %s %s %s %s 2>/dev/null", HELPER_SCRIPT, action, arg1, arg2);
    } else if (arg1) {
        snprintf(cmd, sizeof(cmd), "python3 %s %s %s 2>/dev/null", HELPER_SCRIPT, action, arg1);
    } else {
        snprintf(cmd, sizeof(cmd), "python3 %s %s 2>/dev/null", HELPER_SCRIPT, action);
    }
    return system(cmd);
}

// Check if process is in cooldown
static int check_cooldown(const char* process_name) {
    int result = call_helper_script("check_cooldown", process_name, NULL);
    return (result == 0) ? 0 : 1;  // Returns 1 if in cooldown, 0 if not
}

// Track restart attempt
static void track_restart_c(const char* process_name) {
    call_helper_script("track_restart", process_name, NULL);
}

// Track restart and check if cooldown was activated
static int check_cooldown_after_track(const char* process_name) {
    int result = call_helper_script("check_cooldown_after_track", process_name, NULL);
    return (result == 0) ? 0 : 1;  // Returns 1 if in cooldown, 0 if not
}

// Send email for crash
static void send_email_crash(const char* process_name, pid_t pid, const char* reason) {
    char pid_str[32];
    snprintf(pid_str, sizeof(pid_str), "%d", (int)pid);
    call_helper_script("email_crash", process_name, pid_str);
    if (reason) {
        // Note: reason is not passed to helper script in this simple implementation
        // Could be enhanced to pass reason as third argument
    }
}

// Send email for restart failure
static void send_email_restart_failed(const char* process_name, const char* reason) {
    call_helper_script("email_restart_failed", process_name, reason);
}

int main(int argc, char* argv[]) {
    signal(SIGTERM, handle_signal);
    signal(SIGINT, handle_signal);

    // Only daemonize if not started with --no-daemon flag
    int should_daemonize = 1;
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--no-daemon") == 0) {
            should_daemonize = 0;
            break;
        }
    }
    
    if (should_daemonize) {
        // Become a daemon
        daemonize();
    }
    log_action("Daemon", "c_monitor", getpid(), "started");

    ProcessInfo processes[64];
    ProcessInfo old_processes[64];
    int process_count = 0;

    for (;;) {
        // Save current state before parsing
        memcpy(old_processes, processes, sizeof(processes));
        int old_count = process_count;
        
        process_count = parse_process_list(processes, 64, old_processes, old_count);
        for (int i = 0; i < process_count; ++i) {
            // Check if this process was running in the previous cycle but is now gone
            int was_running_before = 0;
            for (int j = 0; j < old_count; j++) {
                if (strcmp(old_processes[j].name, processes[i].name) == 0 && old_processes[j].pid > 0) {
                    was_running_before = 1;
                    break;
                }
            }
            
            if (processes[i].pid > 0) {
                if (!check_process_exists(processes[i].pid)) {
                    // Process disappeared - check immediately if it's still findable by name
                    // This helps distinguish normal close (might reopen) from kill (completely gone)
                    pid_t new_pid = find_pid_by_name(processes[i].name);
                    
                    if (new_pid > 0 && new_pid != processes[i].pid) {
                        // New instance exists - user might have manually reopened
                        // Or it could be our restart from a previous cycle
                        // Adopt it and don't restart
                        log_action("Stopped", processes[i].name, processes[i].pid, "process replaced - adopted new instance");
                        processes[i].pid = new_pid;
                        processes[i].is_running = 1;
                        log_action("Adopted", processes[i].name, new_pid, "found replacement process");
                        continue;
                    }
                    
                    // No new instance found - check exit signal to determine if should restart
                    // IMPORTANT: By default, assume normal exit (don't restart) unless we confirm crash signal
                    int should_restart = should_restart_on_exit(processes[i].pid, processes[i].name);
                    
                    if (should_restart) {
                        // Process crashed with crash signal (SIGSEGV, SIGABRT, etc.) - restart
                        log_action("Stopped", processes[i].name, processes[i].pid, "process crashed (crash signal detected)");
                        log_action("Detected crash", processes[i].name, processes[i].pid, "");
                        
                        // Send email notification
                        send_email_crash(processes[i].name, processes[i].pid, "crash signal detected");
                        
                        // Check cooldown before restarting
                        if (check_cooldown(processes[i].name)) {
                            log_action("Cooldown", processes[i].name, 0, "too many restarts, cooling down");
                            processes[i].exited_normally = 0;
                            continue;
                        }
                        
                        processes[i].exited_normally = 0;  // Reset flag - this was a crash
                        
                        // Track restart attempt
                        track_restart_c(processes[i].name);
                        
                        // Check if cooldown was activated
                        if (check_cooldown_after_track(processes[i].name)) {
                            log_action("Cooldown", processes[i].name, 0, "cooldown activated after restart tracking");
                            send_email_restart_failed(processes[i].name, "Process entered cooldown due to excessive restarts");
                            continue;
                        }
                        
                        processes[i].pid = start_process(processes[i].name);
                        processes[i].is_running = (processes[i].pid > 0);
                        if (processes[i].is_running) {
                            log_action("Restarted", processes[i].name, processes[i].pid, "after crash signal");
                        } else {
                            log_action("Restart failed", processes[i].name, 0, "unable to start process");
                            send_email_restart_failed(processes[i].name, "Unable to start process after crash");
                        }
                    } else {
                        // Normal exit, window closed, or killed with SIGTERM/SIGKILL - don't restart
                        log_action("Stopped", processes[i].name, processes[i].pid, "normal exit or normal kill - not restarting");
                        processes[i].pid = 0;
                        processes[i].is_running = 0;
                        processes[i].exited_normally = 1;  // Mark as exited normally - don't restart
                    }
                }
            } else {
                // PID is 0 - process not tracked yet
                // If process exited normally, don't restart it
                if (processes[i].exited_normally) {
                    // Process exited normally - don't restart
                    // Only reset the flag if user manually starts the process (we detect a new instance)
                    pid_t existing = find_pid_by_name(processes[i].name);
                    if (existing > 0) {
                        // User manually started it - adopt it and reset the flag
                        processes[i].pid = existing;
                        processes[i].is_running = 1;
                        processes[i].exited_normally = 0;
                        log_action("Adopted", processes[i].name, existing, "user manually started after normal exit");
                    }
                    continue;
                }
                
                // If process was running before but now PID is 0, it might have exited
                // Check if it exited normally before starting a new one
                if (was_running_before && !processes[i].exited_normally) {
                    // Process was running but now gone - check if it exited normally
                    // Find the old PID to check exit status
                    pid_t old_pid = 0;
                    for (int j = 0; j < old_count; j++) {
                        if (strcmp(old_processes[j].name, processes[i].name) == 0) {
                            old_pid = old_processes[j].pid;
                            break;
                        }
                    }
                    
                    if (old_pid > 0) {
                        // Check exit signal for the old PID
                        int should_restart = should_restart_on_exit(old_pid, processes[i].name);
                        if (!should_restart) {
                            // Normal exit - mark it and don't restart
                            log_action("Stopped", processes[i].name, old_pid, "normal exit or normal kill - not restarting");
                            processes[i].exited_normally = 1;
                            continue;
                        } else {
                            // Crash signal - restart it
                            log_action("Stopped", processes[i].name, old_pid, "process crashed (crash signal detected)");
                            log_action("Detected crash", processes[i].name, old_pid, "");
                            
                            // Send email notification
                            send_email_crash(processes[i].name, old_pid, "crash signal detected");
                            
                            // Check cooldown before restarting
                            if (check_cooldown(processes[i].name)) {
                                log_action("Cooldown", processes[i].name, 0, "too many restarts, cooling down");
                                processes[i].exited_normally = 0;
                                continue;
                            }
                            
                            processes[i].exited_normally = 0;
                            
                            // Track restart attempt
                            track_restart_c(processes[i].name);
                            
                            // Check if cooldown was activated
                            if (check_cooldown_after_track(processes[i].name)) {
                                log_action("Cooldown", processes[i].name, 0, "cooldown activated after restart tracking");
                                send_email_restart_failed(processes[i].name, "Process entered cooldown due to excessive restarts");
                                continue;
                            }
                            
                            processes[i].pid = start_process(processes[i].name);
                            processes[i].is_running = (processes[i].pid > 0);
                            if (processes[i].is_running) {
                                log_action("Restarted", processes[i].name, processes[i].pid, "after crash signal");
                            } else {
                                log_action("Restart failed", processes[i].name, 0, "unable to start process");
                                send_email_restart_failed(processes[i].name, "Unable to start process after crash");
                            }
                            continue;
                        }
                    }
                }
                
                // Check if we already started this process in this cycle (avoid duplicate starts)
                int already_started_this_cycle = 0;
                for (int j = 0; j < i; j++) {
                    if (strcmp(processes[j].name, processes[i].name) == 0 && processes[j].pid > 0) {
                        // Same process name already has a PID in this cycle - use that PID
                        processes[i].pid = processes[j].pid;
                        processes[i].is_running = processes[j].is_running;
                        processes[i].exited_normally = 0;  // Reset exit status
                        already_started_this_cycle = 1;
                        break;
                    }
                }
                
                if (!already_started_this_cycle && processes[i].pid == 0) {
                    // Try to adopt an already running process first
                    pid_t existing = find_pid_by_name(processes[i].name);
                    if (existing > 0) {
                        processes[i].pid = existing;
                        processes[i].is_running = 1;
                        // Check if this is a new adoption (PID was 0 before parsing)
                        int was_new = 1;
                        for (int j = 0; j < old_count; j++) {
                            if (strcmp(old_processes[j].name, processes[i].name) == 0 && old_processes[j].pid > 0) {
                                was_new = 0;
                                break;
                            }
                        }
                        if (was_new) {
                            log_action("Adopted", processes[i].name, existing, "found existing process");
                        }
                    } else {
                        // Double-check before starting (avoid race condition)
                        usleep(50 * 1000); // 50ms delay
                        existing = find_pid_by_name(processes[i].name);
                        if (existing > 0) {
                            // Process was just started
                            processes[i].pid = existing;
                            processes[i].is_running = 1;
                            log_action("Adopted", processes[i].name, existing, "found process started by another monitor");
                        } else {
                            // Start only if still not running
                            // Final check: make absolutely sure it's not running
                            existing = find_pid_by_name(processes[i].name);
                            if (existing > 0) {
                                processes[i].pid = existing;
                                processes[i].is_running = 1;
                                log_action("Adopted", processes[i].name, existing, "found process (final check)");
                            } else {
                                // Really start it now
                                pid_t new_pid = start_process(processes[i].name);
                                if (new_pid > 0) {
                                    processes[i].pid = new_pid;
                                    processes[i].is_running = 1;
                                    processes[i].exited_normally = 0;  // Reset exit status when starting
                                    log_action("Started", processes[i].name, new_pid, "initial start");
                                } else {
                                    log_action("Start failed", processes[i].name, 0, "unable to start process");
                                }
                            }
                        }
                    }
                }
            }
        }
        sleep(5);
    }
    return 0;
}






