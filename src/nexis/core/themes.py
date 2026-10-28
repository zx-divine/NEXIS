"""Validated, UI-independent appearance preferences and semantic color tokens."""
import re

THEMES = {
    "og": "Original Crimson Red", "midnight": "Dark Black", "arctic": "Clean White",
    "cyber": "Electric Blue", "matrix": "Emerald Green", "custom": "Custom Colors",
}
CUSTOM_DEFAULT = {"primary": "#FF2338", "background": "#080304",
                  "accent": "#D4AF37", "text": "#F4E9E5"}
BASES = {
    "og": CUSTOM_DEFAULT,
    "midnight": dict(primary="#D4D8E0", background="#090B0E", accent="#BEC7D5", text="#F0F2F5"),
    "arctic": dict(primary="#005DB8", background="#F5F7FA", accent="#6742A0", text="#18212C"),
    "cyber": dict(primary="#43BAFF", background="#050D20", accent="#80DEFF", text="#E5F3FF"),
    "matrix": dict(primary="#36E580", background="#040E09", accent="#B0EF6D", text="#E4F7E9"),
}


def theme_id(value):
    return {"dark": "og", "light": "arctic"}.get(value, value)


def rgb(value):
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise ValueError("Use a hexadecimal color such as #43BAFF (six digits).")
    return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))


def luminance(value):
    channels = [v / 255 for v in rgb(value)]
    return sum(w * (v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4)
               for w, v in zip((.2126, .7152, .0722), channels))


def contrast(a, b):
    light, dark = sorted((luminance(a), luminance(b)), reverse=True)
    return (light + .05) / (dark + .05)


def mix(a, b, amount):
    return "#" + "".join(f"{round(x * (1 - amount) + y * amount):02X}" for x, y in zip(rgb(a), rgb(b)))


def readable(color, background, minimum=4.5):
    if contrast(color, background) >= minimum:
        return color
    endpoint = max(("#000000", "#FFFFFF"), key=lambda x: contrast(x, background))
    for step in range(1, 101):
        adjusted = mix(color, endpoint, step / 100)
        if contrast(adjusted, background) >= minimum:
            return adjusted
    return endpoint


def validate_custom(value):
    if not isinstance(value, dict) or set(value) != set(CUSTOM_DEFAULT):
        raise ValueError("A custom theme needs primary, background, accent and text colors.")
    result = {key: "#" + "".join(f"{v:02X}" for v in rgb(color)) for key, color in value.items()}
    panel = mix(result["background"], result["text"], .04)
    hover = mix(result["background"], result["text"], .09)
    if min(contrast(result["text"], bg) for bg in (result["background"], panel, hover)) < 4.5:
        raise ValueError("Text must have at least 4.5:1 contrast on backgrounds and panels. Choose darker or lighter text.")
    return result


def tokens(selected="og", custom=None):
    selected = theme_id(selected)
    if selected not in THEMES:
        raise ValueError("Choose a built-in or custom theme.")
    base = validate_custom(CUSTOM_DEFAULT if custom is None else custom) if selected == "custom" else BASES[selected]
    bg, text = base["background"], base["text"]
    panel, hover = mix(bg, text, .04), mix(bg, text, .09)
    result = dict(base, panel=panel, hover=hover,
                  primary=readable(base["primary"], hover), accent=readable(base["accent"], hover),
                  muted=readable(mix(text, bg, .3), hover), border=readable(mix(text, bg, .6), bg, 3))
    result.update(on_primary=max(("#000000", "#FFFFFF"), key=lambda c: contrast(c, result["primary"])),
                  success=readable("#32BA72", hover), warning=readable("#D4A320", hover),
                  error=readable("#E63754", hover), grid=mix(bg, text, .15), glow=mix(base["primary"], text, .65))
    if selected == "og":
        result.update(panel="#0D0506", hover="#2B0B10", border=readable("#8B0000", bg, 3), grid="#341014")
    return result
