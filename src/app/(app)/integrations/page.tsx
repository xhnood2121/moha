import { getLocale } from "@/lib/locale";
import { t } from "@/lib/i18n";

export default async function IntegrationsPage() {
  const locale = await getLocale();

  const sallaConfigured = Boolean(process.env.SALLA_CLIENT_ID);
  const zidConfigured = Boolean(process.env.ZID_CLIENT_ID);

  return (
    <div>
      <h1 className="text-2xl font-semibold">{t(locale, "nav.integrations")}</h1>
      <p className="mt-1 text-sm text-muted">
        ربط رسمي عبر OAuth. لا نطلب كلمات المرور ولا نتجاوز أي حماية.
      </p>

      <div className="mt-8 grid gap-4 sm:grid-cols-2">
        <ProviderCard
          name="Salla"
          configured={sallaConfigured}
          authUrl="/api/integrations/salla/start"
        />
        <ProviderCard
          name="Zid"
          configured={zidConfigured}
          authUrl="/api/integrations/zid/start"
        />
      </div>
    </div>
  );
}

function ProviderCard({
  name,
  configured,
  authUrl,
}: {
  name: string;
  configured: boolean;
  authUrl: string;
}) {
  return (
    <div className="rounded-lg border border-border bg-surface p-5">
      <div className="text-lg font-semibold">{name}</div>
      <p className="mt-1 text-xs text-muted">
        {configured
          ? "جاهز للربط — اضغط الزر لبدء OAuth الرسمي."
          : "لم تتم تهيئة بيانات تطبيق المنصة بعد (سيتم في المرحلة 2)."}
      </p>
      <a
        href={configured ? authUrl : "#"}
        aria-disabled={!configured}
        className={[
          "mt-4 inline-block rounded-md px-4 py-2 text-sm",
          configured
            ? "bg-brand text-brand-fg hover:opacity-90"
            : "cursor-not-allowed border border-border text-muted",
        ].join(" ")}
      >
        ربط {name}
      </a>
    </div>
  );
}
