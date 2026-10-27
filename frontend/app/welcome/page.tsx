import { OnboardingPreferences } from "@/components/onboarding-preferences";
import { auth } from "@/lib/auth";
import { redirect } from "next/navigation";
import { headers } from "next/headers";

export default async function Welcome() {
  const session = await auth.api.getSession({
      headers: await headers(),
    });

    // No session: can't onboard without being signed in.
    if (!session) {
      redirect("/login");
    }

    // Already onboarded: this page is a one-time flow, not a settings page.
    if (session.user.onboardingComplete) {
      redirect("/");
    }
  
  return (
    <section className="flex flex-1 items-center justify-center px-4 py-12">
      <OnboardingPreferences />
    </section>
  );
}
