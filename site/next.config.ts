import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
  // basePath / assetPrefix for GitHub Pages project site are set in Phase 4.
};

export default nextConfig;
