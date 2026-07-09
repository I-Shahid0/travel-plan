import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Suspense } from "react";

import { AuthForm } from "@/components/auth-form";
import { getSession } from "@/lib/session";

export const metadata: Metadata = {
  title: "Join the expedition",
};

export default async function SignUpPage() {
  const session = await getSession();
  if (session) redirect("/search");

  return (
    <Suspense>
      <AuthForm variant="sign-up" />
    </Suspense>
  );
}
