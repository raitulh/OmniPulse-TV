import { useEffect, useRef, useState } from 'react';
import { Activity, Camera, CameraOff, CheckCircle2, LoaderCircle, ShieldCheck } from 'lucide-react';
import { completeCoachSession, createCoachSession, sendCoachMetric } from '../../lib/api';

const MODEL_URL = import.meta.env.VITE_POSE_MODEL_URL || 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task';
const WASM_URL = import.meta.env.VITE_POSE_WASM_URL || 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22/wasm';
type Point = { x: number; y: number; visibility?: number };
type Result = { landmarks?: Point[][] };
type Landmarker = { detectForVideo: (video: HTMLVideoElement, timestamp: number) => Result; close: () => void };
type Props = { onBack: () => void; onMessage: (message: string, isError?: boolean) => void };
const CONNECTIONS: Array<[number, number]> = [[11,12],[11,13],[13,15],[12,14],[14,16],[11,23],[12,24],[23,24],[23,25],[25,27],[24,26],[26,28],[27,29],[29,31],[28,30],[30,32]];

function jointAngle(a: Point, b: Point, c: Point): number {
  const u = { x: a.x - b.x, y: a.y - b.y }; const v = { x: c.x - b.x, y: c.y - b.y };
  const denominator = Math.hypot(u.x, u.y) * Math.hypot(v.x, v.y);
  if (!denominator) return 0;
  const cosine = Math.max(-1, Math.min(1, (u.x * v.x + u.y * v.y) / denominator));
  return Math.round(Math.acos(cosine) * 180 / Math.PI);
}

