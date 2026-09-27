from __future__ import annotations

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Pocketful</title>
  <style>
    :root {
      --bg: #0f172a;
      --card-bg: #1e293b;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --primary: #38bdf8;
      --accent: #22c55e;
      --danger: #ef4444;
      --border: #334155;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
      padding: 16px;
    }
    .container { max-width: 720px; margin: 0 auto; }
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--border);
      margin-bottom: 24px;
    }
    nav a {
      color: var(--primary);
      text-decoration: none;
      margin-right: 12px;
      font-weight: 500;
    }
    nav a:hover { text-decoration: underline; }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 20px;
      margin-bottom: 20px;
    }
    h2 { font-size: 1.25rem; margin-bottom: 12px; color: var(--primary); }
    .form-group { margin-bottom: 12px; }
    label { display: block; font-size: 0.875rem; color: var(--text-muted); margin-bottom: 4px; }
    input, select, textarea, button {
      width: 100%;
      padding: 10px;
      background: #0f172a;
      border: 1px solid var(--border);
      border-radius: 6px;
      color: var(--text);
      font-size: 1rem;
    }
    button {
      background: var(--primary);
      color: #0f172a;
      font-weight: 600;
      cursor: pointer;
      border: none;
      margin-top: 8px;
    }
    button:hover { opacity: 0.9; }
    .btn-secondary { background: var(--border); color: var(--text); }
    .btn-danger { background: var(--danger); color: #fff; }
    .btn-sm { width: auto; padding: 6px 12px; font-size: 0.875rem; display: inline-block; margin-right: 6px; }
    .error-msg {
      background: rgba(239, 68, 68, 0.15);
      border: 1px solid var(--danger);
      color: var(--danger);
      padding: 8px 12px;
      border-radius: 6px;
      margin-top: 8px;
      font-size: 0.875rem;
    }
    .balance-box {
      display: flex;
      gap: 16px;
      margin-bottom: 16px;
    }
    .balance-item {
      flex: 1;
      padding: 12px;
      background: rgba(56, 189, 248, 0.05);
      border-radius: 6px;
      border: 1px solid var(--border);
    }
    .balance-label { font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; }
    .balance-val { font-size: 1.25rem; font-weight: bold; color: var(--text); }
    .item-card {
      border: 1px solid var(--border);
      background: rgba(255, 255, 255, 0.02);
      border-radius: 6px;
      padding: 12px;
      margin-bottom: 8px;
    }
    .hidden { display: none !important; }
  </style>
</head>
<body>
<div class="container">
  <header>
    <div>
      <span style="font-weight:bold; font-size:1.25rem; color:var(--primary); margin-right:16px;">Pocketful</span>
      <span id="nav-links">
        <a href="/">Wallet</a>
        <a href="/requests">Requests</a>
        <a href="/split">Split</a>
        <a href="/authorizations">Authorizations</a>
      </span>
    </div>
    <div id="user-header"></div>
  </header>

  <!-- LOGIN PAGE -->
  <div id="page-login" class="card hidden">
    <h2>Log in to Pocketful</h2>
    <div class="form-group">
      <label>Email</label>
      <input type="email" data-testid="login-email" id="login-email">
    </div>
    <div class="form-group">
      <label>Password</label>
      <input type="password" data-testid="login-password" id="login-password">
    </div>
    <button data-testid="login-submit" onclick="submitLogin()">Log In</button>
    <div id="auth-error-login-container"></div>
    <p style="margin-top:12px; font-size:0.875rem;"><a href="/signup">Need an account? Sign up</a></p>
  </div>

  <!-- SIGNUP PAGE -->
  <div id="page-signup" class="card hidden">
    <h2>Create your Pocketful account</h2>
    <div class="form-group">
      <label>Email</label>
      <input type="email" data-testid="signup-email" id="signup-email">
    </div>
    <div class="form-group">
      <label>Password</label>
      <input type="password" data-testid="signup-password" id="signup-password">
    </div>
    <div class="form-group">
      <label>Display Name</label>
      <input type="text" data-testid="signup-display-name" id="signup-display-name">
    </div>
    <button data-testid="signup-submit" onclick="submitSignup()">Sign Up</button>
    <div id="auth-error-signup-container"></div>
    <p style="margin-top:12px; font-size:0.875rem;"><a href="/login">Already registered? Log in</a></p>
  </div>

  <!-- WALLET / HOME PAGE -->
  <div id="page-home" class="hidden">
    <div class="card">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
        <h2>Wallet Balances</h2>
        <button data-testid="wallet-refresh" class="btn-sm btn-secondary" onclick="refreshWallet()">Refresh</button>
      </div>
      <div class="balance-box">
        <div class="balance-item">
          <div class="balance-label">Available</div>
          <div class="balance-val" data-testid="wallet-available" data-amount="0">0.00 EUR</div>
        </div>
        <div id="held-box-container"></div>
        <div class="balance-item">
          <div class="balance-label">Total Balance</div>
          <div class="balance-val" data-testid="wallet-balance" data-amount="0">0.00 EUR</div>
        </div>
      </div>
    </div>

    <!-- PAY FORM -->
    <div class="card">
      <h2>Send Payment</h2>
      <div class="form-group">
        <label>Recipient Handle</label>
        <input type="text" data-testid="pay-handle" id="pay-handle" oninput="onPayFieldChange()">
      </div>
      <div class="form-group">
        <label>Amount (Decimal)</label>
        <input type="text" data-testid="pay-amount" id="pay-amount" placeholder="15.00" oninput="onPayFieldChange()">
      </div>
      <div class="form-group">
        <label>Note</label>
        <input type="text" data-testid="pay-note" id="pay-note" oninput="onPayFieldChange()">
      </div>
      <div class="form-group">
        <label>Visibility</label>
        <select data-testid="pay-visibility" id="pay-visibility" onchange="onPayFieldChange()">
          <option value="public">public</option>
          <option value="private">private</option>
        </select>
      </div>
      <button data-testid="pay-submit" onclick="submitPay()">Send Payment</button>
      <div id="pay-error-container"></div>
      <div id="pay-uncertain-container"></div>
    </div>

    <!-- REQUEST FORM -->
    <div class="card">
      <h2>Request Money</h2>
      <div class="form-group">
        <label>Payer Handle</label>
        <input type="text" data-testid="request-handle" id="request-handle">
      </div>
      <div class="form-group">
        <label>Amount (Decimal)</label>
        <input type="text" data-testid="request-amount" id="request-amount" placeholder="10.00">
      </div>
      <div class="form-group">
        <label>Note</label>
        <input type="text" data-testid="request-note" id="request-note">
      </div>
      <button data-testid="request-submit" onclick="submitRequest()">Create Request</button>
      <div id="request-form-error-container"></div>
    </div>

    <!-- AUTHORIZATION FORM -->
    <div class="card">
      <h2>Authorize Payment Hold</h2>
      <div class="form-group">
        <label>Recipient Handle</label>
        <input type="text" data-testid="authorize-handle" id="authorize-handle">
      </div>
      <div class="form-group">
        <label>Amount (Decimal)</label>
        <input type="text" data-testid="authorize-amount" id="authorize-amount" placeholder="20.00">
      </div>
      <div class="form-group">
        <label>Note</label>
        <input type="text" data-testid="authorize-note" id="authorize-note">
      </div>
      <div class="form-group">
        <label>Visibility</label>
        <select data-testid="authorize-visibility" id="authorize-visibility">
          <option value="public">public</option>
          <option value="private">private</option>
        </select>
      </div>
      <button data-testid="authorize-submit" onclick="submitAuthorize()">Authorize Hold</button>
      <div id="authorize-error-container"></div>
    </div>

    <!-- ACTIVITY FEED -->
    <div class="card">
      <h2>Activity Feed</h2>
      <div id="empty-activity-container"></div>
      <div id="activity-list" data-testid="activity-list"></div>
    </div>
  </div>

  <!-- REQUESTS PAGE -->
  <div id="page-requests" class="hidden">
    <div class="card">
      <h2>Incoming Requests</h2>
      <div id="incoming-list" data-testid="incoming-list"></div>
    </div>
    <div class="card">
      <h2>Outgoing Requests</h2>
      <div id="outgoing-list" data-testid="outgoing-list"></div>
    </div>
    <div id="empty-requests-container"></div>
    <div id="request-action-error-container"></div>
  </div>

  <!-- SPLIT PAGE -->
  <div id="page-split" class="card hidden">
    <h2>Split a Bill</h2>
    <div class="form-group">
      <label>Amount</label>
      <input type="text" data-testid="split-amount" id="split-amount" placeholder="30.00" oninput="updateSplitPreview()">
    </div>
    <div class="form-group">
      <label>Participant Handles (comma-separated, in order)</label>
      <input type="text" data-testid="split-handles" id="split-handles" placeholder="ada, bob, cy" oninput="updateSplitPreview()">
    </div>
    <div class="form-group">
      <label>Note</label>
      <input type="text" data-testid="split-note" id="split-note">
    </div>
    <div id="split-preview-container"></div>
    <button data-testid="split-submit" onclick="submitSplit()">Submit Split</button>
    <div id="split-error-container"></div>
  </div>

  <!-- AUTHORIZATIONS PAGE -->
  <div id="page-authorizations" class="hidden">
    <div class="card">
      <h2>Authorizations</h2>
      <div id="empty-authorizations-container"></div>
      <div id="authorization-list" data-testid="authorization-list"></div>
      <div id="authorization-error-container"></div>
    </div>
  </div>

</div>

<script>
let currentUser = null;
let currentCurrency = "EUR";
let currentMinorUnits = 2;
let payIdempotencyKey = generateKey();

function generateKey() {
  return "ui_k_" + Math.random().toString(36).substring(2, 15) + Date.now();
}

function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift();
  return null;
}

