def normalize_apps(reg_apps, menu_apps):
    seen = set()
    result = []

    for app in reg_apps + menu_apps:
        name = app.get("name", "").strip()
        if not name or name.lower() in seen:
            continue

        seen.add(name.lower())
        result.append(app)

    return result