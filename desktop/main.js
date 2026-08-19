const { app, BrowserWindow, Menu, Tray } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const WebSocket = require('ws');

const ROOT = path.join(__dirname, '..');
const VENV_PY = path.join(ROOT, 'venv', 'Scripts', 'python.exe');
const BARQ_UI = path.join(ROOT, 'barq_ui');
const UI_URL = 'http://127.0.0.1:3000';
const BACKEND_URL = 'ws://127.0.0.1:8000/ws';

let win = null;
let ws = null;
let backend = null;
let nextServer = null;
let wsRetry = null;
let tray = null;
let isQuitting = false;

const START_HIDDEN = process.argv.includes('--hidden');

function log(...args) {
  console.log('[Barq]', ...args);
}

function startBackend() {
  if (backend) return;
  log('Starting backend...');
  backend = spawn(VENV_PY, ['server.py'], {
    cwd: ROOT,
    windowsHide: true,
    stdio: 'ignore',
  });
  backend.on('exit', (code) => {
    log('Backend exited', code);
    backend = null;
  });
}

function startNext() {
  if (nextServer) return;
  log('Starting UI server...');
  const npmCmd = process.platform === 'win32' ? 'npm.cmd' : 'npm';
  nextServer = spawn(npmCmd, ['run', 'start'], {
    cwd: BARQ_UI,
    windowsHide: true,
    stdio: 'ignore',
    shell: true,
  });
  nextServer.on('exit', (code) => {
    log('UI server exited', code);
    nextServer = null;
  });
}

function waitForUI(cb, attempts = 0) {
  if (attempts > 60) {
    log('UI server never became ready.');
    return;
  }
  const http = require('http');
  const req = http.get('http://127.0.0.1:3000', (res) => {
    res.resume();
    cb();
  });
  req.on('error', () => {
    setTimeout(() => waitForUI(cb, attempts + 1), 1200);
  });
  req.setTimeout(2000, () => {
    req.destroy();
    setTimeout(() => waitForUI(cb, attempts + 1), 1200);
  });
}

function connectWS() {
  clearTimeout(wsRetry);
  if (ws) return;
  try {
    ws = new WebSocket(BACKEND_URL);
  } catch {
    ws = null;
  }
  if (!ws) {
    wsRetry = setTimeout(connectWS, 1500);
    return;
  }
  ws.on('open', () => log('Backend connected.'));
  ws.on('message', (raw) => {
    try {
      const msg = JSON.parse(raw.toString());
      if (msg.type === 'wake') {
        log('Wake word heard - showing overlay.');
        if (win && !win.isDestroyed()) {
          win.show();
          win.focus();
        }
      } else if (msg.type === 'sleep') {
        log('Sleep - hiding overlay.');
        if (win && !win.isDestroyed()) win.hide();
      }
    } catch {
      /* ignore */
    }
  });
  ws.on('close', () => {
    ws = null;
    wsRetry = setTimeout(connectWS, 1500);
  });
  ws.on('error', () => {
    ws = null;
    wsRetry = setTimeout(connectWS, 1500);
  });
}

function createWindow() {
  win = new BrowserWindow({
    width: 540,
    height: 620,
    minWidth: 420,
    minHeight: 520,
    show: !START_HIDDEN,
    frame: false,
    transparent: true,
    backgroundColor: '#00000000',
    resizable: true,
    alwaysOnTop: true,
    skipTaskbar: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    },
  });

  const { screen } = require('electron');
  const display = screen.getPrimaryDisplay().workArea;
  const [x, y] = [display.x + display.width - 540 - 20, display.y + display.height - 620 - 20];
  win.setBounds({ x, y, width: 540, height: 620 });

  win.loadURL(UI_URL);

  win.on('close', (event) => {
    if (!isQuitting) {
      event.preventDefault();
      win.hide();
    }
  });

  win.on('closed', () => {
    win = null;
  });
}

function createTray() {
  tray = new Tray(path.join(ROOT, 'barq.png'));
  tray.setToolTip('Barq Assistant');
  tray.setContextMenu(
    Menu.buildFromTemplate([
      { label: 'Show Barq', click: () => { if (win) { win.show(); win.focus(); } } },
      { label: 'Hide', click: () => { if (win) win.hide(); } },
      { type: 'separator' },
      { label: 'Quit', click: () => { isQuitting = true; app.quit(); } },
    ])
  );
  tray.on('double-click', () => {
    if (win) {
      if (win.isVisible()) win.hide();
      else { win.show(); win.focus(); }
    }
  });
}

app.whenReady().then(() => {
  if (process.platform === 'win32') {
    app.setLoginItemSettings({
      openAtLogin: true,
      path: process.execPath,
      args: ['--hidden'],
    });
  }

  startBackend();
  startNext();
  setTimeout(connectWS, 1500);
  waitForUI(() => {
    createWindow();
    setTimeout(createTray, 300);
  });
});

app.on('window-all-closed', (e) => {
  // keep running in background (Siri-like) unless user explicitly quits
  e.preventDefault();
});

app.on('before-quit', () => {
  isQuitting = true;
  try {
    if (backend) backend.kill();
  } catch {}
  try {
    if (nextServer) nextServer.kill();
  } catch {}
  if (ws) ws.close();
});