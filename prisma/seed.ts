// Demo seed for local dev. Creates one user, one Salla merchant, and a few
// order events spread across the last 30 days so /my-store has visible data.
//
// Idempotent: re-running upserts.

import "dotenv/config";
import bcrypt from "bcryptjs";
import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();

const DEMO_EMAIL = "demo@raqman.test";
const DEMO_PASSWORD = "demo-password-1234";
const SALLA_EXTERNAL_ID = "99999";

async function main() {
  const passwordHash = await bcrypt.hash(DEMO_PASSWORD, 12);

  const user = await prisma.user.upsert({
    where: { email: DEMO_EMAIL },
    create: {
      email: DEMO_EMAIL,
      name: "حساب تجريبي",
      locale: "ar",
      role: "USER",
      passwordHash,
      subscriptions: { create: { plan: "PRO", status: "ACTIVE" } },
    },
    update: { passwordHash },
    select: { id: true, email: true },
  });

  const merchant = await prisma.merchant.upsert({
    where: {
      platform_externalId: { platform: "SALLA", externalId: SALLA_EXTERNAL_ID },
    },
    create: {
      userId: user.id,
      platform: "SALLA",
      externalId: SALLA_EXTERNAL_ID,
      storeName: "متجر تجريبي",
      storeDomain: "demo.salla.sa",
      scopes: ["orders.read", "settings.read"],
    },
    update: { userId: user.id, uninstalledAt: null },
    select: { id: true, storeName: true },
  });

  const samples = [
    { id: "ORD-1001", days: 1, total: 425.5, items: 2 },
    { id: "ORD-1002", days: 3, total: 189.0, items: 1 },
    { id: "ORD-1003", days: 5, total: 1240.75, items: 4 },
    { id: "ORD-1004", days: 8, total: 89.0, items: 1 },
    { id: "ORD-1005", days: 12, total: 560.25, items: 3 },
    { id: "ORD-1006", days: 18, total: 2150.0, items: 6 },
    { id: "ORD-1007", days: 22, total: 310.5, items: 2 },
    { id: "ORD-1008", days: 27, total: 745.0, items: 3 },
  ];

  for (const s of samples) {
    await prisma.orderEvent.upsert({
      where: {
        merchantId_externalOrderId_eventType: {
          merchantId: merchant.id,
          externalOrderId: s.id,
          eventType: "order.created",
        },
      },
      create: {
        merchantId: merchant.id,
        externalOrderId: s.id,
        eventType: "order.created",
        totalMinor: Math.round(s.total * 100),
        currency: "SAR",
        itemCount: s.items,
        occurredAt: new Date(Date.now() - s.days * 24 * 3600 * 1000),
        payloadHash: `seed-${s.id}`,
      },
      update: {
        totalMinor: Math.round(s.total * 100),
        itemCount: s.items,
        occurredAt: new Date(Date.now() - s.days * 24 * 3600 * 1000),
      },
    });
  }

  console.log(`✓ user      ${user.email}`);
  console.log(`✓ merchant  ${merchant.storeName} (${SALLA_EXTERNAL_ID})`);
  console.log(`✓ orders    ${samples.length} events seeded`);
  console.log("");
  console.log("Sign in with:");
  console.log(`  email     ${DEMO_EMAIL}`);
  console.log(`  password  ${DEMO_PASSWORD}`);
}

main()
  .catch((err) => {
    console.error(err);
    process.exitCode = 1;
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
