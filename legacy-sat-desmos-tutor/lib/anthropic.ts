import Anthropic from "@anthropic-ai/sdk";

let client: Anthropic | null = null;

/**
 * Lazily-constructed singleton Anthropic client. Lazy so that importing this
 * module (e.g. from a route file during build) never throws just because
 * ANTHROPIC_API_KEY isn't set yet - the error only surfaces when a request
 * actually tries to call the API.
 */
export function getAnthropicClient(): Anthropic {
  if (!client) {
    client = new Anthropic();
  }
  return client;
}

/** Model used for the SAT Desmos solve endpoint. Override via env if needed. */
export const SOLVE_MODEL = process.env.ANTHROPIC_SOLVE_MODEL ?? "claude-opus-5";
