const status = document.getElementById("status");
const tokenBox = document.getElementById("token");
const ask = (type, dataUrl) => new Promise((done) => chrome.runtime.sendMessage({ type, dataUrl }, done));

function show(message, good) {
  status.textContent = message;
  status.className = good ? "good" : "bad";
}

async function refresh() {
  const answer = await ask("health");
  if (answer && answer.ok) {
    const n = answer.data.feed;
    show(n ? `Connected. Your feed: ${n} photos.` : "Connected. Upload your feed export to start.", n > 0);
  } else {
    show(answer ? answer.error : "No reply. Is the check service running?", false);
  }
}

document.getElementById("save").onclick = async () => {
  await chrome.storage.local.set({ token: tokenBox.value.trim() });
  refresh();
};

document.getElementById("zip").onchange = (event) => {
  const file = event.target.files[0];
  if (!file) return;
  show("Reading your export…", true);
  const reader = new FileReader();
  reader.onload = async () => {
    const answer = await ask("feed", reader.result);
    if (answer && answer.ok) show(`Feed loaded: ${answer.data.feed} photos.`, true);
    else show(answer ? answer.error : "Could not load the export.", false);
  };
  reader.readAsDataURL(file);
};

chrome.storage.local.get("token").then(({ token = "" }) => {
  tokenBox.value = token;
  if (token) refresh();
});
