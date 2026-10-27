import { ArticleFeed } from "@/components/article-feed";

export default async function CardPreview(props: PageProps<"/preview/card">) {
  const searchParams = await props.searchParams;
  return <ArticleFeed showTour={searchParams.tour === "welcome"} />;
}
