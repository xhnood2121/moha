export type Vendor = "salla" | "zid" | "other";

export const VENDOR_CHANNEL: Record<Vendor, { label: string; href: string }> = {
  salla: {
    label: "security@salla.sa",
    href: "mailto:security@salla.sa",
  },
  zid: {
    label: "Zid Bug Bounty",
    href: "https://bugbounty.zid.sa/",
  },
  other: {
    label: "تواصل مع المنصة المعنية",
    href: "https://owasp.org/www-project-vulnerability-disclosure/",
  },
};

export function reportToMarkdown(r: {
  title: string;
  vendor: string;
  severity: string;
  summary: string;
  reproSteps: string;
  impact: string;
  remediation: string;
}): string {
  return [
    `# ${r.title}`,
    "",
    `**Vendor**: ${r.vendor}`,
    `**Severity**: ${r.severity}`,
    "",
    "## Summary",
    r.summary,
    "",
    "## Reproduction steps",
    r.reproSteps,
    "",
    "## Impact",
    r.impact,
    "",
    "## Recommendation",
    r.remediation,
    "",
  ].join("\n");
}
