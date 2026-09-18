import tkinter as tk
from tkinter import filedialog
import json
import os
from PIL import Image, ImageTk

CONFIG_FILE = "jx32.json"
SCALE = 0.5  # Viewport scale (1080p -> 960x540)

BG_MAIN = "#1e1e1e"
BG_PANEL = "#252526"
FG_TEXT = "#d4d4d4"
ACCENT = "#007acc"
HANDLE_COLOR = "#ffffff"

class JxConfUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("jx32 Scene Configurator")
        self.geometry("1100x820")
        self.configure(bg=BG_MAIN)
        
        # Load or initialize config
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                self.data = json.load(f)
        else:
            self.data = {"display": {"base_resolution": 1080}, "scenes": {"up_next": {"elements": {}}}}

        # Migrate old layout to absolute elements if necessary
        scene = self.data.setdefault("scenes", {}).setdefault("up_next", {})
        if "elements" not in scene:
            # Provide some default absolute blocks to start with
            scene["elements"] = {
                "accent": {"type": "rect", "x": 60, "y": 180, "w": 8, "h": 720, "color": "#e50914"},
                "tag": {"type": "text", "x": 90, "y": 210, "w": 200, "h": 40, "text": "UP NEXT", "color": "#e50914"},
                "title": {"type": "text", "x": 90, "y": 280, "w": 600, "h": 80, "text": "Video Title Here", "color": "#ffffff"},
                "duration": {"type": "text", "x": 90, "y": 460, "w": 300, "h": 40, "text": "Duration: 24:00", "color": "#aaaaaa"},
                "bar": {"type": "rect", "x": 90, "y": 975, "w": 840, "h": 8, "color": "#323232"},
                "countdown": {"type": "text", "x": 90, "y": 1005, "w": 200, "h": 30, "text": "Starting in 5s", "color": "#aaaaaa"},
                "thumb": {"type": "rect", "x": 1040, "y": 200, "w": 840, "h": 680, "color": "#222222"}
            }
            
        self.elements = scene["elements"]
        self.base_w = 1920
        self.base_h = self.data["display"].get("base_resolution", 1080)
        self.cw = int(self.base_w * SCALE)
        self.ch = int(self.base_h * SCALE)
        
        self.selected_id = None
        self.drag_state = {"action": None, "x": 0, "y": 0, "orig_w": 0, "orig_h": 0, "orig_x": 0, "orig_y": 0}
        self.image_cache = {} # Keeps PIL PhotoImages alive
        
        self.setup_ui()
        self.load_images()
        self.redraw()

    def setup_ui(self):
        # Preview Canvas
        prev_frame = tk.Frame(self, bg=BG_MAIN)
        prev_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        self.canvas = tk.Canvas(prev_frame, width=self.cw, height=self.ch, bg="#000000", highlightthickness=1)
        self.canvas.pack()
        
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        
        # Docks
        docks = tk.Frame(self, bg=BG_MAIN, height=200)
        docks.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=10)
        
        # Sources List
        src_dock = tk.Frame(docks, bg=BG_PANEL)
        src_dock.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        tk.Label(src_dock, text="Sources", bg="#333", fg="#fff", anchor="w").pack(fill=tk.X)
        self.listbox = tk.Listbox(src_dock, bg="#1c1c1c", fg=FG_TEXT, borderwidth=0)
        self.listbox.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self.listbox.bind("<<ListboxSelect>>", self.on_list_select)
        
        # Properties
        prop_dock = tk.Frame(docks, bg=BG_PANEL)
        prop_dock.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        tk.Label(prop_dock, text="Properties", bg="#333", fg="#fff", anchor="w").pack(fill=tk.X)
        self.lbl_props = tk.Label(prop_dock, text="Select an element", bg=BG_PANEL, fg=FG_TEXT, justify=tk.LEFT)
        self.lbl_props.pack(pady=10, padx=10, anchor="nw")
        
        # Controls
        ctrl_dock = tk.Frame(docks, bg=BG_PANEL)
        ctrl_dock.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        tk.Label(ctrl_dock, text="Controls", bg="#333", fg="#fff", anchor="w").pack(fill=tk.X)
        tk.Button(ctrl_dock, text="Add Image", command=self.add_image, bg="#444", fg="#fff").pack(fill=tk.X, padx=10, pady=5)
        tk.Button(ctrl_dock, text="Save Config", command=self.save_config, bg=ACCENT, fg="#fff").pack(fill=tk.X, padx=10, pady=5)

    def s(self, val): return int(val * SCALE)
    def us(self, val): return int(val / SCALE)

    def load_images(self):
        for eid, el in self.elements.items():
            if el["type"] == "image" and os.path.exists(el["path"]):
                img = Image.open(el["path"]).resize((self.s(el["w"]), self.s(el["h"])), Image.LANCZOS)
                self.image_cache[eid] = ImageTk.PhotoImage(img)

    def refresh_listbox(self):
        self.listbox.delete(0, tk.END)
        for eid in self.elements:
            self.listbox.insert(tk.END, eid)
            if eid == self.selected_id:
                self.listbox.selection_set(tk.END)

    def redraw(self):
        self.canvas.delete("all")
        self.refresh_listbox()
        
        for eid, el in self.elements.items():
            x, y, w, h = self.s(el["x"]), self.s(el["y"]), self.s(el["w"]), self.s(el["h"])
            
            if el["type"] == "rect":
                self.canvas.create_rectangle(x, y, x+w, y+h, fill=el.get("color", "#fff"), outline="", tags=(eid, "item"))
            elif el["type"] == "text":
                self.canvas.create_rectangle(x, y, x+w, y+h, outline="#444", dash=(2,2), tags=(eid, "item")) # Bounding box
                self.canvas.create_text(x, y, text=el.get("text",""), fill=el.get("color", "#fff"), font=("Arial", max(10, int(h*0.8))), anchor="nw", tags=(eid, "item"))
            elif el["type"] == "image":
                if eid in self.image_cache:
                    self.canvas.create_image(x, y, image=self.image_cache[eid], anchor="nw", tags=(eid, "item"))
                else:
                    self.canvas.create_rectangle(x, y, x+w, y+h, fill="#555", tags=(eid, "item"))
                    self.canvas.create_text(x+w//2, y+h//2, text="IMG Missing", fill="#f00", tags=(eid, "item"))

        # Draw handles for selected item
        if self.selected_id and self.selected_id in self.elements:
            el = self.elements[self.selected_id]
            x, y, w, h = self.s(el["x"]), self.s(el["y"]), self.s(el["w"]), self.s(el["h"])
            hw = 4 # handle width
            self.canvas.create_rectangle(x-hw, y-hw, x+hw, y+hw, fill=HANDLE_COLOR, tags=(self.selected_id, "handle_tl"))
            self.canvas.create_rectangle(x+w-hw, y-hw, x+w+hw, y+hw, fill=HANDLE_COLOR, tags=(self.selected_id, "handle_tr"))
            self.canvas.create_rectangle(x-hw, y+h-hw, x+hw, y+h+hw, fill=HANDLE_COLOR, tags=(self.selected_id, "handle_bl"))
            self.canvas.create_rectangle(x+w-hw, y+h-hw, x+w+hw, y+h+hw, fill=HANDLE_COLOR, tags=(self.selected_id, "handle_br"))
            
            self.lbl_props.config(text=f"ID: {self.selected_id}\nType: {el['type']}\nX: {el['x']}  |  Y: {el['y']}\nW: {el['w']}  |  H: {el['h']}")

    def on_list_select(self, event):
        if not self.listbox.curselection(): return
        self.selected_id = self.listbox.get(self.listbox.curselection()[0])
        self.redraw()

    def on_press(self, event):
        tags = self.canvas.gettags(self.canvas.find_withtag(tk.CURRENT))
        if not tags:
            self.selected_id = None
            self.redraw()
            return

        eid = tags[0]
        self.selected_id = eid
        el = self.elements[eid]
        
        # Determine drag action (move vs resize corner)
        action = "move"
        for t in tags:
            if t.startswith("handle_"): action = t

        self.drag_state = {
            "action": action, "x": event.x, "y": event.y,
            "orig_x": el["x"], "orig_y": el["y"], 
            "orig_w": el["w"], "orig_h": el["h"]
        }
        self.redraw()

    def on_drag(self, event):
        if not self.selected_id or not self.drag_state["action"]: return
        
        el = self.elements[self.selected_id]
        dx, dy = self.us(event.x - self.drag_state["x"]), self.us(event.y - self.drag_state["y"])
        st = self.drag_state
        
        if st["action"] == "move":
            el["x"] = st["orig_x"] + dx
            el["y"] = st["orig_y"] + dy
        else:
            # Resizing
            keep_aspect = not (event.state & 0x0001) # Shift key breaks aspect ratio
            new_w, new_h = st["orig_w"], st["orig_h"]
            new_x, new_y = st["orig_x"], st["orig_y"]
            
            if "br" in st["action"]: new_w += dx; new_h += dy
            elif "tr" in st["action"]: new_w += dx; new_y += dy; new_h -= dy
            elif "bl" in st["action"]: new_x += dx; new_w -= dx; new_h += dy
            elif "tl" in st["action"]: new_x += dx; new_w -= dx; new_y += dy; new_h -= dy
            
            if keep_aspect and st["orig_h"] != 0:
                ratio = st["orig_w"] / st["orig_h"]
                # Dominate by whichever axis moved more
                if abs(dx) > abs(dy): new_h = int(new_w / ratio)
                else: new_w = int(new_h * ratio)
                
                # Correct X/Y shifts for top/left handles when locked
                if "tl" in st["action"] or "bl" in st["action"]: new_x = st["orig_x"] + (st["orig_w"] - new_w)
                if "tl" in st["action"] or "tr" in st["action"]: new_y = st["orig_y"] + (st["orig_h"] - new_h)

            el["w"], el["h"] = max(10, new_w), max(10, new_h)
            el["x"], el["y"] = new_x, new_y
            
            if el["type"] == "image": self.load_images() # Reload PIL image at new scale

        self.redraw()

    def on_release(self, event):
        self.drag_state["action"] = None

    def add_image(self):
        path = filedialog.askopenfilename(filetypes=[("Images", "*.png;*.jpg;*.jpeg")])
        if path:
            eid = f"img_{len(self.elements)}"
            self.elements[eid] = {"type": "image", "path": path, "x": 0, "y": 0, "w": 400, "h": 400}
            self.selected_id = eid
            self.load_images()
            self.redraw()

    def save_config(self):
        self.data["scenes"]["up_next"]["elements"] = self.elements
        with open(CONFIG_FILE, "w") as f:
            json.dump(self.data, f, indent=2)
        self.lbl_props.config(text="Config Saved!")

if __name__ == "__main__":
    app = JxConfUI()
    app.mainloop()