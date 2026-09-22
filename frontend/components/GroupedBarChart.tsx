"use client";

import { useId, useState } from "react";

export interface BarSeries {
  key: string;
  label: string;
  color: string;
}

export interface BarGroup {
  label: string;
  values: Record<string, number>; // series key -> value
}

/** Thin, rounded-end grouped bar chart with a hover tooltip and a legend
 * when there's more than one series. Colors are passed in by the caller
 * (fixed categorical slots), never generated here. */
export function GroupedBarChart({
  groups,
  series,
  height = 220,
  formatValue,
}: {
  groups: BarGroup[];
  series: BarSeries[];
  height?: number;
  formatValue: (v: number) => string;
}) {
  const gradientId = useId();
  const [hover, setHover] = useState<{ group: string; series: string; value: number } | null>(null);

  const max = Math.max(1, ...groups.flatMap((g) => series.map((s) => g.values[s.key] ?? 0)));
  const width = 640;
  const padding = { top: 12, right: 12, bottom: 28, left: 12 };
  const chartW = width - padding.left - padding.right;
  const chartH = height - padding.top - padding.bottom;
  const groupW = chartW / Math.max(groups.length, 1);
  const barGap = 3;
  const barW = Math.max(4, (groupW - barGap * (series.length + 1)) / series.length);
  // ~6px/char at 11px font size; leave a small margin so adjacent labels never touch.
  const maxLabelChars = Math.max(3, Math.floor(groupW / 6) - 1);

  return (
    <div>
      {series.length > 1 && (
        <div className="flex gap-4 mb-2 text-xs" style={{ color: "var(--text-secondary)" }}>
          {series.map((s) => (
            <span key={s.key} className="flex items-center gap-1.5">
              <span className="inline-block w-2.5 h-2.5 rounded-sm" style={{ background: s.color }} />
              {s.label}
            </span>
          ))}
        </div>
      )}
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full" role="img" aria-label="Bar chart">
        <defs>
          <linearGradient id={gradientId} x1="0" y1="1" x2="0" y2="0">
            <stop offset="0%" stopColor="var(--seq-200)" />
            <stop offset="100%" stopColor="var(--seq-500)" />
          </linearGradient>
        </defs>
        <line
          x1={padding.left}
          y1={padding.top + chartH}
          x2={padding.left + chartW}
          y2={padding.top + chartH}
          stroke="var(--baseline)"
          strokeWidth={1}
        />
        {groups.map((g, gi) => {
          const gx = padding.left + gi * groupW;
          return (
            <g key={g.label}>
              {series.map((s, si) => {
                const v = g.values[s.key] ?? 0;
                const h = max > 0 ? (v / max) * chartH : 0;
                const x = gx + barGap + si * (barW + barGap);
                const y = padding.top + chartH - h;
                const isHovered = hover?.group === g.label && hover.series === s.key;
                return (
                  <rect
                    key={s.key}
                    x={x}
                    y={y}
                    width={barW}
                    height={Math.max(h, 1)}
                    rx={4}
                    fill={series.length > 1 ? s.color : `url(#${gradientId})`}
                    opacity={isHovered ? 1 : 0.92}
                    onMouseEnter={() => setHover({ group: g.label, series: s.key, value: v })}
                    onMouseLeave={() => setHover(null)}
                  >
                    <title>
                      {g.label} · {s.label}: {formatValue(v)}
                    </title>
                  </rect>
                );
              })}
              <text
                x={gx + groupW / 2}
                y={height - 8}
                textAnchor="middle"
                fontSize={11}
                fill="var(--text-muted)"
              >
                {truncate(g.label, maxLabelChars)}
                <title>{g.label}</title>
              </text>
            </g>
          );
        })}
      </svg>
      {hover && (
        <div className="text-xs mt-1" style={{ color: "var(--text-secondary)" }}>
          <strong style={{ color: "var(--foreground)" }}>{hover.group}</strong> —{" "}
          {series.find((s) => s.key === hover.series)?.label}: {formatValue(hover.value)}
        </div>
      )}
    </div>
  );
}

function truncate(label: string, max: number): string {
  return label.length > max ? `${label.slice(0, max - 1)}…` : label;
}
