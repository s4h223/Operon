export const PROBLEM_TYPES = [
  "linear_equations",
  "systems",
  "quadratics",
  "functions",
  "regressions",
  "statistics",
  "circles",
  "exponentials",
  "roots",
  "intersections",
  "tables",
  "maxima_minima",
  "other",
] as const;

export type ProblemType = (typeof PROBLEM_TYPES)[number];

export interface DesmosStrategy {
  /** Unique id within the knowledge base. */
  id: string;
  problemType: ProblemType;
  title: string;
  /** When a tutor should reach for this strategy. */
  whenToUse: string;
  /** Exact Desmos expressions/syntax to type into the calculator. */
  desmosSyntax: string[];
  /** Ordered steps a student follows in the Desmos calculator. */
  steps: string[];
  /** Known limitations / gotchas of this approach. */
  limitations: string[];
  /** A verified worked example. */
  example: {
    problem: string;
    desmosInputs: string[];
    answer: string;
    explanation: string;
  };
  /** Keywords used for lightweight lexical retrieval. */
  keywords: string[];
}

export interface SolveRequest {
  problem: string;
}

export interface SolveResponse {
  problemType: ProblemType;
  desmosApplicable: boolean;
  strategy: string;
  desmosInputs: string[];
  steps: string[];
  answer: string;
  explanation: string;
}
