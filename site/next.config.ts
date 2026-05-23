import path from "path";
import type { NextConfig } from "next";
import createMDX from "@next/mdx";

const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
  pageExtensions: ["ts", "tsx", "md", "mdx"],
  turbopack: {
    // Anchor at this folder so Next.js doesn't get confused by lockfiles elsewhere.
    root: path.resolve(__dirname),
  },
  // basePath / assetPrefix for GitHub Pages project site are set in Phase 4.
};

const withMDX = createMDX({
  extension: /\.(md|mdx)$/,
});

export default withMDX(nextConfig);
