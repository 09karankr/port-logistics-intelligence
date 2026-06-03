import axios from "axios";

// VITE_API_URL is set in Vercel env vars (e.g. https://your-ngrok-url.ngrok-free.app)
// Falls back to /api for local Docker / dev server
const API_BASE = import.meta.env.VITE_API_URL ?? "/api";

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 15000,
});

// WebSocket URL derived from API base
const wsBase = import.meta.env.VITE_API_URL
  ? import.meta.env.VITE_API_URL.replace(/^https/, "wss").replace(/^http/, "ws")
  : `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}`;

export const WS_URL = `${wsBase}/ws/stream`;
