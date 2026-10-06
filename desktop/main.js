const { app, BrowserWindow, Menu, Tray, globalShortcut, ipcMain } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const WebSocket = require('ws');
const fs = require('fs');
const http = require('http');

const ROOT = path.join(__dirname, '..');
const VENV_PY = path.join(ROOT, 'venv', 'Scripts', 'python.exe');
const BARQ_UI = path.join(ROOT, 'barq_ui');
const UI_URL = 'http://127.0.0.1:3000';
const BACKEND_URL = 'ws://127.0.0.1:8080/ws';
const BACKEND_HTTP = 'http://127.0.0.1:8080';
const AUTH_FILE = path.join(ROOT, 'barq_data', '.barq_auth');

let win = null;
let ws = null;
let backend = null;
let nextServer = null;
let wsRetry = null;
let tray = null;
let isQuitting = false;
let authToken = null;
let pendingWake = false;

const START_HIDDEN = process.argv.includes('--hidden');
const SERVICE_MODE = process.env.BARQ_SERVICE_MODE === '1';

function log(...args) {
  console.log('[Barq]', ...args);
}

function manualWake() {
  log('Manual wake triggered');
  const token = readAuthToken();
  const req = http.request(`${BACKEND_HTTP}/wake`, { method: 'POST', headers: { 'X-Barq-Token': token || '' } }, (res) => {
    res.resume();
    log('Manual wake request sent');
  });
  req.on('error', (e) => {
    log('Manual wake error:', e.message);
  });
  req.end();
}

function readAuthToken() {
  try {
    if (fs.existsSync(AUTH_FILE)) {
      return fs.readFileSync(AUTH_FILE, 'utf8').trim();
    }
  } catch (e) {
    log('Auth token read error:', e);
  }
  return null;
}

function getWSUrl() {
  const token = readAuthToken();
  if (token) {
    return `${BACKEND_URL}?token=${encodeURIComponent(token)}`;
  }
  return BACKEND_URL;
}

function checkBackendHealth(cb) {
  const req = http.get(BACKEND_HTTP + '/health/live', (res) => {
    res.resume();
    cb(res.statusCode === 200);
  });
  req.on('error', () => cb(false));
  req.setTimeout(2000, () => { req.destroy(); cb(false); });
}

function checkUIHealth(cb) {
  const req = http.get(UI_URL, (res) => {
    res.resume();
    cb(res.statusCode === 200);
  });
  req.on('error', () => cb(false));
  req.setTimeout(2000, () => { req.destroy(); cb(false); });
}

function startBackend() {
  if (backend) return;
  checkBackendHealth((healthy) => {
    if (healthy) {
      log('Backend already running on port 8080');
      return;
    }
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
  });
}

function startNext() {
  if (nextServer) return;
  checkUIHealth((healthy) => {
    if (healthy) {
      log('UI server already running on port 3000');
      return;
    }
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
    ws = new WebSocket(getWSUrl());
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
        log('Wake word heard - showing window.');
        pendingWake = true;
        if (win && !win.isDestroyed()) {
          win.show();
          win.focus();
        }
      } else if (msg.type === 'sleep') {
        log('Sleep - hiding window.');
        pendingWake = false;
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
  const { screen } = require('electron');
  const display = screen.getPrimaryDisplay().workArea;
  const width = Math.min(1320, display.width - 40);
  const height = Math.min(850, display.height - 40);
  win = new BrowserWindow({
    width,
    height,
    minWidth: 420,
    minHeight: 520,
    show: !START_HIDDEN || pendingWake,
    frame: true,
    transparent: false,
    backgroundColor: '#050d15',
    resizable: true,
    alwaysOnTop: false,
    skipTaskbar: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    },
  });

  const [x, y] = [display.x + Math.floor((display.width - width) / 2), display.y + Math.floor((display.height - height) / 2)];
  win.setBounds({ x, y, width, height });

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
      { label: 'Wake Barq', click: () => { manualWake(); } },
      { type: 'separator' },
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
  ipcMain.handle('barq-token', () => readAuthToken());
  if (process.platform === 'win32' && app.isPackaged) {
    app.setLoginItemSettings({
      openAtLogin: true,
      path: process.execPath,
      args: ['--hidden'],
    });
  }

  // Register global shortcut for manual wake (Ctrl+Shift+Space)
  globalShortcut.register('Control+Shift+Space', () => {
    log('Global shortcut triggered - manual wake');
    manualWake();
  });

  if (!SERVICE_MODE) {
    startBackend();
    startNext();
    setInterval(() => {
      startBackend();
      startNext();
    }, 10000);
  }
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
