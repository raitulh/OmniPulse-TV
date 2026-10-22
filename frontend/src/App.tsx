import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import {
  Activity, ArrowRight, ArrowUpRight, BarChart3, BrainCircuit, Check, ChevronDown,
  ChevronRight, CircleHelp, Clock3, Command, Compass, Database, Fingerprint,
  Gauge, House, LifeBuoy, LoaderCircle, LockKeyhole, LogOut, Mic, Play,
  Settings2, ShieldCheck, Sparkles, Trophy, Tv, Users, X,
} from 'lucide-react';
import PoseCoach from './features/coach/PoseCoach';
import { useSpatialFocus } from './hooks/useSpatialFocus';
import {
  ApiError, authorizeDevice, clearStoredToken, createViewingSession, ensureAuthenticated, getEvents, getHealth,
  loadCurrentUser, getTactical, getTimeline, logout, pollDeviceToken, requestDeviceCode, resolveMode, runAnalysis,
  sendFeedback, subscribeEventStream, updatePreferences,
} from './lib/api';
import type { AnalysisResponse, DeviceCodeResponse, MeResponse, Mode, Player, SportEvent, TacticalData, TimelineItem } from './lib/types';
import { intentFromCommand, recommendMode } from './lib/experience';

const sampleEvent: SportEvent = {
  id: 'demo-football-001', sport: 'football', league: 'OmniPulse Sample League',
  title: 'North City vs Harbor United', home_team: 'North City', away_team: 'Harbor United',
  status: 'sample', source_type: 'sample', score_home: 2, score_away: 1,
  starts_at: null, updated_at: null,
};
const sampleTactical: TacticalData = {
  event_id: sampleEvent.id, source_type: 'sample',
  field: { width: 100, height: 100, coordinate_system: 'normalized-0-100', source_type: 'sample' },
  players: [
    { id: 'player-07', name: 'A. Rivera', team: 'North City', role: 'Midfielder', x: 33, y: 42, speed_kph: 21.4, source_type: 'sample' },
    { id: 'player-12', name: 'M. Chen', team: 'North City', role: 'Forward', x: 58, y: 34, speed_kph: 26.1, source_type: 'sample' },
    { id: 'player-04', name: 'J. Okafor', team: 'Harbor United', role: 'Defender', x: 67, y: 58, speed_kph: 19.2, source_type: 'sample' },
    { id: 'player-09', name: 'S. Rahman', team: 'Harbor United', role: 'Midfielder', x: 42, y: 68, speed_kph: 23.0, source_type: 'sample' },
    { id: 'player-18', name: 'T. Brooks', team: 'North City', role: 'Winger', x: 72, y: 24, speed_kph: 28.3, source_type: 'sample' },
    { id: 'player-03', name: 'L. Silva', team: 'Harbor United', role: 'Goalkeeper', x: 91, y: 50, speed_kph: 0, source_type: 'sample' },
  ],
  connections: [{ from: 'player-07', to: 'player-12', label: 'pass', source_type: 'sample' }, { from: 'player-12', to: 'player-18', label: 'run option', source_type: 'sample' }],
};
const sampleTimeline: TimelineItem[] = [
  { id: 'evt-001', clock_seconds: 210, minute: 4, type: 'pass', team: 'North City', player_id: 'player-07', target_player_id: 'player-12', label: 'Progressive pass', source_type: 'sample' },
  { id: 'evt-002', clock_seconds: 1425, minute: 24, type: 'shot', team: 'North City', player_id: 'player-12', label: 'Shot on target', source_type: 'sample' },
  { id: 'evt-003', clock_seconds: 2680, minute: 45, type: 'pass', team: 'Harbor United', player_id: 'player-09', target_player_id: 'player-04', label: 'Switch of play', source_type: 'sample' },
];
type Tab = 'home' | 'xray' | 'household' | 'coach' | 'settings' | 'landing' | 'activate';
type Recognition = { lang: string; interimResults: boolean; onresult: ((event: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null; onerror: (() => void) | null; onend: (() => void) | null; start: () => void; stop: () => void };
type SpeechWindow = Window & { SpeechRecognition?: new () => Recognition; webkitSpeechRecognition?: new () => Recognition };

function IconButton({ children, onClick, className = '', label }: { children: ReactNode; onClick: () => void; className?: string; label: string }) {
  return <button className={`icon-button ${className}`} aria-label={label} title={label} onClick={onClick} data-focusable="true">{children}</button>;
}
function SourceChip({ source }: { source: string }) { const label = source === 'provider' ? 'PROVIDER DATA' : source === 'sample' ? 'SAMPLE DATA' : 'DATA UNAVAILABLE'; return <span className={`source-chip ${source === 'provider' ? 'source-provider' : source === 'sample' ? 'source-sample' : 'source-unavailable'}`}>{label}</span>; }

function teamInitials(name: string): string {
  return name.trim().split(/\s+/).slice(0, 2).map((part) => part[0] || '').join('').toUpperCase() || '—';
}

export default function App() {
  const [tab, setTab] = useState<Tab>(window.location.pathname === '/landing' ? 'landing' : window.location.pathname === '/activate' ? 'activate' : 'home');
  const [me, setMe] = useState<MeResponse | null>(null);
  const [events, setEvents] = useState<SportEvent[]>([]);
  const [activeEventId, setActiveEventId] = useState(sampleEvent.id);
  const [tactical, setTactical] = useState<TacticalData>(sampleTactical);
  const [timeline, setTimeline] = useState<TimelineItem[]>(sampleTimeline);
  const [activeSessionId, setActiveSessionId] = useState<string | undefined>();
  const [mode, setMode] = useState<Mode>('analyst');
  const [selectedPlayerId, setSelectedPlayerId] = useState('player-07');
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [commandText, setCommandText] = useState('Break down this play');
  const [voiceOpen, setVoiceOpen] = useState(false);
  const [voiceState, setVoiceState] = useState<'idle' | 'listening' | 'processing'>('idle');
  const [deviceModalOpen, setDeviceModalOpen] = useState(false);
  const [deviceCodeData, setDeviceCodeData] = useState<DeviceCodeResponse | null>(null);
  const [exitModalOpen, setExitModalOpen] = useState(false);
  const [apiReady, setApiReady] = useState(false);
  const [booting, setBooting] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<{ text: string; error?: boolean } | null>(null);
  const [feedback, setFeedback] = useState('');
  const [detailLevel, setDetailLevel] = useState('advanced');
  const [spoilers, setSpoilers] = useState('avoid');
  const [motionReduced, setMotionReduced] = useState(() => { try { return localStorage.getItem('omnipulse.reduceMotion') === 'true'; } catch { return false; } });
  const recognitionRef = useRef<Recognition | null>(null);
  const priorFocusRef = useRef<HTMLElement | null>(null);
  useSpatialFocus(tab !== 'landing' && tab !== 'activate');

  const activeEvent = useMemo(() => events.find((event) => event.id === activeEventId) || sampleEvent, [events, activeEventId]);
  const selectedPlayer = useMemo(() => tactical.players.find((player) => player.id === selectedPlayerId), [tactical.players, selectedPlayerId]);

  useEffect(() => {
    document.documentElement.classList.toggle('reduce-motion', motionReduced);
    try { localStorage.setItem('omnipulse.reduceMotion', String(motionReduced)); } catch { /* storage may be unavailable on some TV runtimes */ }
  }, [motionReduced]);

  useEffect(() => {
    let alive = true;
    async function boot() {
      setBooting(true);
      try {
        await ensureAuthenticated();
        const [profile, eventList, health] = await Promise.all([loadCurrentUser(), getEvents(), getHealth()]);
        if (!alive) return;
        setMe(profile); setEvents(eventList); setApiReady(health.status === 'ready');
        if (eventList.length) setActiveEventId(eventList[0].id);
        const prefs = profile.profile.preferences;
        if (prefs.default_mode === 'family' || prefs.default_mode === 'analyst' || prefs.default_mode === 'catch_up') setMode(prefs.default_mode);
        if (typeof prefs.detail_level === 'string') setDetailLevel(prefs.detail_level);
        if (typeof prefs.spoiler_policy === 'string') setSpoilers(prefs.spoiler_policy);
      } catch (error) {
        if (!alive) return;
        setApiReady(false);
        setToast({ text: error instanceof Error ? error.message : 'API is unavailable. The sample preview is still available.', error: true });
      } finally { if (alive) setBooting(false); }
    }
    void boot();
    return () => { alive = false; recognitionRef.current?.stop(); };
  }, []);

  useEffect(() => {
    if (tab !== 'xray' || !activeEventId) return;
    let alive = true;
    void Promise.all([getTactical(activeEventId), getTimeline(activeEventId)]).then(([nextTactical, nextTimeline]) => {
      if (!alive) return;
      setTactical(nextTactical); setTimeline(nextTimeline);
      if (!nextTactical.players.some((player) => player.id === selectedPlayerId)) setSelectedPlayerId(nextTactical.players[0]?.id || '');
    }).catch(() => {
      if (!alive) return;
      setTactical(activeEventId === sampleEvent.id ? sampleTactical : { event_id: activeEventId, source_type: 'unavailable', field: { width: 100, height: 100, coordinate_system: 'normalized-0-100', source_type: 'unavailable' }, players: [], connections: [] }); setTimeline(activeEventId === sampleEvent.id ? sampleTimeline : []);
    });
    return () => { alive = false; };
  }, [tab, activeEventId]);

  useEffect(() => {
    if (!toast) return;
    const id = window.setTimeout(() => setToast(null), 4500);
    return () => window.clearTimeout(id);
  }, [toast]);

  function navigate(next: Tab) {
    setTab(next);
    const path = next === 'landing' ? '/landing' : next === 'activate' ? '/activate' : '/app';
    if (window.location.pathname !== path) window.history.pushState({}, '', path);
  }

  useEffect(() => {
    const onPop = () => {
      const p = window.location.pathname;
      setTab(p === '/landing' ? 'landing' : p === '/activate' ? 'activate' : 'home');
    };
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  useEffect(() => {
    if (voiceOpen || deviceModalOpen || exitModalOpen) {
      priorFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      const selector = deviceModalOpen ? '.device-auth-modal [data-focusable="true"]' : exitModalOpen ? '.exit-modal [data-focusable="true"]' : '.voice-modal input[data-focusable="true"]';
      const frame = window.requestAnimationFrame(() => document.querySelector<HTMLElement>(selector)?.focus({ preventScroll: true }));
      return () => window.cancelAnimationFrame(frame);
    }
    if (priorFocusRef.current?.isConnected) priorFocusRef.current.focus({ preventScroll: true });
    return undefined;
  }, [voiceOpen, deviceModalOpen, exitModalOpen]);

  useEffect(() => {
    const onKeyboardBack = (event: KeyboardEvent) => {
      const back = event.key === 'Escape' || event.key === 'BrowserBack' || event.key === 'Backspace' || event.keyCode === 10009 || event.keyCode === 4;
      if (back) {
        if (voiceOpen) {
          event.preventDefault(); recognitionRef.current?.stop(); setVoiceOpen(false); return;
        }
        if (deviceModalOpen) {
          event.preventDefault(); setDeviceModalOpen(false); return;
        }
        if (exitModalOpen) {
          event.preventDefault(); setExitModalOpen(false); return;
        }
        if (tab !== 'home' && tab !== 'landing' && tab !== 'activate') {
          event.preventDefault(); navigate('home'); return;
        }
        if (tab === 'home') {
          event.preventDefault(); setExitModalOpen(true); return;
        }
      }
      if ((voiceOpen || deviceModalOpen || exitModalOpen) && event.key === 'Tab') {
        const modal = document.querySelector<HTMLElement>('[role="dialog"][aria-modal="true"]');
        const items = [...(modal || document).querySelectorAll<HTMLElement>('[data-focusable="true"]:not([disabled])')];
        if (!items.length) return;
        const first = items[0]; const last = items[items.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      }
    };
    window.addEventListener('keydown', onKeyboardBack);
    return () => window.removeEventListener('keydown', onKeyboardBack);
  }, [voiceOpen, deviceModalOpen, exitModalOpen, tab]);

  async function openDeviceAuthModal() {
    try {
      const res = await requestDeviceCode();
      setDeviceCodeData(res);
      setDeviceModalOpen(true);
    } catch (error) { showError(error); }
  }

  useEffect(() => {
    if (!deviceModalOpen || !deviceCodeData) return;
    let cancelled = false;
    const interval = window.setInterval(async () => {
      try {
        const tokens = await pollDeviceToken(deviceCodeData.device_code);
        if (tokens && !cancelled) {
          window.clearInterval(interval);
          setDeviceModalOpen(false);
          setToast({ text: 'TV authorized and connected!' });
          const user = await loadCurrentUser();
          setMe(user);
        }
      } catch { /* pending authorization */ }
    }, (deviceCodeData.interval || 5) * 1000);
    return () => { cancelled = true; window.clearInterval(interval); };
  }, [deviceModalOpen, deviceCodeData]);

  useEffect(() => {
    if (tab !== 'xray' || !activeEventId || !apiReady) return;
    const unsubscribe = subscribeEventStream(activeEventId, () => {
      // live stream heartbeat
    });
    return () => unsubscribe();
  }, [tab, activeEventId, apiReady]);

  async function openXray(eventId = activeEventId, chosenMode = mode) {
    setActiveEventId(eventId);
    setActiveSessionId(undefined);
    setAnalysis(null);
    navigate('xray');
    if (apiReady) {
      try {
        const session = await createViewingSession(eventId, chosenMode);
        setActiveSessionId(session.id);
      } catch (error) { showError(error); }
    }
  }

  function showError(error: unknown) {
    const message = error instanceof ApiError ? `${error.message}${error.requestId ? ` (${error.requestId})` : ''}` : error instanceof Error ? error.message : 'Something went wrong.';
    setToast({ text: message, error: true });
  }

  async function submitCommand(text: string, player?: Player) {
    if (!text.trim()) return;
    setVoiceState('processing');
    try {
      const result = await runAnalysis(activeEventId, text.trim(), player, activeSessionId);
      setAnalysis(result);
      if (result.visualization.focus_id) setSelectedPlayerId(result.visualization.focus_id);
      setToast({ text: `Analysis ready · ${result.provider} provider` });
    } catch (error) {
      showError(error);
      setAnalysis({ command_id: 'local-preview', intent: intentFromCommand(text), mode, source_type: 'sample', provider: 'local-preview', analysis: { summary: 'API analysis is unavailable. This preview is sample-only; reconnect the backend to get the saved analysis workflow.', player_ids: player ? [player.id] : [] }, visualization: { type: 'tactical_nodes', focus_id: player?.id || null, nodes: player ? [player] : tactical.players.slice(0, 3) }, created_at: new Date().toISOString() });
    } finally { setVoiceState('idle'); }
  }

  function startVoice() {
    const speechWindow = window as SpeechWindow;
    const Speech = speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition;
    setVoiceOpen(true);
    if (!Speech) {
      setToast({ text: 'Browser speech recognition is unavailable. Type the command in the voice panel instead.' });
      return;
    }
    try {
      const recognition = new Speech();
      recognition.lang = 'en-US'; recognition.interimResults = false;
      recognition.onresult = (event) => {
        const text = event.results[0]?.[0]?.transcript;
        if (text) { setCommandText(text); void submitCommand(text, selectedPlayer); }
      };
      recognition.onerror = () => { setVoiceState('idle'); setToast({ text: 'Voice capture failed. Type the command instead.', error: true }); };
      recognition.onend = () => setVoiceState('idle');
      recognitionRef.current = recognition;
      setVoiceState('listening'); recognition.start();
    } catch { setVoiceState('idle'); setToast({ text: 'Voice capture cannot start on this platform. Use typed commands.', error: true }); }
  }

  async function savePreferences() {
    if (!me) { setToast({ text: 'Connect the backend before saving preferences.', error: true }); return; }
    setSaving(true);
    try {
      await updatePreferences(me.household.id, { default_mode: mode, detail_level: detailLevel, spoiler_policy: spoilers });
      setMe({ ...me, profile: { ...me.profile, preferences: { ...me.profile.preferences, default_mode: mode, detail_level: detailLevel, spoiler_policy: spoilers } } });
      setToast({ text: 'Preferences saved to the backend.' });
    } catch (error) { showError(error); }
    finally { setSaving(false); }
  }

  async function sendUserFeedback() {
    if (feedback.trim().length < 4) { setToast({ text: 'Please add a little more detail to your feedback.', error: true }); return; }
    try { await sendFeedback('ux', feedback.trim(), { screen: tab, app_version: '0.1.0' }); setFeedback(''); setToast({ text: 'Feedback recorded.' }); }
    catch (error) { showError(error); }
  }

  if (tab === 'landing') return <Landing onLaunch={() => navigate('home')} onDemo={() => openXray(sampleEvent.id)} />;
  if (tab === 'activate') return <ActivateScreen onReturn={() => navigate('home')} />;

  return <div className={`app-shell ${motionReduced ? 'reduce-motion' : ''}`}>
    <aside className="sidebar">
      <button className="brand-lockup" onClick={() => navigate('home')} data-focusable="true" aria-label="OmniPulse TV home"><span className="brand-mark"><Activity size={22}/></span><span className="brand-copy"><strong>omnipulse</strong><small>SPORTS INTELLIGENCE</small></span></button>
      <div className="side-label">EXPERIENCE</div>
      <nav className="nav-list" aria-label="Main navigation">
        <NavItem active={tab === 'home'} onClick={() => navigate('home')} icon={<House size={19}/>} label="Watch Hub"/>
        <NavItem active={tab === 'xray'} onClick={() => void openXray()} icon={<Activity size={19}/>} label="Sports X-Ray" badge="AI"/>
        <NavItem active={tab === 'household'} onClick={() => navigate('household')} icon={<Users size={19}/>} label="Household"/>
        <NavItem active={tab === 'coach'} onClick={() => navigate('coach')} icon={<Gauge size={19}/>} label="Active Coach"/>
      </nav>
      <div className="side-label side-label-lower">PREFERENCES</div>
      <nav className="nav-list"><NavItem active={tab === 'settings'} onClick={() => navigate('settings')} icon={<Settings2 size={19}/>} label="Settings"/><NavItem active={false} onClick={() => navigate('landing')} icon={<Compass size={19}/>} label="Product website"/></nav>
      <div className="sidebar-bottom">
        <div className="connected-card"><div className="connected-head"><span className={`status-dot ${apiReady ? 'online' : 'offline'}`}/><span>{apiReady ? 'Backend connected' : 'Preview mode'}</span></div><p>{apiReady ? 'Preferences persist through the API.' : 'Connect the local API for saved state.'}</p><SourceChip source={activeEvent.source_type}/></div>
        <div className="viewer-row"><div className="avatar">{me?.profile.nickname?.slice(0, 1).toUpperCase() || 'V'}</div><div className="viewer-copy"><strong>{me?.profile.nickname || 'Guest viewer'}</strong><span>{me?.demo ? 'DEMO PROFILE' : 'VIEWER PROFILE'}</span></div><ChevronDown size={16} className="muted"/></div>
      </div>
    </aside>

    <main className="main-content">
      <header className="topbar"><div className="breadcrumbs"><span>OmniPulse</span><ChevronRight size={14}/><strong>{({ home: 'Watch Hub', xray: 'Sports X-Ray', household: 'Household', coach: 'Active Coach', settings: 'Settings', landing: 'Landing', activate: 'Activate' } as Record<Tab,string>)[tab]}</strong></div><div className="topbar-actions"><button className="button button-quiet" onClick={() => void openDeviceAuthModal()} data-focusable="true" style={{ minHeight: 35, padding: '0 11px', fontSize: 11 }}><Tv size={15}/> Link TV</button><span className={`system-pill ${apiReady ? 'good' : 'warn'}`}><span className="status-dot"/>{apiReady ? 'SYSTEM READY' : 'SAMPLE PREVIEW'}</span><IconButton label="Help and product info" onClick={() => setToast({ text: 'Sample dataset only. Check README for setup and platform limitations.' })}><CircleHelp size={18}/></IconButton></div></header>
      {booting && <div className="boot-banner"><LoaderCircle className="spin" size={16}/> Connecting to OmniPulse services…</div>}

      {tab === 'home' && <HomeScreen event={activeEvent} events={events.length ? events : [sampleEvent]} mode={mode} onMode={setMode} onOpen={openXray} onNavigate={navigate} apiReady={apiReady} onDeviceAuth={() => void openDeviceAuthModal()} />}
      {tab === 'xray' && <XrayScreen event={activeEvent} tactical={tactical} timeline={timeline} selectedPlayer={selectedPlayer} selectedPlayerId={selectedPlayerId} setSelectedPlayerId={setSelectedPlayerId} analysis={analysis} commandText={commandText} setCommandText={setCommandText} onAnalyze={() => void submitCommand(commandText, selectedPlayer)} onPlayerAnalyze={(player) => { setSelectedPlayerId(player.id); void submitCommand(`Analyze player ${player.id}`, player); }} onVoice={startVoice} voiceState={voiceState} onBack={() => navigate('home')} />}
      {tab === 'household' && <HouseholdScreen me={me} mode={mode} setMode={setMode} detailLevel={detailLevel} setDetailLevel={setDetailLevel} spoilers={spoilers} setSpoilers={setSpoilers} onSave={() => void savePreferences()} saving={saving} onOpen={openXray} />}
      {tab === 'coach' && <PoseCoach onBack={() => navigate('home')} onMessage={(text, error) => setToast({ text, error })} />}
      {tab === 'settings' && <SettingsScreen motionReduced={motionReduced} setMotionReduced={setMotionReduced} feedback={feedback} setFeedback={setFeedback} onSendFeedback={() => void sendUserFeedback()} onReset={() => { clearStoredToken(); logout(); }} onDeviceAuth={() => void openDeviceAuthModal()} />}
    </main>

    {voiceOpen && <div className="overlay-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setVoiceOpen(false); }}><section className="voice-modal panel" role="dialog" aria-modal="true" aria-labelledby="voice-title"><button className="modal-close" onClick={() => { recognitionRef.current?.stop(); setVoiceOpen(false); }} data-focusable="true" aria-label="Close voice panel"><X size={20}/></button><div className={`voice-orb ${voiceState}`}><Mic size={30}/></div><p className="eyebrow">MULTIMODAL COMMAND</p><h2 id="voice-title">{voiceState === 'listening' ? 'Listening for your command' : voiceState === 'processing' ? 'Reading the play' : 'Ask OmniPulse'}</h2><p className="muted">Try “Break down this play” or “Who is player 07?”</p><form onSubmit={(event) => { event.preventDefault(); void submitCommand(commandText, selectedPlayer); setVoiceOpen(false); }} className="command-form"><input value={commandText} onChange={(event) => setCommandText(event.target.value)} aria-label="Command text" placeholder="Enter a sports question…" data-focusable="true"/><button className="button button-primary" type="submit" data-focusable="true"><ArrowRight size={18}/> Analyze</button></form><div className="modal-foot"><span><ShieldCheck size={15}/> Uses selected event context</span><span className="muted">Speech capability depends on device</span></div></section></div>}

    {deviceModalOpen && deviceCodeData && (
      <div className="overlay-backdrop" role="presentation" onMouseDown={(e) => { if (e.target === e.currentTarget) setDeviceModalOpen(false); }}>
        <section className="device-auth-modal panel" role="dialog" aria-modal="true" aria-labelledby="device-title">
          <button className="modal-close" onClick={() => setDeviceModalOpen(false)} data-focusable="true" aria-label="Close TV activation"><X size={20}/></button>
          <div className="icon-tile copper-tile"><Tv size={26}/></div>
          <p className="eyebrow">DEVICE AUTHORIZATION · RFC 8628</p>
          <h2 id="device-title">Link your TV account</h2>
          <ol className="device-auth-steps">
            <li>On your mobile phone or browser, go to: <strong>{window.location.origin}/activate</strong></li>
            <li>Sign in and enter the activation code shown below:</li>
          </ol>
          <div className="device-code-box">
            <span className="device-user-code">{deviceCodeData.user_code}</span>
          </div>
          <p className="muted microcopy" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 7 }}><LoaderCircle className="spin" size={14}/> Waiting for authorization on mobile… Code expires in 10 minutes.</p>
        </section>
      </div>
    )}

    {exitModalOpen && (
      <div className="overlay-backdrop" role="presentation" onMouseDown={(e) => { if (e.target === e.currentTarget) setExitModalOpen(false); }}>
        <section className="exit-modal panel" role="dialog" aria-modal="true" aria-labelledby="exit-title">
          <div className="icon-tile copper-tile"><LogOut size={24}/></div>
          <h2 id="exit-title">Exit OmniPulse TV?</h2>
          <p>Are you sure you want to close the application and return to Fire TV home?</p>
          <div className="button-row">
            <button className="button button-quiet" onClick={() => setExitModalOpen(false)} data-focusable="true">Stay in App</button>
            <button className="button button-primary" onClick={() => { if (window.history.length > 1) window.history.back(); else navigate('landing'); }} data-focusable="true">Exit App</button>
          </div>
        </section>
      </div>
    )}

    {toast && <div className={`toast ${toast.error ? 'toast-error' : ''}`} role="status"><span className="toast-icon">{toast.error ? <LifeBuoy size={17}/> : <Check size={17}/>}</span><span>{toast.text}</span><button onClick={() => setToast(null)} aria-label="Dismiss notification"><X size={16}/></button></div>}
  </div>;
}

function NavItem({ active, onClick, icon, label, badge }: { active: boolean; onClick: () => void; icon: ReactNode; label: string; badge?: string }) {
  return <button className={`nav-item ${active ? 'active' : ''}`} onClick={onClick} aria-current={active ? 'page' : undefined} data-focusable="true"><span className="nav-icon">{icon}</span><span>{label}</span>{badge && <span className="nav-badge">{badge}</span>}</button>;
}

function HomeScreen({ event, events, mode, onMode, onOpen, onNavigate, apiReady, onDeviceAuth }: { event: SportEvent; events: SportEvent[]; mode: Mode; onMode: (mode: Mode) => void; onOpen: (id?: string, mode?: Mode) => void; onNavigate: (tab: Tab) => void; apiReady: boolean; onDeviceAuth?: () => void }) {
  const [resolveBusy, setResolveBusy] = useState(false);
  async function suggestMode() {
    setResolveBusy(true);
    try { const result = await resolveMode(event.id); onMode(result.mode); }
    catch { onMode(recommendMode({ default_mode: mode, detail_level: mode === 'analyst' ? 'advanced' : mode === 'family' ? 'simple' : 'balanced' }).mode); }
    finally { setResolveBusy(false); }
  }
  return <section className="screen home-screen"><div className="welcome-row"><div><p className="eyebrow">YOUR LIVING ROOM, REIMAGINED</p><h1>See the game <em>differently.</em></h1><p className="subheading">AI sports intelligence built for the big screen.</p></div><div className="button-row"><button className="button button-quiet" onClick={onDeviceAuth} data-focusable="true"><Tv size={17}/> Link TV Device</button><button className="button button-quiet" onClick={() => onNavigate('household')} data-focusable="true"><Users size={17}/> Household</button></div></div>
    <div className="hero-card"><div className="hero-grain"/><div className="hero-copy"><div className="hero-topline"><span className="hero-live"><span className="live-dot"/> FEATURED EXPERIENCE</span><SourceChip source={event.source_type}/></div><h2>Understand the<br/><em>moment behind the match.</em></h2><p>Move beyond the score. Explore player movement, key sequences and contextual AI explanations with your remote.</p><div className="hero-actions"><button className="button button-primary" onClick={() => onOpen(event.id, mode)} data-focusable="true"><Play size={18} fill="currentColor"/> Explore Sports X-Ray <ArrowRight size={17}/></button><button className="button button-outline" onClick={() => onNavigate('coach')} data-focusable="true"><Activity size={18}/> Active Coach</button></div><div className="hero-meta"><span><ShieldCheck size={15}/> Source-labelled insights</span><span><Command size={15}/> Remote-first design</span></div></div><div className="hero-visual"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="visual-score"><div className="score-team"><span className="team-monogram">{teamInitials(event.home_team)}</span><span>{event.home_team}</span></div><strong>{event.score_home ?? '—'} <i>—</i> {event.score_away ?? '—'}</strong><div className="score-team"><span className="team-monogram copper-monogram">{teamInitials(event.away_team)}</span><span>{event.away_team}</span></div></div><div className="pitch-mini"><div className="pitch-midline"/><div className="pitch-circle"/>{[[24,28],[35,49],[47,36],[57,60],[67,32],[77,49],[86,41]].map(([x,y], index) => <span key={index} className={`pitch-dot pitch-dot-${index % 3}`} style={{ left: `${x}%`, top: `${y}%` }}/>)}</div><div className="visual-caption"><span className="visual-caption-dot"/> Tactical layer <span className="caption-divider"/> {event.source_type === 'sample' ? 'Sample event' : event.source_type === 'provider' ? 'Provider event' : 'Data unavailable'}</div></div></div>
    <div className="section-title-row"><div><p className="eyebrow">YOUR EXPERIENCE</p><h2>Choose your point of view</h2></div><button className="text-button" onClick={() => void suggestMode()} disabled={resolveBusy} data-focusable="true">{resolveBusy ? 'Resolving…' : 'Suggest a mode'} <ArrowUpRight size={16}/></button></div>
    <div className="mode-grid"><ModeCard title="Analyst Mode" label="GO DEEPER" description="Tactical nodes, player details and deeper context." icon={<BarChart3 size={22}/>} active={mode === 'analyst'} accent="lime" onClick={() => onMode('analyst')}/><ModeCard title="Family Lounge" label="KEEP IT SIMPLE" description="Clear scores, approachable summaries and less clutter." icon={<House size={22}/>} active={mode === 'family'} accent="copper" onClick={() => onMode('family')}/><ModeCard title="Catch Me Up" label="QUICK RECAP" description="A concise timeline of the sample match events." icon={<Clock3 size={22}/>} active={mode === 'catch_up'} accent="white" onClick={() => onMode('catch_up')}/></div>
    <div className="section-title-row events-title"><div><p className="eyebrow">SPORTS INTELLIGENCE</p><h2>Explore a match</h2></div><span className="muted microcopy">{events.length} available {events.length === 1 ? 'event' : 'events'}</span></div>
    <div className="event-grid">{events.map((item) => <button className="event-card panel" key={item.id} onClick={() => onOpen(item.id, mode)} data-focusable="true"><div className="event-card-top"><span className="sport-tag"><Trophy size={14}/> {item.sport.toUpperCase()}</span><SourceChip source={item.source_type}/></div><div className="event-teams"><span>{item.home_team}</span><strong>{item.score_home ?? '—'} <i>:</i> {item.score_away ?? '—'}</strong><span>{item.away_team}</span></div><div className="event-footer"><span>{item.league}</span><span className="open-link">Open X-Ray <ArrowUpRight size={15}/></span></div></button>)}</div>
    <div className="status-strip"><div className="status-item"><span className={`status-dot ${apiReady ? 'online' : 'offline'}`}/><div><strong>{apiReady ? 'API connected' : 'Preview mode'}</strong><span>{apiReady ? 'Backend-backed experience' : 'Connect backend to persist changes'}</span></div></div><div className="status-item"><Database size={19}/><div><strong>Data provenance</strong><span>Sample datasets labelled clearly</span></div></div><div className="status-item"><Fingerprint size={19}/><div><strong>Privacy-first</strong><span>Camera processing stays local</span></div></div></div>
  </section>;
}

function ModeCard({ title, label, description, icon, active, accent, onClick }: { title: string; label: string; description: string; icon: ReactNode; active: boolean; accent: string; onClick: () => void }) {
  return <button className={`mode-card panel ${active ? 'selected' : ''} accent-${accent}`} onClick={onClick} data-focusable="true"><div className="mode-card-top"><span className="mode-icon">{icon}</span>{active ? <span className="selected-mark"><Check size={14}/></span> : <ArrowUpRight size={17} className="muted"/>}</div><span className="eyebrow">{label}</span><h3>{title}</h3><p>{description}</p></button>;
}

function XrayScreen({ event, tactical, timeline, selectedPlayer, selectedPlayerId, setSelectedPlayerId, analysis, commandText, setCommandText, onAnalyze, onPlayerAnalyze, onVoice, voiceState, onBack }: {
  event: SportEvent; tactical: TacticalData; timeline: TimelineItem[]; selectedPlayer?: Player; selectedPlayerId: string; setSelectedPlayerId: (id: string) => void; analysis: AnalysisResponse | null; commandText: string; setCommandText: (text: string) => void; onAnalyze: () => void; onPlayerAnalyze: (player: Player) => void; onVoice: () => void; voiceState: string; onBack: () => void;
}) {
  return <section className="screen xray-screen"><div className="section-heading"><div><p className="eyebrow">TACTICAL INTELLIGENCE</p><h1>Sports <em>X-Ray</em></h1><p className="subheading">Explore the shape of a play, one player at a time.</p></div><div className="heading-actions"><SourceChip source={event.source_type}/><button className="button button-quiet" onClick={onBack} data-focusable="true">Back to Hub</button></div></div>
    <div className="match-bar panel"><div className="match-side"><span className="team-monogram">{teamInitials(event.home_team)}</span><div><strong>{event.home_team}</strong><span>{event.league}</span></div></div><div className="match-score"><strong>{event.score_home ?? '—'} <i>:</i> {event.score_away ?? '—'}</strong><span className="sample-status"><span className="live-dot muted-dot"/> {event.source_type === 'provider' ? event.status.toUpperCase() : 'SAMPLE FIXTURE'}</span></div><div className="match-side match-side-right"><div><strong>{event.away_team}</strong><span>Opponent</span></div><span className="team-monogram copper-monogram">{teamInitials(event.away_team)}</span></div></div>
    <div className="xray-layout"><div className="xray-main"><div className="panel pitch-panel"><div className="panel-heading"><div><p className="eyebrow">TACTICAL FIELD</p><h3>Spatial play view</h3></div><div className="panel-heading-right"><span className="legend-item"><i className="legend-dot legend-home"/> {event.home_team}</span><span className="legend-item"><i className="legend-dot legend-away"/> {event.away_team}</span></div></div><div className="pitch-large"><div className="pitch-boundary"/><div className="pitch-halfline"/><div className="pitch-center-circle"/><div className="pitch-box pitch-box-left"/><div className="pitch-box pitch-box-right"/><div className="pitch-small-box pitch-small-left"/><div className="pitch-small-box pitch-small-right"/><svg className="pass-lines" viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="Sample tactical connections">{tactical.connections.map((connection) => { const from = tactical.players.find((p) => p.id === connection.from); const to = tactical.players.find((p) => p.id === connection.to); return from && to ? <line key={`${connection.from}-${connection.to}`} x1={from.x} y1={from.y} x2={to.x} y2={to.y} stroke="#C6F36B" strokeWidth="0.45" strokeDasharray="1.4 1.2" opacity=".9"/> : null; })}</svg>{tactical.players.map((player) => <button key={player.id} className={`player-node ${player.team === event.home_team ? 'home-node' : 'away-node'} ${selectedPlayerId === player.id ? 'player-selected' : ''}`} style={{ left: `${player.x}%`, top: `${player.y}%` }} title={`${player.name}, ${player.role}`} aria-label={`Select ${player.name}`} aria-pressed={selectedPlayerId === player.id} onClick={() => setSelectedPlayerId(player.id)} data-focusable="true"><span className="player-number">{player.id.replace('player-', '')}</span><span className="player-name">{player.name}</span></button>)}</div><div className="pitch-footer"><span><span className={`status-dot ${tactical.source_type === 'unavailable' ? 'offline' : 'online'}`}/> {tactical.source_type === 'sample' ? 'Illustrative sample coordinates' : tactical.source_type === 'provider' ? 'Provider-sourced coordinates' : 'Tactical coordinates unavailable'}</span><span>{tactical.players.length} nodes <span className="caption-divider"/> {tactical.field.coordinate_system}</span></div></div>
      <div className="panel timeline-panel"><div className="panel-heading"><div><p className="eyebrow">EVENT TIMELINE</p><h3>Key moments</h3></div><span className="muted microcopy">{timeline.length} events</span></div><div className="timeline-list">{timeline.map((item) => <button key={item.id} className="timeline-item" onClick={() => { setSelectedPlayerId(item.player_id); }} data-focusable="true"><span className="timeline-minute">{item.minute}'</span><span className="timeline-marker"><span/></span><span className="timeline-copy"><strong>{item.label}</strong><small>{item.team} · {item.type}</small></span><ChevronRight size={16} className="muted"/></button>)}</div></div>
      </div><aside className="xray-sidebar"><div className="panel player-detail"><div className="detail-top"><p className="eyebrow">SELECTED PLAYER</p><span className="player-id">{selectedPlayer?.id.replace('player-', '#') || '—'}</span></div>{selectedPlayer ? <><div className="player-profile"><div className={`player-avatar ${selectedPlayer.team === event.home_team ? '' : 'copper-avatar'}`}>{selectedPlayer.name.split(' ').map((n) => n[0]).join('').replace('.', '')}</div><div><h3>{selectedPlayer.name}</h3><p className="muted">{selectedPlayer.role}</p></div></div><div className="detail-divider"/><div className="detail-row"><span>Team</span><strong>{selectedPlayer.team}</strong></div><div className="detail-row"><span>Sample speed</span><strong>{selectedPlayer.speed_kph?.toFixed(1) ?? '—'} km/h</strong></div><div className="detail-row"><span>Field coordinate</span><strong>{selectedPlayer.x}, {selectedPlayer.y}</strong></div><button className="button button-primary full-button" onClick={() => onPlayerAnalyze(selectedPlayer)} data-focusable="true"><Sparkles size={17}/> Analyze Player <ArrowRight size={16}/></button></> : <p className="muted">Select a player node to view details.</p>}</div>
      <div className="panel ask-panel"><div className="ask-title"><span className="ai-spark"><Sparkles size={17}/></span><div><h3>Ask OmniPulse</h3><p className="muted">Context-aware analysis</p></div></div><button className="voice-action" onClick={onVoice} data-focusable="true"><span className={`voice-action-icon ${voiceState === 'listening' ? 'listening' : ''}`}><Mic size={18}/></span><span><strong>{voiceState === 'listening' ? 'Listening…' : 'Use voice command'}</strong><small>“Break down this play”</small></span><ArrowUpRight size={17} className="muted"/></button><form className="ask-form" onSubmit={(event) => { event.preventDefault(); onAnalyze(); }}><label htmlFor="analysis-prompt">Or type a command</label><input id="analysis-prompt" value={commandText} onChange={(event) => setCommandText(event.target.value)} placeholder="Ask about this play…" data-focusable="true"/><button className="button button-outline full-button" type="submit" data-focusable="true"><Sparkles size={16}/> Analyze context</button></form>{analysis && <div className="analysis-result"><div className="analysis-result-head"><span className="eyebrow">ANALYSIS RESULT</span><SourceChip source={analysis.source_type}/></div><p>{analysis.analysis.summary}</p><div className="analysis-meta"><span>{analysis.provider} provider</span><span>{analysis.analysis.player_ids.length} player references</span></div></div>}<p className="disclaimer"><ShieldCheck size={14}/> Data source is labelled. Sample analysis is not a live broadcast feed.</p></div></aside></div>
  </section>;
}

function HouseholdScreen({ me, mode, setMode, detailLevel, setDetailLevel, spoilers, setSpoilers, onSave, saving, onOpen }: { me: MeResponse | null; mode: Mode; setMode: (mode: Mode) => void; detailLevel: string; setDetailLevel: (value: string) => void; spoilers: string; setSpoilers: (value: string) => void; onSave: () => void; saving: boolean; onOpen: (id?: string, mode?: Mode) => void }) {
  return <section className="screen settings-screen"><div className="section-heading"><div><p className="eyebrow">PERSONALIZATION ENGINE</p><h1>Your household, <em>your game.</em></h1><p className="subheading">Preferences adapt the interface—not the facts.</p></div><div className="profile-large"><div className="avatar avatar-large">{me?.profile.nickname?.slice(0, 1).toUpperCase() || 'V'}</div><div><strong>{me?.profile.nickname || 'Guest viewer'}</strong><span>{me?.household.name || 'Demo household'}</span></div></div></div>
    <div className="settings-grid"><div className="panel settings-panel"><div className="panel-heading"><div><p className="eyebrow">DEFAULT EXPERIENCE</p><h3>How should OmniPulse feel?</h3></div></div><div className="choice-list"><ChoiceRow active={mode === 'analyst'} title="Analyst Mode" detail="Tactical nodes and deeper explanations" onClick={() => setMode('analyst')}/><ChoiceRow active={mode === 'family'} title="Family Lounge" detail="Simple summaries and less on-screen detail" onClick={() => setMode('family')}/><ChoiceRow active={mode === 'catch_up'} title="Catch Me Up" detail="Short recaps with relevant timeline events" onClick={() => setMode('catch_up')}/></div><div className="form-field"><label htmlFor="detail-level">Analysis detail</label><select id="detail-level" value={detailLevel} onChange={(event) => setDetailLevel(event.target.value)} data-focusable="true"><option value="simple">Simple</option><option value="balanced">Balanced</option><option value="advanced">Advanced</option></select></div><div className="form-field"><label htmlFor="spoilers">Spoiler policy</label><select id="spoilers" value={spoilers} onChange={(event) => setSpoilers(event.target.value)} data-focusable="true"><option value="allow">Allow match results</option><option value="avoid">Avoid unnecessary spoilers</option><option value="strict">Strict spoiler-free mode</option></select></div><button className="button button-primary" onClick={onSave} disabled={saving} data-focusable="true">{saving ? <LoaderCircle className="spin" size={17}/> : <Check size={17}/>} Save preferences</button></div>
    <div className="settings-aside"><div className="panel memory-explainer"><span className="big-icon"><BrainCircuit size={27}/></span><p className="eyebrow">EXPLAINABLE MEMORY</p><h3>Suggested, never forced.</h3><p className="muted">Personalization uses saved preferences and recent viewing actions. You can override a suggestion at any time.</p><div className="memory-point"><Check size={16}/> User can change the mode</div><div className="memory-point"><Check size={16}/> Preferences persist via API</div><div className="memory-point"><Check size={16}/> No identity recognition claim</div><button className="button button-outline full-button" onClick={() => onOpen(sampleEvent.id, mode)} data-focusable="true">Try this experience <ArrowRight size={16}/></button></div><div className="privacy-note"><LockKeyhole size={19}/><div><strong>Privacy by design</strong><p>Only stated preferences are stored. Camera frames are not sent by the Coach interface.</p></div></div></div></div>
  </section>;
}

function ChoiceRow({ active, title, detail, onClick }: { active: boolean; title: string; detail: string; onClick: () => void }) { return <button className={`choice-row ${active ? 'active' : ''}`} onClick={onClick} data-focusable="true"><span className={`radio-indicator ${active ? 'checked' : ''}`}>{active && <span/>}</span><span className="choice-copy"><strong>{title}</strong><small>{detail}</small></span>{active && <span className="selected-tag">SELECTED</span>}</button>; }

function SettingsScreen({ motionReduced, setMotionReduced, feedback, setFeedback, onSendFeedback, onReset, onDeviceAuth }: { motionReduced: boolean; setMotionReduced: (value: boolean) => void; feedback: string; setFeedback: (value: string) => void; onSendFeedback: () => void; onReset: () => void; onDeviceAuth?: () => void }) {
  return <section className="screen settings-screen"><div className="section-heading"><div><p className="eyebrow">PREFERENCES & TRUST</p><h1>Settings</h1><p className="subheading">Make the experience comfortable, transparent and predictable.</p></div></div><div className="settings-grid"><div className="panel settings-panel"><div className="panel-heading"><div><p className="eyebrow">DISPLAY</p><h3>Interface behavior</h3></div></div><div className="toggle-row"><div><strong>Reduce motion</strong><p>Use fewer transitions and animated effects.</p></div><button className={`toggle-switch ${motionReduced ? 'on' : ''}`} role="switch" aria-checked={motionReduced} onClick={() => setMotionReduced(!motionReduced)} data-focusable="true"><span/></button></div><div className="detail-divider"/><div className="panel-heading"><div><p className="eyebrow">AUTHENTICATION</p><h3>Device pairing</h3></div></div><p className="muted">Pair this TV screen with a phone or computer account using a temporary 6-character code.</p><div className="button-row"><button className="button button-primary" onClick={onDeviceAuth} data-focusable="true"><Tv size={16}/> Link with TV Code</button><button className="button button-outline" onClick={onReset} data-focusable="true">Reset session</button></div></div><div className="panel feedback-panel"><div className="big-icon"><LifeBuoy size={25}/></div><p className="eyebrow">PRODUCT FEEDBACK</p><h3>Help improve OmniPulse</h3><p className="muted">Share a focus-navigation issue, confusing state or data-quality problem. Do not include passwords or sensitive personal information.</p><textarea value={feedback} onChange={(event) => setFeedback(event.target.value)} maxLength={2000} placeholder="Describe what happened and how to reproduce it…" data-focusable="true"/><button className="button button-primary full-button" onClick={onSendFeedback} data-focusable="true">Send feedback <ArrowRight size={16}/></button></div></div></section>;
}

function ActivateScreen({ onReturn }: { onReturn: () => void }) {
  const urlParams = new URLSearchParams(window.location.search);
  const [code, setCode] = useState(urlParams.get('code') || '');
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  async function handleAuthorize(e: React.FormEvent) {
    e.preventDefault();
    if (!code.trim()) return;
    setBusy(true);
    setErrorMsg('');
    try {
      await ensureAuthenticated();
      await authorizeDevice(code.trim());
      setDone(true);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Activation failed. Check the code and try again.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="activate-page">
      <div className="activate-card">
        <div className="brand-lockup" style={{ justifyContent: 'center', marginBottom: 20 }}>
          <span className="brand-mark"><Activity size={22}/></span>
          <span className="brand-copy"><strong>omnipulse</strong><small>TV ACTIVATION</small></span>
        </div>
        {!done ? (
          <>
            <h1>Enter Code</h1>
            <p className="muted" style={{ fontSize: 13, lineHeight: 1.6 }}>
              Enter the activation code displayed on your TV screen to link your OmniPulse account.
            </p>
            <form onSubmit={handleAuthorize}>
              <input
                className="activate-code-input"
                value={code}
                onChange={(e) => setCode(e.target.value.toUpperCase())}
                placeholder="XXXX-XXXX"
                maxLength={12}
                required
                autoFocus
              />
              {errorMsg && <p style={{ color: 'var(--copper)', fontSize: 12, margin: '8px 0' }}>{errorMsg}</p>}
              <button className="button button-primary full-button" type="submit" disabled={busy} style={{ minHeight: 46 }}>
                {busy ? <LoaderCircle className="spin" size={17}/> : <Check size={17}/>} Authorize TV
              </button>
            </form>
            <div style={{ marginTop: 20 }}>
              <button className="text-button" onClick={onReturn} style={{ fontSize: 12 }}>
                Return to Product Site
              </button>
            </div>
          </>
        ) : (
          <div>
            <div className="icon-tile" style={{ background: 'rgba(198,243,107,0.12)', color: 'var(--accent)', margin: '0 auto 16px' }}>
              <Check size={32}/>
            </div>
            <h1>TV Authorized!</h1>
            <p className="muted" style={{ fontSize: 13, lineHeight: 1.7, margin: '14px 0 24px' }}>
              Your TV has been successfully linked. Look at your television screen—it will automatically open the Watch Hub.
            </p>
            <button className="button button-outline full-button" onClick={onReturn}>
              Done
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function Landing({ onLaunch, onDemo }: { onLaunch: () => void; onDemo: () => void }) {
  return <div className="landing-page"><header className="landing-nav"><button className="brand-lockup" onClick={onLaunch} data-focusable="true"><span className="brand-mark"><Activity size={22}/></span><span className="brand-copy"><strong>omnipulse</strong><small>SPORTS INTELLIGENCE</small></span></button><div className="landing-nav-links"><a href="#experience">Experience</a><a href="#personalization">Personalization</a><a href="#privacy">Privacy</a><button className="button button-primary" onClick={onLaunch} data-focusable="true">Open app <ArrowUpRight size={16}/></button></div></header><main><section className="landing-hero"><div className="landing-hero-copy"><p className="eyebrow"><span className="live-dot"/> A NEW WAY TO WATCH</p><h1>The game is more<br/><em>than the score.</em></h1><p>Bring tactical context, household-aware viewing and interactive sports intelligence to the biggest screen in your home.</p><div className="hero-actions"><button className="button button-primary" onClick={onDemo} data-focusable="true"><Play size={17} fill="currentColor"/> Explore the experience</button><button className="button button-outline" onClick={onLaunch} data-focusable="true">Open product <ArrowRight size={17}/></button></div><div className="landing-proof"><span><ShieldCheck size={16}/> Source-labelled analysis</span><span><Command size={16}/> Remote-first by design</span></div></div><div className="landing-art"><div className="landing-glow"/><div className="landing-score-card panel"><div className="score-card-top"><span className="hero-live"><span className="live-dot"/> TACTICAL LAYER</span><span className="mini-chip">SAMPLE</span></div><div className="landing-score"><span>NC</span><strong>2 <i>—</i> 1</strong><span className="copper-monogram">HU</span></div><div className="landing-pitch">{[[20,28],[35,54],[50,37],[62,62],[77,29],[84,53]].map(([x,y],i)=><span key={i} className={`landing-pitch-point point-${i%3}`} style={{left:`${x}%`,top:`${y}%`}}/>)}<svg viewBox="0 0 100 100" preserveAspectRatio="none"><line x1="20" y1="28" x2="50" y2="37"/><line x1="50" y1="37" x2="77" y2="29"/><line x1="35" y1="54" x2="62" y2="62"/></svg></div><div className="landing-analysis"><span className="ai-spark"><Sparkles size={15}/></span><div><strong>Play context ready</strong><small>Visual nodes · Timeline · AI explanation</small></div><ArrowUpRight size={16}/></div></div><div className="floating-chip chip-one"><span className="chip-pulse"/> Context aware</div><div className="floating-chip chip-two"><Activity size={15}/> Remote focus</div></div></section>
    <section className="landing-features" id="experience"><div className="section-title-row"><div><p className="eyebrow">BUILT AROUND THE MOMENT</p><h2>Three layers. One experience.</h2></div><p className="muted landing-section-description">The companion to the game—without taking control away from you.</p></div><div className="landing-feature-grid"><article className="landing-feature"><span className="feature-index">01 / CONTEXT</span><div className="feature-icon"><BrainCircuit size={22}/></div><h3>A viewing experience that learns your preferences</h3><p>Choose the level of detail, save household settings, and let OmniPulse suggest a mode you can always override.</p></article><article className="landing-feature"><span className="feature-index">02 / INTERACTION</span><div className="feature-icon feature-copper"><Command size={22}/></div><h3>Ask with voice. Explore with your remote.</h3><p>Move from a natural-language command to a tactical field and navigate the analysis with visible focus states.</p></article><article className="landing-feature"><span className="feature-index">03 / MOVEMENT</span><div className="feature-icon"><Activity size={22}/></div><h3>Bring movement into the experience</h3><p>On supported camera environments, local pose estimation can show landmarks and derived joint metrics with explicit consent.</p></article></div></section>
    <section className="landing-personalization" id="personalization"><div><p className="eyebrow">PERSONAL BY DESIGN</p><h2>More context.<br/><em>Less clutter.</em></h2><p className="muted">Analyst Mode surfaces deeper tactical detail. Family Lounge keeps the experience clear. Catch Me Up focuses on a compact recap. Saved preferences guide suggestions, but never remove your control.</p><button className="text-button" onClick={onLaunch} data-focusable="true">Explore preferences <ArrowRight size={16}/></button></div><div className="preference-preview panel"><div className="panel-heading"><div><p className="eyebrow">HOUSEHOLD PROFILE</p><h3>Viewing preference</h3></div><span className="status-dot online"/></div><div className="preference-option selected"><span className="radio-indicator checked"><span/></span><div><strong>Analyst Mode</strong><small>Tactical field and deeper detail</small></div><Check size={17}/></div><div className="preference-option"><span className="radio-indicator"/><div><strong>Family Lounge</strong><small>Simple, spoiler-aware summaries</small></div></div><div className="preference-option"><span className="radio-indicator"/><div><strong>Catch Me Up</strong><small>Compact event recap</small></div></div><div className="privacy-mini"><ShieldCheck size={17}/><span>Preference-led, not identity recognition.</span></div></div></section>
    <section className="landing-privacy" id="privacy"><div className="privacy-icon"><LockKeyhole size={25}/></div><p className="eyebrow">BUILT WITH TRANSPARENCY</p><h2>Intelligent, not intrusive.</h2><p>Sample sports data is clearly labelled. Camera frames are processed locally by the coach feature. The API stores derived metrics only, and household settings remain under user control.</p><button className="button button-primary" onClick={onLaunch} data-focusable="true">Enter OmniPulse <ArrowRight size={17}/></button></section></main><footer className="landing-footer"><span>© 2026 OmniPulse TV · Prototype</span><span>Source-labelled · Remote-first · Consent-aware</span></footer></div>;
}
