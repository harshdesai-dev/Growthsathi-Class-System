import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

async function client() {
  const source = await readFile(
    new URL("../src/lib/api.ts", import.meta.url),
    "utf8",
  );
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ESNext,
      target: ts.ScriptTarget.ES2022,
    },
  });
  return import(
    `data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}#${Math.random()}`
  );
}
const response = (status, body) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

test("concurrent expired identity checks share one refresh", async () => {
  const originalFetch = globalThis.fetch;
  const originalWindow = globalThis.window;
  let refreshes = 0;
  let refreshed = false;
  let redirects = 0;
  globalThis.window = {
    location: {
      assign() {
        redirects++;
      },
    },
  };
  globalThis.fetch = async (path) => {
    if (path === "/api/auth/context/")
      return response(200, { csrfToken: "synthetic-test-csrf" });
    if (path === "/api/auth/refresh/") {
      refreshes++;
      await new Promise((resolve) => setTimeout(resolve, 10));
      refreshed = true;
      return response(200, {});
    }
    return refreshed ? response(200, { role: "ADMIN" }) : response(401, {});
  };
  try {
    const { api } = await client();
    const results = await Promise.all([
      api("/api/auth/me/"),
      api("/api/auth/me/"),
    ]);
    assert.equal(refreshes, 1);
    assert.deepEqual(
      results.map((result) => result.role),
      ["ADMIN", "ADMIN"],
    );
    assert.equal(redirects, 0);
  } finally {
    globalThis.fetch = originalFetch;
    globalThis.window = originalWindow;
  }
});

test("a permission denial after refresh does not log the user out", async () => {
  const originalFetch = globalThis.fetch;
  const originalWindow = globalThis.window;
  let requests = 0;
  let redirects = 0;
  globalThis.window = {
    location: {
      assign() {
        redirects++;
      },
    },
  };
  globalThis.fetch = async (path) => {
    if (path === "/api/auth/context/")
      return response(200, { csrfToken: "synthetic-test-csrf" });
    if (path === "/api/auth/refresh/") return response(200, {});
    return response(++requests === 1 ? 401 : 403, { detail: "Forbidden" });
  };
  try {
    const { api } = await client();
    await assert.rejects(api("/api/fees/"), (error) => error.status === 403);
    assert.equal(redirects, 0);
  } finally {
    globalThis.fetch = originalFetch;
    globalThis.window = originalWindow;
  }
});
