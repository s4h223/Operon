import type { SolveResponse } from "@/lib/types";
import DesmosGraph from "./DesmosGraph";

const PROBLEM_TYPE_LABELS: Record<string, string> = {
  linear_equations: "Linear Equations",
  systems: "Systems of Equations",
  quadratics: "Quadratics",
  functions: "Functions",
  regressions: "Regressions",
  statistics: "Statistics",
  circles: "Circles",
  exponentials: "Exponentials",
  roots: "Roots & Radicals",
  intersections: "Intersections",
  tables: "Tables",
  maxima_minima: "Maxima / Minima",
  other: "Other",
};

export default function ResultCard({ result }: { result: SolveResponse }) {
  return (
    <div className="w-full rounded-xl border border-slate-700 bg-slate-900/60 p-6 space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="inline-flex items-center rounded-full bg-indigo-500/20 px-3 py-1 text-sm font-medium text-indigo-300">
          {PROBLEM_TYPE_LABELS[result.problemType] ?? result.problemType}
        </span>
        <span
          className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-medium ${
            result.desmosApplicable
              ? "bg-emerald-500/20 text-emerald-300"
              : "bg-amber-500/20 text-amber-300"
          }`}
        >
          {result.desmosApplicable ? "Desmos shortcut available" : "Desmos not needed here"}
        </span>
      </div>

      <div>
        <h2 className="text-lg font-semibold text-white">{result.strategy}</h2>
      </div>

      {result.desmosInputs.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-400">
            Type into Desmos
          </h3>
          <ul className="space-y-1.5">
            {result.desmosInputs.map((input, i) => (
              <li
                key={i}
                className="rounded-md bg-slate-800 px-3 py-2 font-mono text-sm text-emerald-300"
              >
                {input}
              </li>
            ))}
          </ul>
        </div>
      )}

      {result.desmosInputs.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-400">
            Live preview
          </h3>
          <DesmosGraph desmosInputs={result.desmosInputs} />
        </div>
      )}

      <div>
        <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-400">
          Steps
        </h3>
        <ol className="list-decimal space-y-1.5 pl-5 text-slate-200">
          {result.steps.map((step, i) => (
            <li key={i}>{step}</li>
          ))}
        </ol>
      </div>

      <div className="rounded-lg bg-slate-800/70 p-4">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
          Answer
        </h3>
        <p className="mt-1 text-xl font-bold text-white">{result.answer}</p>
      </div>

      <div>
        <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-400">
          Why this works
        </h3>
        <p className="text-slate-300">{result.explanation}</p>
      </div>
    </div>
  );
}
