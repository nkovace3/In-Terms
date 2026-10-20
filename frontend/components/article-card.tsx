"use client";

import { useState } from "react";
import { ArrowLeftRight, Loader2, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { translateArticle } from "@/lib/actions";
import type { Article, InTerms } from "@/lib/types";

export interface ArticleCardProps {
  article: Article;
  /** Which category to translate into — no picker UI exists yet, so this is chosen by the caller. */
  translationTarget: string;
  /**
   * Placeholder for the user's chosen "personal color" (from the future
   * sign-up color picker). Passed as a raw OKLCH string so it can be
   * dropped straight into an inline CSS variable.
   */
  personalAccent: string;
}

export function ArticleCard({
  article,
  translationTarget,
  personalAccent,
}: ArticleCardProps) {
  const [flipped, setFlipped] = useState(false);
  const [inTerms, setInTerms] = useState<InTerms | null>(null);
  const [isTranslating, setIsTranslating] = useState(false);
  const [error, setError] = useState(false);

  async function handleTranslate() {
    if (inTerms) {
      setFlipped(true);
      return;
    }

    setIsTranslating(true);
    setError(false);

    try {
      const result = await translateArticle(article.id, translationTarget);
      setInTerms(result);
      setFlipped(true);
    } catch {
      setError(true);
    } finally {
      setIsTranslating(false);
    }
  }

  return (
    <div
      className="group [perspective:1800px]"
      style={{ "--personal-accent": personalAccent } as React.CSSProperties}
    >
      <div
        className={cn(
          "relative h-[460px] w-full transition-transform duration-700 ease-[cubic-bezier(0.22,1,0.36,1)] [transform-style:preserve-3d]",
          flipped && "[transform:rotateY(180deg)]"
        )}
      >
        {/* Front — neutral, original short-form article */}
        <div className="absolute inset-0 flex h-full flex-col gap-4 rounded-3xl border border-border bg-card p-6 [backface-visibility:hidden]">
          <div className="flex items-center justify-between">
            <span className="rounded-full bg-secondary px-3 py-1 text-xs font-medium text-secondary-foreground">
              {article.category}
            </span>
            <span className="text-xs text-muted-foreground">{article.source}</span>
          </div>

          <div className="flex flex-col gap-2">
            <h3 className="line-clamp-2 text-xl font-bold tracking-tight text-foreground">
              {article.headline}
            </h3>
            <p className="line-clamp-2 text-sm text-muted-foreground">
              {article.summary}
            </p>
          </div>

          <ul className="flex flex-1 flex-col gap-1.5 overflow-y-auto">
            {article.key_points.slice(0, 3).map((point) => (
              <li
                key={point}
                className="flex items-start gap-2 text-sm text-foreground"
              >
                <span className="mt-1.5 size-1 shrink-0 rounded-full bg-muted-foreground" />
                <span className="line-clamp-2">{point}</span>
              </li>
            ))}
          </ul>

          <button
            type="button"
            onClick={handleTranslate}
            disabled={isTranslating}
            className="relative flex cursor-pointer items-center justify-center gap-2 overflow-hidden rounded-xl border border-border bg-background py-2.5 text-sm font-medium text-foreground transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-70"
          >
            <span className="pointer-events-none absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/40 to-transparent transition-transform duration-1000 ease-out group-hover:translate-x-full dark:via-white/10" />
            {isTranslating ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Sparkles className="size-4" />
            )}
            {isTranslating
              ? `Translating to ${translationTarget}…`
              : `Translate to ${translationTarget}`}
          </button>

          {error && (
            <p className="text-center text-xs text-destructive">
              Couldn&apos;t translate that one — try again.
            </p>
          )}
        </div>

        {/* Back — translated, rendered in the reader's personal color */}
        <div
          className="absolute inset-0 flex h-full flex-col gap-4 rounded-3xl border p-6 [backface-visibility:hidden] [transform:rotateY(180deg)]"
          style={{
            borderColor: "var(--personal-accent)",
            backgroundColor: "color-mix(in oklch, var(--personal-accent) 6%, var(--card))",
          }}
        >
          {inTerms && (
            <>
              <div className="flex items-center justify-between">
                <span
                  className="rounded-full px-3 py-1 text-xs font-medium text-white"
                  style={{ backgroundColor: "var(--personal-accent)" }}
                >
                  In terms of {inTerms.target_category}
                </span>
                <span className="text-xs text-muted-foreground">
                  {article.source}
                </span>
              </div>

              <div className="flex flex-col gap-2">
                <h3 className="line-clamp-2 text-xl font-bold tracking-tight text-foreground">
                  {inTerms.headline}
                </h3>
                <p className="line-clamp-2 text-sm text-muted-foreground">
                  {inTerms.summary}
                </p>
              </div>

              <ul className="flex flex-1 flex-col gap-1.5 overflow-y-auto">
                {inTerms.key_points.slice(0, 3).map((point) => (
                  <li
                    key={point}
                    className="flex items-start gap-2 text-sm text-foreground"
                  >
                    <span
                      className="mt-1.5 size-1 shrink-0 rounded-full"
                      style={{ backgroundColor: "var(--personal-accent)" }}
                    />
                    <span className="line-clamp-2">{point}</span>
                  </li>
                ))}
              </ul>
            </>
          )}

          <button
            type="button"
            onClick={() => setFlipped(false)}
            className="flex cursor-pointer items-center justify-center gap-2 rounded-xl border border-border bg-background py-2.5 text-sm font-medium text-foreground transition-colors hover:bg-muted"
          >
            <ArrowLeftRight className="size-4" />
            Back to original
          </button>
        </div>
      </div>
    </div>
  );
}
