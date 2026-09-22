"use client";

import type { ProfessorRecommendation } from "@/lib/types";

function ConfidenceBadge({ label }: { label: string }) {
  const cls = label.toLowerCase() === "high" ? "high" : label.toLowerCase() === "moderate" ? "moderate" : "low";
  return <span className={`badge ${cls}`}>{label} confidence</span>;
}

function ProfessorCard({
  rec,
  featured,
  onCompareToggle,
  compareSelected,
}: {
  rec: ProfessorRecommendation;
  featured?: boolean;
  onCompareToggle?: () => void;
  compareSelected?: boolean;
}) {
  return (
    <div className={`card p-6 ${featured ? "" : "opacity-90"}`} style={featured ? { borderColor: "var(--accent-end)" } : {}}>
      {featured && (
        <div className="gradient-text font-semibold text-base mb-2 uppercase tracking-wide">Best Match for You</div>
      )}
      <div className="flex items-baseline justify-between">
        <h3 className="text-2xl font-semibold">{rec.display_name}</h3>
        <div className="text-4xl font-bold gradient-text">{rec.personal_fit?.toFixed(0)}</div>
      </div>
      <div className="flex items-center gap-2 mt-1 mb-4">
        <span className="text-base" style={{ color: "var(--text-muted)" }}>
          Personal Fit
        </span>
        <ConfidenceBadge label={rec.confidence_label} />
      </div>

      {rec.reasons.length > 0 && (
        <div className="mb-3">
          <div className="text-base font-semibold mb-1" style={{ color: "var(--text-muted)" }}>
            Why this fits
          </div>
          <ul className="list-disc pl-5 space-y-1 text-base">
            {rec.reasons.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </div>
      )}

      {rec.tradeoffs.length > 0 && (
        <div>
          <div className="text-base font-semibold mb-1" style={{ color: "var(--text-muted)" }}>
            Tradeoffs
          </div>
          <ul className="list-disc pl-5 space-y-1 text-base" style={{ color: "var(--text-muted)" }}>
            {rec.tradeoffs.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </div>
      )}

      {onCompareToggle && (
        <label className="flex items-center gap-2 mt-4 text-base cursor-pointer" style={{ color: "var(--text-muted)" }}>
          <input type="checkbox" checked={!!compareSelected} onChange={onCompareToggle} />
          Add to comparison
        </label>
      )}
    </div>
  );
}

export default function ResultsView({
  bestMatch,
  alternatives,
  compareKeys,
  onCompareToggle,
  onCompare,
}: {
  bestMatch: ProfessorRecommendation;
  alternatives: ProfessorRecommendation[];
  compareKeys: string[];
  onCompareToggle: (key: string) => void;
  onCompare: () => void;
}) {
  return (
    <div className="w-full max-w-3xl mx-auto">
      <ProfessorCard
        rec={bestMatch}
        featured
        onCompareToggle={() => onCompareToggle(bestMatch.professor_key)}
        compareSelected={compareKeys.includes(bestMatch.professor_key)}
      />

      {alternatives.length > 0 && (
        <div className="mt-8">
          <h4 className="text-xl font-semibold mb-4" style={{ color: "var(--text-muted)" }}>
            Next-best alternatives
          </h4>
          <div className="flex flex-col gap-4">
            {alternatives.map((alt) => (
              <ProfessorCard
                key={alt.professor_key}
                rec={alt}
                onCompareToggle={() => onCompareToggle(alt.professor_key)}
                compareSelected={compareKeys.includes(alt.professor_key)}
              />
            ))}
          </div>
        </div>
      )}

      {compareKeys.length >= 2 && (
        <button className="btn-primary mt-8" onClick={onCompare}>
          Compare {compareKeys.length} professors
        </button>
      )}
    </div>
  );
}
