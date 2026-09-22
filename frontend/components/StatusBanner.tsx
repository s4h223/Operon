export function ErrorBanner({ message }: { message: string }) {
  return (
    <div
      className="card p-4 text-sm"
      style={{ color: "var(--status-critical)", borderColor: "var(--status-critical)" }}
    >
      <strong>Error:</strong> {message}
      <div className="mt-1" style={{ color: "var(--text-secondary)" }}>
        Is the Operon API running? Check <code>NEXT_PUBLIC_API_BASE_URL</code> (defaults to
        http://localhost:8000).
      </div>
    </div>
  );
}

export function LoadingBlock() {
  return (
    <div className="p-6 text-sm" style={{ color: "var(--text-muted)" }}>
      Loading…
    </div>
  );
}

export function EmptyBlock({ message }: { message: string }) {
  return (
    <div className="p-6 text-sm" style={{ color: "var(--text-muted)" }}>
      {message}
    </div>
  );
}
