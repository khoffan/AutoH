import tkinter as tk

def select_apps_ui(apps):
    selected = []
    filtered_apps = apps.copy()

    root = tk.Tk()
    root.title("Select Applications")
    root.geometry("520x650")

    # 🔍 Search box
    search_var = tk.StringVar()

    search_entry = tk.Entry(root, textvariable=search_var)
    search_entry.pack(fill=tk.X, padx=10, pady=5)
    search_entry.focus()

    # 📋 Listbox
    lb = tk.Listbox(root, selectmode=tk.MULTIPLE)
    lb.pack(fill=tk.BOTH, expand=True, padx=10)

    def refresh_list():
        lb.delete(0, tk.END)
        for app in filtered_apps:
            lb.insert(tk.END, app["name"])

    refresh_list()

    def on_search(*_):
        nonlocal filtered_apps
        keyword = search_var.get().lower()

        if not keyword:
            filtered_apps = apps.copy()
        else:
            filtered_apps = [
                app for app in apps
                if keyword in app["name"].lower()
            ]

        refresh_list()

    search_var.trace_add("write", on_search)

    def confirm():
        for i in lb.curselection():
            selected.append(filtered_apps[i])
        root.destroy()

    tk.Button(root, text="Confirm", command=confirm).pack(pady=10)

    root.mainloop()
    return selected