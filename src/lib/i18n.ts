export type Locale = "ar" | "en";

export const DEFAULT_LOCALE: Locale = "ar";
export const SUPPORTED_LOCALES: Locale[] = ["ar", "en"];

const dict = {
  ar: {
    "app.name": "رقمان",
    "app.tagline": "ذكاء سوق التجارة الإلكترونية في السعودية",
    "nav.dashboard": "لوحة التحكم",
    "nav.market": "نظرة على السوق",
    "nav.myStore": "متجري",
    "nav.integrations": "الربط (سلة / زد)",
    "nav.bugReports": "تقارير الثغرات",
    "nav.settings": "الإعدادات",
    "nav.signOut": "تسجيل الخروج",
    "auth.login": "تسجيل الدخول",
    "auth.register": "إنشاء حساب",
    "auth.email": "البريد الإلكتروني",
    "auth.password": "كلمة المرور",
    "auth.name": "الاسم",
    "auth.submit": "متابعة",
    "auth.haveAccount": "لديك حساب؟",
    "auth.noAccount": "ليس لديك حساب؟",
    "auth.errors.invalid": "بيانات الدخول غير صحيحة",
    "auth.errors.exists": "البريد الإلكتروني مستخدم مسبقًا",
    "paywall.title": "هذه الميزة للمشتركين",
    "paywall.body":
      "اشترك في خطة Pro للوصول إلى تحليلات السوق المتقدمة والتقارير المفصّلة.",
    "paywall.cta": "ترقية الاشتراك",
    "data.verifiedOnly": "بيانات موثّقة (متجرك)",
    "data.publicEstimate": "تقدير من بيانات عامة",
    "common.loading": "جاري التحميل…",
    "common.error": "حدث خطأ",
    "common.empty": "لا توجد بيانات",
  },
  en: {
    "app.name": "Raqman",
    "app.tagline": "Saudi e-commerce market intelligence",
    "nav.dashboard": "Dashboard",
    "nav.market": "Market overview",
    "nav.myStore": "My store",
    "nav.integrations": "Integrations (Salla / Zid)",
    "nav.bugReports": "Bug reports",
    "nav.settings": "Settings",
    "nav.signOut": "Sign out",
    "auth.login": "Sign in",
    "auth.register": "Create account",
    "auth.email": "Email",
    "auth.password": "Password",
    "auth.name": "Name",
    "auth.submit": "Continue",
    "auth.haveAccount": "Already have an account?",
    "auth.noAccount": "Don't have an account?",
    "auth.errors.invalid": "Invalid credentials",
    "auth.errors.exists": "Email already registered",
    "paywall.title": "Pro feature",
    "paywall.body":
      "Upgrade to Pro to unlock advanced market analytics and detailed reports.",
    "paywall.cta": "Upgrade",
    "data.verifiedOnly": "Verified (your store)",
    "data.publicEstimate": "Estimate from public data",
    "common.loading": "Loading…",
    "common.error": "Something went wrong",
    "common.empty": "No data",
  },
} as const satisfies Record<Locale, Record<string, string>>;

export type MessageKey = keyof (typeof dict)["ar"];

export function t(locale: Locale, key: MessageKey): string {
  return dict[locale][key] ?? dict[DEFAULT_LOCALE][key] ?? key;
}

export function dirFor(locale: Locale): "rtl" | "ltr" {
  return locale === "ar" ? "rtl" : "ltr";
}

export function formatNumber(locale: Locale, n: number): string {
  return new Intl.NumberFormat(locale === "ar" ? "ar-SA" : "en-US").format(n);
}

export function formatSAR(locale: Locale, minor: number): string {
  const v = minor / 100;
  return new Intl.NumberFormat(locale === "ar" ? "ar-SA" : "en-US", {
    style: "currency",
    currency: "SAR",
    maximumFractionDigits: 2,
  }).format(v);
}
