const configured = (process.env.REACT_APP_BACKEND_URL || '').trim();

function normalizeBaseUrl(raw) {
  if (!raw) return '';
  return raw.endsWith('/') ? raw.slice(0, -1) : raw;
}

function inferLocalBackend() {
  if (typeof window === 'undefined') return 'http://localhost:8000';
  const { protocol, hostname } = window.location;
  return `${protocol}//${hostname}:8000`;
}

const baseUrl = normalizeBaseUrl(configured || inferLocalBackend());
export const API_BASE = `${baseUrl}/api`;

