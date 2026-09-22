# Operon frontend

Next.js + TypeScript client for the Operon API (`../backend`).

## Setup

```bash
npm install
cp .env.local.example .env.local   # NEXT_PUBLIC_API_BASE_URL, defaults to http://localhost:8000
npm run dev
```

Open http://localhost:3000. The backend must be running separately (`../backend`).

## Pages

- `/` — KPI overview + quick links.
- `/upload` — upload a CSV, review/edit the auto-suggested column mapping, process it.
- `/analytics` — AR/AP KPIs, aging (AR vs AP by bucket), concentration, payment behavior.
- `/forecast` — 30/60/90-day cash flow forecast with a daily projected-balance chart.
- `/risk` — train the late-payment model; browse ML-scored risk per outstanding invoice.
- `/anomalies` — run duplicate/statistical anomaly detection; browse flagged records with reasons.

## Structure

- `lib/api.ts` — typed fetch client for the backend.
- `lib/types.ts` — TypeScript types mirroring the backend's Pydantic schemas.
- `lib/entityFields.ts` — standard field lists per entity, mirroring `backend/app/normalization/entity_specs.py` (used to populate the mapping dropdowns).
- `lib/useApi.ts` — small fetch-on-mount hook (loading/error/reload) shared by every page.
- `components/` — chart primitives (`GroupedBarChart`, `BalanceLineChart`), `StatTile`, `RiskBadge`, `Nav`.

Charts use a small custom SVG implementation (no charting library) following a fixed
categorical color order (blue = AR/receivables/inflows, orange = AP/payables/outflows,
never reassigned) and a reserved status palette (green/amber/red) for risk tiers, kept
distinct from the categorical colors so risk badges never read as "just another series."