function setCookie(name, value) {
  document.cookie = `${name}=${value}; Path=/; SameSite=Lax`;
  localStorage.setItem(name, value);
}

function getToken() {
  return localStorage.getItem("token") || getCookie("token");
}

function formatMoney(minor, minorUnits, currency) {
  if (minorUnits === 0) {
    return minor + " " + currency;
  }
  const str = String(minor).padStart(minorUnits + 1, "0");
  const whole = str.slice(0, -minorUnits);
  const frac = str.slice(-minorUnits);
  return whole + "." + frac + " " + currency;
}

function parseDecimalToMinor(str, minorUnits) {
  if (typeof str !== "string") return null;
  str = str.trim();
  if (minorUnits === 0) {
    if (!/^[0-9]+$/.test(str)) return null;
    return parseInt(str, 10);
  }
  if (!/^[0-9]+(\\.[0-9]+)?$/.test(str)) {
    return null;
  }
  const parts = str.split('.');
  const whole = parseInt(parts[0], 10);
  if (parts.length === 1) {
    return whole * Math.pow(10, minorUnits);
  }
  const fracStr = parts[1];
  if (fracStr.length > minorUnits) {
    return null; // more decimal places than allowed
  }
  const paddedFrac = fracStr.padEnd(minorUnits, '0');
  const frac = parseInt(paddedFrac, 10);
  return whole * Math.pow(10, minorUnits) + frac;
}

