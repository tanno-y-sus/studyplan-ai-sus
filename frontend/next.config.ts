import type { NextConfig } from "next";

// 画面からの /api/* をバックエンドに中継する（ブラウザは画面と同じ URL だけにアクセスすればよい）
const backend = process.env.BACKEND_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};

export default nextConfig;
