/** @type {import('next').NextConfig} */
const apiOrigin = process.env.BIOPULSE_API_ORIGIN?.replace(/\/$/, "");

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    if (!apiOrigin) return [];
    return [{ source: "/api/:path*", destination: `${apiOrigin}/api/:path*` }];
  },
};
export default nextConfig;
