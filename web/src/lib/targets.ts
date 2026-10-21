// Validation for the Me page form (UI_SPEC.md 6.3 sanity limits; the API checks the same
// limits in api/app/me.py). Pure, unit tested in targets.test.ts.

export interface ProfileInput {
  nickname: string;
  calorieBudget: string; // raw text from the inputs
  proteinGoal: string;
}

export interface ProfileErrors {
  nickname?: string;
  calorieBudget?: string;
  proteinGoal?: string;
}

export const LIMITS = {
  calorieBudget: { min: 800, max: 6000 },
  proteinGoal: { min: 0, max: 400 },
};

function wholeNumber(text: string): number | null {
  return /^\d+$/.test(text.trim()) ? Number(text.trim()) : null;
}

export function validateProfile(input: ProfileInput): ProfileErrors {
  const errors: ProfileErrors = {};
  if (input.nickname.trim().length > 40) errors.nickname = "Keep it to 40 characters.";

  const budgetText = input.calorieBudget.trim();
  const proteinText = input.proteinGoal.trim();
  if (!budgetText && !proteinText) return errors; // targets left as they are

  const budget = wholeNumber(budgetText);
  const { min: bMin, max: bMax } = LIMITS.calorieBudget;
  if (budget === null || budget < bMin || budget > bMax) {
    errors.calorieBudget = `Enter a whole number from ${bMin} to ${bMax.toLocaleString("en-US")}.`;
  }

  const protein = wholeNumber(proteinText);
  const { min: pMin, max: pMax } = LIMITS.proteinGoal;
  if (protein === null || protein < pMin || protein > pMax) {
    errors.proteinGoal = `Enter a whole number from ${pMin} to ${pMax}.`;
  }
  return errors;
}
