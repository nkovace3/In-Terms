import { AmbientGlow } from "@/components/ambient-glow";
import { OnboardingPreferences } from "@/components/onboarding-preferences";

export default function Welcome() {
  return (
    <section className="relative flex flex-1 items-center justify-center overflow-hidden px-4 py-12">
      <AmbientGlow />
      <OnboardingPreferences />
    </section>
  );
}
