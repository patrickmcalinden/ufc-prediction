// Server-side JSON loaders. These run at build time (App Router server
// components or generateStaticParams), so plain fs is fine — there's
// no runtime in the static export.

import { promises as fs } from "fs";
import path from "path";

import type {
  Event,
  EventSnapshot,
  PerformancePayload,
  UpcomingPayload,
} from "./types";

const DATA_DIR = path.join(process.cwd(), "public", "data");

async function readJson<T>(rel: string): Promise<T> {
  const raw = await fs.readFile(path.join(DATA_DIR, rel), "utf-8");
  return JSON.parse(raw) as T;
}

export async function getUpcoming(): Promise<UpcomingPayload> {
  return readJson<UpcomingPayload>("upcoming.json");
}

export async function getPerformance(): Promise<PerformancePayload> {
  return readJson<PerformancePayload>("performance.json");
}

export async function getEvents(): Promise<Event[]> {
  return readJson<Event[]>("events.json");
}

export async function getSnapshot(eventId: number): Promise<EventSnapshot> {
  return readJson<EventSnapshot>(`snapshots/${eventId}.json`);
}

export async function listSnapshotIds(): Promise<number[]> {
  const dir = path.join(DATA_DIR, "snapshots");
  try {
    const files = await fs.readdir(dir);
    return files
      .filter((f) => f.endsWith(".json"))
      .map((f) => parseInt(f.replace(".json", ""), 10))
      .filter((n) => Number.isFinite(n));
  } catch {
    return [];
  }
}
