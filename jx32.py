import requests
import subprocess
import socket
import json
import time
import io
import os
import tempfile
from PIL import Image, ImageDraw, ImageFont
from jx32_config import JxConfig

cfg = JxConfig("jx32.json")
HEADERS = {"X-Emby-Token": cfg.jf_api}

def get_raw_elements():
    """Reads elements directly from cfg.data to avoid CWD path mismatches."""
    return cfg.data.get("scenes", {}).get("up_next", {}).get("elements", {})

# ─── Jellyfin Helpers ─────────────────────────────────────────────────────────

def get_user_id():
    r = requests.get(f"{cfg.jf_url}/Users", headers=HEADERS, params={"api_key": cfg.jf_api})
    r.raise_for_status()
    return r.json()[0]["Id"]

def get_playlist_items():
    r = requests.get(
        f"{cfg.jf_url}/Playlists/{cfg.jf_playlist}/Items",
        headers=HEADERS,
        params={
            "api_key": cfg.jf_api,
            "Fields": "MediaSources,Overview,SeriesName,SeriesId",
            "UserId": get_user_id(),
        }
    )
    r.raise_for_status()
    return r.json()["Items"]

def get_stream_url(item_id):
    return (
        f"{cfg.jf_url}/Videos/{item_id}/stream"
        f"?api_key={cfg.jf_api}"
        f"&VideoCodec=h264"
        f"&AudioCodec=aac"
        f"&MaxWidth={cfg.width}"
        f"&MaxHeight={cfg.height}"
    )

def get_thumbnail(item_id, series_id=None, width=700):
    targets = [(item_id, "Primary"), (item_id, "Backdrop")]
    if series_id:
        targets.extend([(series_id, "Primary"), (series_id, "Backdrop")])

    for target_id, img_type in targets:
        try:
            r = requests.get(
                f"{cfg.jf_url}/Items/{target_id}/Images/{img_type}",
                headers=HEADERS,
                params={"api_key": cfg.jf_api, "width": width},
                timeout=5
            )
            if r.status_code == 200:
                print(f"  [Thumb] Loaded {img_type} image for ID: {target_id}")
                return Image.open(io.BytesIO(r.content))
        except Exception as e:
            print(f"  [Thumb Error] Failed {img_type} for {target_id}: {e}")

    print(f"  [Thumb Warning] No image available for item {item_id}")
    return None

def format_duration(ticks):
    if not ticks:
        return "Unknown"
    seconds = ticks // 10_000_000
    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)
    return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"

def wrap_text(text, max_chars=None):
    if max_chars is None:
        max_chars = max(14, int(28 * cfg.height / cfg.base_res))
    words = text.split()
    lines, current = [], ""
    for word in words:
        if len(current) + len(word) + 1 <= max_chars:
            current += ("" if not current else " ") + word
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return "\n".join(lines)

# ─── MPV IPC ──────────────────────────────────────────────────────────────────

def connect_mpv_socket(retries=30):
    for _ in range(retries):
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.connect(cfg.mpv_socket)
            s.settimeout(2.0)
            return s
        except Exception:
            time.sleep(0.3)
    raise RuntimeError("Could not connect to mpv IPC socket")

def mpv_command(sock, *args):
    cmd = json.dumps({"command": list(args)}) + "\n"
    try:
        sock.sendall(cmd.encode())
    except Exception as e:
        print(f"MPV IPC error: {e}")

def mpv_get_property(sock, prop):
    request_id = int(time.time() * 1000) % 100000
    cmd = json.dumps({"command": ["get_property", prop], "request_id": request_id}) + "\n"
    try:
        sock.sendall(cmd.encode())
        buffer = ""
        deadline = time.time() + 2.0
        while time.time() < deadline:
            try:
                data = sock.recv(4096).decode(errors="ignore")
                buffer += data
                lines = buffer.split("\n")
                buffer = lines[-1]
                for line in lines[:-1]:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                        if msg.get("request_id") == request_id:
                            if msg.get("error") == "success":
                                return msg.get("data")
                            return None
                    except Exception:
                        pass
            except socket.timeout:
                break
    except Exception as e:
        print(f"get_property error: {e}")
    return None

def drain_socket(sock):
    old_timeout = sock.gettimeout()
    sock.settimeout(0.1)
    try:
        while True:
            sock.recv(4096)
    except Exception:
        pass
    sock.settimeout(old_timeout)

