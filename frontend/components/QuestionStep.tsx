"use client";

import { useState } from "react";
import type { Question } from "@/lib/types";

const DEFAULT_RATING = 3;

function RateQuestion({
  question,
  onComplete,
}: {
  question: Question;
  onComplete: (ratings: Record<string, number>) => void;
}) {
  const min = question.scale_min ?? 1;
  const max = question.scale_max ?? 5;
  const scale = Array.from({ length: max - min + 1 }, (_, i) => min + i);

  const [ratings, setRatings] = useState<Record<string, number>>(() =>
    Object.fromEntries(question.options.map((opt) => [opt.value, DEFAULT_RATING])),
  );

  return (
    <div className="w-full max-w-2xl mx-auto">
      <h2 className="text-4xl font-semibold mb-2">{question.text}</h2>
      <p className="text-base mb-7" style={{ color: "var(--text-muted)" }}>
        {min} = {question.scale_min_label ?? "Not important"} · {max} ={" "}
        {question.scale_max_label ?? "Very important"}
      </p>

      <div className="flex flex-col gap-4">
        {question.options.map((opt) => (
          <div key={opt.value} className="option-card" style={{ cursor: "default" }}>
            <div className="font-semibold text-xl">{opt.label}</div>
            {opt.description && (
              <div className="text-base mt-1 mb-4" style={{ color: "var(--text-muted)" }}>
                {opt.description}
              </div>
            )}
            <div className="flex gap-2 flex-wrap justify-center" role="group" aria-label={opt.label}>
              {scale.map((value) => {
                const selected = ratings[opt.value] === value;
                return (
                  <button
                    key={value}
                    type="button"
                    aria-pressed={selected}
                    className="rating-pip"
                    data-selected={selected ? "true" : "false"}
                    onClick={() => setRatings((prev) => ({ ...prev, [opt.value]: value }))}
                  >
                    {value}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      <button className="btn-primary mt-7 w-full" onClick={() => onComplete(ratings)}>
        Continue
      </button>
    </div>
  );
}

export default function QuestionStep({
  question,
  index,
  total,
  onAnswer,
  onAnswerRatings,
  onSkip,
}: {
  question: Question;
  index: number;
  total: number;
  onAnswer: (value: string) => void;
  onAnswerRatings: (ratings: Record<string, number>) => void;
  onSkip: () => void;
}) {
  if (question.type === "rate") {
    return (
      <div className="w-full">
        <div className="text-base mb-2 text-center" style={{ color: "var(--text-muted)" }}>
          Question {index + 1} of {total}
        </div>
        <RateQuestion question={question} onComplete={onAnswerRatings} />
      </div>
    );
  }

  return (
    <div className="w-full max-w-lg mx-auto">
      <div className="text-base mb-2" style={{ color: "var(--text-muted)" }}>
        Question {index + 1} of {total}
      </div>
      <h2 className="text-4xl font-semibold mb-6">{question.text}</h2>
      <div className="flex flex-col gap-3">
        {question.options.map((opt) => (
          <button key={opt.value} className="option-card" onClick={() => onAnswer(opt.value)}>
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
