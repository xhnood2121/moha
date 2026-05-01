import { NextResponse } from "next/server";
import { z } from "zod";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/db";

const updateSchema = z.object({
  title: z.string().min(3).max(200).optional(),
  vendor: z.enum(["salla", "zid", "other"]).optional(),
  severity: z.enum(["LOW", "MEDIUM", "HIGH", "CRITICAL"]).optional(),
  summary: z.string().min(1).max(8000).optional(),
  reproSteps: z.string().min(1).max(20000).optional(),
  impact: z.string().min(1).max(8000).optional(),
  remediation: z.string().min(1).max(8000).optional(),
  status: z
    .enum(["DRAFT", "SUBMITTED", "TRIAGED", "RESOLVED", "REJECTED"])
    .optional(),
});

async function ownedReport(id: string, userId: string) {
  return prisma.bugReport.findFirst({ where: { id, userId } });
}

export async function PUT(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const session = await auth();
  if (!session) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  const { id } = await params;
  const existing = await ownedReport(id, session.user.id);
  if (!existing) return NextResponse.json({ error: "not_found" }, { status: 404 });

  const parsed = updateSchema.safeParse(await req.json().catch(() => null));
  if (!parsed.success) {
    return NextResponse.json({ error: "invalid_input" }, { status: 400 });
  }

  const report = await prisma.bugReport.update({
    where: { id },
    data: parsed.data,
    select: { id: true, status: true },
  });

  return NextResponse.json({ report });
}

export async function DELETE(
  _req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const session = await auth();
  if (!session) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  const { id } = await params;
  const existing = await ownedReport(id, session.user.id);
  if (!existing) return NextResponse.json({ error: "not_found" }, { status: 404 });

  await prisma.bugReport.delete({ where: { id } });
  return NextResponse.json({ ok: true });
}
