# SAT Desmos Tutor

A specialized SAT Math tutor that answers one question: **what's the fastest
way to solve this exact problem using Desmos?** It does not behave like a
generic AI math solver — it classifies the problem, pulls verified Desmos
strategies from a knowledge base, and tells the student exactly what to type
into the calculator, what feature of the graph/table to look at, and how to
read off the answer.

## Stack

- **Next.js 16 (App Router) + TypeScript + React** — frontend and backend in
  one project.
- **Tailwind CSS 4** — styling.
- **Anthropic Claude API** (`@anthropic-ai/sdk`) — called only from the server
  (`app/api/solve/route.ts`), so the API key is never exposed to the browser.
- **Zod** — validates the request in and the structured response out.

## Getting started

```bash
npm install
cp .env.example .env.local   # then fill in ANTHROPIC_API_KEY
npm run dev
```

Open [http://localhost:3000](http://localhost:3000), paste an SAT math
problem, and submit.

## How a request flows

1. **Frontend** (`components/SolverForm.tsx`) posts `{ problem }` to
   `POST /api/solve`.
2. **Retrieval** (`lib/retrieval.ts`) heuristically classifies the problem
   into one of twelve SAT categories (linear equations, systems, quadratics,
   functions, regressions, statistics, circles, exponentials, roots,
   intersections, tables, maxima/minima) and pulls the most relevant
   strategies out of the knowledge base by keyword match. This keeps only a
   handful of relevant strategies in Claude's context instead of the whole
   corpus — the same shape a real vector-search retrieval step would have.
3. **Prompting** (`lib/systemPrompt.ts`) builds a system prompt that tells
   Claude it's a Desmos-shortcut tutor (not a generic solver) and interpolates
   the retrieved strategies — problem type, when to use it, exact Desmos
   syntax, limitations, and a verified worked example.
4. **Structured generation** (`app/api/solve/route.ts`) calls
   `client.messages.parse()` with `output_config.format` set to a Zod schema
   (`lib/schema.ts`), so Claude's response is constrained to:
   `problemType`, `strategy`, `desmosInputs`, `steps`, `answer`,
   `explanation`, `desmosApplicable`.
5. **Validation** — the parsed response is re-validated with
   `SolveResponseSchema.safeParse()`. Any failure (invalid shape, refusal,
   rate limit, auth error, missing API key, network error) returns a
   well-formed fallback response (`lib/fallback.ts`) instead of a raw error,
   so the frontend never has to special-case failure modes.
6. **Frontend** renders the strategy, the literal strings to type into
   Desmos, step-by-step UI actions, the answer, and a short explanation
   (`components/ResultCard.tsx`) — plus a live embedded Desmos calculator
   (`components/DesmosGraph.tsx`) preloaded with the returned expressions,
   where the returned inputs are literal graphable expressions.

## Knowledge base (`lib/knowledgeBase.ts`)

Currently a hand-verified, hard-coded array of strategies — one entry per
Desmos technique (intersection-solving, root-finding, regression, tables,
sliders, stats functions, etc.), each with: when to use it, exact Desmos
syntax, ordered UI steps, known limitations, and a verified worked example.
`lib/retrieval.ts` is the only file that reads from it, so it's a drop-in
replacement point.

## Roadmap (as designed, not yet built)

- **Image input**: accept a screenshot of a problem, run it through a
  vision-capable Claude call to extract/normalize the problem text, then feed
  that into the exact same `/api/solve` pipeline unchanged.
- **Real RAG**: replace the lexical scoring in `lib/retrieval.ts` with an
  embeddings index (e.g. store the knowledge base in a vector DB) without
  touching any caller — `getStrategiesForProblem()` is the seam.
- **Benchmark dataset**: a growing set of real SAT-style questions paired
  with manually verified optimal Desmos solutions, used to evaluate generated
  responses for correct syntax, correct answers, correct strategy selection,
  and whether the Desmos approach actually beats solving it by hand.
- **Deeper Desmos embedding**: the current `DesmosGraph` component already
  preloads graphable `desmosInputs` into a live embedded calculator; this can
  be extended to also preload tables/regressions and sliders once the
  knowledge base's non-graph strategies carry structured (not just
  human-readable) setup data.

## Environment variables

See `.env.example`:

- `ANTHROPIC_API_KEY` (required, server-only)
- `ANTHROPIC_SOLVE_MODEL` (optional, defaults to `claude-opus-5`)
- `NEXT_PUBLIC_DESMOS_API_KEY` (optional, defaults to Desmos's public `demo`
  key — register your own at
  [desmos.com/api](https://www.desmos.com/api/v1.11/docs/index.html) before
  shipping to real users)