function showError(containerId, testId, message) {
  clearError(containerId, testId);
  const container = document.getElementById(containerId);
  if (!container) return;
  const el = document.createElement("div");
  el.className = "error-msg";
  el.setAttribute("data-testid", testId);
  el.textContent = message;
  container.appendChild(el);
}

function clearError(containerId, testId) {
  const container = document.getElementById(containerId);
  if (!container) return;
  const existing = container.querySelector(`[data-testid='${testId}']`);
  if (existing) existing.remove();
}

function renderUserHeader() {
  const container = document.getElementById("user-header");
  container.innerHTML = "";
  if (currentUser) {
    const userSpan = document.createElement("span");
    userSpan.setAttribute("data-testid", "current-user");
    userSpan.textContent = "Logged in as " + currentUser.display_name + " (";

    const handleSpan = document.createElement("span");
    handleSpan.setAttribute("data-testid", "current-handle");
    handleSpan.textContent = currentUser.handle;
    userSpan.appendChild(handleSpan);
    userSpan.appendChild(document.createTextNode(")"));

    const logoutBtn = document.createElement("button");
    logoutBtn.className = "btn-sm btn-secondary";
    logoutBtn.setAttribute("data-testid", "logout-button");
    logoutBtn.textContent = "Log out";
    logoutBtn.onclick = logout;

    container.appendChild(userSpan);
    container.appendChild(document.createTextNode(" "));
    container.appendChild(logoutBtn);
  }
}

