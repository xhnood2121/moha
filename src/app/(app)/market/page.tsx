import { Paywall } from "@/components/Paywall";
import { prisma } from "@/lib/db";
import { getLocale } from "@/lib/locale";
import { formatNumber, formatSAR, t } from "@/lib/i18n";

export default async function MarketPage() {
  const locale = await getLocale();
  return (
    <div>
      <h1 className="text-2xl font-semibold">{t(locale, "nav.market")}</h1>
      <p className="mt-1 text-sm text-muted">
        تقديرات مبنية على بيانات الكتالوج العام فقط (احترامًا لـ robots.txt).
        لا نعرض أي رقم مبيعات هنا — أرقام المبيعات الموثّقة تظهر فقط في
        صفحة "متجري" بعد الربط الرسمي.
      </p>

      <div className="mt-8">
        <Paywall required="PRO">
          <Overview />
        </Paywall>
      </div>
    </div>
  );
}

async function Overview() {
  const locale = await getLocale();
  const [storeCount, productCount, byCategory, recentSnapshots] = await Promise.all([
    prisma.publicStore.count({
      where: { isActive: true, isClosed: false, robotsAllowsUs: true },
    }),
    prisma.publicProduct.count(),
    prisma.publicProduct.groupBy({
      by: ["category"],
      _count: { _all: true },
      orderBy: { _count: { category: "desc" } },
      take: 10,
    }),
    prisma.publicProduct.count({
      where: { lastSeenAt: { gte: new Date(Date.now() - 7 * 24 * 3600 * 1000) } },
    }),
  ]);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 rounded-md border border-border bg-surface px-3 py-2 text-xs text-muted">
        <span className="rounded-full bg-muted/20 px-2 py-0.5">
          {t(locale, "data.publicEstimate")}
        </span>
        <span>
          الأرقام أدناه مبنية على لقطات الكتالوج العامة فقط، وليست مقياسًا
          للمبيعات.
        </span>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Card label="متاجر مرصودة (مسموحة بـ robots)" value={formatNumber(locale, storeCount)} />
        <Card label="منتجات في الكتالوج" value={formatNumber(locale, productCount)} />
        <Card label="منتجات شوهدت آخر ٧ أيام" value={formatNumber(locale, recentSnapshots)} />
      </div>

      <section>
        <h2 className="text-lg font-medium">أكثر الفئات وجودًا في الكتالوج</h2>
        <p className="mt-1 text-xs text-muted">
          عدد المنتجات الفريدة لكل فئة عبر المتاجر المرصودة.
        </p>
        <ul className="mt-3 divide-y divide-border rounded-lg border border-border bg-surface">
          {byCategory.length === 0 ? (
            <li className="p-4 text-sm text-muted">{t(locale, "common.empty")}</li>
          ) : (
            byCategory.map((c) => (
              <li
                key={c.category ?? "_uncategorized"}
                className="flex items-center justify-between px-4 py-2 text-sm"
              >
                <span>{c.category ?? "غير مصنّف"}</span>
                <span className="text-muted">
                  {formatNumber(locale, c._count._all)}
                </span>
              </li>
            ))
          )}
        </ul>
      </section>

      <PriceDistribution />
    </div>
  );
}

async function PriceDistribution() {
  const locale = await getLocale();
  const products = await prisma.publicProduct.findMany({
    where: { priceMinor: { not: null } },
    select: { priceMinor: true },
    take: 5000,
  });

  if (products.length === 0) {
    return (
      <section>
        <h2 className="text-lg font-medium">توزيع الأسعار</h2>
        <p className="mt-2 text-sm text-muted">{t(locale, "common.empty")}</p>
      </section>
    );
  }

  const sorted = products
    .map((p) => p.priceMinor!)
    .filter((n): n is number => typeof n === "number")
    .sort((a, b) => a - b);

  const pct = (q: number) => sorted[Math.floor(sorted.length * q)] ?? 0;
  const median = pct(0.5);
  const p25 = pct(0.25);
  const p75 = pct(0.75);
  const p95 = pct(0.95);

  return (
    <section>
      <h2 className="text-lg font-medium">توزيع الأسعار (ريال)</h2>
      <div className="mt-3 grid grid-cols-4 gap-3">
        <Card label="P25" value={formatSAR(locale, p25)} />
        <Card label="الوسيط" value={formatSAR(locale, median)} />
        <Card label="P75" value={formatSAR(locale, p75)} />
        <Card label="P95" value={formatSAR(locale, p95)} />
      </div>
    </section>
  );
}

function Card({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-1 text-lg font-semibold">{value}</div>
    </div>
  );
}
