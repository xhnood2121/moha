import Link from "next/link";
import { auth } from "@/lib/auth";
import { getActivePlan } from "@/lib/subscription";
import { getLocale } from "@/lib/locale";
import { t } from "@/lib/i18n";

export default async function SettingsPage() {
  const session = await auth();
  const locale = await getLocale();
  const plan = session ? await getActivePlan(session.user.id) : "FREE";

  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-semibold">{t(locale, "nav.settings")}</h1>

      <section className="mt-6 rounded-lg border border-border bg-surface p-5">
        <h2 className="text-lg font-medium">الحساب</h2>
        <div className="mt-2 text-sm text-muted">{session?.user.email}</div>
      </section>

      <section className="mt-4 rounded-lg border border-border bg-surface p-5">
        <h2 className="text-lg font-medium">الاشتراك</h2>
        <div className="mt-2 text-sm">
          الخطة الحالية: <span className="font-semibold">{plan}</span>
        </div>
        <Link
          href="/settings/billing"
          className="mt-3 inline-block text-sm text-brand hover:underline"
        >
          إدارة الاشتراك
        </Link>
      </section>
    </div>
  );
}
