import robotsParser from "robots-parser";
import { prisma } from "@/lib/db";

const ROBOTS_TTL_MS = 24 * 3600 * 1000;

export type RobotsCheck = { allowed: boolean; crawlDelayMs: number };

export async function isAllowed(
  url: string,
  userAgent: string
): Promise<RobotsCheck> {
  const u = new URL(url);
  const host = u.host;
  const robotsUrl = `${u.protocol}//${host}/robots.txt`;

  let state = await prisma.crawlHostState.findUnique({ where: { host } });
  const stale =
    !state?.robotsFetchedAt ||
    Date.now() - state.robotsFetchedAt.getTime() > ROBOTS_TTL_MS;

  if (stale) {
    let body = "";
    try {
      const res = await fetch(robotsUrl, {
        headers: { "User-Agent": userAgent, Accept: "text/plain" },
      });
      body = res.ok ? await res.text() : "";
    } catch {
      body = "";
    }
    state = await prisma.crawlHostState.upsert({
      where: { host },
      create: { host, robotsTxt: body, robotsFetchedAt: new Date() },
      update: { robotsTxt: body, robotsFetchedAt: new Date() },
    });
  }

  const robots = robotsParser(robotsUrl, state?.robotsTxt ?? "");
  const allowed = robots.isAllowed(url, userAgent) !== false;
  const crawlDelay = robots.getCrawlDelay(userAgent);
  const crawlDelayMs = crawlDelay ? Math.max(0, crawlDelay) * 1000 : 0;

  return { allowed, crawlDelayMs };
}
