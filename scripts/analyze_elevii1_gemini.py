#!/usr/bin/env python3
"""Extract simple research notes from downloaded elevii1 TikToks with Gemini."""

from __future__ import annotations

import argparse
import collections
import concurrent.futures
import json
import os
import re
import sys
import time
from pathlib import Path

from google import genai


MODEL = "gemini-3.1-pro-preview"
ROOT = Path("research/elevii1")
CONTENT_DIR = ROOT / "content"
SLIDES_DIR = ROOT / "slideshows" / "tiktok" / "elevii1"
OUTPUT_DIR = ROOT / "extractions"


PROMPT = """You are analyzing one TikTok post for content research.

Keep this simple and concrete. Do not create content strategy. Do not suggest remakes. Do not fact-check. Do not add medical disclaimers. Do not use complex JSON.

Write Markdown with exactly these sections:

## Entire Transcript

Provide the full transcript from top to bottom.

- If this is a spoken video, transcribe the spoken words as completely as possible in order.
- If there is on-screen text that matters while someone is speaking, include it inline as [On-screen text: ...].
- If this is a slideshow/photo post, transcribe every slide in order as [Slide 1], [Slide 2], etc. Include any audio lyrics/spoken words only if they are meaningful to the content.
- Preserve peptide names, supplement names, dosages, timelines, routines, warnings, examples, and calls to action.
- If a word is not clear, write [inaudible] and keep going.

## Analysis

### What Is Being Said / Communicated

Summarize the main communicated message after reading/watching the full post.

### Knowledge Shared

List the practical knowledge, explanations, steps, routines, or educational points shared in the post.

### Claims Made

List claims the creator makes or implies.

### Visible Text / Slides / Images

Describe important on-screen text, slideshow text, labels, objects, screenshots, product shots, body/fitness visuals, and any visual proof being used.

### Hook

State the opening hook or curiosity angle in one or two sentences.
"""


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        value = value.strip().strip("\"'")
        if key:
            values[key] = value
    return values


def video_id_from_name(name: str) -> str | None:
    match = re.search(r"(\d{18,20})", name)
    return match.group(1) if match else None


def info_for_video(video_id: str) -> dict:
    matches = sorted(CONTENT_DIR.glob(f"*{video_id}*.info.json"))
    if not matches:
        return {}
    try:
        return json.loads(matches[0].read_text())
    except Exception:
        return {}


def title_from_info(video_id: str) -> str:
    data = info_for_video(video_id)
    return data.get("title") or data.get("description") or ""


def collect_items() -> list[dict]:
    slide_groups: dict[str, dict[str, list[Path]]] = collections.defaultdict(
        lambda: {"images": [], "audio": []}
    )
    if SLIDES_DIR.exists():
        for path in sorted(SLIDES_DIR.iterdir()):
            if not path.is_file():
                continue
            video_id = video_id_from_name(path.name)
            if not video_id:
                continue
            suffix = path.suffix.lower()
            if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
                slide_groups[video_id]["images"].append(path)
            elif suffix in {".mp3", ".m4a", ".wav", ".aac"}:
                slide_groups[video_id]["audio"].append(path)

    slideshow_ids = {video_id for video_id, group in slide_groups.items() if group["images"]}
    items: list[dict] = []

    for video_id in sorted(slideshow_ids):
        group = slide_groups[video_id]
        items.append(
            {
                "id": video_id,
                "type": "slideshow",
                "info": info_for_video(video_id),
                "files": sorted(group["images"]) + sorted(group["audio"]),
            }
        )

    for path in sorted(CONTENT_DIR.glob("*.mp4")):
        video_id = video_id_from_name(path.name)
        if not video_id or video_id in slideshow_ids:
            continue
        items.append(
            {
                "id": video_id,
                "type": "video",
                "info": info_for_video(video_id),
                "files": [path],
            }
        )

    return sorted(items, key=lambda item: item["id"])


def wait_for_file(client: genai.Client, uploaded):
    name = uploaded.name
    while True:
        current = client.files.get(name=name)
        state = getattr(current, "state", None)
        state_name = getattr(state, "name", str(state))
        if state_name == "ACTIVE":
            return current
        if state_name == "FAILED":
            raise RuntimeError(f"Gemini file processing failed for {name}")
        time.sleep(2)


