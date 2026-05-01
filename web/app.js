(() => {
  const ROLE = (() => {
    const path = (location.pathname || "/").toLowerCase();
    if (path.startsWith("/phone")) return "phone";
    return "desktop";
  })();

  const $ = (selector) => document.querySelector(selector);

  const els = {
    subtitle: $("#subtitle"),
    roleChip: $("#roleChip"),
    connChip: $("#connChip"),
    pairingPanel: $("#pairingPanel"),
    qrImage: $("#qrImage"),
    qrFallback: $("#qrFallback"),
    pairLink: $("#pairLink"),
    pairToken: $("#pairToken"),
    copyLink: $("#copyLink"),
    copyToken: $("#copyToken"),
    messages: $("#messages"),
    text: $("#text"),
    send: $("#send"),
    toast: $("#toast"),
    tokenModal: $("#tokenModal"),
    tokenInput: $("#tokenInput"),
  };

  const state = {
    connected: false,
    paired: false,
    ws: null,
    pairingInfo: null,
    reconnectTimer: null,
    toastTimer: null,
    messagesById: new Set(),
  };

  els.roleChip.textContent = ROLE === "phone" ? "Phone" : "Desktop";
  els.pairingPanel.hidden = ROLE !== "desktop";

  function webSocketUrl() {
    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${location.host}/ws`;
  }

  function formatTime(ts) {
    const date = new Date(ts);
    const hh = String(date.getHours()).padStart(2, "0");
    const mm = String(date.getMinutes()).padStart(2, "0");
    return `${hh}:${mm}`;
  }

  function showToast(message) {
    if (!message) return;
    els.toast.textContent = message;
    els.toast.classList.add("show");
    clearTimeout(state.toastTimer);
    state.toastTimer = setTimeout(() => {
      els.toast.classList.remove("show");
    }, 1700);
  }

  function setConnection(connected) {
    state.connected = connected;
    els.connChip.textContent = connected ? "Online" : "Offline";
    els.connChip.classList.toggle("pill-live", connected);
    els.send.disabled = !connected;
  }

  function readTokenFromLocation() {
    const hash = new URLSearchParams((location.hash || "").replace(/^#/, ""));
    const search = new URLSearchParams(location.search || "");
    const token = hash.get("token") || search.get("token");
    if (!token) return "";

    const cleanUrl = new URL(location.href);
    cleanUrl.hash = "";
    cleanUrl.searchParams.delete("token");
    history.replaceState({}, "", cleanUrl.pathname + cleanUrl.search + cleanUrl.hash);
    return token.trim();
  }

  async function fetchJson(path, options = {}) {
    const response = await fetch(path, options);
    const text = await response.text();
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = null;
    }

    if (!response.ok) {
      const detail = data && data.detail ? data.detail : `HTTP ${response.status}`;
      throw new Error(detail);
    }
    return data;
  }

  async function isPaired() {
    try {
      await fetchJson("/api/session");
      state.paired = true;
      return true;
    } catch {
      state.paired = false;
      return false;
    }
  }

  async function pairWithToken(token) {
    if (!token) return false;
    await fetchJson("/api/pair", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
    });
    state.paired = true;
    return true;
  }

  function openTokenModal() {
    els.tokenInput.value = "";
    els.tokenModal.showModal();
    setTimeout(() => els.tokenInput.focus(), 60);
  }

  async function loadDesktopPairingInfo() {
    if (ROLE !== "desktop") return null;
    if (state.pairingInfo) return state.pairingInfo;

    const info = await fetchJson("/api/pairing");
    state.pairingInfo = info;
    els.pairLink.value = info.pair_url || info.phone_url || "";
    els.pairToken.value = info.token || "";

    if (info.phone_url) {
      els.qrFallback.textContent = "Scan this QR code with your phone camera.";
      els.qrImage.src = "/api/pairing-qr.svg";
      els.qrImage.hidden = false;
    } else {
      els.qrFallback.textContent = "No reachable local IP was detected on this machine.";
      els.qrImage.hidden = true;
    }

    return info;
  }

  async function ensurePaired({ silent = false } = {}) {
    const tokenFromUrl = readTokenFromLocation();
    if (tokenFromUrl) {
      try {
        await pairWithToken(tokenFromUrl);
        showToast("Device paired.");
      } catch (error) {
        showToast(String(error.message || "Pairing failed."));
      }
    }

    if (await isPaired()) {
      return true;
    }

    if (ROLE === "desktop") {
      try {
        const info = await loadDesktopPairingInfo();
        if (info && info.token) {
          await pairWithToken(info.token);
          return true;
        }
      } catch {
        // ignore and fall back to the modal
      }
    }

    if (!silent) {
      openTokenModal();
    }
    return false;
  }

  function appendMessage(message, copied) {
    if (!message || state.messagesById.has(message.id)) return;
    state.messagesById.add(message.id);

    const mine = message.sender === ROLE;
    const row = document.createElement("article");
    row.className = mine ? "message message-mine" : "message";

    const bubble = document.createElement("div");
    bubble.className = "message-bubble";
    bubble.textContent = message.text || "";

    const meta = document.createElement("div");
    meta.className = "message-meta";
    meta.textContent = `${message.sender || "?"} · ${formatTime(message.ts)}`;

    row.appendChild(bubble);
    row.appendChild(meta);
    els.messages.appendChild(row);
    els.messages.scrollTop = els.messages.scrollHeight;

    if (ROLE === "desktop" && message.sender === "phone" && copied) {
      showToast("Copied to clipboard.");
    }
  }

  function connectSocket() {
    clearTimeout(state.reconnectTimer);
    if (!state.paired) return;

    try {
      const ws = new WebSocket(webSocketUrl());
      state.ws = ws;

      ws.onopen = () => {
        setConnection(true);
      };

      ws.onclose = async (event) => {
        setConnection(false);
        state.ws = null;

        if (event.code === 1008) {
          state.paired = false;
          await fetchJson("/api/unpair", { method: "POST" }).catch(() => {});
          openTokenModal();
          return;
        }

        state.reconnectTimer = setTimeout(async () => {
          if (await ensurePaired({ silent: true })) {
            connectSocket();
          }
        }, 900);
      };

      ws.onerror = () => {
        setConnection(false);
      };

      ws.onmessage = (event) => {
        let data = null;
        try {
          data = JSON.parse(event.data);
        } catch {
          return;
        }

        if (!data || !data.type) return;
        if (data.type === "history" && Array.isArray(data.messages)) {
          for (const item of data.messages) {
            appendMessage(item, false);
          }
          return;
        }
        if (data.type === "message" && data.message) {
          appendMessage(data.message, Boolean(data.copied));
        }
      };
    } catch {
      setConnection(false);
    }
  }

  function autosize() {
    els.text.style.height = "auto";
    els.text.style.height = `${Math.min(els.text.scrollHeight, 150)}px`;
  }

  async function sendMessage() {
    const text = (els.text.value || "").trim();
    if (!text) return;

    if (!(await ensurePaired())) {
      return;
    }

    els.send.disabled = true;
    try {
      await fetchJson("/api/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sender: ROLE === "phone" ? "phone" : "desktop",
          text,
        }),
      });
      els.text.value = "";
      autosize();
    } catch (error) {
      showToast(String(error.message || "Send failed."));
    } finally {
      els.send.disabled = !state.connected;
    }
  }

  async function copyValue(value, label) {
    if (!value) return;
    try {
      await navigator.clipboard.writeText(value);
      showToast(`${label} copied.`);
    } catch {
      showToast(`Could not copy ${label.toLowerCase()}.`);
    }
  }

  els.send.addEventListener("click", sendMessage);
  els.text.addEventListener("input", autosize);
  els.text.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      sendMessage();
    }
  });

  els.copyLink.addEventListener("click", () => copyValue(els.pairLink.value, "Link"));
  els.copyToken.addEventListener("click", () => copyValue(els.pairToken.value, "Token"));

  els.tokenModal.addEventListener("close", async () => {
    if (els.tokenModal.returnValue !== "ok") return;
    const token = (els.tokenInput.value || "").trim();
    if (!token) return;

    try {
      await pairWithToken(token);
      showToast("Device paired.");
      connectSocket();
    } catch (error) {
      showToast(String(error.message || "Pairing failed."));
      openTokenModal();
    }
  });

  (async () => {
    autosize();
    setConnection(false);
    if (ROLE === "desktop") {
      await loadDesktopPairingInfo().catch(() => {});
    }
    const paired = await ensurePaired({ silent: false });
    if (paired) {
      connectSocket();
    }
  })();
})();
