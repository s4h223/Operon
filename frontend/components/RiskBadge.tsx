const TIER_CONFIG = {
  low: { color: "var(--status-good)", label: "Low risk", icon: "●" },
  medium: { color: "var(--status-warning)", label: "Medium risk", icon: "▲" },
  high: { color: "var(--status-critical)", label: "High risk", icon: "■" },
} as const;

export function RiskBadge({ tier }: { tier: "low" | "medium" | "high" }) {
  const cfg = TIER_CONFIG[tier];
  return (
    <span
      className="inline-flex items-center gap-1.5 text-xs font-medium px-2 py-0.5 rounded-full"
      style={{ color: cfg.color, border: `1px solid ${cfg.color}` }}
    >
      <span aria-hidden>{cfg.icon}</span>
      {cfg.label}
    </span>
  );
}
