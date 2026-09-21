import { z } from "zod";
import { PROBLEM_TYPES } from "./types";

export const SolveRequestSchema = z.object({
  problem: z
    .string()
    .trim()
    .min(3, "Problem text is too short.")
    .max(4000, "Problem text is too long."),
});

/**
 * Shape Claude must return, enforced via output_config.format (structured
 * outputs) on the /api/solve call. Also re-validated on the response with
 * .safeParse() before it's trusted and sent to the frontend.
 */
export const SolveResponseSchema = z.object({
  problemType: z.enum(PROBLEM_TYPES).describe(
    "The SAT math category this problem belongs to."
  ),
  desmosApplicable: z
    .boolean()
    .describe("True if a genuine Desmos shortcut exists for this problem."),
  strategy: z
    .string()
    .min(1)
    .describe(
      "One-sentence name of the Desmos strategy used (e.g. 'Graph both equations and find the intersection')."
    ),
  desmosInputs: z
    .array(z.string())
    .describe(
      "Exact strings to type into the Desmos expression list, in order, using Desmos syntax (e.g. 'y_1=3x+5')."
    ),
  steps: z
    .array(z.string())
    .min(1)
    .describe(
      "Concrete Desmos UI actions the student takes, in order (e.g. 'Click the intersection point')."
    ),
  answer: z
    .string()
    .min(1)
    .describe("The final answer to the question that was actually asked."),
  explanation: z
    .string()
    .min(1)
    .describe(
      "Brief explanation of why this Desmos approach works and how to interpret the result."
    ),
});

export type ValidatedSolveResponse = z.infer<typeof SolveResponseSchema>;
