import { redirect } from "next/navigation";
import { auth } from "@/lib/auth";
import { headers } from "next/headers";
import { ArticleFeed } from "@/components/article-feed";

export default async function Home(props: PageProps<"/">) {
  const session = await auth.api.getSession({
    headers: await headers(),
  });

  if (!session) {
    redirect("/login");
  }

  const searchParams = await props.searchParams;
  const showTour = searchParams.tour === "welcome";

  return <ArticleFeed showTour={showTour} />;
}
