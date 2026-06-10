#!/usr/bin/env python3
import json
import os
import re
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
PEPINTEL = ROOT / "PepIntel"
API_BASE_URL = os.environ.get("GHOSTFEED_API_BASE_URL", "https://api.ghostfeed.ai")
ASSET_NAMES = ROOT / "asset-names.json"


def load_env():
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def clean_name(value):
    value = re.sub(r"[^A-Za-z0-9]+", " ", value).strip()
    return re.sub(r"\s+", " ", value) or "Unknown"


def slugify(value):
    value = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    return re.sub(r"-+", "-", value) or "asset"


def split_avatar_name(name):
    clean = clean_name(name)
    words = clean.split()
    if words and words[0].lower() in {"fit", "fat"}:
        return clean_name(" ".join(words[1:])), words[0].title()
    if words and words[-1].lower() in {"fit", "fat"}:
        return clean_name(" ".join(words[:-1])), words[-1].title()
    return clean, "Base"


def api_get(path, key):
    workspace_id = os.environ.get("GHOSTFEED_WORKSPACE_ID")
    if not workspace_id:
        raise SystemExit("Missing GHOSTFEED_WORKSPACE_ID in .env")
    req = urllib.request.Request(
        f"{API_BASE_URL}{path}",
        headers={
            "Authorization": f"Bearer {key}",
            "X-Workspace-Id": workspace_id,
            "User-Agent": "Mozilla/5.0 Codex-Ghostfeed-Assets/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as res:
        return json.loads(res.read().decode("utf-8"))


def download(url, path):
    if path.exists() and path.stat().st_size > 0:
        return
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Codex-Ghostfeed-Assets/1.0"})
    with urllib.request.urlopen(req, timeout=120) as res:
        path.write_bytes(res.read())


def ext_from_url(url, default):
    suffix = Path(urlparse(url).path).suffix.lower()
    return suffix if suffix else default


def asset_url(asset):
    if asset.get("type") == "video":
        return asset.get("videoUrl") or asset.get("url")
    return asset.get("imageUrl") or asset.get("url")


def load_asset_names():
    if not ASSET_NAMES.exists():
        return {}
    payload = json.loads(ASSET_NAMES.read_text())
    return payload.get("assets", {})


def stable_asset_id(asset, index):
    return (
        asset.get("id")
        or asset.get("assetId")
        or asset.get("frameId")
        or asset.get("videoId")
        or asset.get("imageId")
        or asset.get("_id")
        or f"unknown-{index:04d}"
    )


def asset_key(avatar_id, asset, index):
    return f"{avatar_id}:{stable_asset_id(asset, index)}"


def catalog_entry(catalog, key):
    entry = catalog.get(key)
    return entry if isinstance(entry, dict) else {}


def default_filename(asset, index, url):
    asset_type = asset.get("type") or "image"
    source = slugify(asset.get("source") or "asset")
    stable_id = slugify(stable_asset_id(asset, index))
    default_ext = ".mp4" if asset_type == "video" else ".png"
    return f"{source}-{stable_id}{ext_from_url(url, default_ext)}"


def media_dir(base_dir, asset_type, entry):
    if entry.get("status") == "unusable":
        folder = "Videos" if asset_type == "video" else "Images"
        return base_dir / folder / "_Unusable"
    return base_dir / ("Videos" if asset_type == "video" else "Images")


def filename_for_asset(catalog, key, asset, index, url):
    entry = catalog_entry(catalog, key)
    filename = entry.get("filename") or default_filename(asset, index, url)
    return Path(filename).name


def sync_avatar_assets(key, avatar, catalog):
    master, variant = split_avatar_name(avatar["name"])
    base_dir = PEPINTEL / "Avatars" / master / variant
    images_dir = base_dir / "Images"
    videos_dir = base_dir / "Videos"
    images_dir.mkdir(parents=True, exist_ok=True)
    videos_dir.mkdir(parents=True, exist_ok=True)

    page = 1
    all_assets = []
    while True:
        payload = api_get(f"/api/v1/avatars/{avatar['avatarId']}/assets?type=all&page={page}&limit=100", key)
        if not payload.get("success"):
            raise RuntimeError(payload)
        data = payload.get("data", {})
        assets = data.get("assets") or data.get("items") or []
        all_assets.extend(assets)
        pages = data.get("pages") or data.get("totalPages") or page
        if page >= pages or not assets:
            break
        page += 1

    downloaded = []
    for index, asset in enumerate(all_assets, 1):
        url = asset_url(asset)
        if not url:
            continue
        asset_type = asset.get("type") or "image"
        key = asset_key(avatar["avatarId"], asset, index)
        path = media_dir(base_dir, asset_type, catalog_entry(catalog, key))
        path.mkdir(parents=True, exist_ok=True)
        path = path / filename_for_asset(catalog, key, asset, index, url)
        download(url, path)
        downloaded.append({
            "assetKey": key,
            "type": asset_type,
            "source": asset.get("source"),
            "localPath": str(path.relative_to(ROOT)),
            "url": url,
        })

    return {
        "avatarId": avatar["avatarId"],
        "avatarName": avatar["name"],
        "master": master,
        "variant": variant,
        "count": len(downloaded),
        "assets": downloaded,
    }


def main():
    load_env()
    key = os.environ.get("GHOSTFEED_API_KEY")
    if not key:
        raise SystemExit("Missing GHOSTFEED_API_KEY in .env")
    catalog = load_asset_names()

    for folder in ["Avatars", "Videos", "Export"]:
        (PEPINTEL / folder).mkdir(parents=True, exist_ok=True)

    avatars_payload = api_get("/api/v1/avatars?page=1&limit=100", key)
    avatars = avatars_payload.get("data", {}).get("avatars", [])
    manifest = []
    for avatar in avatars:
        print(f"Syncing {avatar['name']}")
        manifest.append(sync_avatar_assets(key, avatar, catalog))

    (PEPINTEL / "Avatars" / "_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"Synced {len(manifest)} avatars")


if __name__ == "__main__":
    main()
