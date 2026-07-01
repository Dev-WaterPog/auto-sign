const STORAGE_KEY = "auto-sign-access-token";

export function getAccessToken(): string {
  if (typeof window === "undefined") return "";
  return window.localStorage.getItem(STORAGE_KEY) ?? "";
}

export function setAccessToken(token: string): void {
  window.localStorage.setItem(STORAGE_KEY, token);
}

export function clearAccessToken(): void {
  window.localStorage.removeItem(STORAGE_KEY);
}
