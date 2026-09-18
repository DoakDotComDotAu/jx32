import json
from PIL import ImageFont

class JxConfig:
    def __init__(self, config_path="jx32.json"):
        with open(config_path, "r") as f:
            self.data = json.load(f)

        # Server
        self.jf_url = self.data["server"]["url"]
        self.jf_api = self.data["server"]["api_key"]
        self.jf_playlist = self.data["server"]["playlist_id"]

        # Display
        self.width = self.data["display"]["width"]
        self.height = self.data["display"]["height"]
        self.fullscreen = self.data["display"]["fullscreen"]
        self.mpv_socket = self.data["display"]["mpv_socket"]
        self.base_res = self.data["display"]["base_resolution"]

        # Global Fonts
        self.fonts = self._load_fonts()

    def scale(self, value):
        """Scale a 1080p layout value to the current resolution."""
        return int(value * (self.height / self.base_res))

    def _load_fonts(self):
        bold = self.data["fonts"]["bold"]
        regular = self.data["fonts"]["regular"]
        try:
            return {
                "big":       ImageFont.truetype(bold,    self.scale(64)),
                "med":       ImageFont.truetype(regular, self.scale(30)),
                "sm":        ImageFont.truetype(regular, self.scale(20)),
                "tag":       ImageFont.truetype(bold,    self.scale(24)),
                "countdown": ImageFont.truetype(regular, self.scale(22)),
            }
        except Exception:
            f = ImageFont.load_default()
            return {k: f for k in ("big", "med", "sm", "tag", "countdown")}

    def get_up_next_scene(self):
        """Processes the Up Next JSON scene into usable layout coordinates and RGBA tuples."""
        scene = self.data["scenes"]["up_next"]
        l = scene["layout"]
        c = scene["colors"]
        s = self.scale
        w, h = self.width, self.height

        colors = {
            "bg_start": c["bg_gradient_start"],
            "bg_end": c["bg_gradient_end"],
            "accent": tuple(c["accent"]),
            "text_primary": tuple(c["text_primary"]),
            "text_secondary": tuple(c["text_secondary"]),
            "countdown": tuple(c["countdown"]),
            "bar_track": tuple(c["bar_track"]),
        }

        layout = {
            "accent_x1":      s(l["accent_x"]),
            "accent_x2":      s(l["accent_x"] + l["accent_w"]),
            "accent_y1":      s(l["accent_y_pad"]),
            "accent_y2":      h - s(l["accent_y_pad"]),
            "tag_x":          s(l["content_x"]),
            "tag_y":          s(l["tag_y"]),
            "title_x":        s(l["content_x"]),
            "title_y":        s(l["title_y"]),
            "title_wrap":     w // 2 - s(l["half_width_pad"]),
            "duration_x":     s(l["content_x"]),
            "duration_y":     s(l["duration_y"]),
            "bar_x":          s(l["content_x"]),
            "bar_y":          h - s(l["bar_bottom_pad"]),
            "bar_w":          w // 2 - s(l["half_width_pad"]),
            "bar_h":          s(l["bar_h"]),
            "countdown_x":    s(l["content_x"]),
            "countdown_y":    h - s(l["countdown_bottom_pad"]),
            "thumb_panel_x":  w // 2 + s(l["thumb_x_offset"]),
            "thumb_max_w":    w // 2 - s(l["half_width_pad"]),
            "thumb_max_h":    h - s(l["thumb_y_pad"]),
        }

        return {
            "duration": scene["duration"],
            "animations": scene["animations"],
            "colors": colors,
            "layout": layout
        }