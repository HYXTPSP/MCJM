import os
import json
import shutil
from pathlib import Path

import jmcomic
from flask import Flask, request, jsonify

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("[MCJM] WARNING: Pillow not installed, WebP->PNG conversion disabled")

app = Flask(__name__)
DEFAULT_CACHE_DIR = Path("cache").resolve()
progress_store = {}


def make_option(cache_dir: str) -> jmcomic.JmOption:
    return jmcomic.create_option_by_str(f'''
dir_rule:
  base_dir: {Path(cache_dir).as_posix()}
  rule: Bd/Aid/Pphoto_id
download:
  cache: true
client:
  postman:
    meta_data:
      proxies: {{}}
''')


def _convert_webp_to_png(cache_dir: Path, chapter_id: str):
    # jmcomic saves to <cache_dir>/<photo.album_id>/<chapter_id>/
    # photo.album_id may differ from album.album_id, so we search by chapter_id
    ch_dir = None
    for album_dir in cache_dir.iterdir():
        candidate = album_dir / chapter_id
        if candidate.is_dir():
            ch_dir = candidate
            break
    if ch_dir is None:
        print(f"[MCJM]   convert skip: chapter dir not found for {chapter_id}")
        return
    files = sorted(ch_dir.iterdir())
    for f in files:
        if f.suffix.lower() == ".webp":
            png_path = f.with_suffix(".png")
            if HAS_PIL:
                try:
                    img = Image.open(f)
                    img.save(png_path, "PNG")
                    f.unlink()
                except Exception as e:
                    print(f"[MCJM]   convert failed: {f.name} ({e})")
            else:
                os.rename(f, png_path)


@app.route("/api/progress", methods=["GET"])
def api_progress():
    album_id = request.args.get("album_id", "")
    data = progress_store.get(album_id)
    if data is None:
        return jsonify({"current": 0, "total": 1})
    return jsonify(data)


@app.route("/api/download", methods=["POST"])
def api_download():
    body = request.get_json(force=True)
    album_id = body.get("album_id", "").strip()
    if not album_id:
        return jsonify({"status": "error", "message": "缺少 album_id"}), 400

    user_cache_dir = body.get("cache_dir", "")
    cache_dir = Path(user_cache_dir).resolve() if user_cache_dir else DEFAULT_CACHE_DIR

    try:
        album_cache_dir = cache_dir / str(album_id)
        if album_cache_dir.exists():
            shutil.rmtree(album_cache_dir)

        option = make_option(str(cache_dir))
        client = option.new_jm_client()

        print(f"[MCJM] 获取专辑: {album_id}")
        album = client.get_album_detail(album_id)
        total = len(album.episode_list)
        print(f"[MCJM] 标题: {album.name}，章节数: {total}")
        progress_store[album_id] = {"current": 0, "total": total}

        chapters = []
        for idx, ep in enumerate(album.episode_list):
            ch_id = str(ep[0])
            ch_name = ep[2] or f"第{ep[1]}话"
            print(f"[MCJM] 下载章节 {idx+1}/{total}: {ch_name} (id={ch_id})")
            jmcomic.download_photo(ch_id, option)
            _convert_webp_to_png(cache_dir, ch_id)
            chapters.append({"id": ch_id, "name": ch_name})
            progress_store[album_id] = {"current": idx + 1, "total": total}

        return jsonify({
            "status": "ok",
            "album_id": album_id,
            "title": album.name,
            "chapters": chapters,
            "cache_dir": str(cache_dir),
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/ping", methods=["GET"])
def api_ping():
    return jsonify({"status": "pong"})


if __name__ == "__main__":
    port = int(os.environ.get("MCJM_PORT", 28374))
    print(f"MCJM Server starting on http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=False)
