import { knowledgeBase } from "./knowledgeBase";
import { PROBLEM_TYPES, type DesmosStrategy, type ProblemType } from "./types";

/**
 * v1 "retrieval": lightweight lexical scoring over the knowledge base.
 *
 * This intentionally has the same shape a future RAG step would have -
 * `getStrategiesForProblem(problem)` returns a ranked, capped list of
 * strategies - so it can be swapped for an embeddings + vector-search
 * lookup later without changing any caller.
 */

const TYPE_HINT_PATTERNS: Record<ProblemType, RegExp[]> = {
  linear_equations: [/\bsolve for [a-z]\b/i, /\blinear equation\b/i],
  systems: [/\bsystem of\b/i, /\bboth equations\b/i, /\bsimultaneously\b/i],
  quadratics: [/quadratic/i, /parabola/i, /\bfactor(ed|ing)?\b/i],
  functions: [/f\s*\(\s*x\s*\)/i, /\bfunction\b/i, /\bcomposite\b/i],
  regressions: [/line of best fit/i, /regression/i, /best models the data/i],
  statistics: [/\bmean\b/i, /\bmedian\b/i, /standard deviation/i, /data set/i],
  circles: [/\bcircle\b/i, /\bradius\b/i, /\bcenter\b/i],
  exponentials: [/exponential/i, /growth/i, /decay/i, /compound/i],
  roots: [/square root/i, /cube root/i, /\bradical\b/i, /sqrt/i],
  intersections: [/intersect/i, /how many solutions/i, /points in common/i],
  tables: [/\btable\b/i, /which value/i, /answer choices/i],
  maxima_minima: [/\bmaximum\b/i, /\bminimum\b/i, /\bmax\b/i, /\bmin\b/i],
  other: [],
};

/** Very small heuristic classifier used purely to steer retrieval. */
export function classifyProblem(problem: string): ProblemType {
  let best: ProblemType = "other";
  let bestScore = 0;
  for (const type of PROBLEM_TYPES) {
    const patterns = TYPE_HINT_PATTERNS[type];
    const score = patterns.reduce(
      (acc, re) => acc + (re.test(problem) ? 1 : 0),
      0
    );
    if (score > bestScore) {
      bestScore = score;
      best = type;
    }
  }
  return best;
}

function scoreStrategy(strategy: DesmosStrategy, problem: string): number {
  const text = problem.toLowerCase();
  let score = 0;
  for (const keyword of strategy.keywords) {
    if (text.includes(keyword.toLowerCase())) {
      score += 2;
    }
  }
  return score;
}

/**
 * Returns the most relevant strategies for a problem, ranked by lexical
 * match. Always includes at least the strategies for the heuristically
 * classified problemType, even if no keyword matched, so Claude has a
 * reasonable default to work from.
 */
export function getStrategiesForProblem(
  problem: string,
  maxResults = 4
): { classifiedType: ProblemType; strategies: DesmosStrategy[] } {
  const classifiedType = classifyProblem(problem);

  const scored = knowledgeBase
    .map((strategy) => ({
      strategy,
      score:
        scoreStrategy(strategy, problem) +
        (strategy.problemType === classifiedType ? 3 : 0),
    }))
    .sort((a, b) => b.score - a.score);

  const top = scored
    .filter((entry) => entry.score > 0)
    .slice(0, maxResults)
    .map((entry) => entry.strategy);

  if (top.length === 0) {
    return {
      classifiedType,
      strategies: knowledgeBase
        .filter((s) => s.problemType === classifiedType)
        .slice(0, maxResults),
    };
  }

  return { classifiedType, strategies: top };
}
