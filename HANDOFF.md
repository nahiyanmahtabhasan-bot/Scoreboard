# Handoff: Intrakore Scoreboard

## Project summary
Live web scoreboard that reads module progress from a **Google Sheet** (Scorecard tab) and displays it as an interactive dashboard. Now also supports **multi-source** input (Sheets, Word/Google Docs, Google Forms via response sheet, Microsoft Forms). Built as a **Flask** app, pushed to **GitHub**, deployed on **Vercel**.

---

## Repo & paths
| Item | Value |
|---|---|
| **GitHub repo** | https://github.com/nahiyanmahtabhasan-bot/Scoreboard |
| **Local path** | `C:\Users\hasan\intrakore-scoreboard` |
| **Branch** | `main` |
| **Latest committed** | `2d212cd` — Show a top-center date and label team workload as tasks completed |
| **Working tree** | **Uncommitted** multi-source work (see below) — not pushed yet |
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

## Uncommitted work (current session) — multi-source
**Not committed / not deployed.** Modified + new files:

```
M app.py
M parse_scorecard.py
M templates/index.html
M static/style.css
M public/index.html
M public/static/style.css
M requirements.txt
M pyproject.toml
?? sources/__init__.py
?? sources/fetch.py
?? sources/normalize.py
?? sources/parse_docx.py
?? sources/parse_generic_sheet.py
?? sources/parse_ms_forms.py
```

### Decisions locked
- **Config**: browser `localStorage` (`scoreboard-sources-config`) + shareable `#cfg=` URL hash + JSON import/export
- **Display**: **hybrid** — Scorecard mode (existing UI) + Generic boards for other sources
- **Sources v1**: Google Sheet, Word/Google Doc, Google Forms (linked response Sheet), Microsoft Forms (Graph API)

### Sources panel (UI)
- Header **Sources** button next to Refresh
- Add / Edit / Activate / Delete sources
- Preview → display mode → mapping editor
- Share: Copy share link (toast: “Copied to clipboard”, 3s), Export JSON, Import JSON
- **Add source** form opens above the source list (highlighted panel); focuses Name field
- Toolbar buttons use hover/active/focus feedback; Add source is **not** permanently highlighted (fixed)

### Hybrid display
- **Scorecard**: Module Progress / Team Workload / Phase Breakdown (unchanged behavior for Intrakore preset)
- **Generic**: tabs = configured boards — `stats`, `card_grid`, `table`, `text_sections`, `form_summary`

### API routes
| Route | Purpose |
|---|---|
| `GET /` | Scoreboard UI |
| `GET /api/scoreboard` | Scorecard JSON; optional `?sheet_id=&tab=&refresh=1` |
| `GET /api/source/preview` | Sniff tabs/columns/sections; suggest mapping |
| `POST /api/source/fetch` | Body: `{ type, connection, displayMode, mapping, refresh }` → scorecard or generic boards |
| `POST /api/source/upload` | Multipart `.docx` (max ~4MB); `preview=1` for sniff |
| `GET /api/health` | `{ status, ms_forms_configured }` |

### SSRF / fetch allowlist
Only: `docs.google.com`, `drive.google.com`, `www.googleapis.com`, `spreadsheets.google.com`, `graph.microsoft.com`, `login.microsoftonline.com`

### Microsoft Forms (Vercel env)
- `MS_TENANT_ID`, `MS_CLIENT_ID`, `MS_CLIENT_SECRET`
- Optional `MS_FORMS_SCOPE` (default `https://graph.microsoft.com/.default`)
- Secrets never in client config — only form ID + mapping

### Deps
- `flask`, `openpyxl`, **`python-docx>=1.1`** (in `requirements.txt` + `pyproject.toml`)

### Default config seed
Active source = Intrakore Scorecard (`displayMode: scorecard`, mapping preset `intrakore_scorecard`) so fresh load matches prior behavior.

---

## Features already implemented (prior commits)
1. Module Progress — P1/P2; completed pinned on top in default view
2. Completed styling — green outline + Complete badge
3. Sort — completion / priority / name
4. Filter — All, Priority, Completed, Pending, Ongoing, Not started
5. Refresh + auto-refresh every 30s with `?refresh=1`
6. Module click popup — 10 delivery stages
7. Team Workload — **tasks completed** (not hours) + %
8. Phase Breakdown
9. Single-page Module Progress (TV/PC)
10. Page resize 75–175% (`localStorage` `scoreboard-page-scale`)
11. Slideshow mode (pages + minutes; Escape to stop)
12. Top-center date; in slideshow: `Date · Page Name` in bubble

---

## Layout notes
- Compact header + 4 stats (Overall, Completed, Ongoing, Team) — white labels/detail
- TV ≥1800px → 5 cols; PC ≤1600 → 6; down to 2 on mobile
- CSS `zoom: var(--page-scale)` on `.page`
- Team slideshow scrolls `#panel-team .table-wrap`
- Duplicate static: keep `templates/` + `static/` and `public/` in sync

---

## Project structure (current)
```
intrakore-scoreboard/
├── app.py
├── parse_scorecard.py
├── sources/                 # NEW — multi-source fetch/parse/normalize
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
Note: local Flask process may get aborted when the agent shell ends; restart with `python app.py` if needed.

---

## Deploy
```powershell
git push origin main          # preferred — GitHub → Vercel auto-deploy
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
| `SCOREBOARD_CACHE_SECONDS` | `30` |
| `MS_TENANT_ID` / `MS_CLIENT_ID` / `MS_CLIENT_SECRET` | Microsoft Forms |
| Local only | `SCOREBOARD_XLSX`, `SCOREBOARD_USE_LOCAL=1` (disabled on Vercel) |

---

## Key preferences
- Scorecard sheet for Intrakore modules view; completed on top with green outline
- Team Workload = **tasks**, never hours
- Readable white text on stats / slideshow date
- Single-page Module Progress on TV/PC; PC layout unchanged when tuning TV
- Multi-source configs browser-local + shareable; no server DB
- Google Forms = linked response spreadsheet (no Google OAuth)
- Keep `public/` in sync when editing UI

---

## Suggested next steps
1. **Commit + push** multi-source changes to deploy to Vercel
2. Set MS Forms env on Vercel if needed
3. Optional: TV zoom auto-default, custom domain, Safari `transform: scale()` fallback
4. Keep this `HANDOFF.md` updated when major features land

---

Copy this into a new chat to continue.