export default function PoseCoach({ onBack, onMessage }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const landmarkerRef = useRef<Landmarker | null>(null);
  const frameRef = useRef<number | null>(null);
  const sessionRef = useRef<string | null>(null);
  const lastSendRef = useRef(0);
  const lastUiUpdateRef = useRef(0);
  const lastFpsUpdateRef = useRef(0);
  const [phase, setPhase] = useState<'idle'|'starting'|'active'|'unsupported'|'error'|'complete'>('idle');
  const [consent, setConsent] = useState(false);
  const [kneeAngle, setKneeAngle] = useState<number | null>(null);
  const [fps, setFps] = useState(0);
  const [error, setError] = useState('');

  useEffect(() => () => {
    if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
    landmarkerRef.current?.close();
    streamRef.current?.getTracks().forEach((track) => track.stop());
    if (sessionRef.current) void completeCoachSession(sessionRef.current).catch(() => undefined);
  }, []);

  async function start() {
    if (!consent) { onMessage('Please confirm camera consent before starting.', true); return; }
    if (!navigator.mediaDevices?.getUserMedia) { setPhase('unsupported'); setError('Camera access is not supported in this browser or platform.'); return; }
    setPhase('starting'); setError('');
    try {
      const session = await createCoachSession('squat');
      sessionRef.current = session.id;
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } }, audio: false });
      streamRef.current = stream;
      if (!videoRef.current) throw new Error('Camera preview unavailable.');
      videoRef.current.srcObject = stream;
      await videoRef.current.play();
      const vision = await import('@mediapipe/tasks-vision');
      const fileset = await vision.FilesetResolver.forVisionTasks(WASM_URL);
      let landmarker;
      try {
        landmarker = await vision.PoseLandmarker.createFromOptions(fileset, {
          baseOptions: { modelAssetPath: MODEL_URL, delegate: 'GPU' }, runningMode: 'VIDEO', numPoses: 1,
        });
      } catch {
        landmarker = await vision.PoseLandmarker.createFromOptions(fileset, {
          baseOptions: { modelAssetPath: MODEL_URL, delegate: 'CPU' }, runningMode: 'VIDEO', numPoses: 1,
        });
      }
      landmarkerRef.current = landmarker as unknown as Landmarker;
      setPhase('active');
      onMessage('Pose model ready. Joint angles are estimates, not medical advice.');
      drawFrame();
    } catch (caught) {
      streamRef.current?.getTracks().forEach((track) => track.stop()); streamRef.current = null;
      if (sessionRef.current) { try { await completeCoachSession(sessionRef.current); } catch { /* preserve the initial camera error */ } sessionRef.current = null; }
      setPhase('error');
      const message = caught instanceof Error ? caught.message : 'Unable to start camera coaching.';
      setError((caught instanceof DOMException && caught.name === 'NotAllowedError') || message.includes('NotAllowedError') ? 'Camera permission was denied. Enable it in browser settings and retry.' : `${message} Check network access for the pose model and retry.`);
    }
  }

  function drawFrame() {
    const video = videoRef.current; const canvas = canvasRef.current; const model = landmarkerRef.current;
    if (!video || !canvas || !model) return;
    const ctx = canvas.getContext('2d'); if (!ctx) return;
    const render = () => {
      const v = videoRef.current; const c = canvasRef.current; const detector = landmarkerRef.current;
      if (!v || !c || !detector) return;
      const context = c.getContext('2d'); if (!context) return;
      if (v.readyState < 2) { frameRef.current = requestAnimationFrame(render); return; }
      if (c.width !== v.videoWidth || c.height !== v.videoHeight) { c.width = v.videoWidth; c.height = v.videoHeight; }
      const started = performance.now(); const result = detector.detectForVideo(v, started);
      context.clearRect(0, 0, c.width, c.height);
      const points = result.landmarks?.[0];
      if (points) {
        context.lineWidth = Math.max(2, c.width / 300); context.strokeStyle = '#C6F36B'; context.fillStyle = '#B8734E';
        for (const [from, to] of CONNECTIONS) {
          const a = points[from]; const b = points[to];
          if ((a.visibility ?? 1) < 0.45 || (b.visibility ?? 1) < 0.45) continue;
          context.beginPath(); context.moveTo(a.x * c.width, a.y * c.height); context.lineTo(b.x * c.width, b.y * c.height); context.stroke();
        }
        points.forEach((point) => {
          if ((point.visibility ?? 1) < 0.45) return;
          context.beginPath(); context.arc(point.x * c.width, point.y * c.height, Math.max(2.5, c.width / 150), 0, 2 * Math.PI); context.fill();
        });
        const sets = [[points[23],points[25],points[27]],[points[24],points[26],points[28]]].filter((set) => set.every((point) => (point.visibility ?? 1) >= 0.45));
        if (sets.length) {
          const value = Math.round(sets.reduce((sum, set) => sum + jointAngle(set[0], set[1], set[2]), 0) / sets.length);
          const wallNow = Date.now();
          if (wallNow - lastUiUpdateRef.current > 350) { setKneeAngle(value); lastUiUpdateRef.current = wallNow; }
          if (sessionRef.current && wallNow - lastSendRef.current > 5000) {
            lastSendRef.current = wallNow;
            void sendCoachMetric(sessionRef.current, { metric_type: 'knee_angle', value, unit: 'degrees' }).catch(() => undefined);
          }
        }
      }
      const nowMs = Date.now();
      if (nowMs - lastFpsUpdateRef.current > 500) { setFps(Math.round(1000 / Math.max(1, performance.now() - started))); lastFpsUpdateRef.current = nowMs; }
      frameRef.current = requestAnimationFrame(render);
    };
    frameRef.current = requestAnimationFrame(render);
  }

  async function stop() {
    if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
    landmarkerRef.current?.close(); landmarkerRef.current = null;
    streamRef.current?.getTracks().forEach((track) => track.stop()); streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    const sessionId = sessionRef.current;
    sessionRef.current = null;
    if (sessionId) { try { await completeCoachSession(sessionId); } catch { /* camera must still stop */ } }
    setPhase('complete'); onMessage('Session ended. Camera has been stopped.');
  }

  return <section className="screen coach-screen">
    <div className="section-heading"><div><p className="eyebrow">MOVEMENT INTELLIGENCE</p><h1>Active Coach</h1><p className="subheading">Local pose estimation with camera-consent controls.</p></div><button className="button button-quiet" onClick={onBack} data-focusable="true">Back to Hub</button></div>
    {phase === 'idle' && <div className="coach-consent panel"><div className="icon-tile copper-tile"><ShieldCheck size={28}/></div><h2>Your camera stays on this device</h2><p className="muted">Pose landmarks are processed locally. Only derived knee-angle metrics are sent to the API; raw video is not uploaded by this feature. Pose model files are downloaded from the configured model host.</p><label className="consent-check"><input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)}/> I consent to camera access and derived movement-metric processing for this session.</label><button className="button button-primary" disabled={!consent} onClick={() => void start()} data-focusable="true"><Camera size={18}/> Start Camera Coach</button></div>}
    {phase === 'starting' && <div className="panel state-panel"><LoaderCircle className="spin" size={30}/><h2>Preparing camera and pose model</h2><p className="muted">Allow camera permission and keep the device online while model assets load.</p></div>}
    {(phase === 'unsupported' || phase === 'error') && <div className="panel state-panel"><CameraOff size={34}/><h2>Camera coach unavailable</h2><p className="muted">{error}</p><div className="button-row"><button className="button button-primary" onClick={() => setPhase('idle')} data-focusable="true">Try Again</button><button className="button button-quiet" onClick={onBack} data-focusable="true">Return</button></div></div>}
    <div className="coach-grid" hidden={phase !== 'active'} aria-hidden={phase !== 'active'}><div className="coach-video panel"><div className="video-frame"><video ref={videoRef} playsInline muted/><canvas ref={canvasRef}/><div className="video-badge"><span className="live-dot"/> POSE TRACKING</div></div><div className="video-meta"><span><Activity size={16}/> {fps} FPS (approx.)</span><span><Camera size={16}/> Local camera</span></div><button className="button button-danger" onClick={() => void stop()} data-focusable="true" tabIndex={phase === 'active' ? 0 : -1}>End Session</button></div><div className="coach-metrics"><div className="metric-card"><p className="eyebrow">ESTIMATED KNEE ANGLE</p><strong>{kneeAngle === null ? '—' : `${kneeAngle}°`}</strong><span className="muted">Derived from visible pose landmarks</span></div><div className="metric-card"><p className="eyebrow">SESSION SAFETY</p><strong className="metric-title"><ShieldCheck size={20}/> Local processing</strong><span className="muted">Raw frames are not sent to the backend.</span></div></div></div>
    {phase === 'complete' && <div className="panel state-panel"><CheckCircle2 size={36} color="var(--accent)"/><h2>Session ended</h2><p className="muted">Camera tracks are stopped. Derived metrics were recorded when the API was reachable.</p><div className="button-row"><button className="button button-primary" onClick={() => { setKneeAngle(null); setPhase('idle'); sessionRef.current = null; }} data-focusable="true">Start Another Session</button><button className="button button-quiet" onClick={onBack} data-focusable="true">Return to Hub</button></div></div>}
  </section>;
}
