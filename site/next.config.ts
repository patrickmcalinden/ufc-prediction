import path from "path";
import type { NextConfig } from "next";
import createMDX from "@next/mdx";

// On GitHub Pages, the project site lives at /<repo>/, so set
// NEXT_PUBLIC_BASE_PATH=/ufc-prediction in CI. Empty in local dev so
// http://localhost:3000/ keeps working without a prefix.
const basePath = process.env.NEXT_PUBLIC_BASE_PATH || "";

const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
  pageExtensions: ["ts", "tsx", "md", "mdx"],
  basePath: basePath || undefined,
  assetPrefix: basePath || undefined,
  turbopack: {
    // Anchor at this folder so Next.js doesn't get confused by lockfiles elsewhere.
    root: path.resolve(__dirname),
  },
};

const withMDX = createMDX({
  extension: /\.(md|mdx)$/,
});

export default withMDX(nextConfig);
