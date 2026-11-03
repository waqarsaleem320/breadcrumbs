// Watches photo pickers in post composers and checks a photo before it is posted.
(() => {
  const swapped = new WeakSet(); // Inputs we refilled with a blurred photo; do not re-check those.

  const STYLE = `
    :host { all: initial; }
    .box { position: fixed; right: 20px; bottom: 20px; z-index: 2147483647; width: 360px;
      font: 14px/1.5 system-ui, sans-serif; color: #13243a; background: #fff; border: 1px solid #d3dbd7;
      border-radius: 14px; box-shadow: 0 18px 40px -18px rgba(19,36,58,.45); overflow: hidden; }
    .top { display: flex; align-items: center; gap: 10px; padding: 12px 14px; background: #13243a; color: #fff; }
    .top b { font-size: 15px; } .top button { margin-left: auto; background: none; border: 0; color: #fff;
      font-size: 18px; cursor: pointer; }
    .body { padding: 14px 16px 16px; }
    .title { font-weight: 700; font-size: 16px; margin: 0 0 6px; }
    .warn .title { color: #b3261e; } .ok .title { color: #2c8459; }
    .why { color: #56677a; font-size: 13px; margin: 8px 0 0; }
    .row { display: flex; gap: 8px; margin-top: 14px; }
    .row button { flex: 1; border-radius: 9px; padding: 9px 10px; font: 600 13px system-ui, sans-serif; cursor: pointer;
      border: 1px solid #d3dbd7; background: #fff; color: #13243a; }
    .row button.main { background: #13243a; color: #fff; border-color: #13243a; }
    button:focus-visible { outline: 3px solid #1d7a72; outline-offset: 2px; }
    .bar { height: 4px; background: #e7ece9; overflow: hidden; border-radius: 2px; margin-top: 12px; }
    .bar i { display: block; width: 40%; height: 100%; background: #1d7a72; animation: run 1.2s ease-in-out infinite; }
    @keyframes run { from { transform: translateX(-100%); } to { transform: translateX(260%); } }
    @media (prefers-reduced-motion: reduce) { .bar i { animation: none; width: 100%; } }`;

  let host;
  function panel(html) {
    if (!host) {
      host = document.createElement("div");
      host.attachShadow({ mode: "open" });
      document.documentElement.appendChild(host);
    }
    host.shadowRoot.innerHTML = `<style>${STYLE}</style><div class="box" role="dialog" aria-live="polite"
      aria-label="Breadcrumbs check"><div class="top"><b>Breadcrumbs</b><button aria-label="Close">×</button></div>
      <div class="body">${html}</div></div>`;
    host.shadowRoot.querySelector(".top button").onclick = () => host.remove() || (host = null);
    return host.shadowRoot;
  }

  const text = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const ask = (type, dataUrl) => new Promise((done) => chrome.runtime.sendMessage({ type, dataUrl }, done));
  const read = (file) => new Promise((done) => { const r = new FileReader(); r.onload = () => done(r.result); r.readAsDataURL(file); });

  async function useBlurred(input, file, dataUrl) {
    panel(`<p class="title">Blurring clues…</p><p class="why">SAM 3.1 finds signs and logos, then Muse Spark checks the place can no longer be read.</p><div class="bar"><i></i></div>`);
    const answer = await ask("blur", dataUrl);
    if (!answer || !answer.ok) {
      panel(`<div class="warn"><p class="title">Could not blur this photo safely</p><p class="why">${text(answer ? answer.error : "No reply from the extension.")}</p></div>`);
      return;
    }
    const bytes = Uint8Array.from(atob(answer.data.image), (c) => c.charCodeAt(0));
    const blurred = new File([bytes], file.name.replace(/\.\w+$/, "") + "-blurred.jpg", { type: "image/jpeg" });
    const files = new DataTransfer();
    files.items.add(blurred);
    swapped.add(input);
    input.files = files.files;
    input.dispatchEvent(new Event("change", { bubbles: true }));
    check(input, blurred, true);
  }

  async function check(input, file, afterBlur = false) {
    const dataUrl = await read(file);
    const lead = afterBlur ? "Blurred version swapped in. " : "";
    panel(`<p class="title">${lead}Checking ${afterBlur ? "it again" : "this photo against your feed"}…</p><p class="why">An attacker agent looks at your earlier posts plus this one. This takes about a minute.</p><div class="bar"><i></i></div>`);
    const answer = await ask("check", dataUrl);
    if (!answer || !answer.ok) {
      panel(`<p class="title">Breadcrumbs could not check this photo</p><p class="why">${text(answer ? answer.error : "Is the check service running?")}</p>`);
      return;
    }
    const r = answer.data;
    if (r.linked) {
      const others = r.evidence.filter((n) => n !== r.new_post).join(", ");
      const plural = others.includes(",") ? "s" : "";
      const title = afterBlur ? `Even blurred, it still links with post${plural} ${text(others)}` : `This photo links with post${plural} ${text(others)}`;
      const action = afterBlur ? "Remove this photo" : "Use a blurred version";
      const root = panel(`<div class="warn"><p class="title">${title}</p>
        <p>Together they point to <b>${text(r.area)}</b>.</p><p class="why">${text(r.reasoning)}</p>
        <div class="row"><button class="main">${action}</button><button>Post anyway</button></div></div>`);
      const [fix, keep] = root.querySelectorAll(".row button");
      fix.onclick = afterBlur ? () => { input.value = ""; input.dispatchEvent(new Event("change", { bubbles: true })); panel(`<p class="title">Photo removed from this post</p>`); } : () => useBlurred(input, file, dataUrl);
      keep.onclick = () => host.remove() || (host = null);
    } else {
      const alone = r.alone ? ` On its own it shows ${text(r.alone)}.` : "";
      panel(`<div class="ok"><p class="title">${afterBlur ? "Blurred version swapped in. " : ""}No pattern found</p><p class="why">The attacker could not link this photo with your feed.${alone} That is this model on this run, not a guarantee.</p></div>`);
    }
  }

  document.addEventListener("change", (event) => {
    const input = event.target;
    if (!(input instanceof HTMLInputElement) || input.type !== "file") return;
    if (swapped.has(input)) { swapped.delete(input); return; }
    const file = [...(input.files || [])].find((f) => f.type.startsWith("image/"));
    if (file) check(input, file);
  }, true);
})();
