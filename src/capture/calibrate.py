from .window import get_screen_resolution


def relative_rect(rel, screen):
    sw, sh = screen
    return (
        int(rel["x"] * sw),
        int(rel["y"] * sh),
        int(rel["w"] * sw),
        int(rel["h"] * sh),
    )
