// One anonymous session id per browser, kept in localStorage, so the
// backend can tie a customer's messages (and their trace) together.
export function getSessionId(): string {
  if (typeof window === "undefined") return "server";
  let id = window.localStorage.getItem("zeroqueue-session");
  if (!id) {
    id = "web-" + Math.random().toString(36).slice(2) + Date.now().toString(36);
    window.localStorage.setItem("zeroqueue-session", id);
  }
  return id;
}