async function api(path, options = {}) {
  const token = getToken();
  options.headers = options.headers || {};
  if (token) {
    options.headers["Authorization"] = "Bearer " + token;
  }
  if (options.body && typeof options.body === "object" && !(options.body instanceof FormData)) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(options.body);
  }
  const res = await fetch(path, options);
  return res;
}

function onPayFieldChange() {
  payIdempotencyKey = generateKey();
  clearError("pay-error-container", "pay-error");
  clearError("pay-uncertain-container", "pay-uncertain");
}

async function refreshMe() {
  const res = await api("/me");
  if (res.status === 200) {
    currentUser = await res.json();
    currentCurrency = currentUser.currency;
    currentMinorUnits = currentUser.minor_units;

    renderUserHeader();

    const balEl = document.querySelector('[data-testid="wallet-balance"]');
    if (balEl) {
      balEl.setAttribute("data-amount", String(currentUser.balance));
      balEl.textContent = formatMoney(currentUser.balance, currentMinorUnits, currentCurrency);
    }
    const availEl = document.querySelector('[data-testid="wallet-available"]');
    if (availEl) {
      availEl.setAttribute("data-amount", String(currentUser.available));
      availEl.textContent = formatMoney(currentUser.available, currentMinorUnits, currentCurrency);
    }
    const heldContainer = document.getElementById("held-box-container");
    if (heldContainer) {
      heldContainer.innerHTML = "";
      if (currentUser.held > 0) {
        const heldItem = document.createElement("div");
        heldItem.className = "balance-item";
        heldItem.innerHTML = `<div class="balance-label">Held</div><div class="balance-val" data-testid="wallet-held" data-amount="${currentUser.held}">${formatMoney(currentUser.held, currentMinorUnits, currentCurrency)}</div>`;
        heldContainer.appendChild(heldItem);
      }
    }
    return true;
  }
  currentUser = null;
  renderUserHeader();
  return false;
}

async function refreshFeed() {
  const res = await api("/activity?limit=100");
  if (res.status === 200) {
    const data = await res.json();
    const payments = data.payments || [];
    const list = document.getElementById("activity-list");
    const emptyContainer = document.getElementById("empty-activity-container");
    list.innerHTML = "";
    emptyContainer.innerHTML = "";

    if (payments.length === 0) {
      const emptyEl = document.createElement("div");
      emptyEl.setAttribute("data-testid", "empty-activity");
      emptyEl.style.color = "var(--text-muted)";
      emptyEl.textContent = "No visible activity yet";
      emptyContainer.appendChild(emptyEl);
    } else {
      for (const p of payments) {
        const item = document.createElement("div");
        item.className = "item-card";
        item.setAttribute("data-testid", `activity-item-${p.payment_id}`);
        item.setAttribute("data-visibility", p.visibility);

        const parties = document.createElement("div");
        parties.style.fontWeight = "600";
        parties.setAttribute("data-testid", `activity-parties-${p.payment_id}`);
        parties.textContent = `${p.from_handle} -> ${p.to_handle}`;

        const amt = document.createElement("div");
        amt.style.color = "var(--primary)";
        amt.setAttribute("data-testid", `activity-amount-${p.payment_id}`);
        amt.textContent = formatMoney(p.amount, currentMinorUnits, currentCurrency);

        const note = document.createElement("div");
        note.style.fontSize = "0.875rem";
        note.style.color = "var(--text-muted)";
        note.setAttribute("data-testid", `activity-note-${p.payment_id}`);
        note.textContent = p.note || "";

        item.appendChild(parties);
        item.appendChild(amt);
        item.appendChild(note);
        list.appendChild(item);
      }
    }
  }
}

