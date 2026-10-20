"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { ArticleCard } from "@/components/article-card";
import { OverlayNav } from "@/components/overlay-nav";
import type { Article } from "@/lib/types";

const CATEGORIES = ["NBA", "NFL", "MLB", "Reality TV", "US Politics", "Business"];
const MENU_OPTIONS = ["All", ...CATEGORIES];

function pickTranslationTarget(category: string, index: number): string {
  for (let offset = 0; offset < CATEGORIES.length; offset++) {
    const candidate = CATEGORIES[(index + offset) % CATEGORIES.length];
    if (candidate.toLowerCase() !== category.toLowerCase()) return candidate;
  }
  return CATEGORIES[0];
}

export interface ArticleFeedViewProps {
  articles: Article[];
  initialCategory: string;
  personalAccent: string;
}

export function ArticleFeedView({
  articles,
  initialCategory,
  personalAccent,
}: ArticleFeedViewProps) {
  const [selectedCategory, setSelectedCategory] = useState(initialCategory);

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
              <ArticleCard
                article={article}
                translationTarget={pickTranslationTarget(article.category, i)}
                personalAccent={personalAccent}
              />
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
    </div>
  );
}
