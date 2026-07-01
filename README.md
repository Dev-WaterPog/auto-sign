# Auto Sign

Web app that stamps a signature image and today's date onto a PDF template.
The main flow (used by the dashboard page) finds a literal `{{signature}}`
placeholder in the PDF; a second, lower-level API also exists that locates a
signing spot via a configurable regex anchor (e.g. "Signature:", "ลงชื่อ").

- `backend/` — FastAPI service that performs the signing (and optionally stores templates/signatures).
- `frontend/` — Next.js (App Router, TypeScript, Shadcn UI) app that talks to the backend API.

## Backend

```
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API docs at http://localhost:8000/docs. Uploaded templates/signatures and signed
output are stored under `backend/app/storage/`.

Endpoints:
- `POST /api/templates` — upload a PDF template
- `POST /api/signatures` — upload a PNG/JPEG signature image
- `POST /api/sign` — `{ template_id, signature_id, signature_anchor?, date_anchor?, signature_position?, date_value? }`
  → stamps the signature + date, returns a `download_url`. `signature_position` is `"right"` (default),
  `"above"`, or `"below"` the matched anchor — e.g. for a form with a blank line, `"( name )"`, and a title
  underneath, set `signature_anchor` to (part of) the name and `signature_position: "above"` to stamp the
  signature directly over the blank line above the name. The signature's size auto-scales to the anchor
  text's line height and is clamped to the actual whitespace nearby so it can't overlap neighboring lines.
  If `date_anchor` matches multiple times on the page (e.g. a checklist with several "วันที่" fields, one
  per approver), the date is stamped at the occurrence closest to wherever the signature landed, not just
  the first one in the document — and centered within the field's underline when one is detected, instead
  of just following the label. `date_value` (`"YYYY-MM-DD"`) overrides the default of today. Stamps
  *every* page where `signature_anchor` matches (e.g. a multi-page bundle with one signature block per
  page), not just the first.
- `GET /api/sign/{job_id}/download` — download the signed PDF
- `POST /api/sign-document` — multipart `template` (PDF) + `signature` (PNG) + optional `date_value`
  (`"YYYY-MM-DD"`, defaults to today); finds the literal `{{signature}}` placeholder via regex on every
  page, redacts it, stamps the signature image + date (`DD/MM/YYYY`) in its place, and returns the signed
  PDF directly in the response body (also saved under `backend/app/storage/output/`). Returns `422` if the
  placeholder isn't found anywhere in the document.

## Frontend

```
cd frontend
npm install
copy .env.local.example .env.local
npm run dev
```

Open http://localhost:3000 (or the port Next.js picks if 3000 is busy). Set
`NEXT_PUBLIC_API_URL` in `.env.local` if the backend isn't on `localhost:8000`.

## Dashboard (`frontend/src/app/page.tsx`)

Single page that drives the whole flow end to end. If an access code isn't
already saved in the browser (see [Security](#security) below), it shows a
gate asking for one before anything else.

1. Upload a PDF template.
2. Draw or attach a signature via the Signature Pad.
3. Pick how to locate the signing spot — two tabs:
   - **`{{signature}}` placeholder** — template must contain that literal token; calls
     `POST /api/sign-document` (`signDocumentDirect`) directly with both files, no pre-upload needed.
   - **Find text on page** — for real forms with no placeholder (e.g. a blank line above a name). Enter
     text to search for and a position (above/right/below); uploads both files then calls `POST /api/sign`
     (`signDocumentByAnchor`). Badges warn if the anchor text (or the date field) wasn't found and the
     signature/date fell back to the bottom-right corner.
4. Pick the date to stamp (defaults to today, editable).
5. Click "Sign document automatically". The returned signed PDF is shown inline in an `<iframe>` preview
   and can be downloaded via the "Download signed PDF" button.

## Signature Pad

`frontend/src/components/signature-pad.tsx` lets a user either draw a
signature with mouse/touch on a `<canvas>`, or upload an existing signature
photo/scan. Both paths export a transparent PNG:

- **Draw**: canvas is never filled with a background color, so `toBlob`
  already yields a transparent PNG.
- **Upload**: pixels lighter than a threshold (adjustable via the slider) are
  faded to transparent based on luminance, keeping darker ink strokes opaque
  — a simple client-side background removal for typical white-paper scans.

It's wired into the dashboard's signature section via `onSave`, which just
hands the produced `File` back to the page — the file is sent directly to
`/api/sign-document` when signing rather than being pre-uploaded.

## Date font

Stamped dates use Sarabun (`backend/app/assets/fonts/Sarabun-Regular.ttf`,
bundled with the project so it doesn't depend on the host machine having any
Thai font installed) instead of the PDF library's default Helvetica, to match
the look of Thai documents that typically use TH Sarabun/TH SarabunPSK.
Configured once in `backend/app/services/fonts.py` and used by both signing
services.

## Security

The app has **no database and no user accounts** — every upload is just a
file on disk named by a random id, with no owner tracking. Two protections
exist so it can be exposed on a public URL without being wide open:

- **Access token** (`backend/app/core/auth.py`) — set `AUTOSIGN_ACCESS_TOKEN`
  (in `backend/.env`) to require that value on the `X-Access-Token` header
  for every API route except `/api/health`. Leave it unset for local
  development — auth is skipped entirely so there's no friction. The
  frontend gate (`frontend/src/app/page.tsx`) asks for this code once,
  stores it in `localStorage`, and attaches it to every request
  (`frontend/src/lib/api.ts`); a `401` response clears the stored code and
  re-shows the gate. This is a single shared secret, not per-user auth — good
  enough to keep the app from being wide open to search-engine crawlers and
  randoms, not a substitute for real accounts if that's ever needed.
- **Upload size limits** (`backend/app/core/limits.py`) — 5 MB for
  signatures, 25 MB for PDF templates, enforced by capping how many bytes are
  ever read from the upload rather than buffering the whole file first.

Before making the running app reachable from the public internet:
1. Set `AUTOSIGN_ACCESS_TOKEN` to a long random value and share it only with
   intended users.
2. Set `AUTOSIGN_CORS_ORIGINS` to the real frontend domain (never `*`).
3. Periodically clear `backend/app/storage/` — uploaded/signed files are
   never deleted automatically.

See also the root `.gitignore`, which excludes `signature/` and `template/`
(the real signature image and internal documents used to develop this
project) from version control.

## Notes

- The anchor patterns used to locate the signature/date on the page are
  configurable per request (`signature_anchor` / `date_anchor` on `POST
  /api/sign`); defaults live in `backend/app/core/config.py`.
- If no anchor text is found, the signature and date fall back to the
  bottom-right corner of the last page so a document is never left unsigned.
- `signature/signature_pong.jpg` and `template/*.xlsx` at the repo root are
  the original source files provided for this project. The signing pipeline
  works on PDF templates — see the note below about the Excel template.
