import { auth } from "@/lib/auth";
import { prisma } from "@/lib/db";
import { getLocale } from "@/lib/locale";
import { t } from "@/lib/i18n";

export default async function DashboardPage() {
  const session = await auth();
  const locale = await getLocale();

  const merchantCount = session
    ? await prisma.merchant.count({
        where: { userId: session.user.id, uninstalledAt: null },
      })
    : 0;

  return (
    <div>
      <h1 className="text-2xl font-semibold">{t(locale, "nav.dashboard")}</h1>
      <p className="mt-1 text-sm text-muted">
        مرحبًا {session?.user.name ?? session?.user.email}
      </p>

      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Card title="متاجر مرتبطة" value={String(merchantCount)} />
        <Card title="الخطة" value={"Free"} />
        <Card title="حالة الحساب" value={"نشط"} />
      </div>

      <p className="mt-8 text-xs text-muted">
        البيانات الموثّقة تظهر فقط بعد ربط متجرك عبر OAuth الرسمي لسلة أو زد.
        التقديرات في صفحة "نظرة على السوق" مبنية على بيانات عامة فقط.
      </p>
    </div>
  );
}

function Card({ title, value }: { title: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="text-xs text-muted">{title}</div>
      <div className="mt-1 text-2xl font-semibold">{value}</div>
    </div>
  );
}
