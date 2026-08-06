import type { NextConfig } from "next";

import { localApiOrigin } from "./src/lib/api-origin";

const apiOrigin = localApiOrigin();

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/v1/:path*", destination: `${apiOrigin}/api/v1/:path*` }];
  },
};

export default nextConfig;
