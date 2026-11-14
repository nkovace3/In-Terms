export interface Article{
    id: number;
    title: string;
    url: string;
    published_at: string;
    source: string;
    headline: string;
    summary: string;
    key_points: string[];
    created_at: string;
    category: string;
    /** null = not classified yet; treated as sensitive (no translating). */
    sensitive: boolean | null;
}

export interface InTerms{
    id: number;
    article_id: number;
    target_category: string;
    headline: string;
    summary: string;
    key_points: string[];
    created_at: string;
    /** Headline of the real story this card compares against; null if none fit. */
    reference_headline: string | null;
}