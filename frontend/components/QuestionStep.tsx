"use client";

import { useRef, useState } from "react";
import type { Question } from "@/lib/types";

function RankQuestion({
  question,
  onComplete,
}: {
  question: Question;
  onComplete: (ranking: string[]) => void;
}) {
  const [order, setOrder] = useState<string[]>(() => question.options.map((opt) => opt.value));
  const [draggingValue, setDraggingValue] = useState<string | null>(null);
  const [dragOverValue, setDragOverValue] = useState<string | null>(null);
  const touchStartY = useRef<number | null>(null);

  const labelOf = (value: string) => question.options.find((o) => o.value === value)?.label ?? value;

  function moveTo(value: string, targetIndex: number) {
    setOrder((prev) => {
      const from = prev.indexOf(value);
      if (from === -1) return prev;
      const next = [...prev];
      next.splice(from, 1);
      next.splice(Math.max(0, Math.min(targetIndex, next.length)), 0, value);
      return next;
    });
  }

  function move(value: string, delta: number) {
    setOrder((prev) => {
      const from = prev.indexOf(value);
      const to = from + delta;
      if (from === -1 || to < 0 || to >= prev.length) return prev;
      const next = [...prev];
      const [item] = next.splice(from, 1);
      next.splice(to, 0, item);
      return next;
    });
  }

  function handleDrop(targetValue: string) {
    if (draggingValue && draggingValue !== targetValue) {
      moveTo(draggingValue, order.indexOf(targetValue));
    }
    setDraggingValue(null);
    setDragOverValue(null);
  }

  return (
    <div className="w-full max-w-lg mx-auto">
      <div className="text-base mb-2" style={{ color: "var(--text-muted)" }}>
        Drag to rank - most important at the top
      </div>
      <h2 className="text-4xl font-semibold mb-6">{question.text}</h2>

      <ol className="flex flex-col gap-3">
        {order.map((value, i) => {
          const isDragging = draggingValue === value;
          const isDragOver = dragOverValue === value && draggingValue !== value;
          return (
            <li
              key={value}
              draggable
              onDragStart={() => setDraggingValue(value)}
              onDragEnd={() => {
                setDraggingValue(null);
                setDragOverValue(null);
              }}
              onDragOver={(e) => {
                e.preventDefault();
                if (dragOverValue !== value) setDragOverValue(value);
              }}
              onDrop={(e) => {
                e.preventDefault();
                handleDrop(value);
              }}
              onTouchStart={(e) => {
                setDraggingValue(value);
                touchStartY.current = e.touches[0].clientY;
              }}
              onTouchMove={(e) => {
                if (!draggingValue) return;
                const touch = e.touches[0];
                const el = document.elementFromPoint(touch.clientX, touch.clientY);
                const row = el?.closest("[data-rank-value]") as HTMLElement | null;
                const overValue = row?.dataset.rankValue;
                if (overValue && overValue !== dragOverValue) setDragOverValue(overValue);
              }}
              onTouchEnd={() => {
                if (draggingValue && dragOverValue) handleDrop(dragOverValue);
                setDraggingValue(null);
                setDragOverValue(null);
                touchStartY.current = null;
              }}
              data-rank-value={value}
              className="option-card flex items-center gap-4"
              style={{
                cursor: "grab",
                opacity: isDragging ? 0.4 : 1,
                borderColor: isDragOver ? "var(--accent-end)" : undefined,
                touchAction: "none",
              }}
            >
              <span className="gradient-text font-semibold text-xl" style={{ minWidth: "1.6rem" }}>
                {i + 1}
              </span>
              <span aria-hidden="true" style={{ color: "var(--text-muted)", fontSize: "1.2rem", lineHeight: 1 }}>
                ⠿
              </span>
              <span className="flex-1">{labelOf(value)}</span>
              <div className="flex flex-col gap-1">
                <button
                  type="button"
                  aria-label={`Move "${labelOf(value)}" up`}
                  className="btn-secondary"
                  style={{ padding: "0.2rem 0.6rem", fontSize: "0.85rem" }}
                  disabled={i === 0}
                  onClick={() => move(value, -1)}
                >
                  ▲
                </button>
                <button
                  type="button"
                  aria-label={`Move "${labelOf(value)}" down`}
                  className="btn-secondary"
                  style={{ padding: "0.2rem 0.6rem", fontSize: "0.85rem" }}
                  disabled={i === order.length - 1}
                  onClick={() => move(value, 1)}
                >
                  ▼
                </button>
              </div>
            </li>
          );
        })}
      </ol>

      <button className="btn-primary mt-6 w-full" onClick={() => onComplete(order)}>
        Confirm my priority order
      </button>
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
