export interface Semester {
  term_code: string;
  label: string;
}

export interface CourseSearchResult {
  subject: string;
  course_number: string;
  title: string;
}

export interface CourseConfirmResult {
  subject: string;
  course_number: string;
  course_code: string;
  title: string | null;
  known: boolean;
}

export interface SectionMeta {
  crn: string;
  section_id: string;
  meeting_days: string | null;
  meeting_time: string | null;
  modality: string | null;
}

export interface ProfessorListing {
  professor_key: string;
  display_name: string;
  sections: SectionMeta[];
}

export interface QuestionOption {
  value: string;
  label: string;
}

export interface Question {
  id: string;
  field: string;
  text: string;
  options: QuestionOption[];
  always_ask: boolean;
  evidence_probe: string | null;
}

export interface Preferences {
  priority: string;
  workload_preference?: string | null;
  assessment_preference?: string | null;
  structure_preference?: string | null;
  attendance_preference?: string | null;
  support_importance?: string | null;
  modality_preference?: string | null;
}

export interface ComponentResult {
  name: string;
  raw_score: number | null;
  sample_size: number;
  confidence: number;
  note: string;
  weight: number | null;
}

export interface ProfessorRecommendation {
  professor_key: string;
  display_name: string;
  personal_fit: number | null;
  data_confidence: number;
  confidence_label: string;
  reasons: string[];
  tradeoffs: string[];
  components: ComponentResult[];
}

export interface RecommendResponse {
  status: string;
  reason?: string;
  best_match: ProfessorRecommendation | null;
  alternatives: ProfessorRecommendation[];
  all_ranked?: ProfessorRecommendation[];
}

export interface ComparisonRow {
  professor_key: string;
  display_name: string;
  personal_fit: number | null;
  data_confidence: number;
  confidence_label: string;
  course_gpa: number | null;
  grade_sample_size: number;
  withdrawal_rate: number | null;
  sections_taught: number;
  recent_trend: string;
  assessment_structure: Record<string, number | null>;
  workload_note: string;
  teaching_signal_note: string;
  attendance_note: string;
  support_note: string;
  modality: string | null;
  schedule: Record<string, string | null>;
  discussion_themes: string[];
}
