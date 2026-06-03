import { create } from "zustand";
import type { VesselLive, LivePositionUpdate } from "../types";

interface VesselStore {
  vessels: Map<number, VesselLive>;
  selectedMmsi: number | null;
  setVessels: (vessels: VesselLive[]) => void;
  updatePosition: (update: LivePositionUpdate) => void;
  selectVessel: (mmsi: number | null) => void;
}

export const useVesselStore = create<VesselStore>((set) => ({
  vessels: new Map(),
  selectedMmsi: null,

  setVessels: (vessels) =>
    set({ vessels: new Map(vessels.map((v) => [v.mmsi, v])) }),

  updatePosition: (update) =>
    set((state) => {
      const vessels = new Map(state.vessels);
      const existing = vessels.get(update.mmsi);
      if (existing) {
        vessels.set(update.mmsi, {
          ...existing,
          lat: update.lat,
          lon: update.lon,
          speed: update.speed ?? existing.speed,
          heading: update.heading ?? existing.heading,
          nav_status: update.nav_status ?? existing.nav_status,
          last_seen: update.time,
        });
      }
      return { vessels };
    }),

  selectVessel: (mmsi) => set({ selectedMmsi: mmsi }),
}));
