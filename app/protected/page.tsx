import { redirect } from "next/navigation";
import { connection } from "next/server";
import { type ReactNode, Suspense } from "react";

async function ProtectedContent(): Promise<ReactNode> {
  await connection();
  redirect("/dashboard");
  return null; // unreachable; redirect throws
}

export default function ProtectedPage() {
  return (
    <Suspense fallback={null}>
      <ProtectedContent />
    </Suspense>
  );
}
