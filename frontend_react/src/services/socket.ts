import { io, Socket } from 'socket.io-client';
import { WS_URL } from '../api/axios';

let socket: Socket | null = null;

export function getSocket(): Socket {
  if (!socket) {
    socket = io(WS_URL, {
      transports: ['websocket'],
      reconnectionAttempts: Infinity,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 10000,
      auth: {
        token: localStorage.getItem('access_token') || ''
      }
    });
  }
  return socket;
}

/**
 * Update the auth token on the existing socket connection.
 * Call this after token refresh to avoid stale tokens on reconnection.
 */
export function updateSocketToken(): void {
  if (socket) {
    const newToken = localStorage.getItem('access_token') || '';
    (socket.auth as Record<string, string>).token = newToken;
  }
}

export function disconnectSocket(): void {
  if (socket) {
    socket.disconnect();
    socket = null;
  }
}
