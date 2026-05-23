import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Nav from "@/components/Nav";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "UFC Predictor",
  description: "XGBoost + Elo predictions for upcoming UFC fights, with a public performance log.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-background text-foreground">
        <Nav />
        <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8">{children}</main>
        <footer className="mx-auto w-full max-w-5xl px-4 py-6 text-xs text-neutral-500">
          XGBoost + Elo · open-source on{" "}
          <a
            href="https://github.com/patrickmcalinden/ufc-prediction"
            className="hover:underline"
          >
            GitHub
          </a>
        </footer>
      </body>
    </html>
  );
}
