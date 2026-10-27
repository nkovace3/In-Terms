"use client";

import { useEffect, useLayoutEffect, useState } from "react";
import { useRouter } from "next/navigation";

interface TourStep {
  selector: string;
  title: string;
  description: string;
}

const STEPS: TourStep[] = [
  {
    selector: '[data-tour="category-trigger"]',
    title: "Browse by topic",
    description:
      "Switch between categories here, or pick All to see everything in one feed.",
  },
  {
    selector: '[data-tour="translate-trigger"]',
    title: "Translate any story",
    description:
      "Don't follow a topic? Tap here to see the story explained in terms of something you actually understand.",
  },
];

const TOOLTIP_WIDTH = 256;
const TOOLTIP_MARGIN = 16;

/**
 * One-time spotlight walkthrough shown right after /welcome. Triggered by a
 * `?tour=welcome` query param on the redirect into the feed — no persisted
 * "has seen tour" flag needed, since onboardingComplete already means a
 * user can only ever land on that redirect once.
 *
 * Deliberately not a generic "point at any element" tour engine: this only
 * ever runs against the feed's predictable first-load state (nav just
 * mounted, first card on screen), so it just measures the two real target
 * elements directly via data-tour attributes rather than taking on the
 * complexity (and risk of the fixed-position containing-block issue we hit
 * earlier) of a reusable system.
 */
export function WelcomeTour({ onFinish }: { onFinish: () => void }) {
  const router = useRouter();
  const [stepIndex, setStepIndex] = useState(0);
  const [rect, setRect] = useState<DOMRect | null>(null);

  const step = STEPS[stepIndex];

  useLayoutEffect(() => {
    const target = document.querySelector(step.selector);
    // Measuring a real DOM node's layout and syncing it into state is one
    // of the two documented legitimate uses of setState inside an effect
    // (the other being the resize-listener subscription below) — there's
    // no React-only way to know a target's screen position.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setRect(target ? target.getBoundingClientRect() : null);
  }, [step]);

  // If the window resizes mid-tour, keep the spotlight aligned.
  useEffect(() => {
    function handleResize() {
      const target = document.querySelector(step.selector);
      setRect(target ? target.getBoundingClientRect() : null);
    }
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [step]);

  function finish() {
    onFinish();
    router.replace("/");
  }

  function next() {
    if (stepIndex < STEPS.length - 1) {
      setStepIndex((i) => i + 1);
    } else {
      finish();
    }
  }

  // Target not on screen (shouldn't happen on first load, but don't block
  // the app if it ever does) — just end the tour quietly.
  if (!rect) return null;

  const tooltipLeft = Math.min(
    Math.max(rect.left, TOOLTIP_MARGIN),
    window.innerWidth - TOOLTIP_WIDTH - TOOLTIP_MARGIN
  );

  return (
    <div className="fixed inset-0 z-[100]">
      {/* Spotlight: a borderless box sized to the target, with a giant
          box-shadow that dims everything else on the page. */}
      <div
        className="absolute rounded-xl transition-all duration-300"
        style={{
          top: rect.top - 6,
          left: rect.left - 6,
          width: rect.width + 12,
          height: rect.height + 12,
          boxShadow: "0 0 0 9999px rgba(0,0,0,0.65)",
        }}
      />

      <div
        className="absolute z-10 rounded-2xl border border-border bg-popover p-4 shadow-xl transition-all duration-300"
        style={{ top: rect.bottom + 12, left: tooltipLeft, width: TOOLTIP_WIDTH }}
      >
        <p className="text-sm font-semibold text-foreground">{step.title}</p>
        <p className="mt-1 text-xs text-muted-foreground">{step.description}</p>

        <div className="mt-3 flex items-center justify-between">
          <button
            type="button"
            onClick={finish}
            className="cursor-pointer text-xs text-muted-foreground hover:text-foreground"
          >
            Skip
          </button>
          <button
            type="button"
            onClick={next}
            className="cursor-pointer rounded-lg border border-border bg-background px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-muted"
          >
            {stepIndex < STEPS.length - 1 ? "Next" : "Got it"}
          </button>
        </div>
      </div>
    </div>
  );
}
