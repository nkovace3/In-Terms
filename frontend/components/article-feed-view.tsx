"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";
import { ArticleCard } from "@/components/article-card";
import { OverlayNav } from "@/components/overlay-nav";
import { WelcomeTour } from "@/components/welcome-tour";
import { CATEGORIES } from "@/lib/categories";
import type { Article } from "@/lib/types";

const MENU_OPTIONS = ["All", ...CATEGORIES];

/**
 * Round-robin across categories so "All" doesn't read as a block of NBA,
 * then a block of MLB, etc. Sorting by date alone produces those blocks
 * because feeds publish in bursts (ESPN stamps a whole batch with the same
 * time). Each category keeps its own newest-first order, and the category
 * with the freshest story leads each round.
 */
function interleaveByCategory(articles: Article[]): Article[] {
  // Map preserves insertion order, and the input is newest-first, so
  // categories end up ordered by their freshest article.
  const queues = new Map<string, Article[]>();
  for (const article of articles) {
    const queue = queues.get(article.category);
    if (queue) {
      queue.push(article);
    } else {
      queues.set(article.category, [article]);
    }
  }

  const result: Article[] = [];
  for (let round = 0; result.length < articles.length; round++) {
    for (const queue of queues.values()) {
      if (round < queue.length) result.push(queue[round]);
    }
  }
  return result;
}

// Per-tab (sessionStorage) so a fresh visit still opens on the user's
// default category instead of wherever they were days ago.
const FEED_POSITION_KEY = "feed-position";

interface FeedPosition {
  category: string;
  articleId: number;
}

function readFeedPosition(): FeedPosition | null {
  try {
    const raw = sessionStorage.getItem(FEED_POSITION_KEY);
    return raw ? (JSON.parse(raw) as FeedPosition) : null;
  } catch {
    return null;
  }
}

function saveFeedPosition(position: FeedPosition) {
  try {
    sessionStorage.setItem(FEED_POSITION_KEY, JSON.stringify(position));
  } catch {
    // Storage can be unavailable (private mode, quota) — losing the
    // position is fine.
  }
}

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
  const scrollRef = useRef<HTMLDivElement>(null);
  // Position to jump to once the restored category has rendered.
  const pendingRestore = useRef<FeedPosition | null>(null);

  const visibleArticles = useMemo(
    () =>
      selectedCategory === "All"
        ? interleaveByCategory(articles)
        : articles.filter(
            (article) =>
              article.category.toLowerCase() === selectedCategory.toLowerCase()
          ),
    [articles, selectedCategory]
  );

  // Restore position after leaving the feed (e.g. Preferences) and coming
  // back. Read in an effect, not a useState initializer, since sessionStorage
  // doesn't exist during the server render and would cause a hydration
  // mismatch. Skipped during the welcome tour, which should start at the top.
  useEffect(() => {
    if (showTour) return;
    const saved = readFeedPosition();
    if (!saved) return;
    pendingRestore.current = saved;
    // One-time sync from browser-only storage on mount — the case this
    // rule's docs carve out, and it can't move into render without breaking
    // hydration.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setSelectedCategory(saved.category);
  }, [showTour]);

  useEffect(() => {
    const pending = pendingRestore.current;
    const container = scrollRef.current;
    // Wait until the restored category's list is what's actually rendered.
    if (!pending || !container || pending.category !== selectedCategory) {
      return;
    }
    pendingRestore.current = null;

    const index = visibleArticles.findIndex(
      (article) => article.id === pending.articleId
    );
    if (index > 0) {
      container.scrollTop = index * container.clientHeight;
    }
  }, [visibleArticles, selectedCategory]);

  const handleScroll = () => {
    const container = scrollRef.current;
    if (!container) return;
    const index = Math.round(container.scrollTop / container.clientHeight);
    const article = visibleArticles[index];
    if (article) {
      saveFeedPosition({ category: selectedCategory, articleId: article.id });
    }
  };

  return (
    <div
      ref={scrollRef}
      onScroll={handleScroll}
      className="fixed inset-0 snap-y snap-mandatory overflow-y-scroll bg-background [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
    >
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
