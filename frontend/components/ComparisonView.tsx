"use client";

import type { ComparisonRow } from "@/lib/types";

const ROWS: { label: string; render: (r: ComparisonRow) => React.ReactNode }[] = [
  { label: "Personal Fit", render: (r) => (r.personal_fit !== null ? r.personal_fit.toFixed(0) : "—") },
  { label: "Data Confidence", render: (r) => `${r.data_confidence.toFixed(0)} (${r.confidence_label})` },
  { label: "Course GPA", render: (r) => (r.course_gpa !== null ? r.course_gpa.toFixed(2) : "No data") },
  { label: "Graded students (sample size)", render: (r) => String(r.grade_sample_size) },
  { label: "Sections taught (course)", render: (r) => String(r.sections_taught) },
  { label: "Recent trend", render: (r) => r.recent_trend },
  {
    label: "Assessment structure",
    render: (r) =>
      r.assessment_structure && Object.values(r.assessment_structure).some((v) => v !== null && v !== undefined)
        ? `Exam ${r.assessment_structure.exam_weight ?? "?"}% · HW ${r.assessment_structure.homework_weight ?? "?"}% · Project ${
            r.assessment_structure.project_weight ?? "?"
          }%`
        : "No syllabus data",
  },
  { label: "Workload", render: (r) => r.workload_note },
  { label: "Teaching signals", render: (r) => r.teaching_signal_note },
  { label: "Attendance / structure", render: (r) => r.attendance_note },
  { label: "Support", render: (r) => r.support_note },
  { label: "Modality", render: (r) => r.modality ?? "Unknown" },
  {
    label: "Schedule",
    render: (r) => `${r.schedule.meeting_days ?? "?"} ${r.schedule.meeting_time ?? ""}`.trim() || "Unknown",
  },
  { label: "Discussion themes", render: (r) => (r.discussion_themes.length ? r.discussion_themes.join(", ") : "None found") },
];

export default function ComparisonView({ rows, onBack }: { rows: ComparisonRow[]; onBack: () => void }) {
  return (
    <div className="w-full max-w-4xl mx-auto overflow-x-auto">
      <button className="btn-secondary text-base mb-4" onClick={onBack}>
        ← Back to results
      </button>
      <table className="w-full text-base border-collapse">
        <thead>
          <tr>
            <th className="text-center p-3" style={{ color: "var(--text-muted)" }}></th>
            {rows.map((r) => (
              <th key={r.professor_key} className="text-center p-3 border-b" style={{ borderColor: "var(--border)" }}>
                {r.display_name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ROWS.map((row) => (
            <tr key={row.label}>
              <td className="p-3 font-semibold whitespace-nowrap" style={{ color: "var(--text-muted)" }}>
                {row.label}
              </td>
              {rows.map((r) => (
                <td key={r.professor_key} className="p-3 border-b align-top" style={{ borderColor: "var(--border)" }}>
                  {row.render(r)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
