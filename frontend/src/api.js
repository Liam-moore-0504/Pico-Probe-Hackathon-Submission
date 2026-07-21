const API = location.port === "5173" ? "/api" : "";
export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}
export function token() {
  return (
    localStorage.getItem("picoprobe_token") ||
    localStorage.getItem("orchestra_token")
  );
}
export function setTokens(data) {
  localStorage.setItem("picoprobe_token", data.access_token);
  localStorage.setItem("picoprobe_refresh", data.refresh_token || "");
  localStorage.removeItem("orchestra_token");
  localStorage.removeItem("orchestra_refresh");
}
export function clearTokens() {
  localStorage.removeItem("picoprobe_token");
  localStorage.removeItem("picoprobe_refresh");
  localStorage.removeItem("orchestra_token");
  localStorage.removeItem("orchestra_refresh");
}
let refreshPromise = null;
async function refreshSession() {
  const refreshToken = localStorage.getItem("picoprobe_refresh");
  if (!refreshToken) return false;
  if (!refreshPromise)
    refreshPromise = fetch(API + "/auth/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
      .then(async (response) => {
        if (!response.ok) return false;
        setTokens(await response.json());
        return true;
      })
      .catch(() => false)
      .finally(() => {
        refreshPromise = null;
      });
  return refreshPromise;
}
function sessionNeedsRefresh() {
  try {
    const payload = JSON.parse(
      atob(token().split(".")[1].replaceAll("-", "+").replaceAll("_", "/")),
    );
    return !payload.exp || payload.exp * 1000 < Date.now() + 15_000;
  } catch {
    return true;
  }
}
function errorMessage(detail, status) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail
      .map((item) => {
        const field = Array.isArray(item.loc)
          ? item.loc.filter((part) => part !== "body").join(" → ")
          : "";
        return `${field ? field + ": " : ""}${item.msg || "Invalid value"}`;
      })
      .join(" · ");
  if (detail && typeof detail === "object")
    return detail.message || JSON.stringify(detail);
  return `Request failed (${status})`;
}
export async function api(path, options = {}) {
  if (token() && !path.startsWith("/auth/") && sessionNeedsRefresh())
    await refreshSession();
  const headers = { ...(options.headers || {}) };
  if (!(options.body instanceof FormData))
    headers["Content-Type"] = "application/json";
  if (token()) headers.Authorization = `Bearer ${token()}`;
  let response = await fetch(API + path, { ...options, headers });
  if (
    response.status === 401 &&
    token() &&
    !options.sessionRetried &&
    !path.startsWith("/auth/") &&
    (await refreshSession())
  ) {
    response = await fetch(API + path, {
      ...options,
      sessionRetried: true,
      headers: { ...headers, Authorization: `Bearer ${token()}` },
    });
  }
  if (response.status === 401 && token() && !path.startsWith("/auth/")) {
    clearTokens();
    throw new ApiError("Your Pico Probe session expired. Sign in again.", 401);
  }
  if (response.status === 204) return null;
  const body = await response.json().catch(() => ({}));
  if (!response.ok)
    throw new ApiError(
      errorMessage(body.detail, response.status),
      response.status,
    );
  return body;
}
export const get = (p) => api(p);
export const post = (p, b = {}) =>
  api(p, { method: "POST", body: JSON.stringify(b) });
export const put = (p, b = {}) =>
  api(p, { method: "PUT", body: JSON.stringify(b) });
export const del = (p) => api(p, { method: "DELETE" });
