/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  async rewrites() {
    const raw = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const root = raw.replace(/\/$/, "").replace(/\/api\/v[12]$/, "");
    return [
      { source: "/api/v2/:path*", destination: `${root}/api/v2/:path*` },
      { source: "/api/v1/:path*", destination: `${root}/api/v1/:path*` },
    ];
  },
};

export default nextConfig;
