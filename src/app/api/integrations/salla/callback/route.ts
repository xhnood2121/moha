import { NextResponse, type NextRequest } from "next/server";
import { prisma } from "@/lib/db";
import { exchangeCode } from "@/lib/integrations/salla";
import {
  clearStateCookie,
  readStateCookie,
  timingSafeEqualString,
  verifyState,
} from "@/lib/integrations/oauth";

export async function GET(req: NextRequest) {
  const url = new URL(req.url);
  const code = url.searchParams.get("code");
  const stateParam = url.searchParams.get("state");

  if (!code || !stateParam) {
    return NextResponse.json({ error: "missing_params" }, { status: 400 });
  }

  const cookieState = await readStateCookie();
  if (!cookieState || !timingSafeEqualString(cookieState, stateParam)) {
    return NextResponse.json({ error: "state_mismatch" }, { status: 400 });
  }

  const payload = verifyState(stateParam);
  if (!payload || payload.provider !== "salla") {
    return NextResponse.json({ error: "invalid_state" }, { status: 400 });
  }

  let tokens;
  try {
    tokens = await exchangeCode(code);
  } catch (err) {
    return NextResponse.json(
      { error: "token_exchange_failed", detail: String(err) },
      { status: 502 }
    );
  }

  // Identify the merchant. Salla returns merchant info either embedded in the
  // token response or via a /me endpoint; we normalise on `external_id`.
  const externalId =
    (tokens as Record<string, unknown>).merchant?.toString() ??
    (tokens as Record<string, unknown>).user_id?.toString() ??
    `unknown_${payload.nonce}`;
  const storeName =
    ((tokens as Record<string, unknown>).store as { name?: string } | undefined)
      ?.name ?? "Salla store";

  const expiresAt = tokens.expires_in
    ? new Date(Date.now() + tokens.expires_in * 1000)
    : null;

  const merchant = await prisma.merchant.upsert({
    where: { platform_externalId: { platform: "SALLA", externalId } },
    create: {
      userId: payload.userId,
      platform: "SALLA",
      externalId,
      storeName,
      scopes: tokens.scope ? tokens.scope.split(/\s+/) : [],
    },
    update: {
      userId: payload.userId,
      uninstalledAt: null,
      storeName,
      scopes: tokens.scope ? tokens.scope.split(/\s+/) : [],
    },
  });

  await prisma.merchantToken.create({
    data: {
      merchantId: merchant.id,
      accessToken: tokens.access_token,
      refreshToken: tokens.refresh_token,
      expiresAt,
    },
  });

  await prisma.auditLog.create({
    data: {
      userId: payload.userId,
      action: "integration.salla.connected",
      resource: merchant.id,
      meta: { externalId },
    },
  });

  await clearStateCookie();
  return NextResponse.redirect(
    new URL("/my-store", process.env.AUTH_URL ?? "http://localhost:3000")
  );
}
