import { notFound } from "next/navigation";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/db";
import { VENDOR_CHANNEL, reportToMarkdown, type Vendor } from "@/lib/bug-vendors";
import { CopyButton } from "@/components/CopyButton";

export default async function BugReportPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const session = await auth();
  if (!session) return null;
  const { id } = await params;

  const report = await prisma.bugReport.findFirst({
    where: { id, userId: session.user.id },
  });
  if (!report) notFound();

  const vendor = (report.vendor as Vendor) ?? "other";
  const channel = VENDOR_CHANNEL[vendor];
  const md = reportToMarkdown(report);

  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-semibold">{report.title}</h1>
      <div className="mt-1 text-xs text-muted">
        {report.vendor} · {report.severity} · {report.status}
      </div>

      <section className="mt-6 space-y-4">
        <Block title="ملخّص" body={report.summary} />
        <Block title="خطوات إعادة الإنتاج" body={report.reproSteps} mono />
        <Block title="التأثير" body={report.impact} />
        <Block title="التوصية" body={report.remediation} />
      </section>

      <section className="mt-8 rounded-lg border border-border bg-surface p-5">
        <h2 className="text-lg font-medium">الإرسال الرسمي</h2>
        <p className="mt-1 text-sm text-muted">
          انسخ المسوّدة وأرسلها إلى قناة الإفصاح الرسمية. لا نقوم بالإرسال
          نيابةً عنك.
        </p>
        <div className="mt-4 flex items-center gap-3">
          <a
            href={channel.href}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-md bg-brand px-3 py-2 text-sm text-brand-fg"
          >
            {channel.label}
          </a>
          <CopyButton text={md} />
        </div>
      </section>
    </div>
  );
}

function Block({
  title,
  body,
  mono,
}: {
  title: string;
  body: string;
  mono?: boolean;
}) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="text-sm font-medium">{title}</div>
      <pre
        className={[
          "mt-2 whitespace-pre-wrap text-sm",
          mono ? "font-mono" : "",
        ].join(" ")}
      >
        {body}
      </pre>
    </div>
  );
}
