import { OnboardingPreferences } from "@/components/onboarding-preferences";
import { auth } from "@/lib/auth";
import { redirect } from "next/navigation";
import { headers } from "next/headers";

export default async function Preferences() {
  const session = await auth.api.getSession({
    headers: await headers(),
  });

  if (!session) {
    redirect("/login");
  }

  return (
    <section className="flex flex-1 items-center justify-center px-4 py-12">
      <OnboardingPreferences
        mode="edit"
        initialCategory={session.user.favoriteCategory ?? undefined}
        initialColor={session.user.personalColor ?? undefined}
      />
    </section>
  );
}
