import type { ProblemType, SolveResponse } from "./types";

/**
 * Response returned when Claude can't be reached, returns something that
 * doesn't validate, or genuinely has nothing useful to say. The frontend
 * always gets back a well-formed SolveResponse, never a raw error blob.
 */
export function buildFallbackResponse(
  reason: string,
  classifiedType: ProblemType = "other"
): SolveResponse {
  return {
    problemType: classifiedType,
    desmosApplicable: false,
    strategy: "Not available",
    desmosInputs: [],
    steps: [
      "We couldn't generate a verified Desmos strategy for this problem.",
      "Try rephrasing the problem, or solve it with standard algebra for now.",
    ],
    answer: "Unavailable",
    explanation: reason,
  };
}
