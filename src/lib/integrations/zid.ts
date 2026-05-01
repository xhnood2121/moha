import crypto from "node:crypto";

const AUTHORIZE_URL =
  process.env.ZID_AUTHORIZE_URL ?? "https://oauth.zid.sa/oauth/authorize";
const TOKEN_URL = process.env.ZID_TOKEN_URL ?? "https://oauth.zid.sa/oauth/token";

export type ZidTokens = {
  access_token: string;
  refresh_token?: string;
  expires_in?: number;
  authorization?: string;
  token_type?: string;
};

export function buildAuthorizeUrl(state: string): string {
  const clientId = required("ZID_CLIENT_ID");
  const redirect = required("ZID_REDIRECT_URI");

  const u = new URL(AUTHORIZE_URL);
  u.searchParams.set("client_id", clientId);
  u.searchParams.set("response_type", "code");
  u.searchParams.set("redirect_uri", redirect);
  u.searchParams.set("state", state);
  return u.toString();
}

export async function exchangeCode(code: string): Promise<ZidTokens> {
  const body = new URLSearchParams({
    grant_type: "authorization_code",
    code,
    client_id: required("ZID_CLIENT_ID"),
    client_secret: required("ZID_CLIENT_SECRET"),
    redirect_uri: required("ZID_REDIRECT_URI"),
  });

  const res = await fetch(TOKEN_URL, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`zid_token_exchange_failed: ${res.status} ${text}`);
  }
  return (await res.json()) as ZidTokens;
}

export async function refreshTokens(refreshToken: string): Promise<ZidTokens> {
  const body = new URLSearchParams({
    grant_type: "refresh_token",
    refresh_token: refreshToken,
    client_id: required("ZID_CLIENT_ID"),
    client_secret: required("ZID_CLIENT_SECRET"),
  });

  const res = await fetch(TOKEN_URL, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`zid_token_refresh_failed: ${res.status} ${text}`);
  }
  return (await res.json()) as ZidTokens;
}

export function verifyWebhookSignature(
  rawBody: string,
  signatureHeader: string | null
): boolean {
  const secret = process.env.ZID_WEBHOOK_SECRET;
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
