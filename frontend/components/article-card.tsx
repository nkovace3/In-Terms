"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowLeftRight, ChevronDown, Loader2, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { translateArticle } from "@/lib/actions";
import { CATEGORIES } from "@/lib/categories";
import type { Article, InTerms } from "@/lib/types";

export interface ArticleCardProps {
  article: Article;
  /**
   * Placeholder for the user's chosen "personal color" (from the future
   * sign-up color picker). Passed as a raw OKLCH string so it can be
   * dropped straight into an inline CSS variable.
   */
  personalAccent: string;
}

export function ArticleCard({ article, personalAccent }: ArticleCardProps) {
  const [flipped, setFlipped] = useState(false);
  const [inTerms, setInTerms] = useState<InTerms | null>(null);
  const [isTranslating, setIsTranslating] = useState(false);
  const [error, setError] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Can translate into anything except the article's own category.
  const targets = CATEGORIES.filter(
    (category) => category.toLowerCase() !== article.category.toLowerCase()
  );

  // Click-outside-to-close via a document listener, not a fullscreen
  // backdrop div: this card's flip wrapper has transform-style:preserve-3d,
  // which makes it the containing block for position:fixed descendants —
  // so a `fixed inset-0` backdrop here only ever covered the card's own
  // box, not the real viewport, and clicks outside the card fell through.
  useEffect(() => {
    if (!menuOpen) return;

    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [menuOpen]);

  async function handleTranslate(target: string) {
    setMenuOpen(false);
    setIsTranslating(true);
    setError(false);

    try {
      // The backend caches each (article, target) translation in the
      // database, so re-picking a target already generated this session
      // is already cheap server-side — no need to duplicate that caching
      // on the client.
      const result = await translateArticle(article.id, target);
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
          "relative h-[500px] w-full transition-transform duration-700 ease-[cubic-bezier(0.22,1,0.36,1)] [transform-style:preserve-3d]",
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
            <h3 className="text-xl font-bold tracking-tight text-foreground">
              {article.headline}
            </h3>
            <p className="text-sm text-muted-foreground">{article.summary}</p>
          </div>

          <ul className="flex flex-1 flex-col gap-1.5 overflow-y-auto">
            {article.key_points.slice(0, 3).map((point) => (
              <li
                key={point}
                className="flex items-start gap-2 text-sm text-foreground"
              >
                <span className="mt-1.5 size-1 shrink-0 rounded-full bg-muted-foreground" />
                <span>{point}</span>
              </li>
            ))}
          </ul>

          <div ref={menuRef} className="relative">
            {menuOpen && (
              <div className="absolute inset-x-0 bottom-full z-50 mb-2 max-h-48 overflow-y-auto rounded-xl border border-border bg-popover py-1 shadow-lg">
                {targets.map((target) => (
                  <button
                    key={target}
                    type="button"
                    onClick={() => handleTranslate(target)}
                    className="block w-full cursor-pointer px-4 py-2 text-left text-sm text-foreground transition-colors hover:bg-muted"
                  >
                    {target}
                  </button>
                ))}
              </div>
            )}

            <button
              type="button"
              data-tour="translate-trigger"
              onClick={() => setMenuOpen((value) => !value)}
              disabled={isTranslating}
              className="relative flex w-full cursor-pointer items-center justify-center gap-2 overflow-hidden rounded-xl border border-border bg-background py-2.5 text-sm font-medium text-foreground transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-70"
            >
              <span className="pointer-events-none absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/40 to-transparent transition-transform duration-1000 ease-out group-hover:translate-x-full dark:via-white/10" />
              {isTranslating ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Sparkles className="size-4" />
              )}
              {isTranslating ? "Translating…" : "Translate"}
              {!isTranslating && (
                <ChevronDown
                  className={cn(
                    "size-3.5 transition-transform",
                    menuOpen && "rotate-180"
                  )}
                />
              )}
            </button>
          </div>

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
                <h3 className="text-xl font-bold tracking-tight text-foreground">
                  {inTerms.headline}
                </h3>
                <p className="text-sm text-muted-foreground">{inTerms.summary}</p>
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
                    <span>{point}</span>
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
