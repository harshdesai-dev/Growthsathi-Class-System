"use client";
import Link from "next/link";
import { use, useEffect, useState } from "react";
import { api, context, message } from "@/lib/api";
export default function Account({
  params,
}: {
  params: Promise<{ mode: string }>;
}) {
  const { mode } = use(params);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    context().catch((e) => setError(message(e)));
  }, []);
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const fields = Object.fromEntries(new FormData(event.currentTarget));
    try {
      const fragment = new URLSearchParams(window.location.hash.slice(1));
      let path = "password/";
      let payload: unknown = fields;
      if (mode === "forgot") path = "reset/";
      if (mode === "reset" || mode === "activate") {
        path = mode === "reset" ? "reset/confirm/" : "activate/";
        payload = {
          ...fields,
          uid: fragment.get("uid"),
          token: fragment.get("token"),
        };
      }
      const result = await api<{ detail: string }>(
        `/api/auth/${path}`,
        "POST",
        payload,
      );
      setNotice(result.detail);
      if (mode !== "forgot")
        window.history.replaceState(null, "", window.location.pathname);
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="auth-page">
      <section className="auth-card">
        <h1>
          {mode === "forgot"
            ? "Recover your account"
            : mode === "activate"
              ? "Activate your account"
              : "Set your password"}
        </h1>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        {notice ? (
          <p role="status">{notice}</p>
        ) : (
          <form onSubmit={submit}>
            {mode === "forgot" ? (
              <label>
                Institute username
                <input name="username" autoComplete="username" required />
              </label>
            ) : (
              <>
                {mode === "password" && (
                  <label>
                    Current or temporary password
                    <input
                      type="password"
                      name="current_password"
                      autoComplete="current-password"
                      required
                    />
                  </label>
                )}
                <label>
                  New password
                  <input
                    type="password"
                    name="password"
                    minLength={12}
                    maxLength={256}
                    autoComplete="new-password"
                    required
                  />
                </label>
                <p className="muted">
                  Use at least 12 characters. Avoid common passwords and
                  personal details.
                </p>
              </>
            )}
            <button type="submit" disabled={busy}>
              {busy ? "Saving..." : "Continue"}
            </button>
          </form>
        )}
        <Link href="/login">Back to sign in</Link>
      </section>
    </main>
  );
}