async function refreshRequests() {
  const res = await api("/requests?limit=100");
  if (res.status === 200) {
    const data = await res.json();
    const requests = data.requests || [];
    const incList = document.getElementById("incoming-list");
    const outList = document.getElementById("outgoing-list");
    const emptyContainer = document.getElementById("empty-requests-container");
    incList.innerHTML = "";
    outList.innerHTML = "";
    emptyContainer.innerHTML = "";

    let incCount = 0;
    let outCount = 0;

    for (const r of requests) {
      const isIncoming = (r.payer_id === currentUser.user_id);
      const item = document.createElement("div");
      item.className = "item-card";
      item.setAttribute("data-testid", `request-item-${r.request_id}`);
      item.setAttribute("data-status", r.status);

      const parties = document.createElement("div");
      parties.style.fontWeight = "600";
      parties.textContent = isIncoming ? `From: ${r.requester_handle}` : `To: ${r.payer_handle}`;

      const amt = document.createElement("div");
      amt.style.color = "var(--primary)";
      amt.setAttribute("data-testid", `request-amount-${r.request_id}`);
      amt.textContent = formatMoney(r.amount, currentMinorUnits, currentCurrency);

      const note = document.createElement("div");
      note.style.fontSize = "0.875rem";
      note.textContent = r.note || "";

      item.appendChild(parties);
      item.appendChild(amt);
      item.appendChild(note);

      if (isIncoming) {
        incCount++;
        if (r.status === "pending") {
          const btnPay = document.createElement("button");
          btnPay.className = "btn-sm";
          btnPay.setAttribute("data-testid", `request-pay-${r.request_id}`);
          btnPay.textContent = "Pay";
          btnPay.onclick = () => payRequest(r.request_id);

          const btnDecline = document.createElement("button");
          btnDecline.className = "btn-sm btn-secondary";
          btnDecline.setAttribute("data-testid", `request-decline-${r.request_id}`);
          btnDecline.textContent = "Decline";
          btnDecline.onclick = () => declineRequest(r.request_id);

          item.appendChild(btnPay);
          item.appendChild(btnDecline);
        }
        incList.appendChild(item);
      } else {
        outCount++;
        if (r.status === "pending") {
          const btnCancel = document.createElement("button");
          btnCancel.className = "btn-sm btn-danger";
          btnCancel.setAttribute("data-testid", `request-cancel-${r.request_id}`);
          btnCancel.textContent = "Cancel";
          btnCancel.onclick = () => cancelRequest(r.request_id);

          item.appendChild(btnCancel);
        }
        outList.appendChild(item);
      }
    }

    if (incCount === 0 && outCount === 0) {
      const emptyEl = document.createElement("div");
      emptyEl.setAttribute("data-testid", "empty-requests");
      emptyEl.className = "card";
      emptyEl.style.color = "var(--text-muted)";
      emptyEl.textContent = "No requests found";
      emptyContainer.appendChild(emptyEl);
    }
  }
}

async function payRequest(reqId) {
  clearError("request-action-error-container", "request-error");
  const res = await api(`/requests/${reqId}/pay`, {
    method: "POST",
    headers: { "Idempotency-Key": generateKey() },
    body: { visibility: "public" }
  });
  if (res.status === 201 || res.status === 200) {
    await refreshRequests();
    await refreshMe();
  } else {
    const err = await res.json();
    showError("request-action-error-container", "request-error", (err.error && err.error.message) || "Pay refused");
    await refreshRequests();
  }
}

async function declineRequest(reqId) {
  clearError("request-action-error-container", "request-error");
  const res = await api(`/requests/${reqId}/decline`, { method: "POST" });
  if (res.status === 200) {
    await refreshRequests();
  } else {
    const err = await res.json();
    showError("request-action-error-container", "request-error", (err.error && err.error.message) || "Decline refused");
  }
}

async function cancelRequest(reqId) {
  clearError("request-action-error-container", "request-error");
  const res = await api(`/requests/${reqId}/cancel`, { method: "POST" });
  if (res.status === 200) {
    await refreshRequests();
  } else {
    const err = await res.json();
    showError("request-action-error-container", "request-error", (err.error && err.error.message) || "Cancel refused");
  }
}

