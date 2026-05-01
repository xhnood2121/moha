import { Paywall } from "@/components/Paywall";
import { getLocale } from "@/lib/locale";
import { t } from "@/lib/i18n";

export default async function MarketPage() {
  const locale = await getLocale();
  return (
    <div>
      <h1 className="text-2xl font-semibold">{t(locale, "nav.market")}</h1>
      <p className="mt-1 text-sm text-muted">
        {t(locale, "data.publicEstimate")} — تقديرات مبنية على البيانات العامة فقط.
      </p>

      <div className="mt-8">
        <Paywall required="PRO">
          <div className="rounded-lg border border-border bg-surface p-6">
            <p className="text-sm">
              ستظهر هنا في المرحلة الثانية: تحليل الكتالوج العام (الفئات الأكثر
              نموًا، توزيعات الأسعار، إيقاع المنتجات الجديدة) من زحف مهذّب يحترم
              robots.txt ولا يقدّم أي ادعاء بالمبيعات.
            </p>
          </div>
        </Paywall>
      </div>
    </div>
  );
}
