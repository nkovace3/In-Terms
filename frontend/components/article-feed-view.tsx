"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { ArticleCard } from "@/components/article-card";
import { OverlayNav } from "@/components/overlay-nav";
import { WelcomeTour } from "@/components/welcome-tour";
import { CATEGORIES } from "@/lib/categories";
import type { Article } from "@/lib/types";

const MENU_OPTIONS = ["All", ...CATEGORIES];

export interface ArticleFeedViewProps {
  articles: Article[];
  initialCategory: string;
  personalAccent: string;
  showTour?: boolean;
}

export function ArticleFeedView({
  articles,
  initialCategory,
  personalAccent,
  showTour = false,
}: ArticleFeedViewProps) {
  const [selectedCategory, setSelectedCategory] = useState(initialCategory);
  const [tourActive, setTourActive] = useState(showTour);

  const visibleArticles =
    selectedCategory === "All"
      ? articles
      : articles.filter(
          (article) =>
            article.category.toLowerCase() === selectedCategory.toLowerCase()
        );

  return (
    <div className="fixed inset-0 snap-y snap-mandatory overflow-y-scroll bg-background [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      <OverlayNav
        categories={MENU_OPTIONS}
        selectedCategory={selectedCategory}
        onSelectCategory={setSelectedCategory}
      />

      {visibleArticles.length === 0 ? (
        <section className="flex h-dvh w-full items-center justify-center px-6 text-center">
          <p className="text-sm text-muted-foreground">
            No {selectedCategory} stories right now — check back soon.
          </p>
        </section>
      ) : (
        visibleArticles.map((article, i) => (
          <section
            key={article.id}
            className="relative flex h-dvh w-full snap-center snap-always items-center justify-center px-6"
          >
            <div className="w-full max-w-md">
              <ArticleCard article={article} personalAccent={personalAccent} />
            </div>

            {i === 0 && (
              <div className="pointer-events-none absolute bottom-10 left-1/2 flex -translate-x-1/2 animate-bounce flex-col items-center gap-1 text-muted-foreground">
                <span className="text-xs">scroll for the next article</span>
                <ChevronDown className="size-4" />
              </div>
            )}
          </section>
        ))
      )}

      {/* Rendered as a sibling here, not nested in OverlayNav or a card —
          both of those have a transform/backdrop-filter ancestor, which
          would break this tour's own position:fixed spotlight overlay the
          same way it broke the dropdown backdrops earlier. */}
      {tourActive && <WelcomeTour onFinish={() => setTourActive(false)} />}
    </div>
  );
}
