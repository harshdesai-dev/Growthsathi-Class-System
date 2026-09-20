import type { MetadataRoute } from "next";
import { headers } from "next/headers";
export const dynamic = "force-dynamic";
export default async function manifest(): Promise<MetadataRoute.Manifest> {
  const host = (await headers()).get("host") ?? "localhost";
  let name = "Class Portal";
  let color = "#2563eb";
  try {
    const response = await fetch(
      `${process.env.API_BACKEND_URL ?? "http://127.0.0.1:8000"}/api/auth/context/`,
      { headers: { "x-forwarded-host": host }, cache: "no-store" },
    );
    if (response.ok) {
      const branding = await response.json();
      name = branding.name;
      color = branding.primary_color ?? color;
    }
  } catch {}
  return {
    name,
    short_name: name.slice(0, 24),
    description: "Your institute learning workspace",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#f3f6fa",
    theme_color: color,
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png" },
      {
        src: "/icon-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
  };
}