def wait_for_video_end(sock):
    print("  Waiting for video to end (polling)...")
    time.sleep(3.0)
    while True:
        idle = mpv_get_property(sock, "idle-active")
        path = mpv_get_property(sock, "path")
        if idle is True or path is None:
            print("  mpv is idle — video ended.")
            return
        time.sleep(1.0)

def clear_all_overlays(sock):
    for i in range(10):
        mpv_command(sock, "overlay-remove", i)
    time.sleep(0.05)

# ─── Overlay Helpers ──────────────────────────────────────────────────────────

def to_bgra_file(img, path):
    r, g, b, a = img.split()
    bgra = Image.merge("RGBA", (b, g, r, a))
    with open(path, "wb") as f:
        f.write(bgra.tobytes())

def push_overlay(sock, slot, x, y, img):
    w, h = img.size
    path = os.path.join(tempfile.gettempdir(), f"overlay_{slot}.bgra")
    to_bgra_file(img, path)
    mpv_command(sock, "overlay-add", slot, x, y, path, 0, "bgra", w, h, w * 4)

# ─── Scene Generators ─────────────────────────────────────────────────────────

def sc(val):
    return int(val * (cfg.height / cfg.base_res))

def make_up_next_frame(title, series_title, duration_ticks, thumb):
    scene = cfg.get_up_next_scene()
    elements = get_raw_elements()
    colors = scene.get("colors", {})

    img = Image.new("RGBA", (cfg.width, cfg.height), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)

    # Legacy gradient background support
    if "bg_start" in colors and "bg_end" in colors:
        for i in range(cfg.height):
            shade = int(colors["bg_start"] + (i / cfg.height) * (colors["bg_end"] - colors["bg_start"]))
            draw.line([(0, i), (cfg.width, i)], fill=(shade, shade, shade, 255))

    for eid, el in elements.items():
        if eid in ["bar", "countdown"]:
            continue
            
        el_type = el.get("type")
        x, y = sc(el.get("x", 0)), sc(el.get("y", 0))
        w, h = sc(el.get("w", 100)), sc(el.get("h", 100))

        if el_type == "rect":
            if eid == "thumb" and thumb:
                t = thumb.copy().convert("RGBA")
                t.thumbnail((w, h), Image.LANCZOS)
                tx = x + (w // 2) - (t.width // 2)
                ty = y + (h // 2) - (t.height // 2)
                img.paste(t, (tx, ty), t)
            else:
                draw.rectangle([x, y, x + w, y + h], fill=el.get("color", "#ffffff"))

        elif el_type == "text":
            color = el.get("color", "#ffffff")
            font = cfg.fonts.get("med") 
            
            render_text = el.get("text", "")
            if eid == "title":
                render_text = wrap_text(title)
                font = cfg.fonts.get("big")
            elif eid == "series_title":
                render_text = series_title
            elif eid == "duration":
                render_text = f"Duration: {format_duration(duration_ticks)}"
            elif eid == "tag":
                font = cfg.fonts.get("tag")

            if render_text:
                draw.text((x, y), render_text, font=font, fill=color)

        elif el_type == "image":
            img_path = el.get("path", "")
            if os.path.exists(img_path):
                try:
                    static_img = Image.open(img_path).convert("RGBA")
                    static_img = static_img.resize((w, h), Image.LANCZOS)
                    img.paste(static_img, (x, y), static_img) 
                except Exception:
                    pass

    return img

def make_bar_image(progress, bar_w, bar_h, color):
    img = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    filled = int(bar_w * progress)
    if filled > 0:
        draw.rectangle([0, 0, filled, bar_h], fill=color)
    return img

def make_countdown_image(seconds_left, color):
    text = f"Starting in {seconds_left}s"
    padding = cfg.scale(6)
    dummy = Image.new("RGBA", (1, 1))
    bbox = ImageDraw.Draw(dummy).textbbox((0, 0), text, font=cfg.fonts["countdown"])
    w = bbox[2] - bbox[0] + padding * 2
    h = bbox[3] - bbox[1] + padding * 2
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((padding, padding), text, font=cfg.fonts["countdown"], fill=color)
    return img

# ─── Wipe Transitions ─────────────────────────────────────────────────────────

def wipe_in_from_right(sock, frame):
    anim = cfg.get_up_next_scene()["animations"]
    steps = anim["wipe_in_steps"]
    step_time = anim["wipe_in_duration"] / steps

    for i in range(steps + 1):
        t = 1 - (1 - (i / steps)) ** 3
        x = int(cfg.width * (1.0 - t))
        visible_w = cfg.width - x
        if visible_w > 0:
            cropped = frame.crop((0, 0, visible_w, cfg.height))
            push_overlay(sock, 0, x, 0, cropped)
            time.sleep(step_time)
    push_overlay(sock, 0, 0, 0, frame)

def wipe_out_to_left(sock, frame):
    anim = cfg.get_up_next_scene()["animations"]
    steps = anim["wipe_out_steps"]
    step_time = anim["wipe_out_duration"] / steps

    for i in range(steps + 1):
        t = (i / steps) ** 3
        offset = int(cfg.width * t)
        remaining_w = cfg.width - offset
        if remaining_w <= 0:
            break
        cropped = frame.crop((offset, 0, cfg.width, cfg.height))
        push_overlay(sock, 0, 0, 0, cropped)
        time.sleep(step_time)
    clear_all_overlays(sock)

# ─── Up Next Flow ─────────────────────────────────────────────────────────────

def show_up_next_overlay(sock, title, series_title, duration_ticks, item_id, series_id=None):
    scene = cfg.get_up_next_scene()
    elements = get_raw_elements()
    duration = scene.get("duration", 10)

    print(f"  Up Next: {title}")
    thumb = get_thumbnail(item_id, series_id=series_id, width=700)
    frame = make_up_next_frame(title, series_title, duration_ticks, thumb)
    
    wipe_in_from_right(sock, frame)

    start = time.time()
    last_second = -1

    bar_el = elements.get("bar", {"x": 0, "y": 0, "w": 0, "h": 0, "color": "#ffffff"})
    cd_el = elements.get("countdown", {"x": 0, "y": 0, "color": "#ffffff"})

    while True:
        elapsed = time.time() - start
        if elapsed >= duration:
            break

        progress = max(0.0, 1.0 - (elapsed / duration))
        seconds_left = max(1, int(duration - elapsed) + 1)

        if bar_el["w"] > 0:
            push_overlay(sock, 1, sc(bar_el["x"]), sc(bar_el["y"]), 
                         make_bar_image(progress, sc(bar_el["w"]), sc(bar_el["h"]), bar_el.get("color")))

        if seconds_left != last_second and "x" in cd_el:
            push_overlay(sock, 2, sc(cd_el["x"]), sc(cd_el["y"]), 
                         make_countdown_image(seconds_left, cd_el.get("color")))
            last_second = seconds_left

        time.sleep(0.05)

    wipe_out_to_left(sock, frame)

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    if os.path.exists(cfg.mpv_socket):
        os.remove(cfg.mpv_socket)

    black = os.path.join(tempfile.gettempdir(), "black.png")
    Image.new("RGB", (cfg.width, cfg.height), (0, 0, 0)).save(black)

    mpv_proc = subprocess.Popen([
        "mpv", black,
        f"--input-ipc-server={cfg.mpv_socket}",
        f"--geometry={cfg.width}x{cfg.height}+0+0",
        "--no-border", "--ontop", "--keep-open=yes", "--loop=inf",
        "--idle=yes", "--force-window=yes", "--hwdec=no", "--cache=yes",
        "--demuxer-max-bytes=150MiB", "--demuxer-readahead-secs=30",
        "--no-terminal", "--no-osc", "--no-osd-bar",
        f"--fs={'yes' if cfg.fullscreen else 'no'}",
    ])

    print("Waiting for mpv to start...")
    sock = connect_mpv_socket()
    print("Connected to mpv IPC\n")
    time.sleep(0.5)

    print("Fetching playlist...")
    items = get_playlist_items()
    if not items:
        print("No items found.")
        mpv_proc.terminate()
        return

    print(f"Found {len(items)} items. Starting broadcast loop...\n")

    try:
        while True:
            for item in items:
                item_id = item["Id"]
                series_id = item.get("SeriesId")
                title = item.get("Name", "Unknown")
                series_title = item.get("SeriesName", "")
                duration_ticks = item.get("RunTimeTicks", 0)
                stream_url = get_stream_url(item_id)

                drain_socket(sock)
                show_up_next_overlay(sock, title, series_title, duration_ticks, item_id, series_id=series_id)

                print(f"Now Playing: {title}")
                drain_socket(sock)
                mpv_command(sock, "loadfile", stream_url, "replace")
                wait_for_video_end(sock)

                mpv_command(sock, "loadfile", black, "replace")
                time.sleep(0.3)
                print(f"Finished: {title}\n")
            print("--- Playlist complete, looping ---\n")
            
    except KeyboardInterrupt:
        print("Stopping.")
    finally:
        clear_all_overlays(sock)
        sock.close()
        mpv_proc.terminate()

if __name__ == "__main__":
    main()