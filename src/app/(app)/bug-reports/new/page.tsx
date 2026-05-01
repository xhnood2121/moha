"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const SEVERITIES = ["LOW", "MEDIUM", "HIGH", "CRITICAL"] as const;
const VENDORS = ["salla", "zid", "other"] as const;

export default function NewBugReportPage() {
  const router = useRouter();
  const [form, setForm] = useState({
    title: "",
    vendor: "salla" as (typeof VENDORS)[number],
    severity: "MEDIUM" as (typeof SEVERITIES)[number],
    summary: "",
    reproSteps: "",
    impact: "",
    remediation: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const res = await fetch("/api/bug-reports", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(form),
    });
    if (!res.ok) {
      setError("تعذّر حفظ المسوّدة");
      setLoading(false);
      return;
    }
    const body = (await res.json()) as { report: { id: string } };
    router.push(`/bug-reports/${body.report.id}`);
  }

  function field<K extends keyof typeof form>(k: K, v: (typeof form)[K]) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-semibold">مسوّدة تقرير جديد</h1>
      <p className="mt-1 text-xs text-muted">
        مهم: هذه الأداة لتدوين الملاحظات فقط. الإرسال الرسمي يتم من قبلك إلى
        قناة المنصة المعنية. لا تستخدم هذه المسوّدة لاختبارات غير مصرّح بها.
      </p>

      <form onSubmit={onSubmit} className="mt-6 space-y-4">
        <Field label="العنوان">
          <input
            required
            type="text"
            value={form.title}
            onChange={(e) => field("title", e.target.value)}
            className="w-full rounded-md border border-border bg-surface px-3 py-2"
          />
        </Field>

        <div className="grid grid-cols-2 gap-4">
          <Field label="المنصة">
            <select
              value={form.vendor}
              onChange={(e) => field("vendor", e.target.value as typeof form.vendor)}
              className="w-full rounded-md border border-border bg-surface px-3 py-2"
            >
              {VENDORS.map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </select>
          </Field>
          <Field label="الخطورة">
            <select
              value={form.severity}
              onChange={(e) => field("severity", e.target.value as typeof form.severity)}
              className="w-full rounded-md border border-border bg-surface px-3 py-2"
            >
              {SEVERITIES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </Field>
        </div>

        <Field label="الملخّص">
          <textarea
            required
            rows={3}
            value={form.summary}
            onChange={(e) => field("summary", e.target.value)}
            className="w-full rounded-md border border-border bg-surface px-3 py-2"
          />
        </Field>

        <Field label="خطوات إعادة الإنتاج">
          <textarea
            required
            rows={6}
            value={form.reproSteps}
            onChange={(e) => field("reproSteps", e.target.value)}
            className="w-full rounded-md border border-border bg-surface px-3 py-2 font-mono text-sm"
          />
        </Field>

        <Field label="التأثير">
          <textarea
            required
            rows={3}
            value={form.impact}
            onChange={(e) => field("impact", e.target.value)}
            className="w-full rounded-md border border-border bg-surface px-3 py-2"
          />
        </Field>

        <Field label="التوصية">
          <textarea
            required
            rows={3}
            value={form.remediation}
            onChange={(e) => field("remediation", e.target.value)}
            className="w-full rounded-md border border-border bg-surface px-3 py-2"
          />
        </Field>

        {error && <p className="text-sm text-danger">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="rounded-md bg-brand px-4 py-2 text-brand-fg disabled:opacity-50"
        >
          {loading ? "…" : "حفظ المسوّدة"}
        </button>
      </form>
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="block text-sm">{label}</span>
      <div className="mt-1">{children}</div>
    </label>
  );
}
