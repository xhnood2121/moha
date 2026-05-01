import { prisma } from "@/lib/db";

export async function awaitHostSlot(host: string, minIntervalMs: number): Promise<void> {
  const state = await prisma.crawlHostState.findUnique({ where: { host } });
  if (state?.lastRequestAt) {
    const elapsed = Date.now() - state.lastRequestAt.getTime();
    const wait = minIntervalMs - elapsed;
    if (wait > 0) await sleep(wait + jitter());
  } else {
    await sleep(jitter());
  }
}

export async function recordHostRequest(host: string): Promise<void> {
  await prisma.crawlHostState.upsert({
    where: { host },
    create: { host, lastRequestAt: new Date() },
    update: { lastRequestAt: new Date() },
  });
}

export async function recordHostError(host: string): Promise<void> {
  await prisma.crawlHostState.upsert({
    where: { host },
    create: { host, consecutiveErrors: 1 },
    update: { consecutiveErrors: { increment: 1 } },
  });
  const state = await prisma.crawlHostState.findUnique({ where: { host } });
  if (state && state.consecutiveErrors >= 5) {
    await prisma.crawlHostState.update({
      where: { host },
      data: { blockedUntil: new Date(Date.now() + 6 * 3600 * 1000) },
    });
  }
}

export async function isHostBlocked(host: string): Promise<boolean> {
  const state = await prisma.crawlHostState.findUnique({ where: { host } });
  return Boolean(state?.blockedUntil && state.blockedUntil > new Date());
}

export async function clearHostErrors(host: string): Promise<void> {
  await prisma.crawlHostState.update({
    where: { host },
    data: { consecutiveErrors: 0, blockedUntil: null },
  });
}

function jitter(): number {
  return Math.floor(Math.random() * 250);
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}
