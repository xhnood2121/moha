import { prisma } from "@/lib/db";
import type { SubscriptionPlan } from "@prisma/client";

const PLAN_RANK: Record<SubscriptionPlan, number> = {
  FREE: 0,
  PRO: 1,
  BUSINESS: 2,
};

export async function getActivePlan(userId: string): Promise<SubscriptionPlan> {
  const sub = await prisma.subscription.findFirst({
    where: { userId, status: "ACTIVE" },
    orderBy: { startedAt: "desc" },
  });
  return sub?.plan ?? "FREE";
}

export async function hasAtLeastPlan(
  userId: string,
  required: SubscriptionPlan
): Promise<boolean> {
  const plan = await getActivePlan(userId);
  return PLAN_RANK[plan] >= PLAN_RANK[required];
}
