import os
import json
from PIL import ImageFont

class JxConfig:
    def __init__(self, config_path=None):
        base_dir = os.path.dirname(os.path.abspath(__file__))

        # If path is None, default, or relative, resolve relative to script directory
        if config_path is None:
            config_path = os.path.join(base_dir, "jx32.json")
        elif not os.path.isabs(config_path):
            candidate = os.path.join(base_dir, config_path)
            if os.path.exists(candidate):
                config_path = candidate

        self.config_path = os.path.abspath(config_path)

        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config file not found at expected location: {self.config_path}")

        with open(self.config_path, "r") as f:
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
        scenes = self.data.get("scenes", {})
        if "up_next" not in scenes:
            raise KeyError(f"'up_next' missing from 'scenes' in {self.config_path}")

        scene = scenes["up_next"]
        
        if "layout" not in scene:
            keys_found = list(scene.keys())
            raise KeyError(
                f"Missing 'layout' block in 'scenes.up_next' ({self.config_path}). "
                f"Keys found in scene: {keys_found}"
            )

        if "colors" not in scene:
            raise KeyError(f"Missing 'colors' block in 'scenes.up_next' ({self.config_path})")

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
            "duration": scene.get("duration", 5),
            "animations": scene.get("animations", {}),
            "colors": colors,
            "layout": layout
        }