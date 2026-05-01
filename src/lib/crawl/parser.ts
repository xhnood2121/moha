// Parses public catalog data from a storefront page. We only consume:
//   - sitemap.xml product entries (lastmod is intentionally NOT used as a
//     sales-activity proxy — only as a "snapshot freshness" hint for our own
//     scheduling)
//   - JSON-LD Product blocks embedded in product detail pages (a public
//     standard documented by schema.org and emitted by both Salla and Zid
//     storefronts for SEO).
// We do not call any private APIs, do not use authenticated headers, and do
// not infer hidden data from response timing or error messages.

export type ParsedProduct = {
  externalId: string;
  slug?: string;
  name: string;
  category?: string;
  priceMinor?: number;
  currency?: string;
  isAvailable: boolean;
  publicReviews?: number;
};

type Loose = Record<string, unknown>;

export function extractJsonLdProducts(html: string): ParsedProduct[] {
  const blocks = collectJsonLdBlocks(html);
  const out: ParsedProduct[] = [];

  for (const block of blocks) {
    const candidates = flattenSchema(block);
    for (const c of candidates) {
      const type = arrayify(c["@type"]).map(String);
      if (!type.includes("Product")) continue;
      const product = toProduct(c);
      if (product) out.push(product);
    }
  }
  return out;
}

function collectJsonLdBlocks(html: string): Loose[] {
  const re =
    /<script[^>]*type=["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi;
  const out: Loose[] = [];
  let m: RegExpExecArray | null;
  while ((m = re.exec(html))) {
    const body = m[1].trim();
    try {
      const parsed = JSON.parse(body);
      if (Array.isArray(parsed)) out.push(...parsed);
      else if (parsed && typeof parsed === "object") out.push(parsed);
    } catch {
      // Tolerate malformed blocks; storefronts sometimes ship invalid JSON-LD.
    }
  }
  return out;
}

function flattenSchema(node: Loose): Loose[] {
  const out: Loose[] = [];
  const graph = node["@graph"];
  if (Array.isArray(graph)) {
    for (const g of graph) if (g && typeof g === "object") out.push(g as Loose);
  } else {
    out.push(node);
  }
  return out;
}

function arrayify(v: unknown): unknown[] {
  return Array.isArray(v) ? v : v == null ? [] : [v];
}

function toProduct(raw: Loose): ParsedProduct | null {
  const name = typeof raw.name === "string" ? raw.name : undefined;
  const externalId =
    str(raw.sku) ?? str(raw.productID) ?? str(raw["@id"]) ?? str(raw.url);
  if (!name || !externalId) return null;

  const offers = arrayify(raw.offers).filter(
    (o): o is Loose => typeof o === "object" && o !== null
  );
  const offer = offers[0];

  const priceRaw = offer
    ? num(offer.price) ?? num((offer.priceSpecification as Loose)?.price)
    : undefined;
  const currency = offer
    ? str(offer.priceCurrency) ??
      str((offer.priceSpecification as Loose)?.priceCurrency)
    : undefined;

  const availability = offer ? str(offer.availability) ?? "" : "";
  const isAvailable = !/OutOfStock|Discontinued/i.test(availability);

  const aggregate = raw.aggregateRating as Loose | undefined;
  const reviewCount =
    aggregate ? num(aggregate.reviewCount) ?? num(aggregate.ratingCount) : undefined;

  return {
    externalId,
    slug: str(raw.url),
    name,
    category: str(raw.category),
    priceMinor: priceRaw != null ? Math.round(priceRaw * 100) : undefined,
    currency,
    isAvailable,
    publicReviews: reviewCount,
  };
}

function str(v: unknown): string | undefined {
  return typeof v === "string" ? v : undefined;
}
function num(v: unknown): number | undefined {
  if (typeof v === "number") return v;
  if (typeof v === "string") {
    const n = Number(v);
    return Number.isFinite(n) ? n : undefined;
  }
  return undefined;
}

export function extractSitemapUrls(xml: string): string[] {
  const urls: string[] = [];
  const re = /<loc>([^<]+)<\/loc>/gi;
  let m: RegExpExecArray | null;
  while ((m = re.exec(xml))) urls.push(m[1].trim());
  return urls;
}
