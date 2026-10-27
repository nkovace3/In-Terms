"use server";

import { getInTerms } from "@/lib/api";
import type { InTerms } from "@/lib/types";

/**
 * Client-callable entry point for fetching an "in terms of" translation.
 *
 * `getInTerms` (lib/api.ts) reads `process.env.API_BASE_URL`, a server-only
 * env var — a Client Component can't call it directly. This Server Action
 * is the bridge: the client triggers it on demand (only when the reader
 * actually clicks "Translate"), it runs on the server where the env var is
 * available, and it's also the only place this specific LLM-backed,
 * potentially-slow call happens — never prefetched for cards no one asked
 * to translate.
 */
export async function translateArticle(
  articleId: number,
  targetCategory: string
): Promise<InTerms> {
  return getInTerms(articleId, targetCategory);
}
