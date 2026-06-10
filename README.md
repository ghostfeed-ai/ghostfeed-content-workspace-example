# Ghostfeed Content Workspace Example

Portable content workspace for Ghostfeed/PepIntel-style avatar media generation and editing.

This public repo intentionally ships without media assets. Collaborators should use their own Ghostfeed API key and workspace access to download assets locally.

## Quick Start

```bash
cp .env.example .env
# Fill in GHOSTFEED_API_KEY and GHOSTFEED_WORKSPACE_ID
python3 sync_pepintel_assets.py
```

To keep two laptops aligned, pull the latest repo before syncing assets. The
repo does not store media, but it does store `asset-names.json`, which maps
Ghostfeed asset records to canonical local filenames/status.

## What Is Included

- Workspace folder skeleton.
- Ghostfeed asset sync script.
- Canonical asset naming catalog in `asset-names.json`.
- Source-video intake downloader.
- Agent operating rules in `AGENTS.md`.
- Running notes for Ghostfeed skill improvements.

## What Is Not Included

- API keys.
- Avatar images/videos.
- Source reels or TikToks.
- Exported final videos.

Assets are ignored by Git and should be regenerated or synced locally.

## Keeping Two Laptops In Sync

1. Commit and push changes to scripts, docs, and `asset-names.json`.
2. On the other laptop, pull the repo.
3. Run `python3 sync_pepintel_assets.py`.

The sync script uses this order:

- If an asset has a curated entry in `asset-names.json`, use that filename and status.
- Otherwise use a stable fallback name based on the Ghostfeed asset id, not the API list order.
- Downloaded media still stays ignored by Git.

When we visually review and rename assets, the durable version of that decision
should go into `asset-names.json`; then every laptop can recreate the same local
asset library from the Ghostfeed API.

## Folder Structure

```text
PepIntel/
  Avatars/
  Videos/
  Export/
  yet to be clonned/
```

See `AGENTS.md` for naming, unusable-asset, and editing conventions.
