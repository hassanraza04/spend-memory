import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: "Spend Memory",
  description: "A calm place to remember your spending.",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en" data-theme="personal-record">
      <body>{children}</body>
    </html>
  );
}
