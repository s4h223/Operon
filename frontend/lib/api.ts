import type {
  CourseConfirmResult,
  CourseSearchResult,
  Preferences,
  ProfessorListing,
  Question,
  RecommendResponse,
  Semester,
  ComparisonRow,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`Request failed: ${path} (${res.status})`);
  return res.json();
}

async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Request failed: ${path} (${res.status})`);
  return res.json();
}

export function fetchSemesters(): Promise<{ semesters: Semester[] }> {
  return getJSON("/api/semesters");
}

export function searchCourses(q: string): Promise<{ results: CourseSearchResult[] }> {
  return getJSON(`/api/courses/search?q=${encodeURIComponent(q)}`);
}

export function confirmCourse(subject: string, courseNumber: string): Promise<CourseConfirmResult> {
  return getJSON(
    `/api/courses/confirm?subject=${encodeURIComponent(subject)}&course_number=${encodeURIComponent(courseNumber)}`
  );
}

export function fetchProfessors(
  subject: string,
  courseNumber: string,
  term: string
): Promise<{ status: string; reason?: string; professors: ProfessorListing[] }> {
  return getJSON(
    `/api/courses/${encodeURIComponent(subject)}/${encodeURIComponent(courseNumber)}/professors?term=${encodeURIComponent(
      term
    )}`
  );
}

export function fetchQuestionnaire(
  termCode: string,
  subject: string,
  courseNumber: string,
  professorKeys?: string[]
): Promise<{ questions: Question[]; professor_count: number }> {
  return postJSON("/api/questionnaire", {
    term_code: termCode,
    subject,
    course_number: courseNumber,
    professor_keys: professorKeys ?? null,
  });
}

export function fetchRecommendation(
  termCode: string,
  subject: string,
  courseNumber: string,
  preferences: Preferences,
  professorKeys?: string[]
): Promise<RecommendResponse> {
  return postJSON("/api/recommend", {
    term_code: termCode,
    subject,
    course_number: courseNumber,
    professor_keys: professorKeys ?? null,
    preferences,
  });
}

export function fetchComparison(
  termCode: string,
  subject: string,
  courseNumber: string,
  professorKeys: string[],
  preferences: Preferences
): Promise<{ rows: ComparisonRow[] }> {
  return postJSON("/api/compare", {
    term_code: termCode,
    subject,
    course_number: courseNumber,
    professor_keys: professorKeys,
    preferences,
  });
}
