# Handoff: Intrakore Scoreboard

## Project summary
Live web scoreboard that reads module progress from a **Google Sheet** (Scorecard tab) and displays it as an interactive dashboard. Supports **multi-source** input (Sheets, Word/Google Docs, custom websites, Google Forms via response sheet, Microsoft Forms). Built as a **Flask** app, pushed to **GitHub**, deployed on **Vercel**.

---

## Repo & paths
| Item | Value |
|---|---|
| **GitHub repo** | https://github.com/nahiyanmahtabhasan-bot/Scoreboard |
| **Local path** | `C:\Users\hasan\intrakore-scoreboard` |
| **Branch** | `main` (tracks `origin/main`) |
| **Latest committed / pushed** | `d0f059d` — Add multi-source inputs and fix Phase Breakdown from Scorecard matrices |
| **Working tree** | **Uncommitted** website / hero title / loading-overlay polish (see below) — not pushed |
| **Production URL** | **https://intrakore-scoreboard.vercel.app** |
| **Vercel project** | `intrakore/intrakore-scoreboard` (team: intrakore) |
| **Vercel dashboard** | https://vercel.com/intrakore/intrakore-scoreboard |

---

## Google Sheet (default live data source)
| Item | Value |
|---|---|
| **Sheet URL** | https://docs.google.com/spreadsheets/d/1Dt5ae3Cekxnd4XNZr1MdqBfx_vJyVFLeN5j-n-ibSjU/edit |
| **Sheet ID** | `1Dt5ae3Cekxnd4XNZr1MdqBfx_vJyVFLeN5j-n-ibSjU` |
| **Tab used** | `Scorecard` |
| **Sharing required** | **Anyone with the link → Viewer** |
| **Export URL** | `https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx` |

---

## Uncommitted work (this chat) — sources polish
**Not committed / not deployed.** Diff vs `d0f059d`:

```
M HANDOFF.md
M app.py
M templates/index.html
M static/style.css
M public/index.html
M public/static/style.css
M sources/normalize.py
M sources/parse_docx.py
M sources/parse_generic_sheet.py
?? sources/layouts.py
?? sources/parse_bugs.py
```

### What landed in this chat (uncommitted)
1. **Custom website source** (`type: website`) — paste any URL; displayed as full-bleed iframe. Google Docs/Sheets/Slides/Forms URLs auto-converted to `/preview` or `/embed`. Client-side only (no server fetch / SSRF). Fallback “Open in a new tab” if host blocks embedding.
2. **Hero title updates** — `#hero-eyebrow` / `#hero-title` follow active source name. Intrakore scorecard keeps “Live Scoreboard” / “Intrakore · Project Plan”.
3. **Google Doc titles** — `parse_docx` reads `core_properties.title`, else first real H1; fills placeholder names (“New source” / “Untitled”); richer `doc-view` layout for `text_sections`.
4. **Loading overlay** — full-screen popup on **Activate** / save-new-source only (`opts.fromActivate`). **Not** shown on 30s auto-sync or Refresh (refresh icon still spins).
5. Website sources skip the 30s auto-reload of the iframe.
6. **No-AI layout designer** — `sources/layouts.py` infers column roles + picks a template on Preview; Sources editor template gallery + guided field mapper; progress cards sort completed-first.
7. **Source / board mix fix** — Preview no longer forces Scorecard mode just because the workbook *contains* a Scorecard tab; only the selected tab named `Scorecard` gets that preset. Invalid sheet tabs error instead of silently loading the first tab. Activating a source resets board selection (prefers the table named after the sheet). Stale fetch responses ignored. Failed loads clear previous source UI. Hero shows **Rows** for sheets (not Sections: 0). Saving a multi-tab sheet requires an explicit tab pick.
8. **Advanced boards Save** — Preview no longer wipes custom boards when re-previewing; board field changes live-sync into mapping; **Save boards** button in Advanced boards (plus sticky top Preview/Save) so you don’t lose edits scrolling up.
9. **All configured boards render** — normalize no longer silently drops boards with empty/unknown types (e.g. `text_sections` on sheets); Apply field mapping patches roles in place instead of wiping extra boards; generic tabs wrap.
10. **Bug / issue index layout** — new `bug_index` template (auto for BugIndex-like sheets: Severity + Finding/Bug-No-Bug/STATUS). Table-first activation with emphasis chips on Severity / Bug·No Bug / STATUS; categorical Breakdown stats; Findings cards with meta badges (not fake % progress). Role inference no longer treats `#` row numbers as progress or Modules as the card title when a Finding column exists.
11. **Type-aware board fields** — Advanced boards hide irrelevant controls: **Columns** only for `stats` / `table` / `form_summary`; card grids show title / subtitle / progress / **card badges (meta)** instead. Hint text explains which fields each type uses. (Previously selecting Columns on a Progress/`card_grid` board did nothing — only the title field rendered.)
12. **Non-progress activation** — default board pick prefers the data table for `bug_index` / `simple_table` / non-`status_tracker` templates; bug-sheet hero surfaces severity/status tiles from the Breakdown board.
13. **Meta chip text** — finding/status badges show **value only** (e.g. `Bug` / `No Bug` / `Critical`), not `BUG/ NO BUG Bug`; column name stays on hover tooltip.
14. **Bugs as own source** — dedicated **Bug Index** / **Bug analysis** source (snag-list sheet / `BugIndex` tab) shows Unopened / Open / Actioned / Closed summary (blank STATUS → Unopened) and filterable detail cards. Scorecard no longer has a Bugs tab; activate **Bug analysis** from Sources. Hero stats use the same gradient cards as Project Plan; counts update with Status / Severity / Module / Search filters. Severity×module×status pivot table removed from the UI.
15. **Bug analysis hero polish** — removed bottom pivot table; hero Unopened/Open/Actioned/Closed tiles match Project Plan `stat-card` gradients (`stat-primary` / `stat-ongoing` / `stat-complete`); filter changes recompute hero counts from the filtered set.

