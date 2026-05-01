import Link from "next/link";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/db";
import { getLocale } from "@/lib/locale";
import { t } from "@/lib/i18n";
import { Plus } from "lucide-react";

export default async function BugReportsPage() {
  const session = await auth();
  const locale = await getLocale();
  if (!session) return null;

  const reports = await prisma.bugReport.findMany({
    where: { userId: session.user.id },
    orderBy: { updatedAt: "desc" },
  });

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">{t(locale, "nav.bugReports")}</h1>
          <p className="mt-1 text-sm text-muted">
            مسوّدات تقارير ثغرات للإرسال عبر القنوات الرسمية للمنصات
            (security@salla.sa أو bugbounty.zid.sa). هذه الأداة لا تختبر
            ولا ترسل تلقائيًا.
          </p>
        </div>
        <Link
          href="/bug-reports/new"
          className="inline-flex items-center gap-1 rounded-md bg-brand px-3 py-2 text-sm text-brand-fg"
        >
          <Plus size={14} />
          مسوّدة جديدة
        </Link>
      </div>

      {reports.length === 0 ? (
        <div className="mt-8 rounded-lg border border-border bg-surface p-6 text-sm text-muted">
          لا توجد مسوّدات بعد.
        </div>
      ) : (
        <ul className="mt-8 space-y-2">
          {reports.map((r) => (
            <li
              key={r.id}
              className="rounded-lg border border-border bg-surface p-4"
            >
              <Link href={`/bug-reports/${r.id}`} className="block">
                <div className="font-medium">{r.title}</div>
                <div className="text-xs text-muted">
                  {r.vendor} · {r.severity} · {r.status}
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
