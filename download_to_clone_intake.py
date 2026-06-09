#!/usr/bin/env python3
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INTAKE = ROOT / "PepIntel" / "yet to be clonned"
MANIFEST = INTAKE / "_manifest.json"
YT_DLP = shutil.which("yt-dlp") or "/opt/homebrew/bin/yt-dlp"


def slugify(value):
    value = re.sub(r"https?://", "", value.lower())
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value[:80] or "source-video"


def load_manifest():
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text())
    return {"items": []}


def save_manifest(manifest):
    MANIFEST.write_text(json.dumps(manifest, indent=2))


def main():
    urls = [arg for arg in sys.argv[1:] if arg.strip()]
    if not urls:
        raise SystemExit("Usage: python3 download_to_clone_intake.py <instagram-or-tiktok-url> [...]")

    INTAKE.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest()

    for url in urls:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        slug = slugify(url)
        output = f"{stamp}-{slug}.%(ext)s"
        cmd = [
            YT_DLP,
            "--no-playlist",
            "--write-info-json",
            "--paths",
            str(INTAKE),
            "--output",
            output,
            url,
        ]
        print("+ " + " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)

        downloaded = sorted(INTAKE.glob(f"{stamp}-{slug}.*"))
        video_files = [
            path for path in downloaded
            if path.suffix.lower() not in {".json", ".part", ".ytdl"}
        ]
        info_files = [path for path in downloaded if path.name.endswith(".info.json")]

        manifest["items"].append({
            "url": url,
            "downloadedAt": datetime.now().isoformat(timespec="seconds"),
            "ok": result.returncode == 0,
            "returnCode": result.returncode,
            "videos": [str(path.relative_to(ROOT)) for path in video_files],
            "metadata": [str(path.relative_to(ROOT)) for path in info_files],
            "error": result.stderr[-2000:] if result.returncode else None,
            "deleteAfterUpload": True
        })
        save_manifest(manifest)

    print(f"Saved {MANIFEST}")


if __name__ == "__main__":
    main()
