"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronDown, CircleUserRound } from "lucide-react";
import { cn } from "@/lib/utils";

export interface OverlayNavProps {
  categories: string[];
  selectedCategory: string;
  onSelectCategory: (category: string) => void;
}

/**
 * Minimal floating nav for full-bleed, immersive pages (the feed).
 * Deliberately not the site's main SiteNav — this floats over content
 * instead of occupying layout space, and stays neutral (no gold/personal
 * accent) so it never competes with the content underneath it.
 *
 * The profile icon is a placeholder — not wired to real auth/menu yet.
 */
export function OverlayNav({
  categories,
  selectedCategory,
  onSelectCategory,
}: OverlayNavProps) {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Click-outside-to-close via a document listener, not a fullscreen
  // backdrop div: this header has backdrop-blur (a backdrop-filter), which
  // makes it the containing block for position:fixed descendants — so a
  // `fixed inset-0` backdrop here only ever covered the header's own
  // ~64px strip, not the real viewport, and clicks below it fell through.
  useEffect(() => {
    if (!open) return;

    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  return (
    <header className="pointer-events-none fixed inset-x-0 top-0 z-30 flex items-center justify-between bg-gradient-to-b from-background/80 to-transparent px-6 py-4 backdrop-blur-md">
      <span className="text-sm font-bold tracking-tight text-foreground">
        In Terms
      </span>

      <div ref={menuRef} className="pointer-events-auto relative">
        <button
          type="button"
          data-tour="category-trigger"
          onClick={() => setOpen((value) => !value)}
          className="flex cursor-pointer items-center gap-1 rounded-full border border-border bg-background/80 px-3 py-1.5 text-xs font-medium text-foreground backdrop-blur-sm transition-colors hover:bg-muted"
        >
          {selectedCategory}
          <ChevronDown
            className={cn("size-3.5 transition-transform", open && "rotate-180")}
          />
        </button>

        {open && (
          <div className="absolute top-full right-0 z-50 mt-2 w-40 overflow-hidden rounded-xl border border-border bg-popover py-1 shadow-lg">
            {categories.map((category) => (
              <button
                key={category}
                type="button"
                onClick={() => {
                  onSelectCategory(category);
                  setOpen(false);
                }}
                className={cn(
                  "block w-full cursor-pointer px-3 py-2 text-left text-sm transition-colors hover:bg-muted",
                  category === selectedCategory
                    ? "font-semibold text-foreground"
                    : "text-muted-foreground"
                )}
              >
                {category}
              </button>
            ))}
          </div>
        )}
      </div>

      <button
        type="button"
        className="pointer-events-auto flex size-8 cursor-pointer items-center justify-center rounded-full text-foreground/80 transition-colors hover:text-foreground"
      >
        <CircleUserRound className="size-6" />
      </button>
    </header>
  );
}
