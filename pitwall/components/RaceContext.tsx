"use client";

import { createContext, useContext, useState, ReactNode } from "react";

export interface DriverData {
  code: string;
  constructor: string;
  grid: number | null;
  position: number | null;
  is_dnf: boolean;
  points: number | null;
  q_delta: number | null;
  q_session: string | null;
  champ_pos: number | null;
  constructor_champ_pos: number | null;
  team_rolling_avg_finish: number | null;
  driver_rolling_avg_pts: number | null;
  pace_delta: number | null;
  num_stints: number | null;
  median_lap: number | null;
}

export interface RaceData {
  year: number;
  round: number;
  circuit: string;
  circuit_type: string;
  overtaking_index: number | null;
  is_wet: boolean;
  avg_track_temp: number | null;
  winner: string | null;
  podium: string[];
  drivers: DriverData[];
}

interface RaceContextValue {
  race: RaceData | null;
  loading: boolean;
  setRace: (r: RaceData | null) => void;
  setLoading: (v: boolean) => void;
}

const RaceContext = createContext<RaceContextValue>({
  race: null,
  loading: false,
  setRace: () => {},
  setLoading: () => {},
});

export function RaceProvider({ children }: { children: ReactNode }) {
  const [race, setRace] = useState<RaceData | null>(null);
  const [loading, setLoading] = useState(false);

  return (
    <RaceContext.Provider value={{ race, loading, setRace, setLoading }}>
      {children}
    </RaceContext.Provider>
  );
}

export function useRace() {
  return useContext(RaceContext);
}
