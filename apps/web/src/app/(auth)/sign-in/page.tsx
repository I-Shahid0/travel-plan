import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Suspense } from "react";

import { AuthForm } from "@/components/auth-form";
import { getSession } from "@/lib/session";

export const metadata: Metadata = {
  title: "Sign in",
};

export default async function SignInPage() {
  const session = await getSession();
  if (session) redirect("/search");

  return (
    <Suspense>
      <AuthForm variant="sign-in" />
    </Suspense>
  );
}
