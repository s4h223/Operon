export function StatTile({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: "good" | "warning" | "serious" | "critical";
}) {
  const toneColor = tone
    ? {
        good: "var(--status-good)",
        warning: "var(--status-warning)",
        serious: "var(--status-serious)",
        critical: "var(--status-critical)",
      }[tone]
    : undefined;

  return (
    <div className="card p-4 flex flex-col gap-1 min-w-[160px]">
      <span className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>
        {label}
      </span>
      <span className="text-2xl font-semibold tabular" style={{ color: toneColor ?? "var(--foreground)" }}>
        {value}
      </span>
      {sub && (
        <span className="text-xs" style={{ color: "var(--text-secondary)" }}>
          {sub}
        </span>
      )}
    </div>
  );
}
