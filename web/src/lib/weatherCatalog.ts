import { useEffect, useState } from "react";
import { api } from "./api";
import type { WeatherCatalog } from "./types";

let cached: WeatherCatalog | null = null;
let inflight: Promise<WeatherCatalog> | null = null;

/** Stations and task library of the weather tool; fetched once per visit. */
export function useWeatherCatalog(): WeatherCatalog | null {
  const [c, setC] = useState<WeatherCatalog | null>(cached);
  useEffect(() => {
    if (cached) return;
    inflight ??= api.weatherCatalog();
    let live = true;
    inflight.then((x) => { cached = x; if (live) setC(x); }).catch(() => { inflight = null; });
    return () => { live = false; };
  }, []);
  return c;
}

export function newWeatherId(): string {
  const a = new Uint8Array(5); crypto.getRandomValues(a);
  return "W-" + Array.from(a, (b) => b.toString(36).padStart(2, "0")).join("").slice(0, 8);
}
