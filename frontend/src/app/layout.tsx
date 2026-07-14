import type { Metadata } from "next";
import { Figtree, Geist_Mono } from "next/font/google";
import "./globals.css";

// Figtree (Google) — the UI + input font. Self-hosted by next/font, exposed as --font-sans.
const figtree = Figtree({
  variable: "--font-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "ReachBot",
  description: "Reach Capital's AI assistant for portfolio founders.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`dark ${figtree.variable} ${geistMono.variable} h-full antialiased`}
    >
      <head>
        {/* P22 Mackinac Pro (Adobe Typekit) — used for chatbot answer body via --font-serif */}
        <link rel="stylesheet" href="https://use.typekit.net/hlk3lzl.css" />
      </head>
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
