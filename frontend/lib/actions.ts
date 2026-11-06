"use server";

import { ApiError, getInTerms } from "@/lib/api";
import type { InTerms } from "@/lib/types";

export type TranslateResult =
  | { ok: true; inTerms: InTerms }
  | { ok: false; reason: "daily-limit" | "error" };

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
 *
 * Returns a result instead of throwing because Next.js strips thrown error
 * details from Server Actions in production, and the card needs to tell
 * the backend's daily generation cap (429) apart from a real failure.
 */
export async function translateArticle(
  articleId: number,
  targetCategory: string
): Promise<TranslateResult> {
  try {
    return { ok: true, inTerms: await getInTerms(articleId, targetCategory) };
  } catch (error) {
    if (error instanceof ApiError && error.status === 429) {
      return { ok: false, reason: "daily-limit" };
    }
    console.error("translateArticle failed", error);
    return { ok: false, reason: "error" };
  }
}
