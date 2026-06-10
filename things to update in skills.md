# Things to Update in Skills

Running notes for Ghostfeed skill improvements discovered while using the skills for real content generation.

## 2026-06-06

### Install path mismatch

- Ghostfeed developers page says the installable skill content is published in `ghostfeed-ai/ghostfeed-skill` and should be kept in sync with `.agents/skills/<skill-name>`.
- The public GitHub repository currently exposes the installable bundles under `skills/<skill-name>`, not `.agents/skills/<skill-name>`.
- The working install command used `skills/ghostfeed-public-api-core`, `skills/ghostfeed-avatar-api`, `skills/ghostfeed-ugc-reactions-api`, and `skills/ghostfeed-slideshow-api`.
- Suggested update: either update the docs page wording from `.agents/skills` to `skills`, or add a visible installation command that uses the current repository layout.

### Missing Pinterest search workflow

- User expected a Pinterest search feature to be available through the Ghostfeed API/skill for finding image references.
- Installed Ghostfeed skills do not document a Pinterest search endpoint or workflow.
- Live API probe on 2026-06-09 confirmed the route exists:
  - `POST /api/v1/tools/pinterest/search`
  - Body: `{ "query": "fat fitness transformation", "limit": 3 }`
  - Auth: normal public API bearer token plus `X-Workspace-Id`.
  - Response: `success: true`, `data.query`, `data.limit`, `data.maxLimit`, and `data.images[]` where each item has `{ index, imageUrl }`.
  - `maxLimit` observed as `50`.
- `GET /api/v1/tools/pinterest/search` returns 404; this is POST-only.
- Public docs search only surfaced a Ghostfeed blog workflow mentioning external Apify Pinterest scraping, not a public API route.
- Other probed routes returned 404s: `/api/v1/search/pinterest`, `/api/v1/pinterest/search`, `/api/v1/reference-images/search`, and `GET /api/v1/tools`.
- Suggested update: add `POST /api/v1/tools/pinterest/search` to the public skill bundle and document the POST-only method, request body, limit cap, and response shape.

### Import status endpoint shape after Smart Crop

- The UGC skill says to poll `GET /api/v1/ugc/templates/:templateId/import-status` after social import.
- During Smart Crop imports, the generation ledger completed successfully and the source template was readable via `GET /api/v1/ugc/templates/:templateId`.
- However, `GET /api/v1/ugc/templates/:templateId/import-status` returned `{ code: "not_found", message: "Template not found" }` for both imported source template ids after completion.
- Suggested update: clarify whether agents should poll the generation ledger instead of `import-status` for Smart Crop imports, or fix/document the expected `import-status` behavior for `api-import-*` template ids.

### Kling 2.5 Pro naming mismatch

- User asked to use "Kling 2.5 Pro" for prompt-based video generation.
- Public model catalog currently exposes `kling_2_5_turbo` for prompt-driven image-to-video generation, not `kling_2_5_pro`.
- The catalog also exposes `kling_2_6_motion` and `kling_3_motion`, but those are `source_motion` models, which the user explicitly does not want for this workflow.
- Suggested update: document the exact public model id customers should use when they say Kling 2.5 Pro, or expose the expected `kling_2_5_pro` id if it exists internally.

### Kling Turbo minimum duration mismatch

- User asked for 2-3 second prompt-based clips.
- Public model catalog for `kling_2_5_turbo` only allows `durationSeconds` values of `5` or `10`.
- Suggested update: document the minimum available duration for each public video model, or expose shorter 2-3 second durations if supported internally.

### Video generation ledger stays processing after videos complete

- User noticed videos were complete in the Ghostfeed UI while the agent was still polling.
- Root cause confirmed: `GET /api/v1/generations/:generationId` for the seven Carlos `kling_2_5_turbo` video jobs still returns `status: "processing"`, `outputs: []`, and `progressMessage: "Video generation is running"` even after the corresponding videos are complete and visible from `GET /api/v1/ugc/videos`.
- Several UGC video generation ids stayed stuck as `processing` in the generation ledger even after the corresponding videos appeared complete via `/api/v1/ugc/videos`.
- Corresponding completed videos are visible via `/api/v1/ugc/videos` with `stage: "complete"` and `videoGenerationMode: "kling_2_5_turbo"`.
- The core skill currently says to poll `GET /api/v1/generations/:generationId` until complete/failed, which is unsafe for these video jobs.
- Suggested update: for UGC video generation, poll both the generation ledger and `/api/v1/ugc/videos` filtered by `selectedFrameId`, `createdAfter`, or known `videoId` when available. Also update backend generation ledger status when the video stage completes.
