// Weight units. Every weight is stored in kg; the person's preference (Me page) only
// changes how weights are shown and typed. The pound is exactly 0.45359237 kg (D35).

export type WeightUnit = "kg" | "lb";

export const KG_PER_LB = 0.45359237;

export function fromKg(kg: number, unit: WeightUnit): number {
  return unit === "kg" ? kg : kg / KG_PER_LB;
}

export function toKg(value: number, unit: WeightUnit): number {
  return unit === "kg" ? value : value * KG_PER_LB;
}

/** Rounded to a tenth, without a trailing ".0": 72.5747792 kg in lb -> "160". */
export function weightNumber(kg: number, unit: WeightUnit): string {
  const value = Math.round(fromKg(kg, unit) * 10) / 10;
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

/** Always one decimal, for body weight: 74.84274105 kg -> "74.8 kg" or "165.0 lb". */
export function bodyWeight(kg: number, unit: WeightUnit): string {
  return `${fromKg(kg, unit).toFixed(1)} ${unit}`;
}

/** Whole units with thousands separators, for volume: 3490.9 kg -> "3,491 kg" or "7,696 lb". */
export function volume(kg: number, unit: WeightUnit): string {
  return `${Math.round(fromKg(kg, unit)).toLocaleString("en-US")} ${unit}`;
}
