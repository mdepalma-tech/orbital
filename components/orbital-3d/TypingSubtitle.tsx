"use client";

import { useState, useEffect, useRef } from "react";

const INITIAL_TEXT = "Your growth data is fragmented.";
const REVEALED_TEXT = "ORBITAL REVEALS THE STRUCTURE";

const TYPING_MS = 45;
const DELETE_MS = 25;
const RETYPE_MS = 40;

type Phase = "chaos" | "activating" | "orbital";

interface TypingSubtitleProps {
  phase: Phase;
}

export function TypingSubtitle({ phase }: TypingSubtitleProps) {
  const [displayText, setDisplayText] = useState("");
  const [isRevealed, setIsRevealed] = useState(false);
  const phaseRef = useRef<Phase>("chaos");
  const hasStartedActivation = useRef(false);

  // Phase 1: Initial typing on first load (chaos)
  useEffect(() => {
    if (phase !== "chaos") return;
    if (displayText === INITIAL_TEXT) return;

    const timeout = setTimeout(() => {
      setDisplayText(INITIAL_TEXT.slice(0, displayText.length + 1));
    }, TYPING_MS);

    return () => clearTimeout(timeout);
  }, [phase, displayText]);

  // Phase 2: Delete then retype when transitioning to activating
  useEffect(() => {
    if (phase !== "activating") return;
    if (!hasStartedActivation.current) {
      hasStartedActivation.current = true;
    }

    if (displayText.length > 0 && !isRevealed) {
      // Deleting
      const timeout = setTimeout(() => {
        setDisplayText((prev) => prev.slice(0, -1));
      }, DELETE_MS);
      return () => clearTimeout(timeout);
    }

    if (displayText.length === 0 && !isRevealed) {
      // Pause before retyping
      const timeout = setTimeout(() => setIsRevealed(true), 150);
      return () => clearTimeout(timeout);
    }

    if (isRevealed && displayText.length < REVEALED_TEXT.length) {
      // Retyping
      const timeout = setTimeout(() => {
        setDisplayText(REVEALED_TEXT.slice(0, displayText.length + 1));
      }, RETYPE_MS);
      return () => clearTimeout(timeout);
    }
  }, [phase, displayText, isRevealed]);

  // When orbital phase is reached, ensure we show full revealed text
  useEffect(() => {
    if (phase === "orbital") {
      setDisplayText(REVEALED_TEXT);
      setIsRevealed(true);
    }
    phaseRef.current = phase;
  }, [phase]);

  const showRevealedStyle = phase === "orbital" || (phase === "activating" && isRevealed);

  return (
    <div
      className="min-h-[2.5rem] mb-3 flex items-center justify-center"
      aria-live="polite"
    >
      <p
        className={`text-xs uppercase tracking-[0.25em] font-light min-w-0 ${
          showRevealedStyle ? "text-emerald-400/90" : "text-white"
        }`}
      >
        {displayText}
        {(phase === "chaos" && displayText.length < INITIAL_TEXT.length) ||
        (phase === "activating" && !isRevealed && displayText.length > 0) ||
        (phase === "activating" && isRevealed && displayText.length < REVEALED_TEXT.length)
          ? "▌"
          : ""}
      </p>
    </div>
  );
}
