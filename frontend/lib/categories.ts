// Single source of truth for the app's category taxonomy — keep in sync
// with the backend's CATEGORIES dict (backend/api/routes/articles.py).
export const CATEGORIES = [
  "NBA",
  "NFL",
  "MLB",
  "Reality TV",
  "US Politics",
  "Business",
] as const;