async function refreshAuthorizations() {
  const res = await api("/authorizations?limit=100");
  if (res.status === 200) {
    const data = await res.json();
    const auths = data.authorizations || [];
    const list = document.getElementById("authorization-list");
    const emptyContainer = document.getElementById("empty-authorizations-container");
    list.innerHTML = "";
    emptyContainer.innerHTML = "";

    if (auths.length === 0) {
      const emptyEl = document.createElement("div");
      emptyEl.setAttribute("data-testid", "empty-authorizations");
      emptyEl.style.color = "var(--text-muted)";
      emptyEl.textContent = "No authorizations found";
      emptyContainer.appendChild(emptyEl);
    } else {
      for (const a of auths) {
        const item = document.createElement("div");
        item.className = "item-card";
        item.setAttribute("data-testid", `authorization-item-${a.authorization_id}`);
        item.setAttribute("data-status", a.status);

        const parties = document.createElement("div");
        parties.style.fontWeight = "600";
        parties.textContent = `${a.from_handle} -> ${a.to_handle}`;

        const amt = document.createElement("div");
        amt.style.color = "var(--primary)";
        amt.setAttribute("data-testid", `authorization-amount-${a.authorization_id}`);
        amt.textContent = formatMoney(a.amount, currentMinorUnits, currentCurrency);

        const exp = document.createElement("div");
        exp.style.fontSize = "0.75rem";
        exp.style.color = "var(--text-muted)";
        exp.setAttribute("data-testid", `authorization-expires-${a.authorization_id}`);
        exp.textContent = a.expires_at;

        item.appendChild(parties);
        item.appendChild(amt);
        item.appendChild(exp);

        if (a.status === "captured") {
          const cap = document.createElement("div");
          cap.setAttribute("data-testid", `authorization-captured-${a.authorization_id}`);
          cap.textContent = formatMoney(a.captured_amount, currentMinorUnits, currentCurrency);
          item.appendChild(cap);
        }

        const isIncoming = (a.to_user_id === currentUser.user_id);
        const isOutgoing = (a.from_user_id === currentUser.user_id);

        if (isIncoming && a.status === "open") {
          const capInput = document.createElement("input");
          capInput.type = "text";
          capInput.className = "btn-sm";
          capInput.style.width = "100px";
          capInput.setAttribute("data-testid", `authorization-capture-amount-${a.authorization_id}`);
          const remDecimal = (currentMinorUnits === 0) ? String(a.remaining_amount) : (a.remaining_amount / Math.pow(10, currentMinorUnits)).toFixed(currentMinorUnits);
          capInput.value = remDecimal;

          const btnCap = document.createElement("button");
          btnCap.className = "btn-sm";
          btnCap.setAttribute("data-testid", `authorization-capture-${a.authorization_id}`);
          btnCap.textContent = "Capture";
          btnCap.onclick = () => captureAuthorization(a.authorization_id, capInput.value);

          item.appendChild(capInput);
          item.appendChild(btnCap);
        }

        if (isOutgoing && a.status === "open") {
          const btnVoid = document.createElement("button");
          btnVoid.className = "btn-sm btn-danger";
          btnVoid.setAttribute("data-testid", `authorization-void-${a.authorization_id}`);
          btnVoid.textContent = "Void";
          btnVoid.onclick = () => voidAuthorization(a.authorization_id);
          item.appendChild(btnVoid);
        }

        list.appendChild(item);
      }
    }
  }
}

async function captureAuthorization(authId, amtDecimal) {
  clearError("authorization-error-container", "authorization-error");
  const minor = parseDecimalToMinor(amtDecimal, currentMinorUnits);
  const payload = (minor !== null) ? { amount: minor } : {};
  const res = await api(`/authorizations/${authId}/capture`, {
    method: "POST",
    headers: { "Idempotency-Key": generateKey() },
    body: payload
  });
  if (res.status === 201 || res.status === 200) {
    await refreshAuthorizations();
    await refreshMe();
  } else {
    const err = await res.json();
    showError("authorization-error-container", "authorization-error", (err.error && err.error.message) || "Capture refused");
  }
}

