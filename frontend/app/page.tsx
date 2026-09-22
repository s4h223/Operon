"use client";

import { useEffect, useState } from "react";
import Logo from "@/components/Logo";
import QuestionStep from "@/components/QuestionStep";
import ResultsView from "@/components/ResultsView";
import ComparisonView from "@/components/ComparisonView";
import {
  confirmCourse,
  fetchComparison,
  fetchProfessors,
  fetchQuestionnaire,
  fetchRecommendation,
  fetchSemesters,
  searchCourses,
} from "@/lib/api";
import type {
  ComparisonRow,
  CourseConfirmResult,
  CourseSearchResult,
  Preferences,
  ProfessorListing,
  Question,
  RecommendResponse,
  Semester,
} from "@/lib/types";

type Step =
  | "landing"
  | "loading_semesters"
  | "semester"
  | "course_search"
  | "course_confirm"
  | "loading_professors"
  | "scope"
  | "professor_select"
  | "loading_questionnaire"
  | "question"
  | "loading_recommendation"
  | "results"
  | "loading_comparison"
  | "compare"
  | "error";

const RESEARCH_PHASES = [
  "Pulling the current term's sections from GT's registration system",
  "Looking up historical grade distributions per professor",
  "Searching the public web for student discussion",
  "Checking Reddit threads mentioning each professor",
  "Reading any syllabi that turned up",
  "Scoring each professor against what matters to you",
];

/** Cycles through the real phases of the research pass. The backend does
 * this work in one blocking call with no progress stream, so this is an
 * honest description of the sequence rather than a live percentage. */
