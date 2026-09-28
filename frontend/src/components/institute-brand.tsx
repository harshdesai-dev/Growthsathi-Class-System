"use client";

import Image from "next/image";
import { useState } from "react";

export function InstituteBrand({ name, hasLogo, size = 40 }: { name: string; hasLogo?: boolean; size?: number }) {
  const [failed, setFailed] = useState(false);
  const initial = name.trim().slice(0, 1).toUpperCase() || "G";
  if (!hasLogo || failed) return <span className="brand-mark" style={{ width: size, height: size, flexBasis: size }}>{initial}</span>;
  return <span className="brand-logo" style={{ width: size, height: size }}><Image src="/api/branding/logo/" width={size} height={size} alt="" unoptimized onError={() => setFailed(true)} /></span>;
}
