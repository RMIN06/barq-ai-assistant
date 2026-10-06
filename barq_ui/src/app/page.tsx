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

      {/* Scanlines effect */}
      <div className="absolute inset-0 pointer-events-none opacity-10" style={{
        backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,255,255,0.03) 2px, rgba(0,255,255,0.03) 4px)',
        backgroundSize: '100% 4px'
      }} />

      {/* Header bar */}
      <div className="absolute top-0 left-0 right-0 h-10 border-b border-cyan-400/20 bg-[#020412]/90 backdrop-blur-sm flex items-center justify-between px-4 z-20">
        <div className="flex items-center gap-3 text-cyan-400 font-mono text-xs">
          <span className="relative">
            <span className="relative inline-block w-2 h-2 rounded-full bg-cyan-400 animate-pulse mr-2" />
            J.A.R.V.I.S
          </span>
          <span className="text-gray-500 mx-2">|</span>
          <span className="text-green-400">{connected ? aiState.toUpperCase() : 'OFFLINE'}</span>
          <span className="text-gray-500 mx-2">|</span>
          <span className="text-gray-400 font-mono"><Clock3 size={12} className="inline"/> {clock}</span>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setSettingsOpen(v => !v)} aria-label="Settings" className="rounded border border-cyan-900 p-1"><Settings2 size={16}/></button>
          <button
            onClick={wakeBarq}
            className="px-3 py-1 text-xs font-mono bg-cyan-500/20 border border-cyan-500/30 rounded hover:bg-cyan-500/30 transition-colors"
          >
            WAKE
          </button>
          <button
            onClick={sleepBarq}
            className="px-3 py-1 text-xs font-mono bg-red-500/20 border border-red-500/30 rounded hover:bg-red-500/30 transition-colors"
          >
            SLEEP
          </button>
        </div>
      </div>

      {settingsOpen && <div className="absolute right-4 top-12 z-30 rounded border border-cyan-800 bg-[#102532] p-4 text-sm">Wake word: Barq or Jarvis<br/>Camera starts only when enabled.<br/>Conversation is kept on this device.<label className="mt-3 block">Weather city<input value={cityDraft} onChange={e => setCityDraft(e.target.value)} placeholder="City name" className="mt-1 block w-full rounded border border-cyan-700 bg-[#06141d] p-2" /></label><button className="mt-2 rounded bg-cyan-700 px-3 py-1" onClick={() => { const city = cityDraft.trim(); localStorage.setItem('barq_weather_city', city); setWeatherCity(city); setWeatherRefresh(v => v + 1); }}>Save city</button><label className="mt-3 block">Local connection token<input type="password" autoComplete="off" value={tokenDraft} onChange={e => setTokenDraft(e.target.value)} className="mt-1 block w-full rounded border border-cyan-700 bg-[#06141d] p-2" /></label><button className="mt-2 rounded bg-cyan-700 px-3 py-1" onClick={() => { localStorage.setItem('barq_auth_token', tokenDraft.trim()); wsRef.current?.close(); setWeatherRefresh(v => v + 1); setSettingsOpen(false); }}>Connect</button></div>}

      <aside className="dashboard-left absolute bottom-7 left-4 top-14 w-[23%] min-w-[240px] space-y-3 overflow-y-auto text-cyan-300">
        <section className="rounded-xl border border-cyan-900 bg-[#0a1b27] p-4"><h2 className="mb-3 flex gap-2 font-semibold"><Cpu size={17}/>System Stats</h2><p className="text-sm text-slate-400">{stats ? `CPU ${stats.cpu.toFixed(0)}% · RAM ${stats.memory.toFixed(0)}% · Disk ${stats.disk.toFixed(0)}%` : 'Live stats unavailable'}</p></section>
        <section className="rounded-xl border border-cyan-900 bg-[#0a1b27] p-4"><h2 className="mb-3 font-semibold">☁ Weather</h2>{weather ? <div className="text-sm text-slate-300"><strong className="text-xl text-cyan-200">{weather.temperature.toFixed(1)}°C</strong><div>{weather.city}, {weather.country}</div><div className="mt-2 text-xs">Humidity {weather.humidity}% · Wind {weather.wind} km/h · Feels like {weather.feels_like}°C</div><div className="mt-1 text-xs text-slate-500">Open-Meteo</div></div> : <p className="text-sm text-slate-400">{weatherError}</p>}</section>
        <section className="rounded-xl border border-cyan-900 bg-[#0a1b27] p-4"><div className="flex justify-between"><h2 className="flex gap-2 font-semibold"><Camera size={17}/>Camera</h2><button onClick={toggleCamera} aria-label="Toggle camera" title={cameraPending ? 'Cancel camera request' : cameraOn ? 'Turn camera off' : 'Turn camera on'}><Power size={17}/></button></div><div className="mt-3 flex h-36 items-center justify-center rounded border border-cyan-900 bg-[#041019]">{cameraOn ? <video ref={videoRef} autoPlay muted playsInline className="h-full w-full object-contain"/> : <div className="text-center text-slate-500"><CameraOff className="mx-auto"/>{cameraPending ? 'Connecting camera…' : 'Camera off'}</div>}</div><p className="mt-2 text-xs text-slate-400">{cameraError || 'Press power to activate camera.'}</p></section>
        <section className="rounded-xl border border-cyan-900 bg-[#0a1b27] p-4"><h2 className="font-semibold">System Uptime</h2><p className="mt-2 text-sm text-slate-400">{stats ? `${Math.floor(stats.uptime / 3600)} hours` : 'Unavailable'} · {messages.filter(m => m.sender === 'you').length} commands</p></section>
      </aside>

      <section className="dashboard-center absolute bottom-8 left-[25%] right-[29%] top-14 flex flex-col items-center justify-center gap-6 text-center"><div className={`flex h-64 w-64 items-center justify-center rounded-full border-2 border-cyan-800 shadow-[0_0_35px_#053347] ${isListening ? 'animate-pulse' : ''}`}><div className="flex h-40 w-40 items-center justify-center rounded-full border border-cyan-600 bg-[#12384a] text-4xl tracking-widest text-cyan-400">•••••</div></div><h1 className="text-2xl font-bold tracking-widest text-cyan-100">J.A.R.V.I.S</h1><p className="rounded bg-[#102532] px-4 py-2 text-sm text-cyan-300">● {isListening ? 'Listening' : 'Listening for wake word'}</p><div className="flex gap-5"><button onClick={toggleCamera} aria-label="Camera" className="rounded-lg border border-cyan-900 p-3"><Camera/></button><button onClick={wakeBarq} aria-label="Wake" className="rounded-lg border border-cyan-900 p-3"><Mic/></button><button onClick={() => inputRef.current?.focus()} aria-label="Type message" className="rounded-lg border border-cyan-900 p-3"><Keyboard/></button></div></section>

      {/* Main terminal area */}
      <div className="dashboard-chat absolute top-14 bottom-7 left-[72%] right-4 flex flex-col overflow-hidden rounded-xl border border-cyan-900 bg-[#071620] p-4">
        {/* Output panel */}
        <div className="flex-1 overflow-y-auto pr-2" ref={logRef} style={{ fontSize: '13px', lineHeight: '1.6' }}>
          <div className="mb-2 flex justify-between border-b border-cyan-900 pb-2 text-sm text-cyan-300"><strong>Conversation</strong><span className="flex gap-2"><button aria-label="Clear conversation" onClick={() => setMessages([])}><Trash2 size={15}/></button><button aria-label="Export conversation" onClick={exportChat}><Download size={15}/></button></span></div>
          <div ref={logRef} className="font-mono text-sm leading-relaxed space-y-1" style={{ fontFamily: '"JetBrains Mono", "Fira Code", monospace' }}>
            {messages.length === 0 ? (
              <div className="text-cyan-400/40 text-center py-20 font-mono text-sm">
                <div className="mb-4">
                  <span className="text-cyan-400">●</span> J.A.R.V.I.S ready
                </div>
                <div className="text-gray-500 text-xs mb-2">{connected ? 'Connected' : 'Backend offline'}</div>
                <div className="text-gray-500 text-xs">Type a message or use the wake button.</div>
                <div className="mt-4 text-cyan-400/60 text-xs font-mono">
      {commandList.map((cmd) => renderCommand(cmd))}
                </div>
              </div>
            ) : (
              messages.map((m) => (
                <div key={m.id} className={`flex gap-2 items-start ${m.sitrep ? 'border-l-2 border-emerald-400 pl-2' : ''} ${m.sender === 'you' ? 'text-blue-300' : m.sitrep ? 'text-emerald-300' : 'text-cyan-300'}`}>
                  <span className="text-gray-500 font-mono text-xs w-16 shrink-0 select-none">
                    [{new Date(m.timestamp).toLocaleTimeString('en-US', { hour12: false })}]
                  </span>
                  <span className="text-gray-400 font-mono text-xs w-14 shrink-0 select-none">
                    {m.sender === 'you' ? 'USER' : m.sitrep ? 'SITREP' : 'BARQ'}
                  </span>
                  <span className="flex-1 min-w-0 break-words">{m.text}</span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Input bar */}
        <div className="mt-4 border-t border-cyan-400/20 pt-3 flex items-center gap-2">
          <span className="text-cyan-400 font-mono text-sm select-none mr-2">›</span>
          <form onSubmit={handleSubmit} className="flex-1 flex items-center gap-2">
            <input
              ref={inputRef}
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Escape') setInputValue(''); }}
              className="flex-1 bg-transparent border-none outline-none text-white font-mono text-sm caret-cyan-400 placeholder:text-gray-600"
              placeholder="Enter command or type naturally..."
              autoComplete="off"
              spellCheck={false}
              autoFocus
            />
            <button
              type="submit"
              disabled={!inputValue.trim() || !connected}
              className="px-3 py-1 text-xs font-mono bg-cyan-500/20 border border-cyan-500/30 rounded hover:bg-cyan-500/30 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <Send size={15}/>
            </button>
          </form>
          <button
            onClick={wakeBarq}
            className="px-3 py-1.5 text-xs font-mono bg-cyan-500/20 border border-cyan-500/30 rounded hover:bg-cyan-500/30 transition-colors ml-2"
            title="Wake (Ctrl+Shift+Space)"
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