/**
 * NLP Email Assistant — Frontend JavaScript
 *
 * Communicates with the FastAPI backend at /api/* (relative URLs).
 * Supports: chat, inbox, compose, voice input (Web Speech API).
 */

'use strict';

// ── Configuration ─────────────────────────────────────────────────────────
const API = '';  // same-origin; change to e.g. 'http://localhost:8000' for dev

// ── DOM references ────────────────────────────────────────────────────────
const $ = (sel, ctx = document) => ctx.querySelector(sel);
const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];

const chatMessages  = $('#chat-messages');
const chatForm      = $('#chat-form');
const chatInput     = $('#chat-input');
const btnVoice      = $('#btn-voice');
const btnReset      = $('#btn-reset');

const inboxList     = $('#inbox-list');
const inboxSearch   = $('#inbox-search');
const btnRefresh    = $('#btn-refresh');

const composeForm   = $('#compose-form');
const composeTo     = $('#compose-to');
const composeSubj   = $('#compose-subject');
const composeDesc   = $('#compose-desc');
const composeBody   = $('#compose-body');
const btnAiDraft    = $('#btn-ai-draft');
const btnSaveDraft  = $('#btn-save-draft');
const composeAiSt   = $('#compose-ai-status');
const composeResult = $('#compose-result');

const emailModal    = $('#email-modal');
const modalClose    = $('#modal-close');
const modalSubject  = $('#modal-subject');
const modalFrom     = $('#modal-from');
const modalDate     = $('#modal-date');
const modalBody     = $('#modal-body');
const btnModalReply = $('#btn-modal-reply');
const btnModalFwd   = $('#btn-modal-forward');
const btnModalDel   = $('#btn-modal-delete');

const statusDot     = $('#status-dot');
const statusLabel   = $('#status-label');

let currentEmailId  = null;
let currentEmailFrom = '';

// ── Panel navigation ──────────────────────────────────────────────────────
$$('.nav-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    $$('.nav-btn').forEach(b => b.classList.remove('active'));
    $$('.panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    $(`#panel-${btn.dataset.panel}`).classList.add('active');
  });
});

// ── Health check / status ─────────────────────────────────────────────────
async function checkStatus() {
  try {
    const r = await fetch(`${API}/`);
    if (r.ok) {
      statusDot.className = 'status-dot online';
      statusLabel.textContent = 'Online';
      return true;
    }
  } catch (_) {}
  statusDot.className = 'status-dot offline';
  statusLabel.textContent = 'Offline';
  return false;
}
checkStatus();
setInterval(checkStatus, 30_000);

// ── Utility helpers ───────────────────────────────────────────────────────
function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function showResult(el, msg, type = 'success') {
  el.textContent = msg;
  el.className = `result-msg ${type}`;
  el.classList.remove('hidden');
  setTimeout(() => el.classList.add('hidden'), 5000);
}

