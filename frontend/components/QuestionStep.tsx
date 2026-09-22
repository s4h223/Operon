"use client";

import { useState } from "react";
import type { Question } from "@/lib/types";

const ORDINALS = ["1st", "2nd", "3rd", "4th", "5th", "6th", "7th"];

function RankQuestion({
  question,
  onComplete,
}: {
  question: Question;
  onComplete: (ranking: string[]) => void;
}) {
  const [picked, setPicked] = useState<string[]>([]);
  const rankCount = Math.min(question.rank_count ?? 3, question.options.length);
  const remaining = question.options.filter((opt) => !picked.includes(opt.value));
  const currentRank = picked.length + 1;

  function pick(value: string) {
    const next = [...picked, value];
    if (next.length >= rankCount) {
      onComplete(next);
    } else {
      setPicked(next);
    }
  }

  return (
    <div className="w-full max-w-lg mx-auto">
      <div className="text-base mb-2" style={{ color: "var(--text-muted)" }}>
        Pick your {ORDINALS[currentRank - 1] ?? `${currentRank}th`} priority
        {picked.length > 0 && ` (of ${rankCount})`}
      </div>
      <h2 className="text-4xl font-semibold mb-6">{question.text}</h2>

      {picked.length > 0 && (
        <ol className="mb-5 flex flex-col gap-1 text-base" style={{ color: "var(--text-muted)" }}>
          {picked.map((value, i) => {
            const label = question.options.find((o) => o.value === value)?.label ?? value;
            return (
              <li key={value}>
                <span className="gradient-text font-semibold">#{i + 1}</span> {label}
              </li>
            );
          })}
        </ol>
      )}

      <div className="flex flex-col gap-3">
        {remaining.map((opt) => (
          <button key={opt.value} className="option-card text-left" onClick={() => pick(opt.value)}>
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  );
}

export default function QuestionStep({
  question,
  index,
  total,
  onAnswer,
  onAnswerMultiple,
  onSkip,
}: {
  question: Question;
  index: number;
  total: number;
  onAnswer: (value: string) => void;
  onAnswerMultiple: (values: string[]) => void;
  onSkip: () => void;
}) {
  if (question.type === "rank") {
    return (
      <div className="w-full">
        <div className="text-base mb-2 text-center" style={{ color: "var(--text-muted)" }}>
          Question {index + 1} of {total}
        </div>
        <RankQuestion question={question} onComplete={onAnswerMultiple} />
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
