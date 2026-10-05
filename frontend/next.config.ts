import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Bundles only what's needed to run into .next/standalone, so the
  // production image doesn't ship node_modules or the source tree.
  output: "standalone",
};

export default nextConfig;
