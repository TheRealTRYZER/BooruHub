---
trigger: always_on
---

# BooruHub Architecture Guidelines

## ⚙️ Core Architectures & Quirks
- **Media Rendering (CRITICAL)**: Never use video URLs (`.mp4`/`.webm`) in `<img>` or CSS `background-image` (causes browser blocks & 429s). Use static `preview_url`/`sample_url` images for `PostCard.vue`, relationship thumbs, and backdrops. Render videos exclusively in `<video>`.
- **Danbooru Tag Limit**: Free accounts limited to 2 tags. Extra tags are stripped and filtered locally in Python.
- **Danbooru Score 500s**: `order:score` without a floor causes Danbooru 500s. Provider injects score floors (e.g. `score:>=100`).
- **Rule34 Auth**: Requires `user_id` and `api_key` in config; returns plain string `"Missing authentication"` on error.
- **Rule34 Safe Category**: Rule34 has no native `safe` category (empty maps to exclusion unless negated).
- **Guest Mode**: Enforces `rating:general` (strips user rating filters including negative/optional prefixes).
- **Tag Mapping**: Localized tags map to unitags. If positive filter has empty map on a site, that site is excluded. If negative (e.g. `-rating:general`) is unmapped, it is skipped instead of excluding the site.
- **Referrer Meta Policy**: Never set `<meta name="referrer" content="no-referrer">` in the frontend (e.g., `index.html`). This causes browsers to strip referrer headers when fetching media from CDNs (such as Danbooru CDN), leading to 403 Forbidden/CORB errors because the CDNs block requests without referrers. Keep the default referrer policy.

# Testing Rules

- Every new function or module must have at least one unit test before the task is marked complete.
- Use Vitest for unit and integration tests in this project; never introduce Jest as a separate dependency.
- Test files must live next to the module they test: `foo.ts` → `foo.test.ts` in the same directory.
- Write tests that describe behaviour, not implementation: test what the function does, not how it does it.
- Aim for 80% line coverage as a floor; alert me if any PR would drop it below that threshold.
- Use `describe` blocks to group tests by scenario; use `it` or `test` with a sentence that starts with "it should..."
- Mock external APIs and database calls in unit tests; only use real connections in explicitly labelled integration tests.
- Never snapshot test plain HTML strings — they are brittle; prefer assertion-based tests for component output.
- Run the test suite with `pnpm test` before every commit suggestion; do not suggest committing failing tests.
- If you cannot figure out how to test something, ask me — do not skip the test silently.