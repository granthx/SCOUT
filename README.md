<div align="center">

# SCOUT
[https://scout-server.pages.dev/]
### Smart Commerce & Omnichannel Unified Tracker

**One query. Every platform. Best pick.**

SCOUT is an AI-powered shopping assistant that searches Amazon, Flipkart, Blinkit, Zepto, Instamart, Myntra & Ajio simultaneously — ranks every result through a transparent 6-factor scoring engine, and streams a natural-language recommendation back in real time.

[Live Demo](#) · [API Docs](#api-reference) · [Report a Bug](https://github.com/4-thkind/SCOUT/issues)

![Python](https://img.shields.io/badge/Python-100%25-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-async%20%2B%20SSE-009688?logo=fastapi&logoColor=white)
![Status](https://img.shields.io/badge/status-active%20development-e7c98a)

</div>

---

## Why SCOUT

Shopping across Indian e-commerce means opening seven tabs, comparing prices by hand, and second-guessing which platform actually has the fastest delivery. SCOUT collapses that into a single chat message:

![SCOUT Interface](Frontend/logos/image.png)

> **"best wireless headphones under ₹3000"**

...and in under a second, it's already searching, ranking, and narrating a verdict — not just a list of links, but an actual recommendation with reasoning.

```text
You:   best wireless headphones under ₹3000 🎧

SCOUT: The Sony WH-CH520 is your best pick — 50h battery, USB-C charging,
       and Sony's DSEE upscaling at ₹2,990 from Flipkart. If budget is
       tighter, the boAt Rockerz 450 at ₹1,299 punches well above its
       price with 15h playtime and solid bass.

       ┌─────────────────────────────┬────────┬────────┬──────────┐
       │ Product                     │ Price  │ Score  │ Delivery │
       ├─────────────────────────────┼────────┼────────┼──────────┤
       │ Sony WH-CH520 (Flipkart)    │ ₹2,990 │ 94/100 │ 3 days   │
       │ boAt Rockerz 450 (Amazon)   │ ₹1,299 │ 88/100 │ 2 days   │
       │ JBL Tune 520BT (Amazon)     │ ₹2,499 │ 81/100 │ 1 day    │
       └─────────────────────────────┴────────┴────────┴──────────┘
```

---

## How It Works

Six sequential stages, each powered by a specialized component — no hardcoded logic, the LLM drives routing, extraction, and narration end to end.

```mermaid
flowchart TD
    A([User Message<br><i>natural language, Hindi/Hinglish native</i>]) --> B

    B["<b>① Intent Router (Claude)</b><br>classifies into 6 intent types"] --> C
    
    C["<b>② Structured Extraction (Claude)</b><br>NL → typed JSON: budget, brand, features, pincode"] --> D
    
    D["<b>③ Parallel Search</b><br>fans out to every configured platform concurrently<br><i>Amazon · Flipkart · Blinkit · Zepto · Instamart · Myntra · Ajio</i>"]
    
    D --> E["<b>Deduplication</b><br>deduplicated by title fingerprint"]
    
    E --> F["<b>④ 6-Factor Ranking</b><br>price fit · rating · review volume · delivery speed · platform trust · feature match<br>→ 0–100 composite score"]
    
    F --> G["<b>⑤ Review Summarisation (Claude)</b><br>concurrent pros / cons / verdict per top product"]
    
    G --> H["<b>⑥ SSE Streaming</b><br>events flow to the frontend the moment they're ready<br><i>thinking → intent → products → text (token-by-token) → done</i>"]
    
    H --> I([Frontend])
    
    style A fill:#2e2e2e,stroke:#e69a0b,stroke-width:2px,color:#fff
    style I fill:#2e2e2e,stroke:#e69a0b,stroke-width:2px,color:#fff
    style B fill:#1a1a1a,stroke:#333,color:#fff
    style C fill:#1a1a1a,stroke:#333,color:#fff
    style D fill:#1a1a1a,stroke:#333,color:#fff
    style E fill:#1a1a1a,stroke:#333,color:#fff
    style F fill:#1a1a1a,stroke:#333,color:#fff
    style G fill:#1a1a1a,stroke:#333,color:#fff
    style H fill:#1a1a1a,stroke:#333,color:#fff
```

---

## Core Agent Pipeline

```mermaid
flowchart TD
    Trigger["✨ Trigger: Webhook OR Scheduler"] --> Retriever["🔍 Retriever Agent"]
    Retriever -- Fetched Code --> Analyzer["🧪 Analyzer Agent"]
    Analyzer -- Findings & Issues --> Decision["⚖️ Decision Agent"]
    Decision -- Prioritized Tasks --> Execution["⚡ Execution Agent"]
    Execution -- Apply Fixes To Files --> Modified["📄 Modified Code"]
    Modified --> Verifier["✅ Verifier Agent"]
    Verifier -- Verified Results --> Monitor["📊 Monitor Agent"]
    Monitor -- Health & Metrics --> Git["🚀 Git Service"]
    Git -- Auto-Commit --> Committed["📦 Committed"]
    Committed --> Pushed["📤 Pushed"]

    Audit[("🗄️ Full Audit Log - Every Decision")]
    
    Trigger -. Log .-> Audit
    Retriever -. Log .-> Audit
    Analyzer -. Log .-> Audit
    Decision -. Log .-> Audit
    Execution -. Log .-> Audit
    Modified -. Log .-> Audit
    Verifier -. Log .-> Audit
    Monitor -. Log .-> Audit
    Git -. Log .-> Audit
    
    style Audit fill:#2e2e2e,stroke:#e69a0b,stroke-width:2px,color:#fff
```

---

## Key Design Decisions

Built as a ground-up rearchitecture of an earlier prototype (ShoppingGPT), fixing the problems that don't show up until real users hit it:

| Problem in the original prototype                     | Solution in SCOUT                                                    |
| ------------------------------------------------------- | ---------------------------------------------------------------------- |
| Global shared memory across all users                 | Per-session objects, UUID-keyed, Redis or in-memory TTL cache        |
| Keyword-based router — breaks on Hindi/Hinglish        | LLM (Claude) intent router — handles slang, Hinglish, typos natively |
| Synchronous request/response only                     | FastAPI async + Server-Sent Events, streaming from first token       |
| Hardcoded local paths, no env config                   | `pydantic-settings`, fully environment-driven                        |
| Single local product database                          | Live multi-platform API integrations with caching                    |
| No deduplication across platforms                      | Title-fingerprint dedup before results ever reach the ranker         |
| No product scoring                                     | Transparent 6-factor weighted scoring engine, not a black box        |
| No review summarisation                                | Claude-generated pros/cons/verdict per product, computed concurrently |
| No streaming                                            | Full SSE pipeline — badges, intent echo, product cards, live tokens  |

---

## Project Structure

This repo contains both halves of SCOUT:

```
SCOUT/
├── Backend/                 FastAPI service — see below
│   ├── app/
│   │   ├── main.py             app factory
│   │   ├── config.py           environment-driven settings
│   │   ├── agent/               core.py, router.py, prompts.py
│   │   ├── tools/                intent extraction, search, ranking, review summarisation
│   │   ├── integrations/         one module per platform (Amazon, Flipkart, Blinkit, Zepto…)
│   │   ├── models/               Product, SearchIntent, Session, API schemas
│   │   └── services/             LLM wrapper, cache, per-user session isolation
│   └── requirements.txt
│
├── frontend/                 Landing page + interactive demo (static, no build step)
│   ├── index.html
│   ├── styles.css              design tokens lifted straight from DESIGN.md
│   └── script.js                scroll reveal + demo chat interactivity
│
├── DESIGN.md                 Design system: colors, type scale, spacing, component tokens
└── README.md                 you are here
```

---

## Tech Stack

| Layer      | Stack |
|------------|-------|
| Backend    | Python, FastAPI, async/await, Server-Sent Events |
| LLM        | Claude — intent routing, structured extraction, review summarisation, narration |
| Search     | SerpAPI (Google Shopping) day 1 → Amazon PA-API, Flipkart Affiliate API, quick-commerce partnerships |
| Caching    | Redis with local in-memory fallback |
| Frontend   | Vanilla HTML / CSS / JS — no framework, no build step, deploys as static files |
| Design     | Custom token system defined in [`DESIGN.md`](./DESIGN.md) — warm near-black canvas, single amber accent, pill-shaped UI |

---

## Quick Start

### Backend

```bash
cd Backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# add GEMINI_API_KEY and SERP_API_KEY at minimum

python run.py
# → http://localhost:8000
# → http://localhost:8000/docs            interactive API docs
# → http://localhost:8000/api/health      check which platforms are configured
```

### Frontend

```bash
cd frontend
# no build step — just serve the static files
python -m http.server 5500
# → http://localhost:5500
```

Point the demo chat at your local backend by updating the fetch URL in `script.js` if you're not running both on the same origin.

---

## API Reference

### `POST /api/chat` — SSE streaming

```jsonc
// Request
{
  "message": "best wireless headphones under ₹3000",
  "session_id": "abc123",   // optional — server creates one if omitted
  "pincode": "110001"       // optional — enables delivery ETAs
}

// SSE events
event: thinking  → { "message": "Searching across platforms…" }
event: intent    → { "query_text": "...", "budget_max": 3000, ... }
event: products  → { "products": [...], "platforms_searched": [...] }
event: text      → "Best pick is…"        // token-by-token
event: done      → { "session_id": "abc123" }
```

### `GET /api/search` — non-streaming

```
GET /api/search?q=wireless+headphones&budget=3000&pincode=110001&sort=best_value
```

### `GET /api/health`

```json
{
  "status": "ok",
  "llm_connected": true,
  "platforms_configured": ["serp", "amazon", "flipkart"],
  "cache_connected": false
}
```

### Frontend integration example (React / Next.js)

```ts
export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [products, setProducts] = useState<ProductCard[]>([]);

  const sendMessage = async (text: string, sessionId?: string) => {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, session_id: sessionId }),
    });

    const reader = res.body!.getReader();
    const decoder = new TextDecoder();
    let aiText = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      for (const line of decoder.decode(value).split('\n')) {
        if (!line.startsWith('data:')) continue;
        const chunk = JSON.parse(line.slice(5));
        if (chunk.type === 'text')     aiText += chunk.data;
        if (chunk.type === 'products') setProducts(chunk.data.products);
        if (chunk.type === 'done')     setMessages(m => [...m, { role: 'assistant', content: aiText }]);
      }
    }
  };

  return { messages, products, sendMessage };
}
```

---

## Environment Variables

| Variable                                             | Description                       | Required  |
| ------------------------------------------------------ | ------------------------------------ | ----------- |
| `GEMINI_API_KEY`                                      | Claude API key                    | ✅ Yes    |
| `SERP_API_KEY`                                        | SerpAPI key for Google Shopping   | ✅ Day 1  |
| `AMAZON_ACCESS_KEY` / `SECRET_KEY` / `PARTNER_TAG`     | Amazon PA-API 5.0                 | ✅ Week 1 |
| `FLIPKART_AFFILIATE_ID` / `TOKEN`                      | Flipkart Affiliate API            | ✅ Week 1 |
| `BLINKIT_API_KEY` / `BASE_URL`                         | Blinkit (via partnership)         | 🔜 Future |
| `ZEPTO_API_KEY` / `BASE_URL`                           | Zepto (via partnership)           | 🔜 Future |
| `INSTAMART_API_KEY` / `BASE_URL`                       | Swiggy Instamart                  | 🔜 Future |
| `REDIS_URL`                                            | Redis for caching + sessions      | Optional  |

---

## Adding a New Platform

SCOUT's integration layer is a plugin architecture — new platforms don't touch core logic:

1. Create `Backend/app/integrations/<platform>.py` extending `BaseIntegration`
2. Implement `async def search(intent, pincode) -> List[Product]`
3. Register it in `_ECOMMERCE_PLATFORMS` or `_QUICK_COMMERCE_PLATFORMS` in `product_search.py`
4. Add its API keys to `app/config.py` and `.env.example`

---

## Design System

The frontend's visual language — warm near-black canvas, a single disciplined amber accent, pill-shaped buttons/badges, bold display type with italic emphasis — is fully specified as a reusable token system in [`DESIGN.md`](./DESIGN.md). Hand that file to any design tool or AI agent to extend the UI consistently.

---

## Roadmap

- [ ] Live Amazon PA-API + Flipkart Affiliate integration (currently SerpAPI-backed)
- [ ] Blinkit / Zepto / Instamart quick-commerce partnerships
- [ ] Redis-backed session store for production deployments
- [ ] Price-drop tracking and alerts
- [ ] Public hosted demo

---



<div align="center">

Built by [Utkarsh Singh](https://github.com/4-thkind) and [Granth Chhabra](https://github.com/granthx)

</div>
