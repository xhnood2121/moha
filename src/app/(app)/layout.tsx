import { redirect } from "next/navigation";
import { auth } from "@/lib/auth";
import { Sidebar } from "@/components/Sidebar";
import { getLocale } from "@/lib/locale";

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await auth();
  if (!session) redirect("/login");

  const locale = await getLocale();

  return (
    <div className="flex min-h-screen">
      <Sidebar locale={locale} />
      <main className="flex-1 p-6">{children}</main>
    </div>
  );
}
