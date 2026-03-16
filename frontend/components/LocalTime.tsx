"use client";

import { useEffect, useState } from "react";

import { formatBackendTimestamp } from "@/lib/time";

export function LocalTime({ value }: { value: string }) {
  const [display, setDisplay] = useState<string>("");

  useEffect(() => {
    setDisplay(formatBackendTimestamp(value));
  }, [value]);

  return <span>{display || "..."}</span>;
}