function ResearchProgress() {
  const [phase, setPhase] = useState(0);

  useEffect(() => {
    const id = setInterval(() => {
      setPhase((p) => (p + 1) % RESEARCH_PHASES.length);
    }, 2800);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="text-base" style={{ minHeight: "3rem" }}>
      {RESEARCH_PHASES[phase]}
    </div>
  );
}

const BACKEND_UNREACHABLE = "Couldn't reach the FYVE backend. Is it running?";

function Shell({ children }: { children: React.ReactNode }) {
  return (
    // pb-32 keeps scrolling content clear of the fixed GT marker. It lives
    // here rather than on <body> so the landing page stays exactly one
    // viewport tall instead of always having a scrollbar.
    <main className="min-h-screen flex flex-col items-center px-6 pt-14 pb-32" style={{ background: "var(--bg)" }}>
      <div className="mb-14">
        <Logo height={120} />
      </div>
      <div className="w-full flex-1 flex items-start justify-center">{children}</div>
    </main>
  );
}

export default function Home() {
  const [step, setStep] = useState<Step>("landing");
  const [errorMessage, setErrorMessage] = useState<string>("");

  const [semesters, setSemesters] = useState<Semester[]>([]);
  const [selectedTerm, setSelectedTerm] = useState<string | null>(null);

  const [courseQuery, setCourseQuery] = useState("");
  const [courseResults, setCourseResults] = useState<CourseSearchResult[]>([]);
  const [confirmedCourse, setConfirmedCourse] = useState<CourseConfirmResult | null>(null);

  const [professors, setProfessors] = useState<ProfessorListing[]>([]);
  const [professorsReason, setProfessorsReason] = useState<string | undefined>();
  const [selectedProfessorKeys, setSelectedProfessorKeys] = useState<string[]>([]);

  const [questions, setQuestions] = useState<Question[]>([]);
  const [questionIndex, setQuestionIndex] = useState(0);
  const [preferences, setPreferences] = useState<Preferences>({ priority: "balanced" });

  const [recommendation, setRecommendation] = useState<RecommendResponse | null>(null);
  const [compareKeys, setCompareKeys] = useState<string[]>([]);
  const [comparisonRows, setComparisonRows] = useState<ComparisonRow[] | null>(null);

  const [semestersReady, setSemestersReady] = useState(false);

  // --- initial load ---
  // Prefetched while the landing page is on screen so clicking through
  // usually lands straight on the picker with nothing to wait for. A
  // failure here is deliberately silent: the landing page stays put, and
  // the click below retries.
  useEffect(() => {
    fetchSemesters()
      .then((res) => {
        setSemesters(res.semesters);
        setSemestersReady(true);
      })
      .catch(() => undefined);
  }, []);

  function handleGetStarted() {
    if (semestersReady) {
      setStep("semester");
      return;
    }
    // Not ready: either the prefetch is still in flight, or it failed
    // because the backend hadn't finished booting when the page loaded.
    // Retry now rather than dead-ending on a stale failure.
    setStep("loading_semesters");
    fetchSemesters()
      .then((res) => {
        setSemesters(res.semesters);
        setSemestersReady(true);
        setStep("semester");
      })
      .catch(() => setErrorFatal(BACKEND_UNREACHABLE));
  }

  function setErrorFatal(msg: string) {
    setErrorMessage(msg);
    setStep("error");
  }

  // --- course search debounce ---
  useEffect(() => {
    if (step !== "course_search") return;
    const handle = setTimeout(() => {
      if (courseQuery.trim().length === 0) {
        setCourseResults([]);
        return;
      }
      searchCourses(courseQuery)
        .then((res) => setCourseResults(res.results))
        .catch(() => setCourseResults([]));
    }, 250);
    return () => clearTimeout(handle);
  }, [courseQuery, step]);

  async function handleSelectCourse(subject: string, courseNumber: string) {
    try {
      const result = await confirmCourse(subject, courseNumber);
      setConfirmedCourse(result);
      setStep("course_confirm");
    } catch {
      setErrorFatal("Couldn't look up that course.");
    }
  }

  function handleManualCourseSubmit() {
    const match = courseQuery.trim().match(/^([A-Za-z]{2,4})\s*-?\s*(\d{3,4}[A-Za-z]?)$/);
    if (!match) return;
    handleSelectCourse(match[1], match[2]);
  }

  async function handleConfirmCourse() {
    if (!confirmedCourse || !selectedTerm) return;
    setStep("loading_professors");
    try {
      const res = await fetchProfessors(confirmedCourse.subject, confirmedCourse.course_number, selectedTerm);
      setProfessors(res.professors);
      setProfessorsReason(res.reason);
      setStep("scope");
    } catch {
      setErrorFatal("Couldn't retrieve professors for this course/term.");
    }
  }

  async function proceedToQuestions(professorKeys: string[] | undefined) {
    if (!confirmedCourse || !selectedTerm) return;
    setStep("loading_questionnaire");
    try {
      const res = await fetchQuestionnaire(selectedTerm, confirmedCourse.subject, confirmedCourse.course_number, professorKeys);
      setQuestions(res.questions);
      setQuestionIndex(0);
      setPreferences({ priority: "balanced" });
      setStep(res.questions.length > 0 ? "question" : "loading_recommendation");
      if (res.questions.length === 0) {
        void runRecommendation({ priority: "balanced" }, professorKeys);
      }
    } catch {
      setErrorFatal("Couldn't load the preference questionnaire.");
    }
  }

  function handleScopeAll() {
    void proceedToQuestions(undefined);
  }

  function handleScopeSelected() {
    setStep("professor_select");
  }

  function handleAnswer(value: string) {
    const q = questions[questionIndex];
    const updated = { ...preferences, [q.field]: value };
    setPreferences(updated);
    advanceQuestion(updated);
  }

  function handleAnswerRatings(ratings: Record<string, number>) {
    const q = questions[questionIndex];
    const updated = { ...preferences, [q.field]: ratings };
    setPreferences(updated);
    advanceQuestion(updated);
  }

  function handleSkip() {
    advanceQuestion(preferences);
  }

  function advanceQuestion(prefs: Preferences) {
    const next = questionIndex + 1;
    if (next < questions.length) {
      setQuestionIndex(next);
    } else {
      setStep("loading_recommendation");
      void runRecommendation(prefs, selectedProfessorKeys.length ? selectedProfessorKeys : undefined);
    }
  }

  async function runRecommendation(prefs: Preferences, professorKeys: string[] | undefined) {
    if (!confirmedCourse || !selectedTerm) return;
    try {
      const res = await fetchRecommendation(selectedTerm, confirmedCourse.subject, confirmedCourse.course_number, prefs, professorKeys);
      setRecommendation(res);
      setStep(res.status === "ok" ? "results" : "error");
      if (res.status !== "ok") setErrorMessage(res.reason ?? "Not enough evidence to make a recommendation yet.");
    } catch {
      setErrorFatal("Couldn't compute a recommendation.");
    }
  }

  function toggleCompare(key: string) {
    setCompareKeys((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]));
  }

  async function handleCompare() {
    if (!confirmedCourse || !selectedTerm || compareKeys.length < 2) return;
    setStep("loading_comparison");
    try {
      const res = await fetchComparison(selectedTerm, confirmedCourse.subject, confirmedCourse.course_number, compareKeys, preferences);
      setComparisonRows(res.rows);
      setStep("compare");
    } catch {
      setErrorFatal("Couldn't build the comparison.");
    }
  }

  // ---------------------------------------------------------------------

  if (step === "landing") {
    return (
      <main
        className="min-h-screen flex flex-col items-center justify-center text-center px-6 py-16"
        style={{ background: "var(--bg)" }}
      >
        <div className="landing-glow" aria-hidden="true" />
        <div className="relative flex flex-col items-center gap-8" style={{ maxWidth: "40rem" }}>
          <Logo height={190} />

          <h1 className="text-5xl font-bold leading-tight">
            Pick the professor,
            <br />
            <span className="gradient-text">not just the class.</span>
          </h1>

          <button className="btn-primary text-xl" style={{ padding: "1.1rem 3rem" }} onClick={handleGetStarted}>
            Find my professor
          </button>
        </div>
      </main>
    );
  }

  if (
    step === "loading_semesters" ||
    step === "loading_professors" ||
    step === "loading_questionnaire" ||
    step === "loading_recommendation" ||
    step === "loading_comparison"
  ) {
    const isDeepResearch = step === "loading_questionnaire" || step === "loading_recommendation";
    const title =
      step === "loading_semesters"
        ? "Starting up"
        : step === "loading_professors"
          ? "Finding who's teaching this course"
          : step === "loading_comparison"
            ? "Building your comparison"
            : "Gathering evidence";

    // Laid out on its own rather than inside <Shell>, so the logo, spinner
    // and copy sit as one evenly-spaced group centered in the viewport
    // instead of the logo being pinned to the top.
    return (
      <main
        className="min-h-screen flex flex-col items-center justify-center gap-10 px-6 pt-10 pb-28"
        style={{ background: "var(--bg)" }}
      >
        <Logo height={120} />
        <div className="spinner" />
        <div
          className="text-center flex flex-col items-center gap-4"
          style={{ color: "var(--text-muted)", maxWidth: "34rem" }}
        >
          <div className="text-2xl font-semibold loading-dots" style={{ color: "var(--text)" }}>
            {title}
          </div>
          {isDeepResearch && (
            <>
              <p className="text-base">
                Researching grades, syllabi, and public discussion for each professor. This can take a
                little while - it&apos;s doing real research, not a quick lookup.
              </p>
              <p className="text-base font-semibold" style={{ color: "var(--text)" }}>
                Keep this tab open while it works - closing it stops the search.
              </p>
              <ResearchProgress />
            </>
          )}
        </div>
        <div className="progress-track" style={{ maxWidth: "28rem" }} />
      </main>
    );
  }

  if (step === "error") {
    return (
      <Shell>
        <div className="max-w-md text-center">
          <p className="mb-4" style={{ color: "var(--danger)" }}>
            {errorMessage}
          </p>
          <button className="btn-secondary" onClick={() => window.location.reload()}>
            Start over
          </button>
        </div>
      </Shell>
    );
  }

  if (step === "semester") {
    return (
      <Shell>
        <div className="w-full max-w-md">
          <h2 className="text-4xl font-semibold mb-6">What semester are you registering for?</h2>
          <div className="flex flex-col gap-3">
            {semesters.map((s) => (
              <button
                key={s.term_code}
                className="option-card text-left"
                onClick={() => {
                  setSelectedTerm(s.term_code);
                  setStep("course_search");
                }}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>
      </Shell>
    );
  }

  if (step === "course_search") {
    return (
      <Shell>
        <div className="w-full max-w-md">
          <h2 className="text-4xl font-semibold mb-6">Search for a Georgia Tech course</h2>
          <input
            className="input"
            placeholder="e.g. CS 1301, MATH 1552, ACCT 2101"
            value={courseQuery}
            onChange={(e) => setCourseQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleManualCourseSubmit()}
            autoFocus
          />
          <div className="flex flex-col gap-2 mt-4">
            {courseResults.map((c) => (
              <button
                key={`${c.subject}${c.course_number}`}
                className="option-card text-left"
                onClick={() => handleSelectCourse(c.subject, c.course_number)}
              >
                <span className="font-semibold">
                  {c.subject} {c.course_number}
                </span>{" "}
                <span style={{ color: "var(--text-muted)" }}>— {c.title}</span>
              </button>
            ))}
          </div>
          {courseQuery.match(/^[A-Za-z]{2,4}\s*-?\s*\d{3,4}[A-Za-z]?$/) && courseResults.length === 0 && (
            <button className="btn-primary mt-4" onClick={handleManualCourseSubmit}>
              Use &ldquo;{courseQuery.toUpperCase()}&rdquo;
            </button>
          )}
        </div>
      </Shell>
    );
  }

  if (step === "course_confirm" && confirmedCourse) {
    return (
      <Shell>
        <div className="w-full max-w-md text-center">
          <h2 className="text-4xl font-semibold mb-2">
            {confirmedCourse.course_code}
            {confirmedCourse.title ? ` — ${confirmedCourse.title}` : ""}
          </h2>
          {!confirmedCourse.known && (
            <p className="text-base mb-4" style={{ color: "var(--text-muted)" }}>
              This course isn&apos;t in our seed catalog, but FYVE will still try to retrieve live data for it.
            </p>
          )}
          <div className="flex gap-3 justify-center mt-6">
            <button className="btn-primary" onClick={handleConfirmCourse}>
              Confirm
            </button>
            <button className="btn-secondary" onClick={() => setStep("course_search")}>
              Search again
            </button>
          </div>
        </div>
      </Shell>
    );
  }

  if (step === "scope") {
    return (
      <Shell>
        <div className="w-full max-w-md">
          <h2 className="text-4xl font-semibold mb-2">Should FYVE evaluate all professors, or only some?</h2>
          {professorsReason && (
            <p className="text-base mb-4" style={{ color: "var(--danger)" }}>
              {professorsReason}
            </p>
          )}
          {professors.length > 0 && (
            <p className="text-base mb-4" style={{ color: "var(--text-muted)" }}>
              {professors.length} professor(s) found teaching this course this term.
            </p>
          )}
          <div className="flex flex-col gap-3">
            <button className="option-card text-left" onClick={handleScopeAll} disabled={professors.length === 0}>
              Evaluate all available professors
            </button>
            <button className="option-card text-left" onClick={handleScopeSelected} disabled={professors.length === 0}>
              Let me choose which professors
            </button>
          </div>
        </div>
      </Shell>
    );
  }

  if (step === "professor_select") {
    return (
      <Shell>
        <div className="w-full max-w-md">
          <h2 className="text-4xl font-semibold mb-6">Which professors should FYVE evaluate?</h2>
          <div className="flex flex-col gap-2">
            {professors.map((p) => (
              <label key={p.professor_key} className="option-card flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={selectedProfessorKeys.includes(p.professor_key)}
                  onChange={() =>
                    setSelectedProfessorKeys((prev) =>
                      prev.includes(p.professor_key) ? prev.filter((k) => k !== p.professor_key) : [...prev, p.professor_key]
                    )
                  }
                />
                {p.display_name}
              </label>
            ))}
          </div>
          <button
            className="btn-primary mt-6"
            disabled={selectedProfessorKeys.length === 0}
            onClick={() => proceedToQuestions(selectedProfessorKeys)}
          >
            Continue
          </button>
        </div>
      </Shell>
    );
  }

  if (step === "question" && questions[questionIndex]) {
    return (
      <Shell>
        <QuestionStep
          question={questions[questionIndex]}
          index={questionIndex}
          total={questions.length}
          onAnswer={handleAnswer}
          onAnswerRatings={handleAnswerRatings}
          onSkip={handleSkip}
        />
      </Shell>
    );
  }

  if (step === "results" && recommendation?.best_match) {
    return (
      <Shell>
        <ResultsView
          bestMatch={recommendation.best_match}
          // Everyone teaching the course except the winner, best first,
          // with the unscorable ones last - `all_ranked` already carries
          // that order, and falling back to `alternatives` only matters
          // for an older backend that doesn't send it.
          others={(recommendation.all_ranked ?? recommendation.alternatives).filter(
            (p) => p.professor_key !== recommendation.best_match?.professor_key,
          )}
          compareKeys={compareKeys}
          onCompareToggle={toggleCompare}
          onCompare={handleCompare}
        />
      </Shell>
    );
  }

  if (step === "compare" && comparisonRows) {
    return (
      <Shell>
        <ComparisonView rows={comparisonRows} onBack={() => setStep("results")} />
      </Shell>
    );
  }

  return (
    <Shell>
      <div style={{ color: "var(--text-muted)" }}>Loading…</div>
    </Shell>
  );
}
