import { NextResponse } from "next/server";
import Anthropic from "@anthropic-ai/sdk";
import { zodOutputFormat } from "@anthropic-ai/sdk/helpers/zod";

import { getAnthropicClient, SOLVE_MODEL } from "@/lib/anthropic";
import { getStrategiesForProblem } from "@/lib/retrieval";
import { buildSystemPrompt } from "@/lib/systemPrompt";
import { SolveRequestSchema, SolveResponseSchema } from "@/lib/schema";
import { buildFallbackResponse } from "@/lib/fallback";

export const runtime = "nodejs";

export async function POST(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { error: "Request body must be valid JSON." },
      { status: 400 }
    );
  }

  const parsedRequest = SolveRequestSchema.safeParse(body);
  if (!parsedRequest.success) {
    return NextResponse.json(
      { error: parsedRequest.error.issues[0]?.message ?? "Invalid request." },
      { status: 400 }
    );
  }

  const { problem } = parsedRequest.data;

  // "Retrieval": pick the handful of knowledge-base strategies relevant to
  // this problem so Claude's context stays small and on-topic. See
  // lib/retrieval.ts for how this upgrades to real vector search later.
  const { classifiedType, strategies } = getStrategiesForProblem(problem);
  const systemPrompt = buildSystemPrompt(classifiedType, strategies);

  let client: Anthropic;
  try {
    client = getAnthropicClient();
  } catch {
    return NextResponse.json(
      buildFallbackResponse(
        "The tutor is temporarily unavailable (server is missing an API key).",
        classifiedType
      ),
      { status: 200 }
    );
  }

  try {
    const message = await client.messages.parse({
      model: SOLVE_MODEL,
      max_tokens: 4000,
      system: systemPrompt,
      messages: [{ role: "user", content: problem }],
      output_config: {
        format: zodOutputFormat(SolveResponseSchema),
      },
    });

    if (message.stop_reason === "refusal") {
      return NextResponse.json(
        buildFallbackResponse(
          "The tutor declined to answer this problem.",
          classifiedType
        )
      );
    }

    const validated = SolveResponseSchema.safeParse(message.parsed_output);
    if (!validated.success) {
      return NextResponse.json(
        buildFallbackResponse(
          "The tutor's response didn't match the expected format. Please try again.",
          classifiedType
        )
      );
    }

    return NextResponse.json(validated.data);
  } catch (error) {
    if (error instanceof Anthropic.RateLimitError) {
      return NextResponse.json(
        buildFallbackResponse(
          "The tutor is receiving too many requests right now. Please try again shortly.",
          classifiedType
        ),
        { status: 200 }
      );
    }
    if (error instanceof Anthropic.AuthenticationError) {
      return NextResponse.json(
        buildFallbackResponse(
          "The tutor is temporarily unavailable (authentication failed).",
          classifiedType
        ),
        { status: 200 }
      );
    }
    if (error instanceof Anthropic.APIError) {
      return NextResponse.json(
        buildFallbackResponse(
          `The tutor service returned an error (${error.status}). Please try again.`,
          classifiedType
        ),
        { status: 200 }
      );
    }

    console.error("Unexpected error in /api/solve:", error);
    return NextResponse.json(
      buildFallbackResponse(
        "Something went wrong while solving this problem. Please try again.",
        classifiedType
      ),
      { status: 200 }
    );
  }
}
