import type { Mode } from './types';

export type Preferences = { default_mode?: string; detail_level?: string; spoiler_policy?: string };

export function recommendMode(preferences: Preferences): { mode: Mode; scores: Record<Mode, number> } {
  const scores: Record<Mode, number> = { family: 0, analyst: 0, catch_up: 0 };
  const fallback: Mode = 'family';
  const defaultMode: Mode = preferences.default_mode === 'family' || preferences.default_mode === 'analyst' || preferences.default_mode === 'catch_up'
    ? preferences.default_mode : fallback;
  scores[defaultMode] += 3;
  if (preferences.detail_level === 'advanced') scores.analyst += 2;
  if (preferences.detail_level === 'simple') { scores.family += 1; scores.catch_up += 1; }
  if (preferences.spoiler_policy === 'strict') scores.catch_up += 1;
  const priority: Mode[] = ['analyst', 'family', 'catch_up'];
  const mode = priority.reduce((best, candidate) => scores[candidate] > scores[best] ? candidate : best, defaultMode);
  return { mode, scores };
}

export function intentFromCommand(text: string): 'catch_up' | 'break_down_play' | 'help' {
  const value = text.toLocaleLowerCase();
  if (['catch me up', 'summary', 'what did i miss'].some((phrase) => value.includes(phrase))) return 'catch_up';
  if (['player', 'who is', 'speed', 'break down', 'breakdown', 'analyze', 'analyse', 'play'].some((phrase) => value.includes(phrase))) return 'break_down_play';
  return 'help';
}
