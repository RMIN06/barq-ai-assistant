# Barq — One-Time Run Guide (sleeps 24/7, wakes on command)

Set `GROQ_API_KEY` and `DEEPGRAM_API_KEY` in `.env`. Wake words use microphone
voice activity detection followed by Groq Whisper. Picovoice is optional.

## What you get
- Backend + UI + overlay all start together and keep running in the background.
- Overlay stays **hidden** until you say `Barq` or `Jarvis`, then the dashboard opens.
- Say a sleep phrase to dismiss it (see wake/sleep words below).

---

## 1. One-time setup (already done for you)
- Python 3.12 runtime is in `.python312/`; the existing `venv/` uses it.
- Frontend + desktop deps: installed on **D drive** (no C-drive space used)
  - `barq_ui/node_modules`
  - `desktop/node_modules`
  - npm cache: `D:\Barq Assistant\barq-ai-assistant\.npm-cache`
  - Electron cache: `D:\Barq Assistant\barq-ai-assistant\.electron-cache`

## 2. Run it once (this is the whole setup)
Open **Windows PowerShell** (not VS Code — it doesn't need to be open):

```powershell
cd "D:\Barq Assistant\barq-ai-assistant\desktop"
npm start
```

That's it. It will:
1. Start the Python backend (which begins listening for the wake word).
2. Start the UI server.
3. Open the overlay window once so you can confirm it works.

## 3. Make it auto-start at login and stay asleep until you call it
Run once (PowerShell, from the `desktop` folder):

```powershell
npm run install-startup
```

This adds a **Startup shortcut** that launches Barq hidden at every Windows login.
From then on it just lives in your system tray, silent, until you say the wake word.

> To change the keys later, copy `.env.example` to `.env` (same folder as
> `config.py`) and fill in `GROQ_API_KEY` / `DEEPGRAM_API_KEY`.

---

## Wake words (any of these activate it)
`barq`, `jarvis`, `hey barq`, `hey jarvis`

## Sleep words (dismiss it back to the background)
`go to sleep`, `sleep mode`, `standby`, `shut down`, `goodnight`, `turn off`

---

## Controlling the overlay
- **Wake** → say `"Barq"` → small window appears.
- **Transcript** → click the **Transcript** button (top right) to expand/collapse the text view.
- **Move it** → drag the empty top strip.
- **Hide it** → say a sleep word, or right-click the tray icon → Hide.
- **Quit for real** → right-click the tray icon → Quit.

---

## Troubleshooting
- **"No speech heard" / wake word not reacting**
  Make sure your default microphone is set and unmuted in Windows, and there is
  no other app hogging the mic. Speak clearly; the wake check runs about every 3s.
- **Port 8000/3000 busy** → close any previous Barq/python/`next` process:
  ```powershell
  Get-Process | Where-Object { $_.ProcessName -match 'python|next|node|electron' } |
    Stop-Process -Force
  ```
- **Want a console-less Python-only background run** (no overlay UI, just voice):
  ```powershell
  cd "D:\Barq Assistant\barq-ai-assistant"
  Start-Process .\venv\Scripts\pythonw.exe -ArgumentList "server.py"
  ```
  (Overlay UI won't appear in this mode; use `npm start` for the full Siri-style
  overlay.)
