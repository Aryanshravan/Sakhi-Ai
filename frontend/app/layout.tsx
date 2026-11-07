import type { Metadata } from "next";
import { Plus_Jakarta_Sans } from "next/font/google";
import "./globals.css";

const jakarta = Plus_Jakarta_Sans({
  variable: "--font-jakarta",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Sakhi AI",
  description: "Every child deserves a learning companion.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={jakarta.variable}>
      <body className="min-h-dvh font-sans antialiased">{children}</body>
    </html>
  );
}
