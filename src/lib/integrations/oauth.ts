import crypto from "node:crypto";
import { cookies } from "next/headers";

const STATE_COOKIE = "oauth_state";
const STATE_TTL_SECONDS = 600;

export type OAuthStatePayload = {
  provider: "salla" | "zid";
  userId: string;
  nonce: string;
  iat: number;
};

function secret(): string {
  const s = process.env.AUTH_SECRET;
  if (!s) throw new Error("AUTH_SECRET not set");
  return s;
}

export function signState(payload: OAuthStatePayload): string {
  const body = Buffer.from(JSON.stringify(payload)).toString("base64url");
  const mac = crypto
    .createHmac("sha256", secret())
    .update(body)
    .digest("base64url");
  return `${body}.${mac}`;
}

export function verifyState(token: string): OAuthStatePayload | null {
  const [body, mac] = token.split(".");
  if (!body || !mac) return null;
  const expected = crypto
    .createHmac("sha256", secret())
    .update(body)
    .digest("base64url");
  const a = Buffer.from(mac);
  const b = Buffer.from(expected);
  if (a.length !== b.length) return null;
  if (!crypto.timingSafeEqual(a, b)) return null;

  let parsed: OAuthStatePayload;
  try {
    parsed = JSON.parse(Buffer.from(body, "base64url").toString("utf8"));
  } catch {
    return null;
  }
  if (Date.now() / 1000 - parsed.iat > STATE_TTL_SECONDS) return null;
  return parsed;
}

export async function setStateCookie(value: string) {
  const c = await cookies();
  c.set(STATE_COOKIE, value, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: STATE_TTL_SECONDS,
  });
}

export async function readStateCookie(): Promise<string | null> {
  const c = await cookies();
  return c.get(STATE_COOKIE)?.value ?? null;
}

export async function clearStateCookie() {
  const c = await cookies();
  c.delete(STATE_COOKIE);
}

export function newNonce(): string {
  return crypto.randomBytes(16).toString("base64url");
}

export function timingSafeEqualHex(a: string, b: string): boolean {
  const ab = Buffer.from(a, "hex");
  const bb = Buffer.from(b, "hex");
  if (ab.length !== bb.length) return false;
  return crypto.timingSafeEqual(ab, bb);
}

export function timingSafeEqualString(a: string, b: string): boolean {
  const ab = Buffer.from(a);
  const bb = Buffer.from(b);
  if (ab.length !== bb.length) return false;
  return crypto.timingSafeEqual(ab, bb);
}
