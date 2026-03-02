# Orbital

Causal intelligence for e-commerce revenue. See what actually moves your growth.

---

## What is Orbital?

Orbital models the forces driving your e-commerce growth — quantifying incremental impact across revenue, traffic, and conversion using structured statistical modeling. No platform bias. No black box. Clear answers.

### The problem

Attribution shows motion. Not gravity. Your growth data is fragmented across platforms, and last-click models credit channels for sales that would have happened anyway. You can't separate paid lift from seasonality, promotions, or organic demand.

### The approach

Orbital treats revenue as a system of forces — funnel (sessions, conversion, AOV), paid media (Meta, Google, TikTok), demand (seasonality, trend, brand), and events (promotions, launches, inventory, algorithm changes). It isolates how each one affects revenue independently, so you can:

- **Measure true incremental lift** — what spend and events add on top of organic momentum
- **Separate baseline from paid** — avoid crediting channels for seasonal or brand-driven sales
- **Account for overlap** — Meta and Google often reach the same customers; Orbital models that
- **Detect anomalies** — flag supply constraints, algorithm changes, and external shocks
- **Simulate marginal ROI** — understand diminishing returns as spend scales

---

## Features

- **Data ingestion** — Upload Shopify orders, Meta Ads, Google Ads, and TikTok Ads CSV exports
- **Causal modeling** — Python/FastAPI backend with time-aware regression, diagnostics, and confidence scoring
- **Visualization** — 3D orbital interface showing how variables interact and drive revenue
- **Dashboard** — Build data pipelines, run analyses, and persist results
- **Auth & persistence** — Supabase for authentication and storage

---

## Tech Stack

- **Frontend:** Next.js, React, Tailwind CSS, Three.js / React Three Fiber
- **Backend:** Python, FastAPI, Pandas, Statsmodels, Scikit-learn
- **Database:** Supabase (PostgreSQL)

---

## Getting Started

### Prerequisites

- Node.js 18+
- Python 3.10+
- Supabase project

### 1. Install dependencies

```bash
npm install
cd backend && pip install -r requirements.txt
```

### 2. Environment variables

Create `.env.local` in the project root:

```env
NEXT_PUBLIC_SUPABASE_URL=your_supabase_url
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=your_supabase_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
```

### 3. Database setup

Run `supabase_schema.sql` in your Supabase SQL Editor to create the required tables.

### 4. Run locally

```bash
# Terminal 1: Next.js
npm run dev

# Terminal 2: Python modeling backend
cd backend && uvicorn main:app --reload --port 8000
```

Open [http://localhost:3000](http://localhost:3000).

---

## Project structure

```
├── app/                    # Next.js App Router pages & API routes
│   ├── api/               # Upload endpoints (orders, ad spend)
│   ├── dashboard/         # Build & run pages
│   └── auth/              # Auth flows
├── backend/               # Python modeling engine
│   ├── pipeline/          # Fetch, validate, aggregate, model, persist
│   └── main.py            # FastAPI app
├── components/            # React components
│   └── orbital-3d/        # 3D visualization
└── supabase_schema.sql    # Database schema
```

---

## Documentation

- `QUICK_START.md` — Shopify orders upload setup
- `API_UPLOAD_ORDERS.md` — Orders API reference
- `DASHBOARD_IMPLEMENTATION.md` — Dashboard architecture
- `ORBITAL_DESIGN.md` — Landing page design notes

---

## License

Private. All rights reserved.
