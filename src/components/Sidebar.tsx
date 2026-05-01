"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { signOut } from "next-auth/react";
import {
  LayoutDashboard,
  Store,
  Globe2,
  Plug,
  ShieldAlert,
  Settings,
  LogOut,
  type LucideIcon,
} from "lucide-react";
import { t, type Locale } from "@/lib/i18n";

type Item = { href: string; key: Parameters<typeof t>[1]; Icon: LucideIcon };

const items: Item[] = [
  { href: "/dashboard", key: "nav.dashboard", Icon: LayoutDashboard },
  { href: "/market", key: "nav.market", Icon: Globe2 },
  { href: "/my-store", key: "nav.myStore", Icon: Store },
  { href: "/integrations", key: "nav.integrations", Icon: Plug },
  { href: "/bug-reports", key: "nav.bugReports", Icon: ShieldAlert },
  { href: "/settings", key: "nav.settings", Icon: Settings },
];

export function Sidebar({ locale }: { locale: Locale }) {
  const pathname = usePathname();

  return (
    <aside className="hidden w-60 shrink-0 border-e border-border bg-surface p-4 md:block">
      <div className="mb-6 px-2">
        <div className="text-lg font-bold">{t(locale, "app.name")}</div>
        <div className="text-xs text-muted">{t(locale, "app.tagline")}</div>
      </div>

      <nav className="space-y-1">
        {items.map(({ href, key, Icon }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              className={[
                "flex items-center gap-2 rounded-md px-3 py-2 text-sm",
                active
                  ? "bg-brand text-brand-fg"
                  : "text-fg hover:bg-border/40",
              ].join(" ")}
            >
              <Icon size={16} />
              <span>{t(locale, key)}</span>
            </Link>
          );
        })}
      </nav>

      <button
        onClick={() => signOut({ callbackUrl: "/" })}
        className="mt-6 flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-muted hover:bg-border/40"
      >
        <LogOut size={16} />
        <span>{t(locale, "nav.signOut")}</span>
      </button>
    </aside>
  );
}
