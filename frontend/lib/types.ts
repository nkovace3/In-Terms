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
}

export interface InTerms{
    id: number;
    article_id: number;
    target_category: string;
    headline: string;
    summary: string;
    key_points: string[];
    created_at: string;
}