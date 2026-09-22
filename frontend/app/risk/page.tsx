"use client";

import { useState } from "react";
import { ApiError, getRiskScores, trainRiskModel } from "@/lib/api";
import { formatCurrency, formatDate, formatPercent } from "@/lib/format";
import { RiskBadge } from "@/components/RiskBadge";
import { ErrorBanner, LoadingBlock, EmptyBlock } from "@/components/StatusBanner";
import { useApi } from "@/lib/useApi";

export default function RiskPage() {
  const [training, setTraining] = useState(false);
  const [trainMessage, setTrainMessage] = useState<string | null>(null);
  const scores = useApi(() => getRiskScores(0), []);

  async function handleTrain() {
    setTraining(true);
    setTrainMessage(null);
    try {
      const res = await trainRiskModel();
      if (res.trained) {
        const metrics = res.metrics as Record<string, number>;
        setTrainMessage(
          `Trained on ${res.n_train} invoices (${res.n_test} held out). ROC-AUC ${metrics.roc_auc ?? "n/a"}, ` +
            `precision ${metrics.precision}, recall ${metrics.recall}.`,
        );
        scores.reload();
      } else {
        setTrainMessage(String(res.reason));
      }
    } catch (err) {
      setTrainMessage(err instanceof ApiError ? err.message : String(err));
    } finally {
      setTraining(false);
    }
  }

  const notTrained = scores.error?.includes("No trained");

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Late-Payment Risk</h1>
          <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
            A random forest trained on historical payment behavior scores each outstanding invoice&apos;s
            probability of being paid late, with a heuristic expected payment date.
          </p>
        </div>
        <button
          onClick={handleTrain}
          disabled={training}
          className="px-4 py-2 rounded-md text-sm font-medium text-white disabled:opacity-50 shrink-0"
          style={{ background: "var(--series-ar)" }}
        >
          {training ? "Training…" : "Train / retrain model"}
        </button>
      </div>

      {trainMessage && (
        <div className="text-sm card p-3" style={{ color: "var(--text-secondary)" }}>
          {trainMessage}
        </div>
      )}

      {scores.error && !notTrained && <ErrorBanner message={scores.error} />}
      {notTrained && (
        <EmptyBlock message="No trained model yet — click 'Train / retrain model' once you have paid invoice history loaded." />
      )}
      {scores.loading && <LoadingBlock />}

      {scores.data && scores.data.length === 0 && !scores.loading && (
        <EmptyBlock message="No outstanding invoices to score." />
      )}

      {scores.data && scores.data.length > 0 && (
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left border-b" style={{ borderColor: "var(--gridline)", color: "var(--text-muted)" }}>
                <th className="px-3 py-2">Invoice</th>
                <th className="px-3 py-2">Customer</th>
                <th className="px-3 py-2 text-right">Amount</th>
                <th className="px-3 py-2">Due date</th>
                <th className="px-3 py-2 text-right">Days past due</th>
                <th className="px-3 py-2 text-right">P(late)</th>
                <th className="px-3 py-2">Expected payment</th>
                <th className="px-3 py-2">Risk</th>
              </tr>
            </thead>
            <tbody>
              {scores.data.map((r) => (
                <tr key={r.invoice_id} className="border-b" style={{ borderColor: "var(--gridline)" }}>
                  <td className="px-3 py-2 font-mono text-xs">{r.invoice_id}</td>
                  <td className="px-3 py-2">{r.customer_name ?? r.customer_id ?? "—"}</td>
                  <td className="px-3 py-2 text-right tabular">{formatCurrency(r.invoice_amount)}</td>
                  <td className="px-3 py-2 tabular">{formatDate(r.due_date)}</td>
                  <td className="px-3 py-2 text-right tabular">{r.days_past_due}</td>
                  <td className="px-3 py-2 text-right tabular">{formatPercent(r.probability_late * 100)}</td>
                  <td className="px-3 py-2 tabular">{formatDate(r.expected_payment_date)}</td>
                  <td className="px-3 py-2">
                    <RiskBadge tier={r.risk_tier} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
