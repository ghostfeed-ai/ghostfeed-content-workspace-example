# Ghostfeed Content Workspace Agents Guide

This repository is a portable Ghostfeed content workspace example. It is meant to keep two or more laptops aligned on folder structure, scripts, and operating rules without committing the actual media assets.

## Public Repo Rule

Do not commit downloaded assets, exported videos, API keys, `.env`, or source social downloads. Content remains gated behind the Ghostfeed API key and workspace access.

The repo should contain:

- Workspace structure.
- Scripts for syncing/downloading.
- Naming and quality conventions.
- Notes for improving Ghostfeed public skills.

The repo should not contain:

- `GHOSTFEED_API_KEY`.
- Real `.env` files.
- Avatar images or videos.
- Instagram/TikTok downloads.
- Final exports.
- Temporary contact sheets or review files.

## Setup On A New Laptop

1. Copy `.env.example` to `.env`.
2. Fill in `GHOSTFEED_API_KEY` and `GHOSTFEED_WORKSPACE_ID`.
3. Install local tools used by the scripts:
   - `yt-dlp` for one-off social downloads.
   - `gallery-dl` for Instagram reel/profile downloads when `yt-dlp` cannot enumerate them.
   - `ffmpeg` for video editing, contact sheets, and audio/video inspection.
4. Run:

```bash
python3 sync_pepintel_assets.py
```

This downloads avatar assets from the Ghostfeed Avatar API into the local `PepIntel/Avatars/` folder.

## Folder Contract

```text
PepIntel/
  Avatars/
    <Avatar Name>/
      Fat/
        Images/
        Videos/
      Fit/
        Images/
        Videos/
  Videos/
  Export/
  yet to be clonned/
```

`Avatars` is the local avatar asset library.

`Videos` is for intermediate video material we intentionally keep.

`Export` is for final postable outputs.

`yet to be clonned` is the intake folder for downloaded source/reference videos before they are cloned, remade, or deleted after upload/import.

## Asset Naming

Use short scenario-based names. The filename should say what the asset shows, not where it came from.

Good examples:

- `fat-cafe-purple-shirt-green-drink.png`
- `fit-hallway-navy-dress-walk.mp4`
- `fit-elevator-blue-top-sunglasses.png`

Avoid UUID-only names in active media folders. If sync scripts download raw generated names, rename the assets after visual review.

## Unusable Assets

Do not delete questionable assets by default. Move them into an `_Unusable` folder inside the same media folder and include the reason in the filename.

Example:

```text
PepIntel/Avatars/Leah/Fit/Videos/_Unusable/unusable-056-bathroom-mirror-bicep-flex.mp4
```

Normal edit scripts should only scan the active `Images/` and `Videos/` folders and should skip all `_Unusable` folders.

## Editing Workflow

For transformation content, prefer:

- Same or closely matched audio from the reference reel.
- Fat-to-fit visual progression.
- Clean hard cuts unless the reference uses a different rhythm.
- No overlay text unless explicitly requested.
- Ken Burns style zoom/pan on still photos only when the edit is not already using a video generated from that same image/source frame.
- Do not use a still image and its generated video in the same edit unless the user explicitly asks for that repeated-shot effect.

Before exporting final batches, inspect contact sheets or frame strips for:

- Bad framing.
- Fake-looking backgrounds.
- Awkward poses.
- Duplicate shots that weaken pacing.
- Any accidental overlay text when the request says no text.

## Ghostfeed API Notes

Use the Ghostfeed public API skills as the source of truth. If the user says something that differs from the installed skills or observed public API behavior, call it out clearly and add a note to `things to update in skills.md`.

Known useful public API flow:

- List avatars in the configured workspace.
- For each avatar, use the avatar assets endpoint to fetch related image and video assets.
- Group local files by master avatar name and variant, such as `Leah/Fat` and `Leah/Fit`.

Keep this workspace simple. Add automation only when repeated work proves it is needed.
