import type { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

async function proxy(request: NextRequest) {
  const backend = new URL(
    process.env.API_BACKEND_URL ?? "http://127.0.0.1:8000",
  );

  const target = new URL(
    request.nextUrl.pathname.replace(/\/?$/, "/") + request.nextUrl.search,
    backend,
  );

  const headers = new Headers();

  for (const name of [
    "cookie",
    "content-type",
    "x-csrftoken",
    "origin",
    "referer",
  ]) {
    const value = request.headers.get(name);

    if (value) {
      headers.set(name, value);
    }
  }

  /*
   * Railway controls the normal X-Forwarded-Host header.
   *
   * GrowthSathi needs the original public frontend hostname for secure
   * platform/institute tenant resolution, so Vercel forwards it through
   * private application-specific headers.
   *
   * Django will trust these headers only when the shared proxy secret
   * matches PROXY_TENANT_SECRET.
   */
  const originalHost = request.headers.get("host") ?? request.nextUrl.host;

  const proxyTenantSecret = process.env.PROXY_TENANT_SECRET;

  if (proxyTenantSecret) {
    headers.set("x-growthsathi-host", originalHost);
    headers.set("x-growthsathi-proxy-secret", proxyTenantSecret);
  }

  try {
    const upstream = await fetch(target, {
      method: request.method,
      headers,
      body: ["GET", "HEAD"].includes(request.method)
        ? undefined
        : await request.arrayBuffer(),
      redirect: "manual",
      cache: "no-store",
    });

    const outgoing = new Headers();

    for (const name of [
      "content-type",
      "content-disposition",
      "x-content-type-options",
      "content-security-policy",
    ]) {
      const value = upstream.headers.get(name);

      if (value) {
        outgoing.set(name, value);
      }
    }

    for (const cookie of upstream.headers.getSetCookie()) {
      outgoing.append("set-cookie", cookie);
    }

    outgoing.set("cache-control", "no-store, private");

    return new Response(upstream.body, {
      status: upstream.status,
      headers: outgoing,
    });
  } catch {
    return Response.json(
      {
        detail: "The service is temporarily unavailable. Please try again.",
      },
      {
        status: 503,
      },
    );
  }
}

export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
export const PUT = proxy;
export const DELETE = proxy;
