#!/usr/bin/env python3
"""Build a research library from elevii1 extraction Markdown files."""

from __future__ import annotations

import argparse
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
EXTRACTIONS = ROOT / "extractions"
ANALYSIS = ROOT / "analysis"
CHUNKS = ANALYSIS / "_intermediate" / "chunks"
KNOWLEDGE = ANALYSIS / "knowledge-base"
MAX_CHARS_PER_CHUNK = 75000


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


def api_key() -> str:
    env = load_env(Path(".env"))
    key = (
        env.get("GEMINI_KEY")
        or env.get("GEMINI_API_KEY")
        or env.get("GOOGLE_API_KEY")
        or env.get("GOOGLE_GENERATIVE_AI_API_KEY")
        or env.get("GOOGLE_GENAI_API_KEY")
        or os.environ.get("GEMINI_KEY")
        or os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
    )
    if not key:
        raise RuntimeError("No Gemini key found. Expected GEMINI_KEY or GEMINI_API_KEY.")
    return key


def call_gemini(client: genai.Client, prompt: str, retries: int = 4) -> str:
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = client.models.generate_content(model=MODEL, contents=prompt)
            text = response.text or ""
            if text.strip():
                return text.strip() + "\n"
            raise RuntimeError("Empty Gemini response")
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            wait = min(60, 5 * attempt)
            print(f"Gemini call failed on attempt {attempt}/{retries}: {type(exc).__name__}: {exc}")
            if attempt < retries:
                time.sleep(wait)
    raise RuntimeError(f"Gemini call failed after {retries} attempts: {last_exc}")


def extraction_files() -> list[Path]:
    return sorted(EXTRACTIONS.glob("*.md"))


def make_batches(files: list[Path]) -> list[list[Path]]:
    batches: list[list[Path]] = []
    current: list[Path] = []
    size = 0
    for path in files:
        text_len = len(path.read_text(errors="replace"))
        if current and size + text_len > MAX_CHARS_PER_CHUNK:
            batches.append(current)
            current = []
            size = 0
        current.append(path)
        size += text_len
    if current:
        batches.append(current)
    return batches


def chunk_prompt(paths: list[Path], index: int, total: int) -> str:
    joined = []
    for path in paths:
        joined.append(f"\n\n===== SOURCE FILE: {path.name} =====\n{path.read_text(errors='replace')}")

    return f"""You are building a serious research library from TikTok extraction files.

This is chunk {index} of {total}. Your job is exhaustive extraction from this chunk only.

Important:
- Do not create new social content.
- Do not make a strategy summary.
- Do not fact-check or add medical disclaimers.
- Preserve source relationships. Every important point should include source refs using this compact format:
  [video_id | views | likes | comments | link]
- If a peptide, supplement, website, app, product, routine, side effect, or stack appears, keep it. Do not drop niche items.
- Capture exact hooks and visible text/slideshow structures when present.
- This is not a short summary. Dense and complete is better than elegant and short.

Write Markdown with exactly these sections:

# Chunk {index} Research Notes

## Knowledge Items
Group by entity/topic. Include every useful detail from transcripts and analysis:
- what the creator says
- benefits/uses
- side effects/problems
- routines, timing, dosages, storage, injection/reconstitution details
- stacks/pairings
- warnings/mistakes/hacks
- source refs

## Claims
List repeated and one-off claims. Include source refs.

## Content Pillar Signals
List content buckets that appear in this chunk, with examples and source refs.

## Hook Bank
List hooks/openings/on-screen hook text. Include source refs, engagement, why it likely works, and reusable hook pattern.

## Visual Analysis Notes
Capture talking-head style, slideshow structure, on-screen text style, screenshots, proof visuals, product shots, app/website visuals, body visuals, and anything that would help recreate the visual style later. Include source refs.

SOURCE FILES:
{''.join(joined)}
"""


