"use client";

import { useId, useMemo, useState } from "react";

export interface DailyPoint {
  date: string;
  balance: number;
}

/** Single-series line+area chart with a crosshair/tooltip on hover, per the
 * interaction spec: line/area charts get a crosshair, not a per-point legend. */
export function BalanceLineChart({ points, height = 240 }: { points: DailyPoint[]; height?: number }) {
  const gradientId = useId();
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);

  const width = 720;
  const padding = { top: 16, right: 16, bottom: 24, left: 64 };
  const chartW = width - padding.left - padding.right;
  const chartH = height - padding.top - padding.bottom;

  const { path, areaPath, xForIdx, yForVal, min, max } = useMemo(() => {
    const values = points.map((p) => p.balance);
    const min = Math.min(0, ...values);
    const max = Math.max(1, ...values);
    const xForIdx = (i: number) => padding.left + (i / Math.max(points.length - 1, 1)) * chartW;
    const yForVal = (v: number) => padding.top + chartH - ((v - min) / (max - min || 1)) * chartH;
    const path = points.map((p, i) => `${i === 0 ? "M" : "L"}${xForIdx(i)},${yForVal(p.balance)}`).join(" ");
    const areaPath =
      path +
      ` L${xForIdx(points.length - 1)},${padding.top + chartH} L${xForIdx(0)},${padding.top + chartH} Z`;
    return { path, areaPath, xForIdx, yForVal, min, max };
  }, [points, chartW, chartH, padding.left, padding.top]);

  if (points.length === 0) {
    return <div style={{ color: "var(--text-muted)" }}>No forecast data yet.</div>;
  }

  const hovered = hoverIdx !== null ? points[hoverIdx] : null;
  const zeroY = yForVal(0);

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full"
        role="img"
        aria-label="Projected cash balance over time"
        onMouseLeave={() => setHoverIdx(null)}
        onMouseMove={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          const relX = ((e.clientX - rect.left) / rect.width) * width;
          const idx = Math.round(((relX - padding.left) / chartW) * (points.length - 1));
          setHoverIdx(Math.max(0, Math.min(points.length - 1, idx)));
        }}
      >
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--series-ar)" stopOpacity={0.25} />
            <stop offset="100%" stopColor="var(--series-ar)" stopOpacity={0} />
          </linearGradient>
        </defs>
        {[0, 0.25, 0.5, 0.75, 1].map((f) => (
          <line
            key={f}
            x1={padding.left}
            x2={padding.left + chartW}
            y1={padding.top + chartH * f}
            y2={padding.top + chartH * f}
            stroke="var(--gridline)"
            strokeWidth={1}
          />
        ))}
        {min < 0 && (
          <line
            x1={padding.left}
            x2={padding.left + chartW}
            y1={zeroY}
            y2={zeroY}
            stroke="var(--status-critical)"
            strokeDasharray="4 3"
            strokeWidth={1}
          />
        )}
        <path d={areaPath} fill={`url(#${gradientId})`} stroke="none" />
        <path d={path} fill="none" stroke="var(--series-ar)" strokeWidth={2} strokeLinejoin="round" />
        {[0, Math.floor(points.length / 2), points.length - 1].map((i) => (
          <text key={i} x={xForIdx(i)} y={height - 4} fontSize={11} textAnchor="middle" fill="var(--text-muted)">
            {points[i].date.slice(5)}
          </text>
        ))}
        <text x={padding.left - 8} y={padding.top + 4} fontSize={11} textAnchor="end" fill="var(--text-muted)">
          {formatCompact(max)}
        </text>
        <text x={padding.left - 8} y={padding.top + chartH} fontSize={11} textAnchor="end" fill="var(--text-muted)">
          {formatCompact(min)}
        </text>
        {hoverIdx !== null && (
          <line
            x1={xForIdx(hoverIdx)}
            x2={xForIdx(hoverIdx)}
            y1={padding.top}
            y2={padding.top + chartH}
            stroke="var(--baseline)"
            strokeWidth={1}
          />
        )}
        {hoverIdx !== null && (
          <circle cx={xForIdx(hoverIdx)} cy={yForVal(points[hoverIdx].balance)} r={4} fill="var(--series-ar)" />
        )}
      </svg>
      {hovered && (
        <div className="text-xs mt-1" style={{ color: "var(--text-secondary)" }}>
          <strong style={{ color: "var(--foreground)" }}>{hovered.date}</strong> — balance:{" "}
          {formatCompact(hovered.balance)}
        </div>
      )}
    </div>
  );
}

function formatCompact(v: number): string {
  return new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(v);
}
