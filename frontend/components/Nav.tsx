"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Overview" },
  { href: "/upload", label: "Upload & Mapping" },
  { href: "/analytics", label: "AR / AP Analytics" },
  { href: "/forecast", label: "Cash Forecast" },
  { href: "/risk", label: "Late-Payment Risk" },
  { href: "/anomalies", label: "Anomalies" },
];

export function Nav() {
  const pathname = usePathname();
  return (
    <header className="border-b" style={{ borderColor: "var(--border)", background: "var(--surface)" }}>
      <div className="max-w-6xl mx-auto px-6 py-3 flex items-center gap-6">
        <span className="font-semibold text-lg tracking-tight">Operon</span>
        <nav className="flex gap-1 flex-wrap">
          {LINKS.map((link) => {
            const active = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                className="text-sm px-3 py-1.5 rounded-md transition-colors"
                style={{
                  color: active ? "var(--foreground)" : "var(--text-secondary)",
                  background: active ? "var(--background)" : "transparent",
                  fontWeight: active ? 600 : 400,
                }}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
