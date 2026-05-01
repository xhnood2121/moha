import crypto from "node:crypto";

const AUTHORIZE_URL =
  process.env.SALLA_AUTHORIZE_URL ?? "https://accounts.salla.sa/oauth2/auth";
const TOKEN_URL =
  process.env.SALLA_TOKEN_URL ?? "https://accounts.salla.sa/oauth2/token";

export type SallaTokens = {
  access_token: string;
  refresh_token?: string;
  expires_in?: number;
  scope?: string;
  token_type?: string;
};

export function buildAuthorizeUrl(state: string): string {
  const clientId = required("SALLA_CLIENT_ID");
  const redirect = required("SALLA_REDIRECT_URI");
  const scope =
    process.env.SALLA_SCOPES ?? "offline_access orders.read settings.read";

  const u = new URL(AUTHORIZE_URL);
  u.searchParams.set("client_id", clientId);
  u.searchParams.set("response_type", "code");
  u.searchParams.set("redirect_uri", redirect);
  u.searchParams.set("scope", scope);
  u.searchParams.set("state", state);
  return u.toString();
}

export async function exchangeCode(code: string): Promise<SallaTokens> {
  const body = new URLSearchParams({
    grant_type: "authorization_code",
    code,
    client_id: required("SALLA_CLIENT_ID"),
    client_secret: required("SALLA_CLIENT_SECRET"),
    redirect_uri: required("SALLA_REDIRECT_URI"),
  });

  const res = await fetch(TOKEN_URL, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`salla_token_exchange_failed: ${res.status} ${text}`);
  }
  return (await res.json()) as SallaTokens;
}

export async function refreshTokens(refreshToken: string): Promise<SallaTokens> {
  const body = new URLSearchParams({
    grant_type: "refresh_token",
    refresh_token: refreshToken,
    client_id: required("SALLA_CLIENT_ID"),
    client_secret: required("SALLA_CLIENT_SECRET"),
  });

  const res = await fetch(TOKEN_URL, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`salla_token_refresh_failed: ${res.status} ${text}`);
  }
  return (await res.json()) as SallaTokens;
}

// Salla webhook signature: HMAC-SHA256 of the raw body using the shared secret.
// Header name is configurable to allow per-tenant overrides.
export function verifyWebhookSignature(
  rawBody: string,
  signatureHeader: string | null
): boolean {
  const secret = process.env.SALLA_WEBHOOK_SECRET;
  if (!secret || !signatureHeader) return false;
  const expected = crypto
    .createHmac("sha256", secret)
    .update(rawBody)
    .digest("hex");
  const a = Buffer.from(expected);
  const b = Buffer.from(signatureHeader.trim().toLowerCase().replace(/^sha256=/, ""));
  if (a.length !== b.length) return false;
  return crypto.timingSafeEqual(a, b);
}

function required(name: string): string {
  const v = process.env[name];
  if (!v) throw new Error(`${name} is not configured`);
  return v;
}
