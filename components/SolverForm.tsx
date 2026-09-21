"use client";

import { useState, type FormEvent } from "react";
import type { SolveResponse } from "@/lib/types";
import ResultCard from "./ResultCard";

const EXAMPLE_PROBLEM =
  "If 2x + y = 1 and x + y = 7, what is the value of x - y?";

export default function SolverForm() {
  const [problem, setProblem] = useState("");
  const [result, setResult] = useState<SolveResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!problem.trim() || loading) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await fetch("/api/solve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ problem }),
      });

      const data = await res.json();

      if (!res.ok) {
        setError(data.error ?? "Something went wrong. Please try again.");
        return;
      }

      setResult(data as SolveResponse);
    } catch {
      setError("Couldn't reach the server. Check your connection and try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="w-full max-w-2xl space-y-6">
      <form onSubmit={handleSubmit} className="space-y-3">
        <label htmlFor="problem" className="block text-sm font-medium text-slate-300">
          Paste an SAT math problem
        </label>
        <textarea
          id="problem"
          value={problem}
          onChange={(e) => setProblem(e.target.value)}
          placeholder={EXAMPLE_PROBLEM}
          rows={5}
          className="w-full rounded-lg border border-slate-700 bg-slate-900 p-4 text-slate-100 placeholder:text-slate-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
        />
        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={loading || !problem.trim()}
            className="rounded-lg bg-indigo-600 px-5 py-2.5 font-medium text-white transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? "Solving..." : "Solve with Desmos"}
          </button>
          <button
            type="button"
            onClick={() => setProblem(EXAMPLE_PROBLEM)}
            className="text-sm text-slate-400 underline-offset-2 hover:text-slate-200 hover:underline"
          >
            Try an example
          </button>
        </div>
      </form>

      {error && (
        <div className="rounded-lg border border-red-800 bg-red-950/50 p-4 text-red-300">
          {error}
        </div>
      )}

      {result && <ResultCard result={result} />}
    </div>
  );
}
