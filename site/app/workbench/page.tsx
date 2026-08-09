import type { Metadata } from "next";
import { WorkbenchClient } from "./workbench-client";
import "./workbench.css";

export const metadata: Metadata = {
  title: "Retirement Workbench — Retirement Conductor",
  description:
    "A focused operator surface for one evidence-backed field retirement campaign.",
};

export default function WorkbenchPage() {
  return <WorkbenchClient />;
}
