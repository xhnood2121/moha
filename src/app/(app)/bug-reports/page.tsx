import { auth } from "@/lib/auth";
import { prisma } from "@/lib/db";
import { getLocale } from "@/lib/locale";
import { t } from "@/lib/i18n";

export default async function BugReportsPage() {
  const session = await auth();
  const locale = await getLocale();

  const reports = session
    ? await prisma.bugReport.findMany({
        where: { userId: session.user.id },
        orderBy: { updatedAt: "desc" },
      })
    : [];

  return (
    <div>
      <h1 className="text-2xl font-semibold">{t(locale, "nav.bugReports")}</h1>
      <p className="mt-1 text-sm text-muted">
        أدوات لتحرير وإرسال تقارير ثغرات بشكل مسؤول إلى منصات الطرف الثالث
        (Salla / Zid) عبر قنواتها الرسمية. لا تُستخدم هذه الأداة لاختبار غير
        مصرّح به.
      </p>

      {reports.length === 0 ? (
        <div className="mt-8 rounded-lg border border-border bg-surface p-6 text-sm text-muted">
          لا توجد تقارير بعد. ستتم إضافة محرّر التقارير في المرحلة لاحقة.
        </div>
      ) : (
        <ul className="mt-8 space-y-2">
          {reports.map((r) => (
            <li
              key={r.id}
              className="rounded-lg border border-border bg-surface p-4"
            >
              <div className="font-medium">{r.title}</div>
              <div className="text-xs text-muted">
                {r.vendor} · {r.severity} · {r.status}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