async function voidAuthorization(authId) {
  clearError("authorization-error-container", "authorization-error");
  const res = await api(`/authorizations/${authId}/void`, { method: "POST" });
  if (res.status === 200) {
    await refreshAuthorizations();
    await refreshMe();
  } else {
    const err = await res.json();
    showError("authorization-error-container", "authorization-error", (err.error && err.error.message) || "Void refused");
  }
}

function updateSplitPreview() {
  const amtStr = document.getElementById("split-amount").value;
  const handlesStr = document.getElementById("split-handles").value;
  const previewContainer = document.getElementById("split-preview-container");
  previewContainer.innerHTML = "";

  const minor = parseDecimalToMinor(amtStr, currentMinorUnits);
  const handles = handlesStr.split(",").map(h => h.trim()).filter(Boolean);

  if (minor === null || handles.length === 0) {
    return;
  }

  const n = handles.length;
  const base = Math.floor(minor / n);
  const rem = minor % n;

  const previewBox = document.createElement("div");
  previewBox.id = "split-preview";
  previewBox.setAttribute("data-testid", "split-preview");
  previewBox.className = "card";
  previewBox.style.background = "#0f172a";
  previewBox.style.marginTop = "12px";

  const title = document.createElement("div");
  title.style.fontWeight = "600";
  title.style.marginBottom = "8px";
  title.style.fontSize = "0.875rem";
  title.style.color = "var(--primary)";
  title.textContent = "Preview Shares:";
  previewBox.appendChild(title);

  for (let i = 0; i < n; i++) {
    const h = handles[i];
    const shareAmt = base + (i < rem ? 1 : 0);
    const row = document.createElement("div");
    row.style.display = "flex";
    row.style.justifyContent = "space-between";
    row.style.padding = "4px 0";

    const label = document.createElement("span");
    label.textContent = h;

    const val = document.createElement("span");
    val.setAttribute("data-testid", `split-share-${h}`);
    val.style.fontWeight = "bold";
    val.textContent = formatMoney(shareAmt, currentMinorUnits, currentCurrency);

    row.appendChild(label);
    row.appendChild(val);
    previewBox.appendChild(row);
  }
  previewContainer.appendChild(previewBox);
}

async function submitPay() {
  clearError("pay-error-container", "pay-error");
  clearError("pay-uncertain-container", "pay-uncertain");

  const handle = document.getElementById("pay-handle").value;
  const amtStr = document.getElementById("pay-amount").value;
  const note = document.getElementById("pay-note").value;
  const visibility = document.getElementById("pay-visibility").value;

  const minor = parseDecimalToMinor(amtStr, currentMinorUnits);
  if (minor === null || minor < 1) {
    showError("pay-error-container", "pay-error", "Invalid amount");
    return;
  }

  const payload = {
    to_handle: handle,
    amount: minor,
    note: note,
    visibility: visibility
  };

  try {
    const res = await api("/payments", {
      method: "POST",
      headers: { "Idempotency-Key": payIdempotencyKey },
      body: payload
    });

    if (res.status === 201 || res.status === 200) {
      await refreshMe();
      await refreshFeed();
    } else {
      const err = await res.json();
      showError("pay-error-container", "pay-error", (err.error && err.error.message) || "Payment refused");
      await refreshMe();
      await refreshFeed();
    }
  } catch (e) {
    showError("pay-uncertain-container", "pay-uncertain", "Payment outcome uncertain, please retry");
  }
}

async function submitRequest() {
  clearError("request-form-error-container", "request-error");

  const handle = document.getElementById("request-handle").value;
  const amtStr = document.getElementById("request-amount").value;
  const note = document.getElementById("request-note").value;

  const minor = parseDecimalToMinor(amtStr, currentMinorUnits);
  if (minor === null || minor < 1) {
    showError("request-form-error-container", "request-error", "Invalid amount");
    return;
  }

  const res = await api("/requests", {
    method: "POST",
    headers: { "Idempotency-Key": generateKey() },
    body: { payer_handle: handle, amount: minor, note: note }
  });

  if (res.status === 201 || res.status === 200) {
    document.getElementById("request-handle").value = "";
    document.getElementById("request-amount").value = "";
    document.getElementById("request-note").value = "";
  } else {
    const err = await res.json();
    showError("request-form-error-container", "request-error", (err.error && err.error.message) || "Request refused");
  }
}

