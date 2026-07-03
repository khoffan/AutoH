APP_THEME = {
    "appearance_mode": "light",
    "window_bg": "#F5F7FA",
    "surface": "#FFFFFF",
    "surface_alt": "#EEF2F6",
    "panel_border": "#D6DCE5",
    "text": "#17212B",
    "text_muted": "#5B6877",
    "primary": "#1F6FEB",
    "primary_hover": "#195CC5",
    "primary_text": "#FFFFFF",
    "accent": "#0F9D7A",
    "accent_hover": "#0C7C60",
    "danger": "#C4382A",
    "danger_hover": "#A32F24",
    "danger_text": "#FFFFFF",
    "success": "#1B8F4D",
    "warning": "#B7791F",
    "selection": "#DCEBFF",
    "input_bg": "#FFFFFF",
    "input_border": "#C5CED8",
}

WINDOW_SIZES = {
    "config": "1180x760",
    "status": "600x800",
}

PADDING = {
    "outer": 20,
    "panel": 16,
    "section": 12,
    "control": 10,
}


def parse_window_size(size_text):
    width_text, height_text = size_text.lower().split("x", maxsplit=1)
    return int(width_text), int(height_text)


def fit_and_center_window(window, preferred_size, min_size=None, margin=80):
    pref_width, pref_height = parse_window_size(preferred_size)
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()

    max_width = max(360, screen_width - margin)
    max_height = max(280, screen_height - margin)
    width = min(pref_width, max_width)
    height = min(pref_height, max_height)

    if min_size is not None:
        min_width, min_height = min_size
        width = max(width, min(min_width, screen_width))
        height = max(height, min(min_height, screen_height))
        window.minsize(min(min_width, screen_width), min(min_height, screen_height))

    pos_x = max(0, (screen_width - width) // 2)
    pos_y = max(0, (screen_height - height) // 2)
    window.geometry(f"{width}x{height}+{pos_x}+{pos_y}")
