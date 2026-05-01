import type { Metadata } from "next";
import { cookies } from "next/headers";
import { DEFAULT_LOCALE, dirFor, type Locale } from "@/lib/i18n";
import { Providers } from "@/components/Providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "رقمان — Raqman",
  description: "Saudi e-commerce market intelligence",
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const cookieStore = await cookies();
  const cookieLocale = cookieStore.get("locale")?.value as Locale | undefined;
  const locale: Locale =
    cookieLocale === "ar" || cookieLocale === "en" ? cookieLocale : DEFAULT_LOCALE;
  const dir = dirFor(locale);

  return (
    <html lang={locale} dir={dir}>
      <body className="min-h-screen antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
