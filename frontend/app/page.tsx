import { ArticleFeed } from "@/components/article-feed";

// Public on purpose: visitors (e.g. someone clicking through from a
// portfolio link) should land on cards they can flip, not a sign-in wall.
// Signing in only adds personalization — a favorite category and color.
// Generation spend is bounded by the backend's daily cap, not by auth.
export default async function Home(props: PageProps<"/">) {
  const searchParams = await props.searchParams;
  const showTour = searchParams.tour === "welcome";

  return <ArticleFeed showTour={showTour} />;
}
