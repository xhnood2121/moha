import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { buildAuthorizeUrl } from "@/lib/integrations/salla";
import {
  newNonce,
  setStateCookie,
  signState,
} from "@/lib/integrations/oauth";

export async function GET() {
  const session = await auth();
  if (!session) {
    return NextResponse.redirect(new URL("/login", process.env.AUTH_URL ?? "http://localhost:3000"));
  }

  if (!process.env.SALLA_CLIENT_ID) {
    return NextResponse.json({ error: "salla_not_configured" }, { status: 503 });
  }

  const state = signState({
    provider: "salla",
    userId: session.user.id,
    nonce: newNonce(),
    iat: Math.floor(Date.now() / 1000),
  });
  await setStateCookie(state);

  return NextResponse.redirect(buildAuthorizeUrl(state));
}
