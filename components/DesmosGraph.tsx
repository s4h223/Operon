"use client";

import { useEffect, useRef, useState } from "react";

declare global {
  interface Window {
    Desmos?: {
      GraphingCalculator: (
        element: HTMLElement,
        options?: Record<string, unknown>
      ) => DesmosCalculator;
    };
  }
}

interface DesmosCalculator {
  setExpression: (options: { id: string; latex: string }) => void;
  destroy: () => void;
}

const DESMOS_SCRIPT_ID = "desmos-api-script";
// Public "demo" key from Desmos's own docs - fine for local/dev preview.
// For production, register a real key at desmos.com/api and set
// NEXT_PUBLIC_DESMOS_API_KEY.
const DESMOS_API_KEY = process.env.NEXT_PUBLIC_DESMOS_API_KEY || "demo";

function loadDesmosScript(): Promise<void> {
  if (window.Desmos) return Promise.resolve();

  const existing = document.getElementById(
    DESMOS_SCRIPT_ID
  ) as HTMLScriptElement | null;
  if (existing) {
    return new Promise((resolve) => {
      existing.addEventListener("load", () => resolve());
    });
  }

  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.id = DESMOS_SCRIPT_ID;
    script.src = `https://www.desmos.com/api/v1.11/calculator.js?apiKey=${DESMOS_API_KEY}`;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Failed to load Desmos."));
    document.head.appendChild(script);
  });
}

/** Best-effort conversion of our plain-text Desmos syntax to calculator latex. */
function toLatex(input: string): string | null {
  const trimmed = input.trim();
  // Skip descriptive, non-literal lines (e.g. table/setup instructions).
  if (!trimmed || trimmed.includes(":") || /\btable\b/i.test(trimmed)) {
    return null;
  }
  return trimmed.replace(/([a-zA-Z])_(\d+)/g, "$1_{$2}");
}

export default function DesmosGraph({
  desmosInputs,
}: {
  desmosInputs: string[];
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [calculator, setCalculator] = useState<DesmosCalculator | null>(null);

  useEffect(() => {
    let cancelled = false;
    let created: DesmosCalculator | null = null;

    loadDesmosScript()
      .then(() => {
        if (cancelled || !containerRef.current || !window.Desmos) return;
        created = window.Desmos.GraphingCalculator(containerRef.current, {
          keypad: false,
          expressionsCollapsed: true,
        });
        setCalculator(created);
      })
      .catch(() => {
        // Silently fail - the graph is a bonus visual, not required to use
        // the text steps/answer already shown elsewhere on the page.
      });

    return () => {
      cancelled = true;
      created?.destroy();
    };
  }, []);

  useEffect(() => {
    if (!calculator) return;
    desmosInputs.forEach((input, index) => {
      const latex = toLatex(input);
      if (latex) {
        calculator.setExpression({ id: `expr-${index}`, latex });
      }
    });
  }, [calculator, desmosInputs]);

  return (
    <div
      ref={containerRef}
      className="h-80 w-full rounded-lg border border-slate-700"
    />
  );
}
