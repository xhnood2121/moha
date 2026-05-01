// Polite public-catalog crawler.
//
// Constraints (do not relax):
//   1. Identifying User-Agent with contact URL.
//   2. robots.txt fetched and respected per host (cached 24h).
//   3. Hard cap of 1 request/sec/host plus jitter, plus any Crawl-Delay
//      directive from robots.txt (whichever is larger).
//   4. Only fetches storefront pages already listed in PublicStore where
//      isActive=true and isClosed=false; we do not auto-discover hosts.
//   5. Snapshots only public catalog data: product name, category, public
//      price, availability, public review count. No auth, no probing of
//      cart/coupon/OTP endpoints, no inference of hidden state.
//
// Run with: npm run crawl:public

import "dotenv/config";
import { prisma } from "../src/lib/db";
import { isAllowed } from "../src/lib/crawl/robots";
import {
  awaitHostSlot,
  clearHostErrors,
  isHostBlocked,
  recordHostError,
  recordHostRequest,
} from "../src/lib/crawl/scheduler";
import { extractJsonLdProducts, extractSitemapUrls } from "../src/lib/crawl/parser";

const UA =
  process.env.CRAWLER_USER_AGENT ??
  "RaqmanBot/0.1 (+https://raqman.ai/bot; contact@raqman.ai)";
const REQ_PER_SEC = Number(process.env.CRAWLER_REQ_PER_SEC_PER_HOST ?? "1");
const MIN_INTERVAL_MS = Math.max(1000, Math.floor(1000 / Math.max(0.1, REQ_PER_SEC)));
const MAX_PRODUCTS_PER_STORE = Number(process.env.CRAWLER_MAX_PRODUCTS ?? "200");

async function fetchPolite(url: string): Promise<{ status: number; body: string }> {
  const u = new URL(url);
  const host = u.host;

  if (await isHostBlocked(host)) {
    return { status: 0, body: "" };
  }

  const robots = await isAllowed(url, UA);
  if (!robots.allowed) {
    return { status: 0, body: "" };
  }

  const interval = Math.max(MIN_INTERVAL_MS, robots.crawlDelayMs);
  await awaitHostSlot(host, interval);
  await recordHostRequest(host);

  try {
    const res = await fetch(url, {
      headers: {
        "User-Agent": UA,
        Accept: "text/html,application/xml,application/json;q=0.9,*/*;q=0.8",
      },
      redirect: "follow",
    });
    const body = await res.text();
    if (res.status >= 400) await recordHostError(host);
    else await clearHostErrors(host);
    return { status: res.status, body };
  } catch (err) {
    await recordHostError(host);
    console.error("[crawl] fetch error", url, err);
    return { status: 0, body: "" };
  }
}

async function crawlStore(storeId: string) {
  const store = await prisma.publicStore.findUnique({ where: { id: storeId } });
  if (!store || !store.isActive || store.isClosed) return;

  console.log(`[crawl] ${store.domain}`);

  const sitemapUrl = `https://${store.domain}/sitemap_products.xml`;
  const sitemap = await fetchPolite(sitemapUrl);

  let productUrls: string[] = [];
  if (sitemap.status === 200) {
    productUrls = extractSitemapUrls(sitemap.body).slice(0, MAX_PRODUCTS_PER_STORE);
  }

  if (productUrls.length === 0) {
    const fallback = await fetchPolite(`https://${store.domain}/sitemap.xml`);
    if (fallback.status === 200) {
      productUrls = extractSitemapUrls(fallback.body)
        .filter((u) => /\/product|\/p\//i.test(u))
        .slice(0, MAX_PRODUCTS_PER_STORE);
    }
  }

  let snapshotCount = 0;
  for (const url of productUrls) {
    const page = await fetchPolite(url);
    if (page.status !== 200) continue;

    const products = extractJsonLdProducts(page.body);
    for (const p of products) {
      const product = await prisma.publicProduct.upsert({
        where: { storeId_externalId: { storeId: store.id, externalId: p.externalId } },
        create: {
          storeId: store.id,
          externalId: p.externalId,
          slug: p.slug,
          name: p.name,
          category: p.category,
          priceMinor: p.priceMinor,
          currency: p.currency ?? "SAR",
          isAvailable: p.isAvailable,
          publicReviews: p.publicReviews,
        },
        update: {
          name: p.name,
          category: p.category,
          priceMinor: p.priceMinor,
          isAvailable: p.isAvailable,
          publicReviews: p.publicReviews,
          lastSeenAt: new Date(),
        },
      });

      if (p.priceMinor != null) {
        await prisma.publicPricePoint.create({
          data: {
            productId: product.id,
            priceMinor: p.priceMinor,
            isAvailable: p.isAvailable,
          },
        });
      }
      snapshotCount += 1;
    }
  }

  await prisma.publicStore.update({
    where: { id: store.id },
    data: { lastCrawledAt: new Date() },
  });

  console.log(`[crawl] ${store.domain} → ${snapshotCount} products`);
}

async function main() {
  const stores = await prisma.publicStore.findMany({
    where: {
      isActive: true,
      isClosed: false,
      robotsAllowsUs: true,
    },
    orderBy: [{ lastCrawledAt: { sort: "asc", nulls: "first" } }],
    take: Number(process.env.CRAWLER_BATCH_SIZE ?? "50"),
  });

  console.log(`[crawl] processing ${stores.length} stores`);
  for (const s of stores) {
    try {
      await crawlStore(s.id);
    } catch (err) {
      console.error(`[crawl] failed for ${s.domain}`, err);
    }
  }
}

main()
  .catch((err) => {
    console.error(err);
    process.exitCode = 1;
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
