import tkinter as tk
import time

def show_status_pop(runtime, start_time, system_active, system_paused, already_opened, status_window):
    remaining = max(0, int(runtime - (time.time() - start_time)))

    status_text = f"""
SYSTEM STATUS

Active   : {system_active}
Paused   : {system_paused}
Opened   : {already_opened}

Time Left : {remaining // 60} min {remaining % 60} sec

Hotkeys:
Ctrl+Alt+W = Open Apps
Ctrl+Alt+S = Reset
Ctrl+Alt+P = Pause
Ctrl+Alt+Q = Shutdown
Ctrl+Alt+I = Status
"""

    if status_window and status_window.winfo_exists():
        status_window.destroy()

    status_window = tk.Tk()
    status_window.title("System Status")
    status_window.geometry("360x300")
    status_window.resizable(False, False)

    label = tk.Label(status_window, text=status_text, font=("Consolas", 11), justify="left")
    label.pack(padx=15, pady=15)

    status_window.after(4000, status_window.destroy)
    status_window.mainloop()