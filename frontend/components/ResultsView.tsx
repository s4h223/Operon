"use client";

import type { ProfessorRecommendation } from "@/lib/types";

function ConfidenceBadge({ label }: { label: string }) {
  const cls = label.toLowerCase() === "high" ? "high" : label.toLowerCase() === "moderate" ? "moderate" : "low";
  return <span className={`badge ${cls}`}>{label} confidence</span>;
}

function MatchScore({ value, featured }: { value: number; featured?: boolean }) {
  return (
    <div className="leading-none">
      <span className={`${featured ? "text-6xl" : "text-4xl"} font-bold gradient-text`}>{value.toFixed(0)}%</span>
      <div className={`${featured ? "text-base" : "text-sm"} mt-1`} style={{ color: "var(--text-muted)" }}>
        match
      </div>
    </div>
  );
}

function ProfessorCard({
  rec,
  featured,
  rank,
  onCompareToggle,
  compareSelected,
}: {
  rec: ProfessorRecommendation;
  featured?: boolean;
  rank?: number;
  onCompareToggle?: () => void;
  compareSelected?: boolean;
}) {
  const scored = rec.personal_fit !== null && rec.personal_fit !== undefined;

  return (
    <div
      className={`card ${featured ? "p-9" : "p-6"} ${scored ? "" : "opacity-75"}`}
      style={
        featured
          ? {
              // Lift the winner above the alternatives so the page has one
              // obvious answer rather than a wall of equal-looking cards.
              // Sized up via padding/type rather than a transform, which
              // would overflow the gutter on a narrow screen.
              borderColor: "var(--accent-end)",
              borderWidth: "2px",
              boxShadow: "0 12px 44px rgba(91, 127, 232, 0.18)",
            }
          : {}
      }
    >
      {featured && (
        <div className="gradient-text font-semibold text-lg mb-3 uppercase tracking-wide">Best Match for You</div>
      )}
      <div className="flex flex-col items-center gap-2">
        <h3 className={`${featured ? "text-4xl" : "text-2xl"} font-semibold`}>
          {rank !== undefined && (
            <span style={{ color: "var(--text-muted)" }} className="mr-2">
              #{rank}
            </span>
          )}
          {rec.display_name}
        </h3>
        {scored ? (
          <MatchScore value={rec.personal_fit as number} featured={featured} />
        ) : (
          <span className="text-base whitespace-nowrap" style={{ color: "var(--text-muted)" }}>
            Not enough data
          </span>
        )}
      </div>

      {scored && (
        <div className="flex items-center justify-center gap-2 mt-2 mb-4">
          <ConfidenceBadge label={rec.confidence_label} />
        </div>
      )}

      {!scored && (
        <p className="text-base mt-2" style={{ color: "var(--text-muted)" }}>
          This professor is teaching the course, but there wasn&apos;t enough public data (grades,
          syllabus, or student discussion) to score them against your priorities.
        </p>
      )}

      {rec.reasons.length > 0 && (
        <div className="mb-3">
          <div
            className={`${featured ? "text-lg" : "text-base"} font-semibold mb-1`}
            style={{ color: "var(--text-muted)" }}
          >
            Why this fits
          </div>
          <ul className={`space-y-2 ${featured ? "text-lg" : "text-base"}`}>
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
          <ul className="space-y-1 text-base" style={{ color: "var(--text-muted)" }}>
            {rec.tradeoffs.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </div>
      )}

      {onCompareToggle && scored && (
        <label className="flex items-center justify-center gap-2 mt-4 text-base cursor-pointer" style={{ color: "var(--text-muted)" }}>
          <input type="checkbox" checked={!!compareSelected} onChange={onCompareToggle} />
          Compare side by side
        </label>
      )}
    </div>
  );
}

export default function ResultsView({
  bestMatch,
  others,
  compareKeys,
  onCompareToggle,
  onCompare,
}: {
  bestMatch: ProfessorRecommendation;
  /** Every other professor teaching the course, best first, with the ones
   * that couldn't be scored last. */
  others: ProfessorRecommendation[];
  compareKeys: string[];
  onCompareToggle: (key: string) => void;
  onCompare: () => void;
}) {
  const scoredOthers = others.filter((o) => o.personal_fit !== null && o.personal_fit !== undefined);
  const unscored = others.filter((o) => o.personal_fit === null || o.personal_fit === undefined);

  return (
    <div className="w-full max-w-3xl mx-auto">
      <ProfessorCard
        rec={bestMatch}
        featured
        onCompareToggle={() => onCompareToggle(bestMatch.professor_key)}
        compareSelected={compareKeys.includes(bestMatch.professor_key)}
      />

      {scoredOthers.length > 0 && (
        <div className="mt-8">
          <h4 className="text-xl font-semibold mb-4" style={{ color: "var(--text-muted)" }}>
            Everyone else teaching this course, ranked
          </h4>
          <div className="flex flex-col gap-4">
            {scoredOthers.map((alt, i) => (
              <ProfessorCard
                key={alt.professor_key}
                rec={alt}
                rank={i + 2}
                onCompareToggle={() => onCompareToggle(alt.professor_key)}
                compareSelected={compareKeys.includes(alt.professor_key)}
              />
            ))}
          </div>
        </div>
      )}

      {unscored.length > 0 && (
        <div className="mt-8">
          <h4 className="text-xl font-semibold mb-4" style={{ color: "var(--text-muted)" }}>
            Also teaching this course - not enough data to rank
          </h4>
          <div className="flex flex-col gap-4">
            {unscored.map((prof) => (
              <ProfessorCard key={prof.professor_key} rec={prof} />
            ))}
          </div>
        </div>
      )}

      <div className="mt-8">
        {compareKeys.length >= 2 ? (
          <button className="btn-primary" onClick={onCompare}>
            Compare {compareKeys.length} professors side by side
          </button>
        ) : (
          <p className="text-base" style={{ color: "var(--text-muted)" }}>
            Tick &ldquo;Compare side by side&rdquo; on two or more professors to see their grades, workload,
            and schedule in one table.
          </p>
        )}
      </div>
    </div>
  );
}
