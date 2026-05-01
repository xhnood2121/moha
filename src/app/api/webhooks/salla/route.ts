import { NextResponse, type NextRequest } from "next/server";
import { prisma } from "@/lib/db";
import { verifyWebhookSignature } from "@/lib/integrations/salla";
import { normalizeSallaOrder, payloadHash } from "@/lib/integrations/normalize";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const raw = await req.text();
  const sig = req.headers.get("x-salla-signature");
  if (!verifyWebhookSignature(raw, sig)) {
    return NextResponse.json({ error: "invalid_signature" }, { status: 401 });
  }

  let body: { event?: string; merchant?: string | number; data?: unknown };
  try {
    body = JSON.parse(raw);
  } catch {
    return NextResponse.json({ error: "invalid_json" }, { status: 400 });
  }

  const eventType = body.event ?? "unknown";
  const externalMerchantId = body.merchant?.toString();
  if (!externalMerchantId) {
    return NextResponse.json({ error: "missing_merchant" }, { status: 400 });
  }

  const merchant = await prisma.merchant.findUnique({
    where: { platform_externalId: { platform: "SALLA", externalId: externalMerchantId } },
  });
  if (!merchant || merchant.uninstalledAt) {
    return NextResponse.json({ ok: true, ignored: true });
  }

  if (eventType === "app.uninstalled") {
    await prisma.merchant.update({
      where: { id: merchant.id },
      data: { uninstalledAt: new Date() },
    });
    return NextResponse.json({ ok: true });
  }

  if (eventType.startsWith("order.")) {
    const norm = normalizeSallaOrder(eventType, body);
    if (!norm) return NextResponse.json({ ok: true, ignored: true });

    await prisma.orderEvent.upsert({
      where: {
        merchantId_externalOrderId_eventType: {
          merchantId: merchant.id,
          externalOrderId: norm.externalOrderId,
          eventType: norm.eventType,
        },
      },
      create: {
        merchantId: merchant.id,
        externalOrderId: norm.externalOrderId,
        eventType: norm.eventType,
        totalMinor: norm.totalMinor,
        currency: norm.currency,
        itemCount: norm.itemCount,
        occurredAt: norm.occurredAt,
        payloadHash: payloadHash(raw),
      },
      update: {
        totalMinor: norm.totalMinor,
        currency: norm.currency,
        itemCount: norm.itemCount,
        occurredAt: norm.occurredAt,
        payloadHash: payloadHash(raw),
      },
    });
  }

  return NextResponse.json({ ok: true });
}
