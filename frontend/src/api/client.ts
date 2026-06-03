/// <reference types="vite/client" />
import axios from "axios";

const API_BASE = import.meta.env.VITE_API_URL ?? "/api";

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 15000,
});

const wsBase = import.meta.env.VITE_API_URL
  ? import.meta.env.VITE_API_URL.replace(/^https/, "wss").replace(/^http/, "ws")
  : `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}`;

export const WS_URL = `${wsBase}/ws/stream`;