### Bug sheet source (example)
| Item | Value |
|---|---|
| **Sheet URL** | https://docs.google.com/spreadsheets/d/1E7ucvpw7dOismcoBGWm3wqp_oIo_QBKG/edit?gid=1611749406 |
| **Sheet ID** | `1E7ucvpw7dOismcoBGWm3wqp_oIo_QBKG` |
| **Tab** | `BugIndex` |
| **Key columns** | ID, Severity, Finding, Modules, Bug/ No Bug, STATUS |
| **Scoreboard Bugs view** | Activate the **Bug Index** source (not a Scorecard tab); fetch uses `bug_index` / BugIndex → `mode: bugs` |
| **How to wire as a source** | Sources → Add/Edit → paste URL → pick **BugIndex** tab → Preview → confirm **Bug / issue index** template → Save |

### Why “3 columns” only showed the module name
`card_grid` (Progress / Findings cards) never used the Columns multi-select — only `titleField` / `subtitleField` / `progressField`. BugIndex was mis-detected as `status_tracker`, so cards titled on **Modules** and treated `#` as progress. Fixed by type-aware field visibility + `bug_index` layout.

### Decisions locked (multi-source — already on `main` at `d0f059d`)
- **Config**: browser `localStorage` (`scoreboard-sources-config`) + shareable `#cfg=` URL hash + JSON import/export
- **Display**: hybrid — Scorecard + Generic boards + **Website embed** (embed is uncommitted polish on top of committed multi-source)
- **Sources**: Google Sheet, Word/Google Doc, Custom website, Google Forms (linked response Sheet), Microsoft Forms (Graph API)

### Sources panel (UI)
- Header **Sources** button next to Refresh
- Add / Edit / Activate / Delete; Preview → mapping; share link / JSON import-export
- Add source form opens above list; focuses Name
- Activate → loading overlay until fetch completes; auto-sync stays quiet
- **Google Sheet / Forms**: Sheet tab is a dropdown of tabs inside the workbook (Load sheets / Preview fills the list)
- **Hero stats (generic)**: Boards / Rows for ordinary sheets; bug sheets reuse Breakdown tiles (Severity / verdict / STATUS counts)

### Hybrid display
- **Scorecard**: Module Progress / Team Workload / Phase Breakdown
- **Generic**: boards — `stats`, `card_grid`, `table`, `text_sections`, `form_summary` (board tabs are views of the *same* sheet — e.g. Findings cards + BugIndex table — not separate sheet tabs)
- **Website**: iframe of configured URL
- **Layout designer (no AI)**: on Preview, rule-based column-role inference + layout template (`bug_index`, `status_tracker`, `summary_cards`, `team_roster`, `form_responses`, `simple_table`, `document`). Sources editor shows template gallery + guided field mapper; advanced boards under a disclosure with **Save boards**. Type-aware field controls; sticky Preview/Save bar.

### API routes
| Route | Purpose |
|---|---|
| `GET /` | Scoreboard UI |
| `GET /api/scoreboard` | Scorecard JSON; optional `?sheet_id=&tab=&refresh=1` |
| `GET /api/bugs` | Default snag-list BugIndex (legacy/debug); primary path is source fetch with `mode: bugs` |
| `GET /api/source/preview` | Sniff tabs/columns/sections; suggest mapping + `suggested_template` / `column_roles` |
| `POST /api/source/fetch` | `{ type, connection, displayMode, mapping, refresh }` → scorecard, bugs, or generic |
| `POST /api/source/upload` | Multipart `.docx` (max ~4MB); `preview=1` for sniff |
| `GET /api/health` | `{ status, ms_forms_configured }` |

Website sources: **no** API fetch — client iframe only.

### SSRF / fetch allowlist
Only: `docs.google.com`, `drive.google.com`, `www.googleapis.com`, `spreadsheets.google.com`, `graph.microsoft.com`, `login.microsoftonline.com`

### Microsoft Forms (Vercel env)
- `MS_TENANT_ID`, `MS_CLIENT_ID`, `MS_CLIENT_SECRET`
- Optional `MS_FORMS_SCOPE` (default `https://graph.microsoft.com/.default`)
- Secrets never in client config — only form ID + mapping

