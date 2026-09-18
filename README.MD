# Jellyfin Broadcast Client / `jx32` Beta
`jx32` is a python program designed to be broadcast ready for streaming a playlist on your Jellyfin server, through OBS! I designed this so the only edits you mainly need to do are on Jellyfin! Coded in Python!
## Setup
### Dependencies
- mpv
- Linux
- Python3
- Jellyfin
### Jellyfin Setup
1. Go to your Jellyfin admin dashboard
2. Navigate to API Keys
3. Create an API key under the name `jx32` and copy the key
4. Put the key into `jx32.json` in this format
```
  "server": {
    "url": "http://YOUR_JELLYFIN_SERVER:8096",
    "api_key": "YOUR_API_KEY",
    "playlist_id": "YOUR_PLAYLIST_ID"
  }
```
5. Create a playlist in Jellyfin with at least 2 videos in it.
6. Find the playlist ID using the URL. Make sure you only copy the playlist ID. The format is below `http://YOUR_JELLYFIN_SERVER:8096/web/#/details?id=YOUR_PLAYLIST_ID`
7. Put your playlist ID into the `jx32.json` file under `"playlist_id"`
8. Startup `jx32` using `python -m jx32`. If it throws an error about something being not installed, go to the Python Setup step.
### Python Setup
1. Ensure that you have `requirements.txt` in the `jx32/` directory.
2. Ensure you have `pip` installed on your system through `python`.
3. Navigate to the `jx32/` directory using `cd` in your terminal.
4. Run this command `python -m pip install -r requirements.txt --break-system-packages`
5. If something doesn't work, <a href="https://google.com">Google it</a>. I am not responsible for any errors with the Python ecosystem.
### `confui` Configuration Tool
<i>Pronounced con-fue-eye</i>
<br> `confui` is a configuration tool for `jx32` that I created! UI is inspired by OBS. `confui` is a very simple tool. There are 3 main elements of `confui`.
1. Drag around elements
2. Resize elements
3. Insert images<br>
<p></p>
<code>confui</code> will not mainly be updated.

## Startup
To run `jx32`, run `python -m jx32`.<br>
To run `confui`, run `python -m jx32_confui`<br>

You can also run `./run.sh`.

## Gallery
<img src="md/thumb.png"/>

# Credits
Main Developer: <a href="https://elliotd.au/site">ElliotD.Au</a>