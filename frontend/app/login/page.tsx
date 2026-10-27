import { Sparkles } from "lucide-react";
import { SignInButton } from "@/components/sign-in-button";
import { auth } from "@/lib/auth";
import { redirect } from "next/navigation";
import { headers } from "next/headers";

export default async function LogIn() {
  const session = await auth.api.getSession({
    headers: await headers(),
  });

  if (session) {
    redirect("/");
  }

  return (
    <div className="flex flex-1 items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm rounded-3xl border border-border bg-card p-8">
        <div className="flex flex-col items-center gap-6 text-center">
          <div className="flex size-12 items-center justify-center rounded-2xl bg-primary text-primary-foreground">
            <Sparkles className="size-6" />
          </div>

          <div className="flex flex-col gap-2">
            <h1 className="text-3xl font-bold tracking-tight text-foreground">
              Welcome to In Terms
            </h1>
            <p className="text-sm text-muted-foreground">
              Short-form news, translated into terms you actually understand.
            </p>
          </div>

          <SignInButton className="w-full" />
        </div>
      </div>
    </div>
  );
}
