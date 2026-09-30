"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Check, type LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * The checklist shown while a long backend run is in flight.
 *
 * Both the AI Review and the Compliance Checks return everything in one call,
 * so there is no per-step progress to report. What this panel does instead is
 * pace itself off a real clock: each step is given an estimated duration, the
 * elapsed time shown against a finished step is the time it actually spent on
 * screen, and the last step stays in progress for as long as the request takes
 * rather than finishing early and leaving a "done" checklist next to a spinner.
 *
 * Generic because the two tabs differ only in their steps and their wording —
 * duplicating the markup would have meant two panels drifting apart on every
 * change to either.
 */

const TICK_MS = 250;

export interface Step {
  label: string;
  detail: string;
  /** Planned time on screen. The last step ignores this and waits for the run. */
  budget: number;
}

export function formatElapsed(ms: number) {
  const total = Math.max(0, Math.round(ms / 1000));
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`;
}

export function SteppedProgress({
  title,
  subtitle,
  steps,
  icon: Icon,
  footerIcon: FooterIcon,
  footerNote,
  badgeIcon: BadgeIcon,
  badgeLabel,
}: {
  title: string;
  subtitle: string;
  steps: Step[];
  icon: LucideIcon;
  footerIcon: LucideIcon;
  footerNote: string;
  badgeIcon: LucideIcon;
  badgeLabel: string;
}) {
  // One clock for the whole panel. Every duration on screen is read off it.
  const startedAt = useRef(Date.now());
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const timer = setInterval(
      () => setElapsed(Date.now() - startedAt.current),
      TICK_MS
    );
    return () => clearInterval(timer);
  }, []);

  // Where the clock has reached. The final step is never marked done here —
  // the panel unmounts when the run returns, so the checklist can't outrun it.
  const { current, spentBefore } = useMemo(() => {
    let index = 0;
    let consumed = 0;
    while (index < steps.length - 1 && elapsed >= consumed + steps[index].budget) {
      consumed += steps[index].budget;
      index += 1;
    }
    return { current: index, spentBefore: consumed };
  }, [elapsed, steps]);

  // Time each finished step held the screen, and how long the live one has.
  const spentOn = (index: number) => {
    if (index < current) return steps[index].budget;
    return elapsed - spentBefore;
  };

  const activeStep = steps[current];

  return (
    <div className="max-w-2xl overflow-hidden rounded-xl border border-line bg-white">
      <div className="flex items-start gap-3.5 px-5 py-5 sm:px-6">
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-sky">
          <Icon className="h-5 w-5 text-brand" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-[16px] font-semibold text-navy">{title}</h2>
          <p className="mt-0.5 text-[13px] text-subtle">{subtitle}</p>
        </div>
        <span className="flex shrink-0 items-center gap-2 rounded-full bg-sky px-3 py-1.5 text-[12.5px] font-medium text-navy">
          <Spinner />
          {current + 1} of {steps.length}
        </span>
      </div>

      <ol className="border-t border-line px-5 py-5 sm:px-6">
        {steps.map((step, index) => {
          const state =
            index < current ? "done" : index === current ? "active" : "idle";
          const last = index === steps.length - 1;
          return (
            <li key={step.label} className="relative flex gap-3.5 pb-5 last:pb-0">
              {!last && (
                <span
                  aria-hidden
                  className={cn(
                    "absolute left-[13px] top-[30px] bottom-1 w-px",
                    state === "done" ? "bg-compliant/40" : "border-l border-dashed border-line"
                  )}
                />
              )}

              <span className="relative z-10 grid h-[26px] w-[26px] shrink-0 place-items-center">
                {state === "done" ? (
                  <span className="grid h-[22px] w-[22px] place-items-center rounded-full bg-compliant">
                    <Check className="h-3 w-3 text-white" strokeWidth={3} aria-hidden />
                  </span>
                ) : state === "active" ? (
                  <Spinner size={22} />
                ) : (
                  <span className="h-[22px] w-[22px] rounded-full border border-line bg-white" />
                )}
              </span>

              <div className="min-w-0 flex-1">
                <p
                  className={cn(
                    "text-[13.5px]",
                    state === "idle"
                      ? "text-subtle"
                      : state === "active"
                        ? "font-semibold text-navy"
                        : "font-medium text-ink"
                  )}
                >
                  {step.label}
                </p>
                <p className="mt-0.5 text-[12.5px] leading-relaxed text-subtle">
                  {step.detail}
                </p>
              </div>

              <div className="shrink-0 pt-px text-right">
                <p
                  className={cn(
                    "text-[12.5px] font-medium",
                    state === "done"
                      ? "text-compliant"
                      : state === "active"
                        ? "text-brand"
                        : "text-subtle"
                  )}
                >
                  {state === "done"
                    ? "Completed"
                    : state === "active"
                      ? "In progress"
                      : "Pending"}
                </p>
                {state !== "idle" && (
                  <p className="mt-0.5 font-mono text-[11.5px] tabular-nums text-subtle">
                    {formatElapsed(spentOn(index))}
                  </p>
                )}
              </div>
            </li>
          );
        })}
      </ol>

      <div className="flex flex-wrap items-center gap-3 border-t border-line bg-sky/60 px-5 py-4 sm:px-6">
        <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-white">
          <FooterIcon className="h-4 w-4 text-brand" aria-hidden />
        </span>
        <div className="min-w-0 flex-1" role="status" aria-live="polite">
          <p className="text-[13px] font-medium text-navy">
            {activeStep.label}
            <EllipsisDots />
          </p>
          <p className="text-[12.5px] text-subtle">{footerNote}</p>
        </div>
        <span className="flex items-center gap-1.5 rounded-full border border-line bg-white px-3 py-1.5 text-[12px] font-medium text-brand">
          <BadgeIcon className="h-3.5 w-3.5" aria-hidden />
          {badgeLabel}
        </span>
      </div>
    </div>
  );
}

function Spinner({ size = 16 }: { size?: number }) {
  return (
    <span
      aria-hidden
      style={{ height: size, width: size }}
      className="inline-block animate-spin rounded-full border-2 border-brand/25 border-t-brand motion-reduce:animate-none"
    />
  );
}

/** Three dots that fill and clear, so the footer never looks frozen. */
function EllipsisDots() {
  const [count, setCount] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => setCount((n) => (n + 1) % 4), 450);
    return () => clearInterval(timer);
  }, []);
  return (
    <span className="inline-block w-4 text-left">{".".repeat(count)}</span>
  );
}
