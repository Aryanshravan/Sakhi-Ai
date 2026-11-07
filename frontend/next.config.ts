import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  cacheComponents: true,
  partialPrefetching: true,
  // In production the browser talks to /api on this site, which is forwarded to the backend, so the login cookie
  // stays first-party. Set BACKEND_URL (and NEXT_PUBLIC_API_BASE_URL=/api) on the host; locally this is not used.
  async rewrites() {
    const backend = process.env.BACKEND_URL;
    return backend ? [{ source: "/api/:path*", destination: `${backend.replace(/\/$/, "")}/:path*` }] : [];
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
