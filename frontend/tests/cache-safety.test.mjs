import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";
import vm from "node:vm";

test("service worker never intercepts private API or record requests for caching", () => {
  const callbacks = new Map();
  const context = {
    URL,
    self: {
      location: { origin: "https://demo.invalid" },
      addEventListener: (name, handler) => callbacks.set(name, handler),
    },
  };
  vm.runInNewContext(
    fs.readFileSync(new URL("../public/sw.js", import.meta.url), "utf8"),
    context,
  );
  let intercepted = false;
  callbacks.get("fetch")({
    request: {
      url: "https://demo.invalid/api/fees/1/receipt/2/",
      method: "GET",
    },
    respondWith: () => {
      intercepted = true;
    },
  });
  assert.equal(intercepted, false);
  callbacks.get("fetch")({
    request: { url: "https://demo.invalid/api/auth/refresh/", method: "POST" },
    respondWith: () => {
      intercepted = true;
    },
  });
  assert.equal(intercepted, false);
});
