import { NextResponse } from "next/server";
import { z } from "zod";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/db";

const schema = z.object({
  title: z.string().min(3).max(200),
  vendor: z.enum(["salla", "zid", "other"]),
  severity: z.enum(["LOW", "MEDIUM", "HIGH", "CRITICAL"]),
  summary: z.string().min(1).max(8000),
  reproSteps: z.string().min(1).max(20000),
  impact: z.string().min(1).max(8000),
  remediation: z.string().min(1).max(8000),
});

export async function POST(req: Request) {
  const session = await auth();
  if (!session) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  const parsed = schema.safeParse(await req.json().catch(() => null));
  if (!parsed.success) {
    return NextResponse.json({ error: "invalid_input" }, { status: 400 });
  }

  const report = await prisma.bugReport.create({
    data: {
      userId: session.user.id,
      title: parsed.data.title,
      vendor: parsed.data.vendor,
      severity: parsed.data.severity,
      summary: parsed.data.summary,
      reproSteps: parsed.data.reproSteps,
      impact: parsed.data.impact,
      remediation: parsed.data.remediation,
    },
    select: { id: true },
  });

  return NextResponse.json({ report }, { status: 201 });
}
