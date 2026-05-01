import Link from "next/link";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/db";
import { getLocale } from "@/lib/locale";
import { t } from "@/lib/i18n";

export default async function MyStorePage() {
  const session = await auth();
  const locale = await getLocale();

  const merchants = session
    ? await prisma.merchant.findMany({
        where: { userId: session.user.id, uninstalledAt: null },
        orderBy: { installedAt: "desc" },
      })
    : [];

  return (
    <div>
      <h1 className="text-2xl font-semibold">{t(locale, "nav.myStore")}</h1>
      <p className="mt-1 text-sm text-muted">
        {t(locale, "data.verifiedOnly")} — يظهر هنا فقط بعد ربط متجرك عبر
        OAuth الرسمي.
      </p>

      {merchants.length === 0 ? (
        <div className="mt-8 rounded-lg border border-border bg-surface p-6">
          <p className="text-sm">لم تربط متجرًا بعد.</p>
          <Link
            href="/integrations"
            className="mt-3 inline-block rounded-md bg-brand px-4 py-2 text-brand-fg"
          >
            اربط متجرك
          </Link>
        </div>
      ) : (
        <ul className="mt-8 space-y-2">
          {merchants.map((m) => (
            <li
              key={m.id}
              className="rounded-lg border border-border bg-surface p-4"
            >
              <div className="font-medium">{m.storeName}</div>
              <div className="text-xs text-muted">
                {m.platform} · {m.storeDomain ?? m.externalId}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