// ── Chat ──────────────────────────────────────────────────────────────────
function appendMessage(text, role, meta = '') {
  const div = document.createElement('div');
  div.className = `msg ${role}`;
  div.innerHTML = `
    <div>
      <div class="bubble">${escHtml(text)}</div>
      ${meta ? `<div class="msg-meta">${meta}</div>` : ''}
    </div>`;
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

chatForm.addEventListener('submit', async e => {
  e.preventDefault();
  const msg = chatInput.value.trim();
  if (!msg) return;
  chatInput.value = '';
  appendMessage(msg, 'user');

  try {
    const r = await fetch(`${API}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: msg }),
    });
    if (!r.ok) throw new Error(await r.text());
    const data = await r.json();
    const meta = `<span class="intent-badge">${escHtml(data.intent)}</span> ${(data.confidence * 100).toFixed(0)}% confident`;
    appendMessage(data.response, 'assistant', meta);
  } catch (err) {
    appendMessage(`⚠️ Error: ${err.message}`, 'assistant');
  }
});

btnReset.addEventListener('click', async () => {
  await fetch(`${API}/chat/reset`, { method: 'POST' });
  chatMessages.innerHTML = `
    <div class="msg assistant">
      <span class="bubble">Conversation reset. How can I help you?</span>
    </div>`;
});

// ── Voice input (Web Speech API) ──────────────────────────────────────────
let recognition = null;

if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SpeechRecognition();
  recognition.continuous = false;
  recognition.interimResults = false;
  recognition.lang = 'en-US';

  recognition.onresult = e => {
    const transcript = e.results[0][0].transcript;
    chatInput.value = transcript;
    btnVoice.classList.remove('listening');
    chatForm.requestSubmit();
  };
  recognition.onerror = () => btnVoice.classList.remove('listening');
  recognition.onend   = () => btnVoice.classList.remove('listening');
} else {
  btnVoice.title = 'Voice input not supported in this browser';
  btnVoice.style.opacity = '0.4';
}

btnVoice.addEventListener('click', () => {
  if (!recognition) return;
  if (btnVoice.classList.contains('listening')) {
    recognition.stop();
    btnVoice.classList.remove('listening');
  } else {
    recognition.start();
    btnVoice.classList.add('listening');
  }
});

// ── Inbox ─────────────────────────────────────────────────────────────────
async function loadInbox(query = '') {
  inboxList.innerHTML = '<p class="placeholder">Loading…</p>';
  try {
    const url = query
      ? `${API}/email/search?q=${encodeURIComponent(query)}&max_results=20`
      : `${API}/email/inbox?max_results=20`;
    const r = await fetch(url);
    if (!r.ok) throw new Error(await r.text());
    const emails = await r.json();

    if (!emails.length) {
      inboxList.innerHTML = '<p class="placeholder">No emails found.</p>';
      return;
    }
    inboxList.innerHTML = '';
    emails.forEach(mail => {
      const card = document.createElement('div');
      card.className = 'email-card';
      card.dataset.id   = mail.id;
      card.dataset.from = mail.from;
      card.innerHTML = `
        <span class="email-from">${escHtml(mail.from.split('<')[0])}</span>
        <span class="email-date">${escHtml(mail.date.slice(0, 16))}</span>
        <span class="email-subj">${escHtml(mail.subject)}</span>
        <span class="email-snip">${escHtml(mail.snippet.slice(0, 80))}…</span>`;
      card.addEventListener('click', () => openEmailModal(mail));
      inboxList.appendChild(card);
    });
  } catch (err) {
    inboxList.innerHTML = `<p class="placeholder" style="color:var(--red)">Error: ${escHtml(err.message)}</p>`;
  }
}

btnRefresh.addEventListener('click', () => loadInbox(inboxSearch.value.trim()));
inboxSearch.addEventListener('keydown', e => { if (e.key === 'Enter') loadInbox(inboxSearch.value.trim()); });

// Auto-load inbox when switching to it
$$('.nav-btn').forEach(btn => {
  if (btn.dataset.panel === 'inbox') {
    btn.addEventListener('click', () => loadInbox());
  }
});

// ── Email modal ───────────────────────────────────────────────────────────
function openEmailModal(mail) {
  currentEmailId   = mail.id;
  currentEmailFrom = mail.from;
  modalSubject.textContent = mail.subject;
  modalFrom.textContent    = `From: ${mail.from}`;
  modalDate.textContent    = `Date: ${mail.date}`;
  modalBody.textContent    = mail.body || mail.snippet;
  emailModal.classList.remove('hidden');
}

modalClose.addEventListener('click', () => emailModal.classList.add('hidden'));
emailModal.addEventListener('click', e => { if (e.target === emailModal) emailModal.classList.add('hidden'); });

btnModalDel.addEventListener('click', async () => {
  if (!currentEmailId) return;
  await fetch(`${API}/email/${currentEmailId}`, { method: 'DELETE' });
  emailModal.classList.add('hidden');
  loadInbox();
});

btnModalReply.addEventListener('click', () => {
  emailModal.classList.add('hidden');
  // Switch to compose panel, pre-fill To from current email
  $$('.nav-btn').forEach(b => b.classList.remove('active'));
  $$('.panel').forEach(p => p.classList.remove('active'));
  $('[data-panel="compose"]').classList.add('active');
  $('#panel-compose').classList.add('active');
  composeTo.value   = currentEmailFrom;
  composeSubj.value = `Re: ${modalSubject.textContent}`;
  composeDesc.value = '';
  composeBody.value = '';
});

btnModalFwd.addEventListener('click', async () => {
  const to = prompt('Forward to (email address):');
  if (!to) return;
  await fetch(`${API}/email/forward`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message_id: currentEmailId, to }),
  });
  emailModal.classList.add('hidden');
  alert('Email forwarded!');
});

// ── Compose ───────────────────────────────────────────────────────────────
btnAiDraft.addEventListener('click', async () => {
  const to   = composeTo.value.trim();
  const subj = composeSubj.value.trim();
  const desc = composeDesc.value.trim();
  if (!to || !subj) { alert('Please fill in To and Subject first.'); return; }

  composeAiSt.classList.remove('hidden');
  try {
    const prompt = `write an email to ${to} about ${subj}${desc ? ': ' + desc : ''}`;
    const r = await fetch(`${API}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: prompt }),
    });
    if (!r.ok) throw new Error(await r.text());
    const data = await r.json();
    composeBody.value = data.response;
  } catch (err) {
    alert(`AI draft failed: ${err.message}`);
  } finally {
    composeAiSt.classList.add('hidden');
  }
});

btnSaveDraft.addEventListener('click', async () => {
  const to   = composeTo.value.trim();
  const subj = composeSubj.value.trim();
  const body = composeBody.value.trim();
  if (!to || !subj || !body) { alert('Please fill in all fields.'); return; }

  try {
    const r = await fetch(`${API}/email/draft`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ to, subject: subj, body }),
    });
    if (!r.ok) throw new Error(await r.text());
    showResult(composeResult, '💾 Draft saved!', 'success');
  } catch (err) {
    showResult(composeResult, `Error: ${err.message}`, 'error');
  }
});

composeForm.addEventListener('submit', async e => {
  e.preventDefault();
  const to   = composeTo.value.trim();
  const subj = composeSubj.value.trim();
  const body = composeBody.value.trim();
  if (!body) { alert('Email body is empty.'); return; }

  try {
    const r = await fetch(`${API}/email/send`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ to, subject: subj, body }),
    });
    if (!r.ok) throw new Error(await r.text());
    showResult(composeResult, '✅ Email sent!', 'success');
    composeForm.reset();
  } catch (err) {
    showResult(composeResult, `Error: ${err.message}`, 'error');
  }
});
