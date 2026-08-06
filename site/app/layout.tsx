import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Retirement Conductor — Verified field retirement",
  description:
    "A technical pitch and complete verification guide for Retirement Conductor, the DataHub-native control plane for evidence-backed field retirement.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
