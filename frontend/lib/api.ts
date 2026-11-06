import type { Article, InTerms } from "./types";

const API_BASE_URL = process.env.API_BASE_URL;

export class ApiError extends Error {
    constructor(message: string, readonly status: number) {
        super(message);
    }
}

async function fetchFromApi<T>(path: string): Promise<T> {
    if (!API_BASE_URL){
        throw new Error("API_BASE_URL is not confirmed");
    }

    const response = await fetch(`${API_BASE_URL}${path}`, {
        cache: "no-store"
    });

    if(!response.ok){
        throw new ApiError(
            `API request failed: ${response.status} ${response.statusText}`,
            response.status
        );
    }

    return response.json() as Promise<T>;
}

export function getArticles(): Promise<Article[]>{
    return fetchFromApi<Article[]>("/articles");
}

export function getArticle(id: number): Promise<Article>{
    return fetchFromApi<Article>(`/articles/${id}`);
}

export function getInTerms(
    articleId: number,
    targetCategory: string
): Promise<InTerms>{
    return fetchFromApi<InTerms>(
        `/articles/${articleId}/in-terms/${encodeURIComponent(targetCategory)}`
    );
}