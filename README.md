# AI Image Generator (Chainlit + Pollinations)

A small Chainlit app that turns a text prompt into an AI-generated image using the **Pollinations AI** image API. Built as a hands-on exercise in Chainlit's decorator-based event model, and as a practical comparison against Streamlit.

> **Note:** this project originally used Google's Gemini image model, but Gemini's free tier proved too rate-limited for repeated testing during development. It was swapped for Pollinations, which is free, keyless, and has no daily quota — the rest of the app (Chainlit structure, decorators, UI, error handling) is unchanged. See [Gemini → Pollinations](#gemini--pollinations-why-and-what-changed) below for details.

**Live app:** _add your Render URL here after deploying (e.g. `https://chainlit-pollinations-image-gen.onrender.com`)_

## What it does

- Type a description in the chat, Pollinations generates an image, it appears inline.
- A `cl.Step` shows a "Generating with Pollinations" progress indicator while the API call runs.
- Errors (rate limiting, timeouts, bad responses) are caught and shown as a readable chat message instead of crashing the app.
- Each session tracks how many images have been generated (`cl.user_session`).

## Tech stack

| Piece | Choice |
|---|---|
| UI / app framework | [Chainlit](https://docs.chainlit.io) |
| Image generation | [Pollinations AI Image API](https://github.com/pollinations/pollinations/blob/master/APIDOCS.md) — `flux` model by default, via a plain async HTTP call (`httpx`) |
| Config | `python-dotenv` + environment variables |
| Deployment | Render (native Python web service, free tier) |

## Project structure

```
.
├── app.py            # the whole app: decorators, Pollinations call, error handling
├── chainlit.md        # welcome text shown in the Chainlit sidebar
├── requirements.txt
├── render.yaml         # Render Blueprint: build/start commands, env vars
├── .env.example
└── .gitignore
```

## Setup

```bash
git clone <your-repo-url>
cd chainlit-pollinations-image-gen

python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env          # optional — Pollinations works with no keys at all
```

### Environment variables

No key is required to run this app. Everything is optional and only changes behavior:

```
POLLINATIONS_API_TOKEN=        # optional — get one at https://auth.pollinations.ai for higher rate limits + no watermark
POLLINATIONS_MODEL=flux        # image model
POLLINATIONS_WIDTH=1024
POLLINATIONS_HEIGHT=1024
```

`POLLINATIONS_MODEL`/`WIDTH`/`HEIGHT` are configurable so it's a one-line `.env` change to try a different model (e.g. `turbo` for faster, lower-fidelity generations) or resolution without touching code. If `POLLINATIONS_API_TOKEN` is unset, the app still works but is limited to the anonymous tier (~1 request per 15 seconds) and images carry a small watermark.

### Run locally

```bash
chainlit run app.py -w
```

Opens at `http://localhost:8000`. `-w` enables hot-reload while editing.

## How the Chainlit decorators work here

A decorator wraps a function to add behavior around it without changing its body. Chainlit uses decorators to register callbacks for events in a chat session — you don't write layout code, you write handlers, and Chainlit builds the UI around them.

| Decorator | Fires when | What we do with it |
|---|---|---|
| `@cl.on_chat_start` | Once, when a user opens a new chat | Initialize session state (`image_count`) and send a welcome message explaining what to type |
| `@cl.on_message` | Every time the user sends a message | Take the prompt, call Pollinations, handle errors, send the image back |

Other Chainlit UI elements used:
- **`cl.Message`** — every chat bubble, including the welcome text, errors, and the final prompt+image reply.
- **`cl.Image`** — renders the generated PNG bytes inline in the chat.
- **`cl.Step`** — a collapsible "Generating with Pollinations" indicator so the user sees work happening during the API call, instead of a silent pause.
- **`cl.user_session`** — a plain per-session dict that persists across messages without any extra state management, used here to count images generated.

## Pollinations integration

Per the [official API docs](https://github.com/pollinations/pollinations/blob/master/APIDOCS.md), image generation is a single `GET` request:

```
GET https://image.pollinations.ai/prompt/{url-encoded prompt}?model=flux&width=1024&height=1024
```

The response body is the raw image bytes directly (not JSON), so the app just streams that back into a `cl.Image`:

```python
async with httpx.AsyncClient(timeout=90) as client:
    response = await client.get(url, params=params, headers=headers)
# response.content is the image bytes
```

The call is made with `httpx.AsyncClient` (not `requests`) so it doesn't block Chainlit's event loop while waiting on the image — `requests` is synchronous and would stall other sessions during generation.

No API key is required for anonymous use, which is why this project moved off Gemini: Gemini's free tier rate limits (a fixed daily quota, shared across all testing) kept interrupting development, while Pollinations' anonymous tier (~1 request/15s, no daily cap) held up fine for iterative testing. An optional `POLLINATIONS_API_TOKEN` (free registration at [auth.pollinations.ai](https://auth.pollinations.ai)) raises that rate limit and removes the small watermark Pollinations adds to anonymous, unauthenticated requests.

### Gemini → Pollinations, why and what changed

| | Gemini (original) | Pollinations (current) |
|---|---|---|
| Auth | Required API key | None required (optional token for higher limits) |
| Rate limits | Fixed free-tier daily quota | ~1 req/15s anonymous, no daily cap |
| Call shape | `google-genai` SDK, `generate_content()` | Plain HTTP `GET`, raw image bytes back |
| Dependencies | `google-genai` | `httpx` (already a Chainlit dependency) |

Everything else — the Chainlit decorators, the `cl.Step`/`cl.Image` UI, the session counter, the overall app structure — is unchanged. Swapping the image provider only touched `generate_image_bytes()` and the environment variables; that separation is exactly why the swap took minutes rather than a rewrite.

## Error handling

- **Empty prompt** → user is asked to type something, no API call made.
- **Rate limited (HTTP 429)** → caught and shown as a clear "you're being rate limited, wait a moment" message instead of a raw error.
- **Timeout** → the request has a 90s timeout; a timeout is caught and shown as a friendly retry prompt.
- **Non-image response** (e.g. an error page instead of an image) → detected via `content-type` and surfaced as an error rather than silently displaying garbage.
- **Any other API/network error** → logged server-side and shown as a friendly message; the app keeps running for the next prompt.

## Deployment (Render)

Chainlit holds an open WebSocket to the browser, so it needs a real long-running server — not a serverless platform like Vercel. **Render's free web service tier** was chosen because it's genuinely free (no credit card required to sign up), runs Python natively (no Dockerfile needed), and explicitly supports inbound WebSocket connections on the free plan. The one tradeoff: a free service spins down after 15 minutes of no traffic and takes ~1 minute to wake back up on the next visit — worth knowing about before a live demo, so open the URL a minute early.

### Option A — Blueprint (one click, recommended)

This repo includes `render.yaml`, which tells Render exactly how to build and run the app.

1. Push this repo to GitHub.
2. In the [Render Dashboard](https://dashboard.render.com), click **New → Blueprint**, connect the repo, and Render reads `render.yaml` automatically — service name, build command, start command, and env vars are all pre-filled.
3. No required secrets — Pollinations needs no API key. If you registered a `POLLINATIONS_API_TOKEN`, add it under the service's **Environment** tab after it's created (don't commit it to `render.yaml`).
4. Click **Apply** / **Deploy**. Render installs `requirements.txt` and runs the start command.
5. Once the log shows the service is live, open the given `.onrender.com` URL and test a prompt.

### Option B — Manual web service (no render.yaml)

1. In the Render Dashboard: **New → Web Service** → connect this GitHub repo.
2. Runtime: **Python 3**.
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `chainlit run app.py --host 0.0.0.0 --port $PORT --headless`
5. Instance Type: **Free**.
6. Deploy, then open the assigned URL.

Both options produce the same result — `render.yaml` just means you don't fill in the form by hand.

## Streamlit vs Chainlit

Coming from Streamlit, the core difference is **rerun vs. callback**:

- **Streamlit re-runs the entire script top-to-bottom** on every interaction. Anything that needs to survive a click goes into `st.session_state`, and you're constantly reasoning about "what re-executes when this button is pressed."
- **Chainlit only runs the specific callback for the event that happened.** `@cl.on_message` fires once per message; a local variable is just a local variable; `cl.user_session` persists because nothing re-executes around it.

| | Chainlit | Streamlit |
|---|---|---|
| Mental model | Event callbacks (decorators) | Script reruns top to bottom |
| Best for | Chat / conversational AI apps | Dashboards, forms, data apps |
| Chat UI | Built in (message bubbles, streaming, threads) | You assemble it yourself from `st.chat_message` |
| State handling | Plain variables + `cl.user_session`, persists naturally | `st.session_state`, with rerun-aware caveats |
| Layout control | Minimal — you get the chat shell | Full — columns, tabs, sidebars |
| Progress/tool visibility | `cl.Step` for free | Build your own spinner/progress UI |
| Deployment | Needs a real server (WebSockets) — container/VM | Streamlit Community Cloud, one click, free |
| Dev speed for a chat app | Faster — less boilerplate | Slower — you're building chat UI by hand |

**When I'd use which:** Chainlit for anything that's fundamentally a conversation with an LLM/agent — I wrote almost no UI code here and got a working chat interface immediately. Streamlit for anything with charts, tables, or multiple interactive controls around the model, where its rerun model and rich widget set are the whole point.

## Lessons learned

- Chainlit's decorator model removes an entire class of "did this rerun and reset my state" bugs that Streamlit apps often have — session state is just a dict that survives.
- Keeping the image-generation call isolated in one function (`generate_image_bytes`) meant switching providers (Gemini → Pollinations) touched almost nothing else in the app — the decorators, UI, and error-handling shape didn't need to change, only the function's internals and the `.env` keys.
- Free-tier rate limits are a real constraint for iterative development, not just production — it's worth checking a provider's daily/interval limits against how many test calls a normal dev session will make, not just against expected production traffic.
- Async matters even for "simple" HTTP calls: using `httpx.AsyncClient` instead of the blocking `requests` library keeps Chainlit's event loop free to handle other sessions while an image generates.
- `cl.Step` turned "waiting for an API call" from a silent freeze into visible, understandable progress, for basically no extra code.

---

*Built as a learning project comparing Chainlit and Streamlit for AI application development.*
