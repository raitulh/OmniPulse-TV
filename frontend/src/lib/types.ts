export type Mode = 'family' | 'analyst' | 'catch_up';
export type SportEvent = {
  id: string; sport: string; league: string; title: string; home_team: string; away_team: string;
  status: string; source_type: 'sample' | 'provider'; score_home: number | null; score_away: number | null;
  starts_at: string | null; updated_at: string | null;
};
export type Player = {
  id: string; name: string; team: string; role: string; x: number; y: number; speed_kph?: number;
  source_type: 'sample' | 'provider';
};
export type TacticalData = {
  event_id: string; source_type: 'sample' | 'provider' | 'unavailable';
  field: { width: number; height: number; coordinate_system: string; source_type: string };
  players: Player[]; connections: { from: string; to: string; label: string; source_type: string }[];
};
export type TimelineItem = {
  id: string; clock_seconds: number; minute: number; type: string; team: string;
  player_id: string; target_player_id?: string; label: string; source_type: string;
};
export type Profile = { id: string; nickname: string; profile_type: string; preferences: Record<string, unknown> };
export type MeResponse = { subject: string; demo: boolean; household: { id: string; name: string }; profile: Profile };
export type AnalysisResponse = {
  command_id: string; intent: string; mode: Mode; source_type: string; provider: string;
  analysis: { summary: string; player_ids: string[] };
  visualization: { type: string; focus_id: string | null; nodes: Player[] };
  created_at: string;
};
export type DeviceCodeResponse = {
  device_code: string; user_code: string; verification_uri: string;
  verification_uri_complete: string; expires_in: number; interval: number;
};
export type TokenResponse = {
  access_token: string; refresh_token: string; token_type: string;
  expires_in_seconds: number; household_id: string; profile_id: string;
};
