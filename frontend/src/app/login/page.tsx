"use client";
import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type Branding, context, message, type User } from "@/lib/api";

export default function Login() {
  const [branding, setBranding] = useState<Branding | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    context()
      .then(setBranding)
      .catch((e) => setError(message(e)));
  }, []);
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      const result = await api<{ user: User }>("/api/auth/login/", "POST", {
        username: form.get("username"),
        password: form.get("password"),
      });
      window.location.assign(result.user.route);
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="auth-page">
      <section className="auth-card">
        <span className="eyebrow">YOUR CLASSROOM, CONNECTED</span>
        {branding?.has_logo && (
          <Image
            src="/api/branding/logo/"
            width={64}
            height={64}
            alt={`${branding.name} logo`}
            unoptimized
          />
        )}
        <h1>{branding?.name ?? "Welcome"}</h1>
        <p className="muted">
          Sign in to your {branding?.platform ? "platform" : "institute"}{" "}
          account.
        </p>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        {!branding && !error && <p role="status">Loading your institute...</p>}
        {branding && (
          <form onSubmit={submit}>
            <label>
              Username
              <input
                name="username"
                autoComplete="username"
                required
                maxLength={150}
              />
            </label>
            <label>
              Password
              <input
                type="password"
                name="password"
                autoComplete="current-password"
                required
                maxLength={256}
              />
            </label>
            <button type="submit" disabled={busy}>
              {busy ? "Signing in..." : "Sign in"}
            </button>
          </form>
        )}
        <Link href="/account/forgot">Forgot password?</Link>
        <p className="provider">Powered by GrowthSathi</p>
      </section>
    </main>
  );
}
