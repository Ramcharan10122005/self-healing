#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk, messagebox
import psutil
import os
import subprocess
import signal
import time

PROCESS_LIST_FILE = 'process_list.txt'
LOG_FILE = 'healing.log'
REFRESH_MS = 3000

class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title('Self-Healing Process Manager')
        self.root.geometry('1000x650')

        self.processes: dict[str, dict] = {}

        self._build_ui()
        self._load_process_list()
        self._refresh()

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        title = ttk.Label(main, text='Self-Healing Process Manager', font=('Arial', 16, 'bold'))
        title.pack(pady=(0, 10))

        content = ttk.Frame(main)
        content.pack(fill=tk.BOTH, expand=True)

        # Left: process table
        left = ttk.LabelFrame(content, text='Processes', padding=10)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        cols = ('Process', 'PID', 'Status', 'CPU %', 'Memory MB')
        self.tree = ttk.Treeview(left, columns=cols, show='headings')
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=120)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll = ttk.Scrollbar(left, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Right: log
        right = ttk.LabelFrame(content, text='Healing Log', padding=10)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.log = tk.Text(right, height=30, width=50, bg='#1e1e1e', fg='#ffffff')
        self.log.pack(fill=tk.BOTH, expand=True)

        # Controls
        controls = ttk.Frame(main)
        controls.pack(fill=tk.X, pady=(10, 0))
        self.add_btn = ttk.Button(controls, text='Add process', command=self._add_process)
        self.rm_btn = ttk.Button(controls, text='Remove process', command=self._remove_process)
        self.restart_btn = ttk.Button(controls, text='Force restart', command=self._force_restart)
        self.refresh_btn = ttk.Button(controls, text='Refresh', command=self._refresh)
        for w in (self.add_btn, self.rm_btn, self.restart_btn, self.refresh_btn):
            w.pack(side=tk.LEFT, padx=5)

    def _load_process_list(self) -> None:
        self.processes.clear()
        if not os.path.exists(PROCESS_LIST_FILE):
            return
        with open(PROCESS_LIST_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split()
                if len(parts) >= 3:
                    try:
                        # Last two parts are cpu_limit and mem_limit
                        # Everything before that is the process name/command
                        cpu = int(parts[-2])
                        mem = int(parts[-1])
                        name = parts[0]  # Use just the executable name for display
                        self.processes[name] = {'cpu': cpu, 'mem': mem, 'pid': None, 'status': 'Unknown', 'cpu_pct': 0.0, 'mem_mb': 0.0}
                    except (ValueError, IndexError):
                        # Skip invalid lines
                        continue

    def _find_pid(self, name: str):
        for p in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if p.info['name'] == name or (p.info['cmdline'] and name in ' '.join(p.info['cmdline'])):
                    return p.info['pid']
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return None

    def _stats(self, pid: int):
        try:
            proc = psutil.Process(pid)
            cpu = proc.cpu_percent(interval=0.1)
            mem = proc.memory_info().rss / (1024 * 1024)
            return cpu, mem
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return None, None

    def _update_processes(self) -> None:
        self._load_process_list()
        for name, cfg in self.processes.items():
            pid = self._find_pid(name)
            if pid:
                cfg['pid'] = pid
                cpu, mem = self._stats(pid)
                if cpu is not None:
                    cfg['status'] = 'Running'
                    cfg['cpu_pct'] = cpu
                    cfg['mem_mb'] = mem
                else:
                    cfg['status'] = 'Crashed'
                    cfg['cpu_pct'] = 0.0
                    cfg['mem_mb'] = 0.0
            else:
                cfg['pid'] = None
                cfg['status'] = 'Not Running'
                cfg['cpu_pct'] = 0.0
                cfg['mem_mb'] = 0.0

    def _refresh_table(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        for name, cfg in self.processes.items():
            self.tree.insert('', 'end', values=(name, cfg['pid'] or 'N/A', cfg['status'], f"{cfg['cpu_pct']:.1f}", f"{cfg['mem_mb']:.1f}"))

    def _refresh_log(self) -> None:
        if not os.path.exists(LOG_FILE):
            return
        with open(LOG_FILE, 'r') as f:
            lines = f.readlines()[-400:]
        self.log.delete('1.0', tk.END)
        for line in lines:
            self.log.insert(tk.END, line)
        self.log.see(tk.END)

    def _refresh(self) -> None:
        self._update_processes()
        self._refresh_table()
        self._refresh_log()
        self.root.after(REFRESH_MS, self._refresh)

    def _add_process(self) -> None:
        win = tk.Toplevel(self.root)
        win.title('Add process')
        frm = ttk.Frame(win, padding=10)
        frm.pack(fill=tk.BOTH, expand=True)
        name_v, cpu_v, mem_v = tk.StringVar(), tk.StringVar(value='80'), tk.StringVar(value='200')
        for i, (label, var) in enumerate((('Process', name_v), ('CPU %', cpu_v), ('Memory MB', mem_v))):
            ttk.Label(frm, text=label+':').grid(row=i, column=0, sticky='w', pady=4)
            ttk.Entry(frm, textvariable=var).grid(row=i, column=1, sticky='ew', pady=4)
        frm.columnconfigure(1, weight=1)
        def save():
            name = name_v.get().strip()
            try:
                cpu = int(cpu_v.get().strip()); mem = int(mem_v.get().strip())
                assert name
            except Exception:
                messagebox.showerror('Error', 'Invalid inputs'); return
            self.processes[name] = {'cpu': cpu, 'mem': mem, 'pid': None, 'status': 'Unknown', 'cpu_pct': 0.0, 'mem_mb': 0.0}
            self._save_process_list(); win.destroy(); self._refresh()
        ttk.Button(frm, text='Save', command=save).grid(row=3, column=0, pady=8)
        ttk.Button(frm, text='Cancel', command=win.destroy).grid(row=3, column=1, pady=8)

    def _remove_process(self) -> None:
        focus = self.tree.focus()
        if not focus:
            messagebox.showwarning('Warning', 'Select a process'); return
        name = self.tree.item(focus)['values'][0]
        if messagebox.askyesno('Confirm', f'Remove {name}?'):
            self.processes.pop(name, None)
            self._save_process_list(); self._refresh()

    def _force_restart(self) -> None:
        focus = self.tree.focus()
        if not focus:
            messagebox.showwarning('Warning', 'Select a process'); return
        name = self.tree.item(focus)['values'][0]
        pid = self.processes.get(name, {}).get('pid')
        if pid:
            try:
                os.kill(pid, signal.SIGTERM); time.sleep(0.5)
                try: os.kill(pid, 0); os.kill(pid, signal.SIGKILL)
                except OSError: pass
            except OSError: pass
        try:
            subprocess.Popen([name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            messagebox.showerror('Error', f'Failed to restart {name}: {e}')

    def _save_process_list(self) -> None:
        with open(PROCESS_LIST_FILE, 'w') as f:
            f.write('# process_name cpu_limit memory_limit_MB\n')
            for name, cfg in self.processes.items():
                f.write(f"{name} {cfg['cpu']} {cfg['mem']}\n")


def main() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()

if __name__ == '__main__':
    main()


