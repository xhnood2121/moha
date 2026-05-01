import { getLocale } from "@/lib/locale";
import { t } from "@/lib/i18n";

export default async function BillingPage() {
  const locale = await getLocale();
  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-semibold">{t(locale, "paywall.cta")}</h1>
      <p className="mt-2 text-sm text-muted">
        ربط مزوّد الدفع وإدارة الفواتير سيُضاف في مرحلة لاحقة. الخطط:
      </p>

      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        <Plan name="Free" price="٠ ريال" features={["لوحة الحساب", "ربط متجر واحد"]} />
        <Plan
          name="Pro"
          price="—"
          features={["نظرة على السوق", "تحليل كتالوج موسّع"]}
          highlighted
        />
        <Plan
          name="Business"
          price="—"
          features={["وصول API", "حسابات فريق", "دعم مخصّص"]}
        />
      </div>
    </div>
  );
}

function Plan({
  name,
  price,
  features,
  highlighted,
}: {
  name: string;
  price: string;
  features: string[];
  highlighted?: boolean;
}) {
  return (
    <div
      className={[
        "rounded-lg border p-5",
        highlighted ? "border-brand bg-brand/5" : "border-border bg-surface",
      ].join(" ")}
    >
      <div className="text-lg font-semibold">{name}</div>
      <div className="mt-1 text-sm text-muted">{price}</div>
      <ul className="mt-3 space-y-1 text-sm">
        {features.map((f) => (
          <li key={f}>• {f}</li>
        ))}
      </ul>
    </div>
  );
}
