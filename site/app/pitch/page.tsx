import type { Metadata } from "next";
import { Suspense } from "react";
import { PitchClient } from "./pitch-client";
import "./pitch.css";

export const metadata: Metadata = {
  title: "Retirement Conductor — Three-minute pitch",
  description:
    "The opening deck for the Retirement Conductor three-minute demonstration.",
};

export default function PitchPage() {
  return (
    <Suspense>
      <PitchClient />
    </Suspense>
  );
}
