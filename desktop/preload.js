const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('barqDesktop', {
  token: () => ipcRenderer.invoke('barq-token'),
});
