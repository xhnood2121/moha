import Link from "next/link";
import { getLocale } from "@/lib/locale";
import { t } from "@/lib/i18n";

export default async function HomePage() {
  const locale = await getLocale();
  return (
    <main className="mx-auto max-w-3xl px-6 py-20">
      <h1 className="text-4xl font-bold">{t(locale, "app.name")}</h1>
      <p className="mt-2 text-muted">{t(locale, "app.tagline")}</p>

      <div className="mt-10 flex gap-3">
        <Link
          href="/login"
          className="rounded-md bg-brand px-4 py-2 text-brand-fg hover:opacity-90"
        >
          {t(locale, "auth.login")}
        </Link>
        <Link
          href="/register"
          className="rounded-md border border-border px-4 py-2 hover:bg-surface"
        >
          {t(locale, "auth.register")}
        </Link>
      </div>
    </main>
  );
}
