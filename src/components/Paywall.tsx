import Link from "next/link";
import { Lock } from "lucide-react";
import { auth } from "@/lib/auth";
import { hasAtLeastPlan } from "@/lib/subscription";
import { getLocale } from "@/lib/locale";
import { t } from "@/lib/i18n";
import type { SubscriptionPlan } from "@prisma/client";

type Props = {
  required: SubscriptionPlan;
  children: React.ReactNode;
};

export async function Paywall({ required, children }: Props) {
  const session = await auth();
  const locale = await getLocale();

  if (!session) {
    return <PaywallCard locale={locale} cta="/login" />;
  }

  const allowed = await hasAtLeastPlan(session.user.id, required);
  if (!allowed) {
    return <PaywallCard locale={locale} cta="/settings/billing" />;
  }

  return <>{children}</>;
}

function PaywallCard({
  locale,
  cta,
}: {
  locale: Awaited<ReturnType<typeof getLocale>>;
  cta: string;
}) {
  return (
    <div className="mx-auto max-w-md rounded-lg border border-border bg-surface p-8 text-center">
      <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-brand/10 text-brand">
        <Lock size={20} />
      </div>
      <h2 className="text-lg font-semibold">{t(locale, "paywall.title")}</h2>
      <p className="mt-2 text-sm text-muted">{t(locale, "paywall.body")}</p>
      <Link
        href={cta}
        className="mt-5 inline-block rounded-md bg-brand px-4 py-2 text-brand-fg hover:opacity-90"
      >
        {t(locale, "paywall.cta")}
      </Link>
    </div>
  );
}
