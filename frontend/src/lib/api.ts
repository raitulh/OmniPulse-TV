import { z } from 'zod';
import type { AnalysisResponse, DeviceCodeResponse, MeResponse, Mode, Player, SportEvent, TacticalData, TimelineItem, TokenResponse } from './types';

const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');
const tokenKey = 'omnipulse.session';
const refreshTokenKey = 'omnipulse.refresh';
const authMode = (import.meta.env.VITE_AUTH_MODE || 'demo').toLowerCase();
const cognitoDomain = (import.meta.env.VITE_COGNITO_DOMAIN || '').replace(/\/$/, '');
const cognitoClientId = import.meta.env.VITE_COGNITO_CLIENT_ID || '';
const cognitoRedirectUri = import.meta.env.VITE_COGNITO_REDIRECT_URI || `${window.location.origin}/app`;
const cognitoLogoutUri = import.meta.env.VITE_COGNITO_LOGOUT_URI || window.location.origin;
const verifierKey = 'omnipulse.pkce.verifier';
const stateKey = 'omnipulse.pkce.state';
let authenticationPromise: Promise<void> | null = null;
let onboardingPromise: Promise<void> | null = null;

const errorSchema = z.object({ error: z.object({ code: z.string().optional(), message: z.string().optional(), request_id: z.string().nullable().optional() }).optional(), detail: z.string().optional() }).passthrough();

export class ApiError extends Error {
  status: number;
  code?: string;
  requestId?: string;
  constructor(message: string, status: number, code?: string, requestId?: string) {
    super(message); this.name = 'ApiError'; this.status = status; this.code = code; this.requestId = requestId;
  }
}

export function getStoredToken(): string | null {
  try { return sessionStorage.getItem(tokenKey); } catch { return null; }
}

export function getStoredRefreshToken(): string | null {
  try { return sessionStorage.getItem(refreshTokenKey); } catch { return null; }
}

export function setStoredTokens(accessToken: string, refreshToken?: string): void {
  try {
    sessionStorage.setItem(tokenKey, accessToken);
    if (refreshToken) sessionStorage.setItem(refreshTokenKey, refreshToken);
  } catch { /* storage may be unavailable in TV runtimes */ }
}

export function clearStoredToken(): void {
  try {
    sessionStorage.removeItem(tokenKey);
    sessionStorage.removeItem(refreshTokenKey);
  } catch { /* storage may be unavailable in TV runtimes */ }
}

