"use client";

import { useState } from "react";
import { ApiError, getAnomalies, runAnomalyDetection } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { ErrorBanner, LoadingBlock, EmptyBlock } from "@/components/StatusBanner";
import { useApi } from "@/lib/useApi";

const TYPE_COLOR: Record<string, string> = {
  duplicate: "var(--status-warning)",
  statistical: "var(--status-serious)",
};

export default function AnomaliesPage() {
  const [running, setRunning] = useState(false);
  const [runMessage, setRunMessage] = useState<string | null>(null);
  const [filterType, setFilterType] = useState<string>("");
  const anomalies = useApi(() => getAnomalies(undefined, filterType || undefined), [filterType]);

  async function handleRun() {
    setRunning(true);
    setRunMessage(null);
    try {
      const res = await runAnomalyDetection();
      setRunMessage(
        `Flagged ${res.total_flagged} record(s): ${Object.entries(res.by_type)
          .map(([k, v]) => `${v} ${k}`)
          .join(", ") || "none"}.`,
      );
      anomalies.reload();
    } catch (err) {
      setRunMessage(err instanceof ApiError ? err.message : String(err));
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Duplicate & Anomaly Detection</h1>
          <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
            Deterministic duplicate checks (vendor/account + amount + date + description) plus an
            Isolation Forest flagging statistically unusual expenses and transactions, each with a
            human-readable reason.
          </p>
        </div>
        <button
          onClick={handleRun}
          disabled={running}
          className="px-4 py-2 rounded-md text-sm font-medium text-white disabled:opacity-50 shrink-0"
          style={{ background: "var(--series-ar)" }}
        >
          {running ? "Running…" : "Run detectors"}
        </button>
      </div>

      {runMessage && (
        <div className="text-sm card p-3" style={{ color: "var(--text-secondary)" }}>
          {runMessage}
        </div>
      )}

      <div className="flex gap-2 text-sm">
        {["", "duplicate", "statistical"].map((t) => (
          <button
            key={t}
            onClick={() => setFilterType(t)}
            className="px-3 py-1.5 rounded-md border"
            style={{
              borderColor: "var(--border)",
              background: filterType === t ? "var(--surface)" : "transparent",
              fontWeight: filterType === t ? 600 : 400,
            }}
          >
            {t === "" ? "All" : t === "duplicate" ? "Duplicates" : "Statistical outliers"}
          </button>
        ))}
      </div>

      {anomalies.error && <ErrorBanner message={anomalies.error} />}
      {anomalies.loading && <LoadingBlock />}
      {anomalies.data && anomalies.data.length === 0 && !anomalies.loading && (
        <EmptyBlock message="No anomalies flagged yet — click 'Run detectors' after loading expense/transaction data." />
      )}

      {anomalies.data && anomalies.data.length > 0 && (
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left border-b" style={{ borderColor: "var(--gridline)", color: "var(--text-muted)" }}>
                <th className="px-3 py-2">Type</th>
                <th className="px-3 py-2">Entity</th>
                <th className="px-3 py-2">Record</th>
                <th className="px-3 py-2 text-right">Score</th>
                <th className="px-3 py-2">Reason</th>
                <th className="px-3 py-2">Detected</th>
              </tr>
            </thead>
            <tbody>
              {anomalies.data.map((a) => (
                <tr key={a.anomaly_id} className="border-b align-top" style={{ borderColor: "var(--gridline)" }}>
                  <td className="px-3 py-2">
                    <span
                      className="text-xs font-medium px-2 py-0.5 rounded-full border"
                      style={{ color: TYPE_COLOR[a.anomaly_type] ?? "var(--text-secondary)", borderColor: TYPE_COLOR[a.anomaly_type] ?? "var(--border)" }}
                    >
                      {a.anomaly_type}
                    </span>
                  </td>
                  <td className="px-3 py-2">{a.entity_type}</td>
                  <td className="px-3 py-2 font-mono text-xs">{a.entity_id}</td>
                  <td className="px-3 py-2 text-right tabular">{a.score.toFixed(2)}</td>
                  <td className="px-3 py-2" style={{ color: "var(--text-secondary)" }}>
                    {a.reason}
                  </td>
                  <td className="px-3 py-2 tabular text-xs">{formatDate(a.detected_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
