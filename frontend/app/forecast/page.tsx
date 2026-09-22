"use client";

import { useState } from "react";
import { getForecast } from "@/lib/api";
import { formatCurrency } from "@/lib/format";
import { StatTile } from "@/components/StatTile";
import { BalanceLineChart } from "@/components/BalanceLineChart";
import { ErrorBanner, LoadingBlock } from "@/components/StatusBanner";
import { useApi } from "@/lib/useApi";

export default function ForecastPage() {
  const [startingBalance, setStartingBalance] = useState<string>("");
  const forecast = useApi(
    () => getForecast(startingBalance === "" ? undefined : Number(startingBalance)),
    [startingBalance],
  );

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">30 / 60 / 90-Day Cash Flow Forecast</h1>
        <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
          Projects inflows, outflows, and cash balance using invoice/bill due dates, each
          customer&apos;s and vendor&apos;s historical payment delay, and detected recurring expenses.
        </p>
      </div>

      <div className="card p-4 flex items-end gap-3 flex-wrap">
        <label className="flex flex-col gap-1 text-sm">
          <span style={{ color: "var(--text-secondary)" }}>
            Starting cash balance (optional — defaults to net historical bank transactions)
          </span>
          <input
            type="number"
            placeholder="e.g. 250000"
            className="border rounded-md px-3 py-2 bg-transparent w-64"
            style={{ borderColor: "var(--border)" }}
            value={startingBalance}
            onChange={(e) => setStartingBalance(e.target.value)}
          />
        </label>
      </div>

      {forecast.error && <ErrorBanner message={forecast.error} />}
      {forecast.loading && <LoadingBlock />}

      {forecast.data && (
        <>
          <section className="grid sm:grid-cols-3 gap-4">
            {forecast.data.points.map((p) => (
              <StatTile
                key={p.horizon_days}
                label={`+${p.horizon_days} days`}
                value={formatCurrency(p.projected_balance)}
                sub={`in ${formatCurrency(p.projected_inflows)} · out ${formatCurrency(p.projected_outflows)}`}
                tone={p.projected_balance >= forecast.data!.starting_balance ? "good" : "warning"}
              />
            ))}
          </section>

          <section className="card p-4">
            <h2 className="font-medium mb-3">Projected daily cash balance</h2>
            <BalanceLineChart points={forecast.data.daily.map((d) => ({ date: d.date, balance: d.balance }))} />
          </section>
        </>
      )}
    </div>
  );
}
