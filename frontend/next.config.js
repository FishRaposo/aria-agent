/** @type {import('next').NextConfig} */
// A Pages demo is a static export: no server, no runtime. The normal build stays
// server-capable, so the switch is opt-in per build.
const staticExport = process.env.NEXT_STATIC_EXPORT === "1";
const basePath = process.env.NEXT_BASE_PATH || "";

const nextConfig = {
  reactStrictMode: true,
  distDir: process.env.NEXT_DIST_DIR || ".next",
  ...(staticExport
    ? {
        output: "export",
        trailingSlash: true,
        images: { unoptimized: true },
        basePath: basePath || undefined,
        assetPrefix: basePath || undefined,
      }
    : {}),
};

module.exports = nextConfig;
