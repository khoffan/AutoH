import customtkinter as ctk
from ui.config_window import configure_customtkinter, show_configuration_window
from ui.theme import APP_THEME


def get_user_configuration(master, on_modes_changed=None, on_close=None, startup=False):
    return show_configuration_window(
        master,
        on_modes_changed=on_modes_changed,
        on_close=on_close,
        startup=startup,
    )


def _run_configuration():
    configure_customtkinter()
    root = ctk.CTk(fg_color=APP_THEME["window_bg"])
    root.withdraw()
    show_configuration_window(root, on_close=lambda _has_modes: root.destroy(), startup=True)
    root.mainloop()


def show_snackbar_standalone(message):
    configure_customtkinter()
    root = ctk.CTk(fg_color=APP_THEME["window_bg"])
    root.withdraw()

    window = ctk.CTkToplevel(root, fg_color=APP_THEME["surface"])
    window.title("AutoH")
    window.geometry("360x140")
    window.resizable(False, False)
    window.attributes("-topmost", True)

    label = ctk.CTkLabel(
        window,
        text=message,
        wraplength=300,
        justify="center",
        font=ctk.CTkFont(size=15, weight="bold"),
        text_color=APP_THEME["text"],
    )
    label.pack(expand=True, fill="both", padx=20, pady=20)

    window.after(2200, root.destroy)
    root.mainloop()