### Deps
- `flask`, `openpyxl`, **`python-docx>=1.1`**

### Default config seed
Active source = Intrakore Scorecard (`displayMode: scorecard`, mapping preset `intrakore_scorecard`). Also seeds **Bug analysis** (`tab: BugIndex`, `mapping.template: bug_index`, `autoSync: true`) pointing at the snag-list sheet (`…/1E7ucvpw7dOismcoBGWm3wqp_oIo_QBKG/edit?gid=1611749406`). Auto-refresh every 30s applies to Scorecard and Bug analysis when active (not website embeds).

---

## Features already implemented (on main)
1. Module Progress — P1/P2; completed pinned on top
2. Completed styling — green outline + Complete badge
3. Sort / Filter
4. Refresh + auto-refresh every 30s
5. Module click popup — 10 delivery stages
6. Team Workload — **tasks completed** (not hours) + %
7. Phase Breakdown (fixed from Scorecard matrices in `d0f059d`)
8. Single-page Module Progress (TV/PC)
9. Page resize 75–175% (`localStorage` `scoreboard-page-scale`)
10. Slideshow mode
11. Top-center date
12. Multi-source panel + APIs (`d0f059d`)

---

## Layout notes
- Compact header + 4 stats — white labels/detail
- TV ≥1800px → 5 cols; PC ≤1600 → 6; down to 2 on mobile
- CSS `zoom: var(--page-scale)` on `.page`
- Keep `templates/` + `static/` and `public/` in sync

---

## Project structure
```
intrakore-scoreboard/
├── app.py
├── parse_scorecard.py
├── sources/                 # multi-source fetch/parse/normalize + layouts
│   └── layouts.py           # column roles + layout templates (no AI)
├── requirements.txt
├── pyproject.toml           # entrypoint = "app:app"
├── vercel.json
├── .python-version          # 3.12
├── templates/index.html
├── static/style.css
└── public/                  # CDN fallback — keep in sync
```

---

## Local dev
```powershell
cd C:\Users\hasan\intrakore-scoreboard
python -m pip install -r requirements.txt
python app.py
# → http://127.0.0.1:8080
```
Note: local Flask may die when agent shells end → `ERR_CONNECTION_REFUSED`; restart with `python app.py`.

---

## Deploy
```powershell
git push origin main          # GitHub → Vercel auto-deploy
```
CLI `vercel deploy --prod` may hit auth issues.

Git commit author (if committing as bot):
```powershell
git -c user.email="nahiyanmahtabhasan-bot@users.noreply.github.com" -c user.name="nahiyanmahtabhasan-bot" commit -m "message"
```

---

## Env vars
| Variable | Default / notes |
|---|---|
| `GOOGLE_SHEET_ID` | Intrakore sheet ID above |
| `BUGS_SHEET_ID` / `BUGS_SHEET_TAB` | Snag list sheet (`1E7ucvpw7dOismcoBGWm3wqp_oIo_QBKG` / `BugIndex`) |
| `SCOREBOARD_CACHE_SECONDS` | `30` |
| `MS_TENANT_ID` / `MS_CLIENT_ID` / `MS_CLIENT_SECRET` | Microsoft Forms |
| Local only | `SCOREBOARD_XLSX`, `SCOREBOARD_USE_LOCAL=1` (disabled on Vercel) |

---

## Key preferences
- Scorecard for Intrakore modules; completed on top with green outline
- Team Workload = **tasks**, never hours
- Readable white text on stats / slideshow date
- Multi-source configs browser-local + shareable; no server DB
- Google Forms = linked response spreadsheet (no Google OAuth)
- Custom websites = iframe; some hosts block embedding
- Loading popup **only** on source activate/switch — not on 30s sync
- Generic sources: auto layout from heuristics; user can override via template gallery / field mapper (no AI / no LLM cost)
- Bug / snag sheets → `bug_index` (table-first, severity/status chips) — not module progress cards
- Scorecard **Bugs** tab removed — use the seeded **Bug analysis** source instead (blank STATUS = Unopened, not Closed); filterable cards with severity/status chips + module/area/responsible; click a card for full finding detail; hero status tiles match Project Plan gradients and update with filters (no pivot table)
- Advanced board **Columns** control only appears for board types that use it
- Keep `public/` in sync when editing UI

---

## Suggested next steps
1. **Commit + push** uncommitted website/title/loading polish + layout designer + bug_index + type-aware boards to deploy
2. Set MS Forms env on Vercel if needed
3. Optional: TV zoom auto-default, custom domain, Safari `transform: scale()` fallback
4. Optional later: AI source-designer wizard (external LLM) — skipped for now (API cost)
5. Keep this `HANDOFF.md` updated when major features land
6. After deploy: re-open any BugIndex source → pick **BugIndex** tab → **Preview** (should suggest Bug / issue index) → Save / Activate

---

Copy this into a new chat to continue.
