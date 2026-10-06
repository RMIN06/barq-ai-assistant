'use client';
import { useEffect, useRef, useState, useCallback } from 'react';
import { Camera, CameraOff, Clock3, Cpu, Download, Keyboard, Mic, Power, Send, Settings2, Trash2 } from 'lucide-react';

type Msg = { id: string; sender: 'you' | 'barq'; text: string; sitrep?: boolean; timestamp: number };

async function mode(name: 'wake' | 'sleep') {
  const token = localStorage.getItem('barq_auth_token') || '';
  await fetch(`http://127.0.0.1:8080/${name}`, { method: 'POST', headers: { 'X-Barq-Token': token } });
}

const wakeBarq = () => void mode('wake');
const sleepBarq = () => void mode('sleep');

export default function Home() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [connected, setConnected] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [cameraOn, setCameraOn] = useState(false);
  const [cameraPending, setCameraPending] = useState(false);
  const [cameraError, setCameraError] = useState('');
  const [aiState, setAiState] = useState('standby');
  const [clock, setClock] = useState('');
  const [stats, setStats] = useState<{ cpu: number; memory: number; disk: number; uptime: number } | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [tokenDraft, setTokenDraft] = useState('');
  const [weatherCity, setWeatherCity] = useState('');
  const [cityDraft, setCityDraft] = useState('');
  const [weather, setWeather] = useState<{ city: string; country: string; temperature: number; humidity: number; feels_like: number; wind: number } | null>(null);
  const [weatherError, setWeatherError] = useState('Set a city in Settings.');
  const [weatherRefresh, setWeatherRefresh] = useState(0);
  const videoRef = useRef<HTMLVideoElement>(null);
  const cameraRef = useRef<MediaStream | null>(null);
  const cameraRequestRef = useRef(0);
  const wsRef = useRef<WebSocket | null>(null);
  const logRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let retry: ReturnType<typeof setTimeout>;
    const desktop = window as Window & { barqDesktop?: { token: () => Promise<string | null> } };
    void desktop.barqDesktop?.token().then(token => { if (token) localStorage.setItem('barq_auth_token', token); });
    const savedCity = localStorage.getItem('barq_weather_city') || '';
    const savedCityTimer = setTimeout(() => { setWeatherCity(savedCity); setCityDraft(savedCity); }, 0);

    const open = () => {
      const token = localStorage.getItem('barq_auth_token') || '';
      ws = new WebSocket(`ws://127.0.0.1:8080/ws?token=${encodeURIComponent(token)}`);
      wsRef.current = ws;
      ws.onopen = () => setConnected(true);
      ws.onclose = () => {
        setConnected(false);
        retry = setTimeout(open, 1500);
      };
      ws.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data) as { type?: string; text?: string; sitrep?: boolean; aiState?: string };
          if (data.type === 'wake') setIsListening(true);
          if (data.type === 'sleep') setIsListening(false);
          if (data.type === 'state' && data.aiState) setAiState(data.aiState === 'sleeping' ? 'standby' : data.aiState);
          const text = data.text;
          if (text) {
            const sender: 'you' | 'barq' = data.type === 'user' ? 'you' : 'barq';
            setMessages((m) => [
              ...m.slice(-100),
              { id: `${sender}-${Date.now()}`, sender, text: data.text || '', sitrep: Boolean(data.sitrep), timestamp: Date.now() },
            ]);
          }
        } catch {
          /* ignore */
        }
      };
    };
    open();
    const t = setInterval(() => logRef.current?.scrollTo({ top: 1e6, behavior: 'smooth' }), 400);

    const statusInterval = setInterval(() => setClock(new Date().toLocaleString()), 1000);
    const pollStats = async () => { const auth = localStorage.getItem('barq_auth_token') || ''; if (!auth) return; try { const response = await fetch('http://127.0.0.1:8080/system-stats', { headers: { 'X-Barq-Token': auth } }); if (response.ok) setStats(await response.json()); } catch { setStats(null); } };
    void pollStats();
    const statsInterval = setInterval(pollStats, 5000);

    return () => {
      ws?.close();
      clearTimeout(savedCityTimer);
      clearTimeout(retry);
      clearInterval(statusInterval);
      clearInterval(statsInterval);
      clearInterval(t);
    };
  }, []);

  useEffect(() => {
    if (!weatherCity) return;
    const loadWeather = async () => {
      const auth = localStorage.getItem('barq_auth_token') || '';
      if (!auth) return;
      try {
        const response = await fetch(`http://127.0.0.1:8080/weather?city=${encodeURIComponent(weatherCity)}`, { headers: { 'X-Barq-Token': auth } });
        if (!response.ok) throw new Error(`Weather request failed (${response.status})`);
        setWeather(await response.json());
        setWeatherError('');
      } catch (error) { setWeather(null); setWeatherError(error instanceof Error ? error.message : 'Weather unavailable.'); }
    };
    void loadWeather();
    const timer = setInterval(loadWeather, 600000);
    return () => clearInterval(timer);
  }, [weatherCity, weatherRefresh]);

  useEffect(() => {
    if (cameraOn && videoRef.current && cameraRef.current) videoRef.current.srcObject = cameraRef.current;
  }, [cameraOn]);

  useEffect(() => () => {
    cameraRequestRef.current += 1;
    cameraRef.current?.getTracks().forEach(track => track.stop());
  }, []);

  const sendCommand = useCallback((text: string) => {
    if (!text.trim()) return;
    if (wsRef.current?.readyState === WebSocket.OPEN) wsRef.current.send(JSON.stringify({ type: 'command', text }));
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim()) return;
    sendCommand(inputValue);
    setInputValue('');
  };

  const toggleCamera = async () => {
    if (cameraPending) { cameraRequestRef.current += 1; setCameraPending(false); setCameraError('Camera request cancelled.'); return; }
    if (cameraRef.current) { cameraRef.current.getTracks().forEach(t => t.stop()); cameraRef.current = null; setCameraOn(false); return; }
    if (!navigator.mediaDevices?.getUserMedia) { setCameraError('Camera access is unavailable in this window.'); return; }
    const request = ++cameraRequestRef.current;
    setCameraPending(true);
    setCameraError('Requesting camera access…');
    let timeout: ReturnType<typeof setTimeout> | undefined;
    try {
      const stream = await Promise.race([
        navigator.mediaDevices.getUserMedia({ video: true, audio: false }).then(stream => {
          if (request !== cameraRequestRef.current) stream.getTracks().forEach(track => track.stop());
          return stream;
        }),
        new Promise<never>((_, reject) => { timeout = setTimeout(() => reject(new Error('Camera request timed out. Check device access and permissions.')), 10000); }),
      ]);
      if (request !== cameraRequestRef.current) return;
      cameraRef.current = stream;
      setCameraOn(true);
      setCameraError('');
    } catch (error) {
      if (request === cameraRequestRef.current) setCameraError(error instanceof Error ? error.message : 'Camera unavailable or permission denied.');
    } finally {
      if (timeout) clearTimeout(timeout);
      if (request === cameraRequestRef.current) setCameraPending(false);
    }
  };
  const exportChat = () => { const blob = new Blob([messages.map(m => `${m.sender}: ${m.text}`).join('\n')], { type: 'text/plain' }); const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = 'conversation.txt'; link.click(); URL.revokeObjectURL(url); };

  // Command list - each command renders > as a separate span
  const renderCommand = (cmd: string) => (
    <div>
      <span>{'>'}</span> {cmd}
    </div>
  );

  const commandList = ['Try asking a question or giving one specific command.'];

  return (
    <div className="dashboard-shell fixed inset-0 z-50 flex h-screen w-screen overflow-auto lg:overflow-hidden bg-[#050d15] text-white font-sans select-none" style={{ fontFamily: 'Arial, sans-serif' }}>
      {/* Terminal-style background */}
      <div className="absolute inset-0 bg-gradient-to-b from-[#030510] to-[#050818]" />
      <div className="absolute inset-0 opacity-5" style={{ backgroundImage: 'radial-gradient(ellipse at center, rgba(0,255,255,0.07) 0%, transparent 70%)' }} />

      {/* center stage */}
      <div className="relative z-10 flex h-full flex-1 flex-col items-center justify-center">
        <div className="relative h-[38vmin] w-[38vmin]">
          <Canvas camera={{ position: [0, 0, 6], fov: 50 }} dpr={[1, 2]}>
            <JarvisOrb aiState={aiState} />
          </Canvas>
        </div>

        {/* status line */}
        <div className="mt-3 flex items-center gap-2.5 rounded-full border border-white/10 bg-white/5 px-4 py-1.5 backdrop-blur-xl">
          <motion.span
            key={aiState}
            initial={{ scale: 0.5, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ type: 'spring', stiffness: 400, damping: 15 }}
            className={`h-2 w-2 rounded-full ${
              aiState === 'sleeping' ? 'bg-gray-500' :
              aiState === 'listening' ? 'bg-cyan-400' :
              aiState === 'thinking' ? 'bg-amber-400' :
              aiState === 'working' ? 'bg-purple-400' : 'bg-blue-500'
            } ${speaking || aiState === 'listening' ? 'animate-pulse' : ''}`}
          />
          <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-gray-300">
            {STATE_LABEL[aiState] || aiState}
          </span>
          {!connected && (
            <span className="font-mono text-[9px] uppercase tracking-widest text-rose-400">
              offline
            </span>
          )}
        </div>
      </div>

      {/* expand toggle */}
      <motion.button
        onClick={() => setExpanded((v) => !v)}
        initial={false}
        whileTap={{ scale: 0.9 }}
        style={{ WebkitAppRegion: 'no-drag' } as AppRegionStyle}
        className="absolute right-5 top-5 z-20 flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-[10px] font-mono uppercase tracking-widest text-cyan-300 backdrop-blur-xl hover:bg-white/10"
      >
        <Activity className="h-3 w-3" />
        Log
        {expanded ? <ChevronDown className="h-3 w-3" /> : <ChevronUp className="h-3 w-3" />}
      </motion.button>

      {/* left: recent sherry line (only when NOT expanded) */}
      <AnimatePresence>
        {!expanded && lastMsg && (
          <motion.div
            key="caption"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="pointer-events-none absolute bottom-8 left-1/2 z-10 max-w-md -translate-x-1/2 text-center"
          >
            <p className="font-mono text-xs text-gray-400/80">
              {lastMsg.sender === 'barq' ? 'Barq' : 'You'} · {lastMsg.text}
            </p>
          </motion.div>
        )}

        {/* expandable transcript panel */}
        {expanded && (
          <motion.div
            key="panel"
            initial={{ opacity: 0, y: 40, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 40, scale: 0.98 }}
            transition={{ type: 'spring', stiffness: 220, damping: 24 }}
            className="absolute bottom-5 left-1/2 z-20 flex max-h-[46vh] w-[min(560px,92vw)] -translate-x-1/2 flex-col overflow-hidden rounded-2xl border border-white/10 bg-[#0a0f1e]/85 shadow-2xl backdrop-blur-2xl"
          >
            <div ref={logRef} className="flex-1 space-y-2.5 overflow-y-auto custom-scrollbar p-4">
              {messages.length === 0 ? (
                <p className="py-14 text-center font-mono text-xs text-gray-600 italic">
                  Say the wake word to begin a conversation...
                </p>
              ) : (
                messages.map((m) => (
                  <motion.div
                    key={m.id}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    className={`max-w-[85%] rounded-xl px-3 py-2 text-xs leading-relaxed ${
                      m.sender === 'you'
                        ? 'ml-auto border border-blue-500/20 bg-blue-600/10 text-blue-100'
                        : m.sitrep
                        ? 'mr-auto border border-emerald-500/20 bg-emerald-600/10 text-emerald-100'
                        : 'mr-auto border border-white/10 bg-white/5 text-gray-200'
                    }`}
                  >
                    <span className="mb-0.5 block font-mono text-[9px] uppercase tracking-widest opacity-60">
                      {m.sender === 'you' ? 'You' : m.sitrep ? 'Barq · sitrep' : 'Barq'}
                    </span>
                    {m.text}
                  </motion.div>
                ))
              )}
            </div>
            <div className="border-t border-white/10 px-4 py-2 text-center font-mono text-[9px] uppercase tracking-widest text-gray-500">
              Expand to follow the live transcript
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </main>
  );
}