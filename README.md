# Ghostfeed Content Workspace Example

Portable content workspace for Ghostfeed/PepIntel-style avatar media generation and editing.

This public repo intentionally ships without media assets. Collaborators should use their own Ghostfeed API key and workspace access to download assets locally.

## Quick Start

```bash
cp .env.example .env
# Fill in GHOSTFEED_API_KEY and GHOSTFEED_WORKSPACE_ID
python3 sync_pepintel_assets.py
```

## What Is Included

- Workspace folder skeleton.
- Ghostfeed asset sync script.
- Source-video intake downloader.
- Agent operating rules in `AGENTS.md`.
- Running notes for Ghostfeed skill improvements.

## What Is Not Included

- API keys.
- Avatar images/videos.
- Source reels or TikToks.
- Exported final videos.

Assets are ignored by Git and should be regenerated or synced locally.

## Folder Structure

```text
PepIntel/
  Avatars/
  Videos/
  Export/
  yet to be clonned/
```

See `AGENTS.md` for naming, unusable-asset, and editing conventions.

