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
    if (value) headers.set(name, value);
  }
  headers.set(
    "x-forwarded-host",
    request.headers.get("host") ?? request.nextUrl.host,
  );
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
      if (value) outgoing.set(name, value);
    }
    for (const cookie of upstream.headers.getSetCookie())
      outgoing.append("set-cookie", cookie);
    outgoing.set("cache-control", "no-store, private");
    return new Response(upstream.body, {
      status: upstream.status,
      headers: outgoing,
    });
  } catch {
    return Response.json(
      { detail: "The service is temporarily unavailable. Please try again." },
      { status: 503 },
    );
  }
}

export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
export const PUT = proxy;
export const DELETE = proxy;
