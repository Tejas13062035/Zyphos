from core.sidecar_url import get_sidecar_url
SIDECAR_URL = get_sidecar_url()

import subprocess
import os

TOOL_NAME = "music"
TOOL_DESCRIPTION = "Play music by searching YouTube. Actions: play, stop, pause"
TOOL_ARGS = {"action": "play|stop|pause", "query": "song or artist name (for play)"}

PLAYER_PID_FILE = "/tmp/zyp_music.pid"

def run(args: dict) -> dict:
    action = args.get("action", "").lower()
    query = args.get("query", "")

    if action in ["play", "search"]:
        if not query:
            return {"error": "query required for play"}
        try:
            # stop first
            import requests as req
            req.post(f"{SIDECAR_URL}/stop_audio")
            import time
            time.sleep(1)  # wait for VLC to fully close
            
            # delete old file
            import glob
            for f in glob.glob("/mnt/c/zyphos_sidecar/music.*"):
                os.remove(f)

            # try multiple queries
            queries = [
                query,
                query.replace("by", "").strip(),
                query.split("by")[0].strip() if "by" in query else query
            ]
            
            out_path = None
            for q in queries:
                result = subprocess.run(
                    ["yt-dlp", "-f", "bestaudio/best",
                     "-o", "/mnt/c/zyphos_sidecar/music.%(ext)s",
                     "--no-playlist",
                     f"ytsearch1:{q}"],
                    capture_output=True, text=True, timeout=120
                )
                files = glob.glob("/mnt/c/zyphos_sidecar/music.*")
                if files:
                    out_path = files[0]
                    break

            if not out_path:
                return {"error": "download failed after retries"}
            out_path = files[0]
            win_path = r"C:\zyphos_sidecar\\" + os.path.basename(out_path)
            req.post(f"{SIDECAR_URL}/play_audio", json={"path": win_path})
            return {"status": "playing", "query": query}
        except Exception as e:
            return {"error": str(e)}

    elif action == "stop":
        return stop_music()

    elif action == "pause":
        return {"status": "pause not supported in background mode — use stop"}

    else:
        return {"error": f"unknown action: {action}"}

def stop_music() -> dict:
    try:
        import requests as req
        req.post(f"{SIDECAR_URL}/stop_audio")
    except:
        pass
    return {"status": "stopped"}
