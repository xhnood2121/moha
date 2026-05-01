"use client";

import { useState } from "react";
import { Clipboard, Check } from "lucide-react";

export function CopyButton({ text, label = "نسخ كـ Markdown" }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);

  async function onClick() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard API may be unavailable; ignore.
    }
  }

  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-1 rounded-md border border-border px-3 py-2 text-sm hover:bg-border/40"
    >
      {copied ? <Check size={14} /> : <Clipboard size={14} />}
      {copied ? "تم النسخ" : label}
    </button>
  );
}
