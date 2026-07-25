import type { Metadata } from "next";

import { VerificationWorkspace } from "@/features/verification/verification-workspace";

export const metadata: Metadata = {
  title: "Verification",
};

export default function VerificationPage() {
  return <VerificationWorkspace />;
}