def build_chunks(client: genai.Client, force: bool) -> None:
    CHUNKS.mkdir(parents=True, exist_ok=True)
    batches = make_batches(extraction_files())
    manifest = []
    for i, batch in enumerate(batches, start=1):
        manifest.extend(write_chunk_or_split(client, batch, i, len(batches), force))
    (CHUNKS / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def write_chunk_or_split(
    client: genai.Client,
    batch: list[Path],
    index: int,
    total: int,
    force: bool,
    suffix: str = "",
) -> list[dict]:
    stem = f"chunk-{index:03d}{suffix}"
    out = CHUNKS / f"{stem}.md"
    if out.exists() and not force:
        print(f"Skipping {out}")
        return [{"chunk": stem, "file": str(out), "sources": [p.name for p in batch]}]

    print(f"Building {stem}/{total} ({len(batch)} files)")
    try:
        out.write_text(call_gemini(client, chunk_prompt(batch, index, total)))
        return [{"chunk": stem, "file": str(out), "sources": [p.name for p in batch]}]
    except Exception:
        if len(batch) <= 1:
            raise
        midpoint = len(batch) // 2
        print(f"Splitting {stem} into smaller batches")
        left = write_chunk_or_split(client, batch[:midpoint], index, total, force, suffix=f"{suffix}a")
        right = write_chunk_or_split(client, batch[midpoint:], index, total, force, suffix=f"{suffix}b")
        return left + right


def all_chunk_notes() -> str:
    parts = []
    for path in sorted(CHUNKS.glob("chunk-*.md")):
        parts.append(f"\n\n===== {path.name} =====\n{path.read_text(errors='replace')}")
    return "".join(parts)


def relevant_chunk_notes(page: dict) -> str:
    title = str(page.get("title") or "")
    slug = str(page.get("slug") or "")
    why = str(page.get("why") or "")
    raw_terms = [title, slug, why]
    terms: set[str] = set()
    for raw in raw_terms:
        lowered = raw.lower()
        if lowered:
            terms.add(lowered)
        for token in re.split(r"[^a-zA-Z0-9+]+", lowered):
            if len(token) >= 3:
                terms.add(token)

    aliases = {
        "retatrutide": ["reta"],
        "tirzepatide": ["tirz"],
        "ghk-cu": ["ghk", "ghk-cu", "ghk cu"],
        "bpc-157": ["bpc", "bpc-157"],
        "tb-500": ["tb-500", "tb500"],
        "nad-plus": ["nad", "nad+"],
        "melanotan-2": ["melanotan", "mt2"],
        "tesamorelin": ["tesa"],
        "ipamorelin": ["ipa"],
        "cagrilintide": ["cag"],
    }
    for key, values in aliases.items():
        if key in slug.lower() or key in title.lower():
            terms.update(values)

    selected = []
    for path in sorted(CHUNKS.glob("chunk-*.md")):
        text = path.read_text(errors="replace")
        lowered = text.lower()
        if any(term and term in lowered for term in terms):
            selected.append((path, text))

    # If matching gets too narrow, use the full corpus to avoid losing references.
    if len(selected) < 2:
        selected = [(path, path.read_text(errors="replace")) for path in sorted(CHUNKS.glob("chunk-*.md"))]

    parts = [f"\n\n===== {path.name} =====\n{text}" for path, text in selected]
    return "".join(parts)


def final_prompt(target: str, instructions: str) -> str:
    return f"""You are synthesizing a final research file from exhaustive chunk notes.

Target file: {target}

Rules:
- Be detailed. This research run is meant to preserve as much useful information as possible.
- Do not create new social content.
- Do not make Ghostfeed generation instructions.
- Do not fact-check or add medical disclaimers.
- Preserve provenance. Use source refs in this format wherever possible:
  [video_id | views | likes | comments | link]
- Prefer useful organization over brevity.
- If the notes disagree or repeat, merge them but keep important nuances.

{instructions}

CHUNK NOTES:
{all_chunk_notes()}
"""


def write_final(client: genai.Client, path: Path, instructions: str, force: bool) -> None:
    if path.exists() and not force:
        print(f"Skipping {path}")
        return
    print(f"Writing {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(call_gemini(client, final_prompt(path.name, instructions)))


def write_core_finals(client: genai.Client, force: bool) -> None:
    write_final(
        client,
        ANALYSIS / "claims-map.md",
        """Create a comprehensive claims map.

Include:
- repeated claims
- important one-off claims
- problem/solution claims
- stack/pairing claims
- side-effect claims
- timing/dosage/storage/injection claims
- app/product/website claims
- source refs for every claim cluster
- note which claims appear attached to high engagement when obvious from the stats
""",
        force,
    )
    write_final(
        client,
        ANALYSIS / "content-pillars.md",
        """Create a comprehensive content pillar analysis.

Include:
- each pillar name
- what the pillar is about
- subtopics inside it
- representative videos with refs
- why the pillar seems to exist for this creator
- what audience pain/desire it targets
- engagement signals when obvious

Do not invent content ideas. Only analyze what exists.
""",
        force,
    )
    write_final(
        client,
        ANALYSIS / "hook-map.md",
        """Create a detailed hook map.

Include:
- exact hooks and on-screen hook text when available
- group hooks into reusable patterns
- for each pattern: why it works, topics it was used for, source refs, and engagement signals
- high-performing hooks
- weaker or lower-performing hooks when visible from stats
- wording patterns: questions, warnings, beginner guides, side-effect fixes, rankings, timelines, mistakes, hacks, stacks, curiosity

Do not create new posts. This is a hook research library.
""",
        force,
    )
    write_final(
        client,
        ANALYSIS / "visual-analysis.md",
        """Create a detailed visual analysis in one file.

Include:
- talking-head style
- on-screen text style
- slideshow structures
- how slides are written
- screenshots, product shots, app/website visuals
- body/transformation/proof visuals
- background/location patterns
- how visuals support peptide education
- visual patterns attached to high engagement when obvious
- specific examples with source refs

This file can be long. Keep all important visual information together here.
""",
        force,
    )


def entity_index_prompt() -> str:
    return f"""You are creating a knowledge-base page plan from chunk notes.

Return ONLY valid JSON with this shape:
{{
  "pages": [
    {{
      "slug": "lowercase-kebab-case",
      "title": "Human Title",
      "type": "peptide|supplement|stack|routine|side-effect|injection-storage|website-app-product|other",
      "why": "short reason this deserves its own page"
    }}
  ]
}}

Rules:
- Create a separate page for every peptide/compound that appears.
- Also create pages for major supplements, stacks, side effects, injection/storage/reconstitution, websites/apps/products, routines, and other recurring knowledge topics.
- Do not use only the examples given by the user. Discover all topics from the notes.
- Avoid duplicate pages for the same entity. Use canonical names.

CHUNK NOTES:
{all_chunk_notes()}
"""


def parse_json_object(text: str) -> dict:
    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        raise RuntimeError("No JSON object found in Gemini response")
    return json.loads(match.group(0))


def build_entity_index(client: genai.Client, force: bool) -> list[dict]:
    KNOWLEDGE.mkdir(parents=True, exist_ok=True)
    out = KNOWLEDGE / "00-index.json"
    if out.exists() and not force:
        data = json.loads(out.read_text())
    else:
        print("Building knowledge entity index")
        text = call_gemini(client, entity_index_prompt())
        data = parse_json_object(text)
        out.write_text(json.dumps(data, indent=2) + "\n")
    pages = data.get("pages") or []
    if not isinstance(pages, list):
        raise RuntimeError("Knowledge entity index did not include pages list")
    return pages


def knowledge_page_prompt(page: dict) -> str:
    return f"""You are writing a detailed knowledge-base page from research notes.

Page title: {page.get('title')}
Page type: {page.get('type')}
Page reason: {page.get('why')}

Rules:
- Be exhaustive for this topic. Include every useful detail found in the notes.
- Do not fact-check or add medical disclaimers.
- Do not create new social content.
- Preserve source refs in this format:
  [video_id | views | likes | comments | link]
- Include examples, routines, side effects, benefits, stacks, timing, dosage, injection/storage/reconstitution details, warnings, hooks, and visual notes when relevant to this topic.
- If a detail appears multiple times, merge it but keep every important nuance.
- If the notes contain only a small amount on this topic, still write a complete page with all available source refs.

Use this Markdown structure:

# {page.get('title')}

## Overview
## What The Creator Says
## Uses / Benefits Mentioned
## Routines, Timing, Dosage, Or Process Details
## Side Effects, Problems, Or Mistakes Mentioned
## Stacks / Pairings / Related Topics
## Hooks And Angles Used
## Visual Patterns Used
## Source Videos

CHUNK NOTES:
{relevant_chunk_notes(page)}
"""


def safe_slug(slug: str, title: str) -> str:
    base = slug or title
    base = re.sub(r"[^a-zA-Z0-9]+", "-", base).strip("-").lower()
    return base or "topic"


def write_one_knowledge_page(key: str, page: dict) -> tuple[str, bool, str]:
    slug = safe_slug(str(page.get("slug") or ""), str(page.get("title") or "topic"))
    out = KNOWLEDGE / f"{slug}.md"
    client = genai.Client(api_key=key)
    try:
        out.write_text(call_gemini(client, knowledge_page_prompt(page)))
    except Exception as exc:  # noqa: BLE001
        return slug, False, f"{type(exc).__name__}: {exc}"
    return slug, True, str(out)


def build_knowledge_pages(client: genai.Client, force: bool, workers: int = 1) -> None:
    pages = build_entity_index(client, force)
    pending = []
    for page in pages:
        slug = safe_slug(str(page.get("slug") or ""), str(page.get("title") or "topic"))
        out = KNOWLEDGE / f"{slug}.md"
        if out.exists() and not force:
            print(f"Skipping {out}")
            continue
        pending.append(page)

    workers = max(1, workers)
    if workers == 1:
        for page in pending:
            slug = safe_slug(str(page.get("slug") or ""), str(page.get("title") or "topic"))
            out = KNOWLEDGE / f"{slug}.md"
            print(f"Writing knowledge page {out}")
            out.write_text(call_gemini(client, knowledge_page_prompt(page)))
    else:
        key = api_key()
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {}
            for page in pending:
                slug = safe_slug(str(page.get("slug") or ""), str(page.get("title") or "topic"))
                print(f"Queueing knowledge page {slug}")
                futures[executor.submit(write_one_knowledge_page, key, page)] = page
            for future in concurrent.futures.as_completed(futures):
                page = futures[future]
                slug = safe_slug(str(page.get("slug") or ""), str(page.get("title") or "topic"))
                try:
                    _, ok, message = future.result()
                except Exception as exc:  # noqa: BLE001
                    ok = False
                    message = f"{type(exc).__name__}: {exc}"
                if ok:
                    print(f"Wrote {message}")
                else:
                    print(f"FAILED {slug}: {message}")

    md_index = ["# Knowledge Base Index", ""]
    for page in pages:
        slug = safe_slug(str(page.get("slug") or ""), str(page.get("title") or "topic"))
        md_index.append(f"- [{page.get('title')}]({slug}.md) - {page.get('type')}: {page.get('why')}")
    (KNOWLEDGE / "00-index.md").write_text("\n".join(md_index) + "\n")


def write_analysis_index() -> None:
    files = [
        "knowledge-base/00-index.md",
        "claims-map.md",
        "content-pillars.md",
        "hook-map.md",
        "visual-analysis.md",
    ]
    lines = [
        "# elevii1 Research Library",
        "",
        "This folder is built from the local Gemini extraction files. It is research only; no Ghostfeed content generation has started.",
        "",
    ]
    for file in files:
        lines.append(f"- [{file}]({file})")
    lines.append("")
    lines.append("Source extraction files live in `research/elevii1/extractions/`.")
    (ANALYSIS / "00-index.md").write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["chunks", "finals", "all"], default="all")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--workers", type=int, default=1, help="Parallel workers for knowledge pages.")
    args = parser.parse_args()

    client = genai.Client(api_key=api_key())
    ANALYSIS.mkdir(parents=True, exist_ok=True)

    if args.phase in {"chunks", "all"}:
        build_chunks(client, args.force)
    if args.phase in {"finals", "all"}:
        if not list(CHUNKS.glob("chunk-*.md")):
            print("No chunk notes found. Run --phase chunks first.", file=sys.stderr)
            return 2
        build_knowledge_pages(client, args.force, args.workers)
        write_core_finals(client, args.force)
        write_analysis_index()

    print("Done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