def analyze_item(client: genai.Client, item: dict) -> str:
    uploaded_parts = []
    uploaded_names = []
    try:
        for path in item["files"]:
            uploaded = client.files.upload(file=str(path))
            uploaded = wait_for_file(client, uploaded)
            uploaded_parts.append(uploaded)
            uploaded_names.append(uploaded.name)

        info = item.get("info") or {}
        title = info.get("title") or info.get("description") or ""
        context = (
            f"Post type: {item['type']}\n"
            f"TikTok ID: {item['id']}\n"
            f"Downloaded title/caption if available: {title}\n\n"
        )
        response = client.models.generate_content(
            model=MODEL,
            contents=[*uploaded_parts, context + PROMPT.format(video_id=item["id"])],
        )
        return response.text or ""
    finally:
        for name in uploaded_names:
            try:
                client.files.delete(name=name)
            except Exception:
                pass


def render_output(item: dict, text: str) -> str:
    info = item.get("info") or {}
    link = info.get("webpage_url") or f"https://www.tiktok.com/@elevii1/video/{item['id']}"
    caption = info.get("title") or info.get("description") or ""
    header = [
        f"# Video: {item['id']}",
        "",
        f"- Video link: {link}",
        f"- Number of views: {info.get('view_count', 'unknown')}",
        f"- Number of likes: {info.get('like_count', 'unknown')}",
        f"- Number of comments: {info.get('comment_count', 'unknown')}",
        f"- Post type: {item['type']}",
        f"- Caption/title: {caption}",
        "",
    ]
    return "\n".join(header) + text.strip() + "\n"


def process_item(api_key: str, item: dict) -> tuple[str, bool, str]:
    output_path = OUTPUT_DIR / f"{item['id']}.md"
    client = genai.Client(api_key=api_key)
    try:
        text = analyze_item(client, item)
    except Exception as exc:
        error_path = OUTPUT_DIR / f"{item['id']}.error.txt"
        error_path.write_text(f"{type(exc).__name__}: {exc}\n")
        return item["id"], False, f"{type(exc).__name__}: {exc}"
    output_path.write_text(render_output(item, text))
    error_path = OUTPUT_DIR / f"{item['id']}.error.txt"
    if error_path.exists():
        error_path.unlink()
    return item["id"], True, str(output_path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Maximum new items to analyze.")
    parser.add_argument("--force", action="store_true", help="Re-run existing extraction files.")
    parser.add_argument("--only-id", default="", help="Analyze a single TikTok ID.")
    parser.add_argument("--workers", type=int, default=1, help="Number of parallel Gemini calls.")
    args = parser.parse_args()

    env = load_env(Path(".env"))
    api_key = (
        env.get("GEMINI_KEY")
        or env.get("GEMINI_API_KEY")
        or env.get("GOOGLE_API_KEY")
        or env.get("GOOGLE_GENERATIVE_AI_API_KEY")
        or env.get("GOOGLE_GENAI_API_KEY")
        or os.environ.get("GEMINI_KEY")
        or os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
    )
    if not api_key:
        print("No Gemini API key found. Expected GEMINI_KEY or GEMINI_API_KEY.", file=sys.stderr)
        return 2

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    client = genai.Client(api_key=api_key)
    items = collect_items()
    if args.only_id:
        items = [item for item in items if item["id"] == args.only_id]

    pending = []
    for item in items:
        output_path = OUTPUT_DIR / f"{item['id']}.md"
        if output_path.exists() and not args.force:
            continue
        if args.limit and len(pending) >= args.limit:
            break
        pending.append(item)

    attempted = len(pending)
    completed = 0
    workers = max(1, args.workers)
    if workers == 1:
        client = genai.Client(api_key=api_key)
        for item in pending:
            print(f"Analyzing {item['id']} ({item['type']}, {len(item['files'])} files)")
            try:
                text = analyze_item(client, item)
            except Exception as exc:
                error_path = OUTPUT_DIR / f"{item['id']}.error.txt"
                error_path.write_text(f"{type(exc).__name__}: {exc}\n")
                print(f"FAILED {item['id']}: {type(exc).__name__}: {exc}")
                continue
            output_path = OUTPUT_DIR / f"{item['id']}.md"
            output_path.write_text(render_output(item, text))
            error_path = OUTPUT_DIR / f"{item['id']}.error.txt"
            if error_path.exists():
                error_path.unlink()
            completed += 1
            print(f"Wrote {output_path}")
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(process_item, api_key, item): item
                for item in pending
            }
            for future in concurrent.futures.as_completed(futures):
                item = futures[future]
                try:
                    video_id, ok, message = future.result()
                except Exception as exc:
                    video_id = item["id"]
                    ok = False
                    message = f"{type(exc).__name__}: {exc}"
                if ok:
                    completed += 1
                    print(f"Wrote {message}")
                else:
                    print(f"FAILED {video_id}: {message}")

    print(f"attempted={attempted} completed={completed} total_items={len(items)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
