export const dynamic = "force-dynamic";

export function GET() {
  return Response.json({
    status: "ok",
    service: "ai-lab-frontend",
    checkout_id: process.env.AI_LAB_CHECKOUT_ID ?? null,
    source_fingerprint: process.env.AI_LAB_SOURCE_FINGERPRINT ?? null,
  });
}
