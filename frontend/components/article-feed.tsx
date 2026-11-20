import { headers } from "next/headers";
import { ArticleFeedView } from "@/components/article-feed-view";
import { auth } from "@/lib/auth";
import { getArticles } from "@/lib/api";
import { DEFAULT_PERSONAL_COLOR } from "@/lib/colors";

// Hydrating every article as a fully-interactive flip-card gets expensive
// fast — the backend's getArticles() has no limit, so cap what actually
// renders until real pagination/infinite-scroll exists.
const INITIAL_BATCH_SIZE = 100;

export interface ArticleFeedProps {
  /** True for the one-time redirect from /welcome right after onboarding. */
  showTour?: boolean;
}

export async function ArticleFeed({ showTour = false }: ArticleFeedProps) {
  const [articles, session] = await Promise.all([
    getArticles(),
    auth.api.getSession({ headers: await headers() }),
  ]);

  // additionalFields' defaultValue only applies when better-auth creates a
  // *new* user — existing rows can genuinely be null, so fall back here too.
  const favoriteCategory = session?.user.favoriteCategory || "All";
  const personalColor = session?.user.personalColor || DEFAULT_PERSONAL_COLOR;

  return (
    <ArticleFeedView
      articles={articles.slice(0, INITIAL_BATCH_SIZE)}
      initialCategory={favoriteCategory}
      personalAccent={personalColor}
      showTour={showTour}
    />
  );
}