export async function refreshSession(): Promise<boolean> {
  const currentRefresh = getStoredRefreshToken();
  if (!currentRefresh) return false;
  try {
    const res = await fetch(`${API_BASE}/v1/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ refresh_token: currentRefresh }),
    });
    if (!res.ok) {
      clearStoredToken();
      return false;
    }
    const data = await res.json() as TokenResponse;
    setStoredTokens(data.access_token, data.refresh_token);
    return true;
  } catch {
    return false;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set('Accept', 'application/json');
  if (init.body) headers.set('Content-Type', 'application/json');
  const token = getStoredToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 12_000);
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...init, headers, signal: init.signal || controller.signal, credentials: 'omit' });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw new ApiError('The request timed out. Please try again.', 0, 'TIMEOUT');
    throw new ApiError('Could not reach OmniPulse API. Check that the backend is running.', 0, 'NETWORK_ERROR');
  } finally { window.clearTimeout(timeout); }
  if (!response.ok) {
    if (response.status === 401 && !path.includes('/auth/')) {
      const refreshed = await refreshSession();
      if (refreshed) {
        return request<T>(path, init);
      }
      clearStoredToken();
    }
    let message = `Request failed (${response.status})`; let code: string | undefined; let requestId = response.headers.get('X-Request-ID') || undefined;
    try {
      const parsed = errorSchema.parse(await response.json());
      message = parsed.error?.message || parsed.detail || message;
      code = parsed.error?.code; requestId = parsed.error?.request_id || requestId;
    } catch { /* use safe fallback */ }
    throw new ApiError(message, response.status, code, requestId);
  }
  if (response.status === 204) return undefined as T;
  return await response.json() as T;
}


function bytesToBase64Url(bytes: Uint8Array): string {
  let binary = '';
  bytes.forEach((byte) => { binary += String.fromCharCode(byte); });
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
}

async function createPkcePair(): Promise<{ verifier: string; challenge: string }> {
  const random = crypto.getRandomValues(new Uint8Array(32));
  const verifier = bytesToBase64Url(random);
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier));
  return { verifier, challenge: bytesToBase64Url(new Uint8Array(digest)) };
}

async function beginCognitoLogin(): Promise<never> {
  if (!cognitoDomain || !cognitoClientId) throw new Error('Cognito auth is selected but VITE_COGNITO_DOMAIN or VITE_COGNITO_CLIENT_ID is missing.');
  const { verifier, challenge } = await createPkcePair();
  const state = bytesToBase64Url(crypto.getRandomValues(new Uint8Array(24)));
  sessionStorage.setItem(verifierKey, verifier);
  sessionStorage.setItem(stateKey, state);
  const url = new URL(`${cognitoDomain}/oauth2/authorize`);
  url.search = new URLSearchParams({ response_type: 'code', client_id: cognitoClientId, redirect_uri: cognitoRedirectUri, scope: 'openid email profile', code_challenge_method: 'S256', code_challenge: challenge, state }).toString();
  window.location.assign(url.toString());
  throw new Error('Redirecting to sign in…');
}

async function finishCognitoCallback(): Promise<boolean> {
  const url = new URL(window.location.href);
  const code = url.searchParams.get('code');
  if (!code) return false;
  const returnedState = url.searchParams.get('state');
  const expectedState = sessionStorage.getItem(stateKey);
  const verifier = sessionStorage.getItem(verifierKey);
  if (!returnedState || !expectedState || returnedState !== expectedState || !verifier) throw new Error('Sign-in validation failed. Please restart sign-in.');
  if (!cognitoDomain || !cognitoClientId) throw new Error('Cognito configuration is incomplete.');
  const body = new URLSearchParams({ grant_type: 'authorization_code', client_id: cognitoClientId, code, redirect_uri: cognitoRedirectUri, code_verifier: verifier });
  const response = await fetch(`${cognitoDomain}/oauth2/token`, { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: body.toString(), credentials: 'omit' });
  if (!response.ok) throw new Error('Sign-in token exchange failed. Please sign in again.');
  const tokens = await response.json() as { access_token?: string; expires_in?: number; token_type?: string };
  if (!tokens.access_token) throw new Error('Identity provider did not return an access token.');
  sessionStorage.setItem(tokenKey, tokens.access_token);
  sessionStorage.removeItem(verifierKey); sessionStorage.removeItem(stateKey);
  url.searchParams.delete('code'); url.searchParams.delete('state'); url.searchParams.delete('session_state');
  window.history.replaceState({}, '', `${url.pathname}${url.search}${url.hash}`);
  return true;
}

export async function ensureAuthenticated(): Promise<void> {
  if (authMode === 'demo') {
    if (getStoredToken()) return;
    if (!authenticationPromise) {
      authenticationPromise = demoLogin().then(() => undefined).finally(() => { authenticationPromise = null; });
    }
    await authenticationPromise;
    return;
  }
  if (!authenticationPromise) {
    authenticationPromise = (async () => {
      await finishCognitoCallback();
      if (getStoredToken()) return;
      await beginCognitoLogin();
    })().finally(() => { authenticationPromise = null; });
  }
  await authenticationPromise;
}

export function logout(): void {
  clearStoredToken();
  if (authMode === 'cognito' && cognitoDomain && cognitoClientId) {
    const url = new URL(`${cognitoDomain}/logout`);
    url.search = new URLSearchParams({ client_id: cognitoClientId, logout_uri: cognitoLogoutUri }).toString();
    window.location.assign(url.toString());
  } else window.location.reload();
}

export async function demoLogin(): Promise<{ household_id: string; profile_id: string }> {
  const response = await request<{ access_token: string; household_id: string; profile_id: string }>('/v1/auth/demo', { method: 'POST' });
  try { sessionStorage.setItem(tokenKey, response.access_token); } catch { /* app can still show reconnect state */ }
  return response;
}

export async function getMe(): Promise<MeResponse> { return request('/v1/me'); }
export async function loadCurrentUser(): Promise<MeResponse> {
  try { return await getMe(); }
  catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      clearStoredToken();
      await ensureAuthenticated();
      return getMe();
    }
    if (authMode !== 'cognito' || !(error instanceof ApiError) || error.status !== 403) throw error;
    if (!onboardingPromise) {
      onboardingPromise = request('/v1/onboarding', { method: 'POST', body: JSON.stringify({}) }).then(() => undefined).finally(() => { onboardingPromise = null; });
    }
    await onboardingPromise;
    return getMe();
  }
}
export async function getEvents(): Promise<SportEvent[]> {
  const response = await request<{ items: SportEvent[] }>('/v1/sports/events');
  return response.items;
}
export async function getTactical(eventId: string): Promise<TacticalData> { return request(`/v1/sports/events/${encodeURIComponent(eventId)}/tactical`); }
export async function getTimeline(eventId: string): Promise<TimelineItem[]> {
  const response = await request<{ items: TimelineItem[] }>(`/v1/sports/events/${encodeURIComponent(eventId)}/timeline`);
  return response.items;
}
export async function createViewingSession(eventId: string, mode: Mode) {
  return request<{ id: string; status: string; mode: Mode }>('/v1/sessions', { method: 'POST', body: JSON.stringify({ event_id: eventId, mode }) });
}
export async function resolveMode(eventId: string, overrideMode?: Mode) {
  return request<{ mode: Mode; reason: string; scores: Record<Mode, number>; is_suggestion: boolean }>('/v1/experience/resolve', {
    method: 'POST', body: JSON.stringify({ event_id: eventId, override_mode: overrideMode }),
  });
}
export async function updatePreferences(householdId: string, preferences: Record<string, unknown>) {
  return request(`/v1/households/${encodeURIComponent(householdId)}/preferences`, { method: 'PATCH', body: JSON.stringify(preferences) });
}
export async function runAnalysis(eventId: string, text: string, selectedPlayer?: Player, sessionId?: string) {
  const idempotencyKey = typeof crypto.randomUUID === 'function' ? crypto.randomUUID() : `cmd-${Date.now()}-${Math.random().toString(36).slice(2, 12)}`;
  return request<AnalysisResponse>('/v1/ai/commands', { method: 'POST', headers: { 'Idempotency-Key': idempotencyKey }, body: JSON.stringify({ event_id: eventId, text, selected_player_id: selectedPlayer?.id, session_id: sessionId, idempotency_key: idempotencyKey }) });
}
export async function createCoachSession(exercise: 'squat' | 'stretch' | 'athletic_stance') {
  return request<{ id: string; status: string; raw_media_stored: boolean }>('/v1/coach/sessions', { method: 'POST', body: JSON.stringify({ exercise, consent_recorded: true }) });
}
export async function sendCoachMetric(sessionId: string, metric: { metric_type: 'knee_angle' | 'hip_angle' | 'pose_confidence' | 'repetition_count'; value: number; unit: 'degrees' | 'fraction' | 'count'; confidence?: number }) {
  return request<{ accepted: boolean; metrics_count: number }>(`/v1/coach/sessions/${encodeURIComponent(sessionId)}/metrics`, { method: 'POST', body: JSON.stringify(metric) });
}
export async function completeCoachSession(sessionId: string) {
  return request<{ status: string; summary: { metrics_count: number; note: string } }>(`/v1/coach/sessions/${encodeURIComponent(sessionId)}/complete`, { method: 'PATCH' });
}
export async function sendFeedback(category: 'bug' | 'ux' | 'data_quality' | 'accessibility' | 'other', message: string, context: Record<string, unknown> = {}) {
  return request<{ id: string; status: string }>('/v1/feedback', { method: 'POST', body: JSON.stringify({ category, message, context }) });
}
export async function getHealth() { return request<{ status: string; database: string }>('/health/ready'); }

export async function requestDeviceCode(): Promise<DeviceCodeResponse> {
  return request<DeviceCodeResponse>('/v1/auth/device/code', { method: 'POST', body: JSON.stringify({}) });
}

export async function pollDeviceToken(deviceCode: string): Promise<TokenResponse | null> {
  try {
    const res = await request<TokenResponse>('/v1/auth/device/token', {
      method: 'POST',
      body: JSON.stringify({ device_code: deviceCode }),
    });
    setStoredTokens(res.access_token, res.refresh_token);
    return res;
  } catch (error) {
    if (error instanceof ApiError && (error.message.includes('authorization_pending') || error.status === 400)) {
      return null;
    }
    throw error;
  }
}

export async function authorizeDevice(userCode: string): Promise<{ authorized: boolean; user_code: string }> {
  return request<{ authorized: boolean; user_code: string }>('/v1/auth/device/authorize', {
    method: 'POST',
    body: JSON.stringify({ user_code: userCode }),
  });
}

export function subscribeEventStream(eventId: string, onUpdate: (data: unknown) => void): () => void {
  const token = getStoredToken();
  const url = `${API_BASE}/v1/sports/events/${encodeURIComponent(eventId)}/stream?interval=5`;
  const controller = new AbortController();
  (async () => {
    try {
      const response = await fetch(url, {
        headers: token ? { Authorization: `Bearer ${token}`, Accept: 'text/event-stream' } : { Accept: 'text/event-stream' },
        signal: controller.signal,
      });
      if (!response.ok || !response.body) return;
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';
        for (const block of lines) {
          const match = block.match(/data:\s*(.+)/);
          if (match && match[1]) {
            try {
              onUpdate(JSON.parse(match[1]));
            } catch { /* ignore heartbeat format */ }
          }
        }
      }
    } catch {
      /* stream closed or network disconnected */
    }
  })();
  return () => controller.abort();
}