async function submitAuthorize() {
  clearError("authorize-error-container", "authorize-error");

  const handle = document.getElementById("authorize-handle").value;
  const amtStr = document.getElementById("authorize-amount").value;
  const note = document.getElementById("authorize-note").value;
  const visibility = document.getElementById("authorize-visibility").value;

  const minor = parseDecimalToMinor(amtStr, currentMinorUnits);
  if (minor === null || minor < 1) {
    showError("authorize-error-container", "authorize-error", "Invalid amount");
    return;
  }

  const res = await api("/authorizations", {
    method: "POST",
    headers: { "Idempotency-Key": generateKey() },
    body: { to_handle: handle, amount: minor, note: note, visibility: visibility }
  });

  if (res.status === 201 || res.status === 200) {
    await refreshMe();
  } else {
    const err = await res.json();
    showError("authorize-error-container", "authorize-error", (err.error && err.error.message) || "Authorization refused");
  }
}

async function submitSplit() {
  clearError("split-error-container", "split-error");

  const amtStr = document.getElementById("split-amount").value;
  const handlesStr = document.getElementById("split-handles").value;
  const note = document.getElementById("split-note").value;

  const minor = parseDecimalToMinor(amtStr, currentMinorUnits);
  const handles = handlesStr.split(",").map(h => h.trim()).filter(Boolean);

  if (minor === null || minor < 1) {
    showError("split-error-container", "split-error", "Invalid amount");
    return;
  }

  const res = await api("/splits", {
    method: "POST",
    headers: { "Idempotency-Key": generateKey() },
    body: { amount: minor, participant_handles: handles, note: note }
  });

  if (res.status === 201 || res.status === 200) {
    window.location.href = "/requests";
  } else {
    const err = await res.json();
    showError("split-error-container", "split-error", (err.error && err.error.message) || "Split refused");
  }
}

async function submitLogin() {
  clearError("auth-error-login-container", "auth-error");

  const email = document.getElementById("login-email").value;
  const password = document.getElementById("login-password").value;

  const res = await fetch("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password })
  });

  if (res.status === 200) {
    const data = await res.json();
    setCookie("token", data.token);
    await refreshMe();
    window.location.href = "/";
  } else {
    const err = await res.json();
    showError("auth-error-login-container", "auth-error", (err.error && err.error.message) || "Login failed");
  }
}

async function submitSignup() {
  clearError("auth-error-signup-container", "auth-error");

  const email = document.getElementById("signup-email").value;
  const password = document.getElementById("signup-password").value;
  const display_name = document.getElementById("signup-display-name").value;

  const res = await fetch("/auth/signup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, display_name })
  });

  if (res.status === 201) {
    const data = await res.json();
    setCookie("token", data.token);
    await refreshMe();
    window.location.href = "/";
  } else {
    const err = await res.json();
    showError("auth-error-signup-container", "auth-error", (err.error && err.error.message) || "Signup failed");
  }
}

function logout() {
  setCookie("token", "");
  localStorage.removeItem("token");
  currentUser = null;
  renderUserHeader();
  window.location.href = "/login";
}

async function refreshWallet() {
  await refreshMe();
  await refreshFeed();
}

async function initPage() {
  const path = window.location.pathname;
  const loggedIn = await refreshMe();

  if (path === "/login") {
    document.getElementById("page-login").classList.remove("hidden");
  } else if (path === "/signup") {
    document.getElementById("page-signup").classList.remove("hidden");
  } else if (path === "/requests") {
    document.getElementById("page-requests").classList.remove("hidden");
    if (loggedIn) await refreshRequests();
  } else if (path === "/split") {
    document.getElementById("page-split").classList.remove("hidden");
  } else if (path === "/authorizations") {
    document.getElementById("page-authorizations").classList.remove("hidden");
    if (loggedIn) await refreshAuthorizations();
  } else {
    document.getElementById("page-home").classList.remove("hidden");
    if (loggedIn) await refreshFeed();
  }
}

document.addEventListener("DOMContentLoaded", initPage);
</script>
</body>
</html>
"""
