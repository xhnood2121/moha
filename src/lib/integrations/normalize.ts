import crypto from "node:crypto";

export type NormalizedOrder = {
  externalOrderId: string;
  eventType: string;
  totalMinor: number;
  currency: string;
  itemCount: number;
  occurredAt: Date;
};

type Loose = Record<string, unknown>;

function num(v: unknown): number | undefined {
  if (typeof v === "number") return v;
  if (typeof v === "string") {
    const n = Number(v);
    return Number.isFinite(n) ? n : undefined;
  }
  return undefined;
}

function str(v: unknown): string | undefined {
  return typeof v === "string" ? v : v == null ? undefined : String(v);
}

export function normalizeSallaOrder(
  eventType: string,
  payload: unknown
): NormalizedOrder | null {
  const data = (payload as Loose)?.data ?? payload;
  if (!data || typeof data !== "object") return null;
  const d = data as Loose;

  const id = str(d.id) ?? str(d.reference_id);
  if (!id) return null;

  const amounts = (d.amounts ?? d.total ?? {}) as Loose;
  const totalRaw =
    num((amounts.total as Loose)?.amount) ??
    num(amounts.total) ??
    num(d.total) ??
    0;
  const currency =
    str((amounts.total as Loose)?.currency) ??
    str(amounts.currency) ??
    str(d.currency) ??
    "SAR";

  const items = Array.isArray(d.items) ? d.items : [];
  const occurred = str(d.date) ?? str(d.created_at);

  return {
    externalOrderId: id,
    eventType,
    totalMinor: Math.round(totalRaw * 100),
    currency,
    itemCount: items.length,
    occurredAt: occurred ? new Date(occurred) : new Date(),
  };
}

export function normalizeZidOrder(
  eventType: string,
  payload: unknown
): NormalizedOrder | null {
  const d = (payload as Loose) ?? {};
  const order = (d.order ?? d) as Loose;
  if (!order || typeof order !== "object") return null;

  const id = str(order.id) ?? str(order.code);
  if (!id) return null;

  const totalRaw =
    num((order.order_total as Loose)?.amount) ??
    num(order.order_total) ??
    num(order.total) ??
    0;
  const currency =
    str((order.order_total as Loose)?.currency_code) ??
    str(order.currency_code) ??
    "SAR";

  const items = Array.isArray(order.products) ? order.products : [];
  const occurred = str(order.created_at) ?? str(order.order_date);

  return {
    externalOrderId: id,
    eventType,
    totalMinor: Math.round(totalRaw * 100),
    currency,
    itemCount: items.length,
    occurredAt: occurred ? new Date(occurred) : new Date(),
  };
}

export function payloadHash(raw: string): string {
  return crypto.createHash("sha256").update(raw).digest("hex");
}
