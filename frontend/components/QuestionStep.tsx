"use client";

import type { Question } from "@/lib/types";

export default function QuestionStep({
  question,
  index,
  total,
  onAnswer,
  onSkip,
}: {
  question: Question;
  index: number;
  total: number;
  onAnswer: (value: string) => void;
  onSkip: () => void;
}) {
  return (
    <div className="w-full max-w-lg mx-auto">
      <div className="text-base mb-2" style={{ color: "var(--text-muted)" }}>
        Question {index + 1} of {total}
      </div>
      <h2 className="text-4xl font-semibold mb-6">{question.text}</h2>
      <div className="flex flex-col gap-3">
        {question.options.map((opt) => (
          <button key={opt.value} className="option-card text-left" onClick={() => onAnswer(opt.value)}>
            {opt.label}
          </button>
        ))}
      </div>
      {!question.always_ask && (
        <button className="btn-secondary mt-6 text-base" onClick={onSkip}>
          Skip - no preference
        </button>
      )}
    </div>
  );
}
