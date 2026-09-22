"use client";

import {
  getApAging,
  getApPaymentBehavior,
  getArAging,
  getArPaymentBehavior,
  getCustomerConcentration,
  getKpis,
  getVendorConcentration,
} from "@/lib/api";
import { formatCurrency, formatDays, formatPercent } from "@/lib/format";
import { StatTile } from "@/components/StatTile";
import { GroupedBarChart } from "@/components/GroupedBarChart";
import { ErrorBanner, LoadingBlock, EmptyBlock } from "@/components/StatusBanner";
import { useApi } from "@/lib/useApi";
import type { AgingBucket } from "@/lib/types";

const BUCKET_ORDER = ["current", "1-30", "31-60", "61-90", "90+", "no_due_date"];

function mergeAging(ar: AgingBucket[], ap: AgingBucket[]) {
  const byBucket = new Map<string, { ar: number; ap: number }>();
  for (const b of ar) byBucket.set(b.bucket, { ar: b.amount, ap: byBucket.get(b.bucket)?.ap ?? 0 });
  for (const b of ap) byBucket.set(b.bucket, { ar: byBucket.get(b.bucket)?.ar ?? 0, ap: b.amount });
  return BUCKET_ORDER.filter((b) => byBucket.has(b)).map((b) => ({
    label: b,
    values: { ar: byBucket.get(b)!.ar, ap: byBucket.get(b)!.ap },
  }));
}

export default function AnalyticsPage() {
  const kpis = useApi(() => getKpis(), []);
  const arAging = useApi(() => getArAging(), []);
  const apAging = useApi(() => getApAging(), []);
  const topCustomers = useApi(() => getCustomerConcentration(8), []);
  const topVendors = useApi(() => getVendorConcentration(8), []);
  const arBehavior = useApi(() => getArPaymentBehavior(), []);
  const apBehavior = useApi(() => getApPaymentBehavior(), []);

  const agingGroups = arAging.data && apAging.data ? mergeAging(arAging.data, apAging.data) : null;

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">AR / AP Analytics</h1>
        <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
          Working capital, aging, concentration risk, and historical payment behavior.
        </p>
      </div>

      {kpis.error && <ErrorBanner message={kpis.error} />}
      {kpis.loading && <LoadingBlock />}
      {kpis.data && (
        <section className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
          <StatTile label="Total AR" value={formatCurrency(kpis.data.total_ar)} />
          <StatTile label="Overdue AR" value={formatCurrency(kpis.data.overdue_ar)} tone="warning" />
          <StatTile label="Total AP" value={formatCurrency(kpis.data.total_ap)} />
          <StatTile label="Overdue AP" value={formatCurrency(kpis.data.overdue_ap)} tone="warning" />
          <StatTile label="Cash conversion cycle" value={formatDays(kpis.data.cash_conversion_cycle_days)} />
          <StatTile label="Open invoices / bills" value={`${kpis.data.open_invoice_count} / ${kpis.data.open_expense_count}`} />
        </section>
      )}

      <section className="card p-4">
        <h2 className="font-medium mb-3">Aging — outstanding AR vs AP by bucket</h2>
        {agingGroups && agingGroups.length > 0 ? (
          <GroupedBarChart
            groups={agingGroups}
            series={[
              { key: "ar", label: "Receivables (AR)", color: "var(--series-ar)" },
              { key: "ap", label: "Payables (AP)", color: "var(--series-ap)" },
            ]}
            formatValue={formatCurrency}
          />
        ) : (
          <EmptyBlock message="No outstanding invoices or bills yet — upload data to see aging." />
        )}
      </section>

      <section className="grid md:grid-cols-2 gap-4">
        <div className="card p-4">
          <h2 className="font-medium mb-3">Top customers by outstanding AR</h2>
          {topCustomers.data && topCustomers.data.length > 0 ? (
            <GroupedBarChart
              groups={topCustomers.data.map((c) => ({ label: c.name ?? c.entity_id, values: { v: c.amount } }))}
              series={[{ key: "v", label: "Outstanding", color: "var(--series-ar)" }]}
              formatValue={formatCurrency}
            />
          ) : (
            <EmptyBlock message="No customer concentration data yet." />
          )}
        </div>
        <div className="card p-4">
          <h2 className="font-medium mb-3">Top vendors by outstanding AP</h2>
          {topVendors.data && topVendors.data.length > 0 ? (
            <GroupedBarChart
              groups={topVendors.data.map((v) => ({ label: v.name ?? v.entity_id, values: { v: v.amount } }))}
              series={[{ key: "v", label: "Outstanding", color: "var(--series-ap)" }]}
              formatValue={formatCurrency}
            />
          ) : (
            <EmptyBlock message="No vendor concentration data yet." />
          )}
        </div>
      </section>

      <section className="grid md:grid-cols-2 gap-4">
        <div className="card p-4">
          <h2 className="font-medium mb-3">Customer payment behavior (AR)</h2>
          {arBehavior.data ? (
            <dl className="grid grid-cols-2 gap-3 text-sm">
              <Stat label="Avg days to pay" value={formatDays(arBehavior.data.avg_days_to_pay)} />
              <Stat label="Median days to pay" value={formatDays(arBehavior.data.median_days_to_pay)} />
              <Stat label="% paid late" value={formatPercent(arBehavior.data.pct_paid_late)} />
              <Stat label="On-time / late count" value={`${arBehavior.data.on_time_count} / ${arBehavior.data.late_count}`} />
            </dl>
          ) : (
            <EmptyBlock message="No paid invoice history yet." />
          )}
        </div>
        <div className="card p-4">
          <h2 className="font-medium mb-3">Vendor payment behavior (AP)</h2>
          {apBehavior.data ? (
            <dl className="grid grid-cols-2 gap-3 text-sm">
              <Stat label="Avg days to pay" value={formatDays(apBehavior.data.avg_days_to_pay)} />
              <Stat label="Median days to pay" value={formatDays(apBehavior.data.median_days_to_pay)} />
              <Stat label="% paid late" value={formatPercent(apBehavior.data.pct_paid_late)} />
              <Stat label="On-time / late count" value={`${apBehavior.data.on_time_count} / ${apBehavior.data.late_count}`} />
            </dl>
          ) : (
            <EmptyBlock message="No paid expense history yet." />
          )}
        </div>
      </section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs" style={{ color: "var(--text-muted)" }}>
        {label}
      </dt>
      <dd className="tabular font-medium">{value}</dd>
    </div>
  );
}
