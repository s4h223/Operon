"use client";

import Link from "next/link";
import { getKpis, getOutstandingBalances, getUpcomingObligations } from "@/lib/api";
import { formatCurrency, formatDays, formatNumber } from "@/lib/format";
import { StatTile } from "@/components/StatTile";
import { ErrorBanner, LoadingBlock } from "@/components/StatusBanner";
import { useApi } from "@/lib/useApi";

export default function OverviewPage() {
  const kpis = useApi(() => getKpis(), []);
  const balances = useApi(() => getOutstandingBalances(), []);
  const obligations = useApi(() => getUpcomingObligations(30), []);

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Operon</h1>
        <p style={{ color: "var(--text-secondary)" }} className="mt-1">
          Financial operations intelligence: ingest raw CSV exports, normalize them into a standard
          schema, and analyze working capital, cash flow, and risk.
        </p>
      </div>

      {kpis.error && <ErrorBanner message={kpis.error} />}
      {kpis.loading && <LoadingBlock />}
      {kpis.data && (
        <section className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
          <StatTile label="Total AR" value={formatCurrency(kpis.data.total_ar)} sub="outstanding receivables" />
          <StatTile
            label="Overdue AR"
            value={formatCurrency(kpis.data.overdue_ar)}
            tone={kpis.data.overdue_ar > 0 ? "warning" : "good"}
          />
          <StatTile label="Total AP" value={formatCurrency(kpis.data.total_ap)} sub="outstanding payables" />
          <StatTile label="DSO" value={formatDays(kpis.data.dso_days)} sub="days sales outstanding" />
          <StatTile label="DPO" value={formatDays(kpis.data.dpo_days)} sub="days payable outstanding" />
        </section>
      )}

      {balances.data && obligations.data && (
        <section className="grid sm:grid-cols-3 gap-4">
          <StatTile
            label="Net working capital position"
            value={formatCurrency(balances.data.net)}
            sub="outstanding AR − outstanding AP"
            tone={balances.data.net >= 0 ? "good" : "warning"}
          />
          <StatTile
            label="Expected inflows (30d)"
            value={formatCurrency(obligations.data.expected_inflows_total)}
            sub={`${formatNumber(obligations.data.receivables.length)} invoices due`}
          />
          <StatTile
            label="Expected outflows (30d)"
            value={formatCurrency(obligations.data.expected_outflows_total)}
            sub={`${formatNumber(obligations.data.payables.length)} bills due`}
          />
        </section>
      )}

      <section className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {[
          { href: "/upload", title: "Upload data", desc: "Ingest customers, vendors, invoices, payments, expenses, or bank transactions." },
          { href: "/analytics", title: "AR / AP analytics", desc: "Aging, DSO/DPO, concentration, payment behavior, outstanding balances." },
          { href: "/forecast", title: "Cash forecast", desc: "30/60/90-day projected inflows, outflows, and cash balance." },
          { href: "/risk", title: "Late-payment risk", desc: "ML-scored probability of late payment per outstanding invoice." },
          { href: "/anomalies", title: "Anomalies", desc: "Duplicate and statistically unusual transactions, with explanations." },
        ].map((c) => (
          <Link key={c.href} href={c.href} className="card p-4 hover:opacity-90 transition-opacity">
            <h2 className="font-medium">{c.title}</h2>
            <p className="text-sm mt-1" style={{ color: "var(--text-secondary)" }}>
              {c.desc}
            </p>
          </Link>
        ))}
      </section>
    </div>
  );
}
