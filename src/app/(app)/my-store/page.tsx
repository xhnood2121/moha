import Link from "next/link";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/db";
import { getLocale } from "@/lib/locale";
import { formatSAR, formatNumber, t } from "@/lib/i18n";

export default async function MyStorePage() {
  const session = await auth();
  const locale = await getLocale();

  if (!session) return null;

  const merchants = await prisma.merchant.findMany({
    where: { userId: session.user.id, uninstalledAt: null },
    orderBy: { installedAt: "desc" },
  });

  const merchantIds = merchants.map((m) => m.id);
  const since = new Date(Date.now() - 30 * 24 * 3600 * 1000);

  const stats =
    merchantIds.length === 0
      ? null
      : await prisma.orderEvent.groupBy({
          by: ["merchantId"],
          where: {
            merchantId: { in: merchantIds },
            eventType: { in: ["order.created", "order.payment.updated"] },
            occurredAt: { gte: since },
          },
          _sum: { totalMinor: true, itemCount: true },
          _count: { _all: true },
        });

  const byMerchant = new Map<string, { totalMinor: number; orders: number; items: number }>();
  for (const s of stats ?? []) {
    byMerchant.set(s.merchantId, {
      totalMinor: s._sum.totalMinor ?? 0,
      orders: s._count._all,
      items: s._sum.itemCount ?? 0,
    });
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold">{t(locale, "nav.myStore")}</h1>
      <p className="mt-1 text-sm text-muted">
        {t(locale, "data.verifiedOnly")} — أرقام موثّقة من الطلبات الواردة عبر
        Webhook الرسمي لمتجرك خلال آخر ٣٠ يومًا.
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
        <ul className="mt-8 space-y-3">
          {merchants.map((m) => {
            const s = byMerchant.get(m.id);
            return (
              <li
                key={m.id}
                className="rounded-lg border border-border bg-surface p-5"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-medium">{m.storeName}</div>
                    <div className="text-xs text-muted">
                      {m.platform} · {m.storeDomain ?? m.externalId}
                    </div>
                  </div>
                  <span className="rounded-full bg-success/10 px-2 py-0.5 text-xs text-success">
                    موثّق
                  </span>
                </div>

                <div className="mt-4 grid grid-cols-3 gap-4">
                  <Stat
                    label="إجمالي المبيعات"
                    value={formatSAR(locale, s?.totalMinor ?? 0)}
                  />
                  <Stat
                    label="عدد الطلبات"
                    value={formatNumber(locale, s?.orders ?? 0)}
                  />
                  <Stat
                    label="عناصر مُباعة"
                    value={formatNumber(locale, s?.items ?? 0)}
                  />
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-1 text-lg font-semibold">{value}</div>
    </div>
  );
}
