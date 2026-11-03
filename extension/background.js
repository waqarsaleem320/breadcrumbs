// Talks to the local Breadcrumbs check service. Pages never see the token.
const SERVICE = "http://127.0.0.1:8765";

async function call(path, body) {
  const { token = "" } = await chrome.storage.local.get("token");
  const response = await fetch(SERVICE + path, {
    method: body ? "POST" : "GET",
    headers: { "X-Breadcrumbs-Token": token },
    body,
  });
  const data = await response.json().catch(() => ({ error: "The check service sent an unreadable reply." }));
  if (!response.ok) throw new Error(data.error || `Check service error ${response.status}`);
  return data;
}

function toBytes(dataUrl) {
  const raw = atob(dataUrl.split(",")[1]);
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
}

chrome.runtime.onMessage.addListener((message, _sender, reply) => {
  const jobs = {
    health: () => call("/health"),
    check: () => call("/check", toBytes(message.dataUrl)),
    blur: () => call("/blur", toBytes(message.dataUrl)),
    feed: () => call("/feed", toBytes(message.dataUrl)),
  };
  const job = jobs[message.type];
  if (!job) return false;
  job().then((data) => reply({ ok: true, data }), (error) => reply({ ok: false, error: error.message }));
  return true; // Keep the channel open for the async reply.
});
