import { createContext, useContext } from "react";

// bascule le sélecteur d'année vers une vague Findex (fourni par App)
export const WaveNavContext = createContext<((year: number) => void) | null>(null);

export function SeeWaveButton({ year }: { year: number }) {
  const goTo = useContext(WaveNavContext);
  if (!goTo) return null;
  return (
    <button type="button" className="wave-link" onClick={() => goTo(year)}>
      Voir l'enquête {year}
    </button>
  );
}
