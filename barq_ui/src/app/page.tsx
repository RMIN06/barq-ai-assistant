'use client';
import { useEffect, useRef, useState, type CSSProperties } from 'react';
import { Canvas } from '@react-three/fiber';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronUp, ChevronDown, Activity } from 'lucide-react';
import JarvisOrb, { OrbState } from '@/components/JarvisOrb';

type AppRegionStyle = CSSProperties & { WebkitAppRegion?: string };

type Msg = { id: string; sender: 'you' | 'barq'; text: string; sitrep?: boolean };

interface WireMsg {
  type?: string;
  aiState?: OrbState;
  text?: string;
  sitrep?: boolean;
}

const STATE_LABEL: Record<OrbState, string> = {
  sleeping: 'Standby',
  listening: 'Listening',
  thinking: 'Thinking',
  speaking: 'Speaking',
  working: 'Working',
};

export default function Home() {
  const [aiState, setAiState] = useState<OrbState>('sleeping');
  const [expanded, setExpanded] = useState(false);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [connected, setConnected] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let retry: ReturnType<typeof setTimeout>;

    const open = () => {
      ws = new WebSocket('ws://127.0.0.1:8000/ws');
      ws.onopen = () => setConnected(true);
      ws.onclose = () => {
        setConnected(false);
        retry = setTimeout(open, 1500);
      };
      ws.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data) as WireMsg;
          if (data.aiState) setAiState(data.aiState);
          if (data.type === 'wake') setExpanded(true);
          if (data.type === 'sleep') setExpanded(false);
          const text = data.text;
          if (text) {
            const sender: 'you' | 'barq' = data.type === 'user' ? 'you' : 'barq';
            setMessages((m) => [
              ...m.slice(-60),
              { id: `${sender}-${Date.now()}`, sender, text, sitrep: Boolean(data.sitrep) },
            ]);
          }
        } catch {
          /* ignore */
        }
      };
    };
    open();
    const t = setInterval(() => logRef.current?.scrollTo({ top: 1e6, behavior: 'smooth' }), 400);
    return () => {
      ws?.close();
      clearTimeout(retry);
      clearInterval(t);
    };
  }, []);

  const speaking = aiState === 'speaking';
  const lastMsg = messages[messages.length - 1];

  return (
    <main className="relative flex h-screen w-full overflow-hidden bg-[#05070f] text-white font-sans select-none">
      {/* frameless-window drag region */}
      <div style={{ WebkitAppRegion: 'drag' } as AppRegionStyle} className="absolute inset-x-0 top-0 z-30 h-8" />
      {/* animated aurora background */}
      <div className="aurora aurora-a pointer-events-none h-[30vmax] w-[30vmax] bg-cyan-500/15" />
      <div className="aurora aurora-b pointer-events-none h-[26vmax] w-[26vmax] bg-blue-600/15" />
      <div className="aurora aurora-c pointer-events-none h-[20vmax] w-[20vmax] bg-fuchsia-600/10" />

      {/* brand logo */}
      <div style={{ WebkitAppRegion: 'no-drag' } as AppRegionStyle} className="absolute left-5 top-5 z-20 flex items-center gap-2.5">
        <img
          src="/barq.png"
          alt="BARQ"
          className="h-9 w-9 rounded-lg border border-white/15 object-cover shadow-lg"
        />
      </div>

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