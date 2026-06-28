// ── API Key modal ──
async function checkKeyStatus() {
  try {
    const res = await fetch('/key-status');
    const data = await res.json();
    setKeyActive(data.configured);
    if (!data.configured) openKeyModal();
  } catch {}
}

function setKeyActive(active) {
  const btn = document.getElementById('key-btn');
  const label = document.getElementById('key-btn-label');
  btn.className = 'key-btn' + (active ? ' active' : '');
  label.textContent = active ? 'API Key ✓' : 'Set API Key';
}

function openKeyModal() {
  document.getElementById('key-modal').classList.add('open');
  document.getElementById('modal-error').textContent = '';
  setTimeout(() => document.getElementById('key-input').focus(), 60);
}

function closeKeyModal() {
  document.getElementById('key-modal').classList.remove('open');
  document.getElementById('key-input').value = '';
  document.getElementById('modal-error').textContent = '';
}

function handleOverlayClick(e) {
  if (e.target === document.getElementById('key-modal')) closeKeyModal();
}

function toggleVis() {
  const inp = document.getElementById('key-input');
  inp.type = inp.type === 'password' ? 'text' : 'password';
}

async function saveKey() {
  const key = document.getElementById('key-input').value.trim();
  if (!key) { document.getElementById('modal-error').textContent = 'Please paste your API key.'; return; }
  const errEl = document.getElementById('modal-error');
  const btn = document.getElementById('save-key-btn');
  btn.disabled = true;
  btn.textContent = 'Verifying…';
  errEl.textContent = '';
  try {
    const res = await fetch('/set-key', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ api_key: key }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({ detail: 'Unknown error' }));
      errEl.textContent = data.detail || 'Failed to verify key.';
      return;
    }
    localStorage.setItem('savedApiKey', key);
    setKeyActive(true);
    closeKeyModal();
    appendMessage('assistant', '✅ API key saved! You can now chat and run AI actions.');
  } catch (e) {
    errEl.textContent = 'Network error: ' + e.message;
  } finally {
    btn.disabled = false;
    btn.textContent = 'Verify & Save';
  }
}

// ── CodeMirror setup ──
const editor = CodeMirror.fromTextArea(document.getElementById('editor'), {
  mode: 'python',
  theme: 'dracula',
  lineNumbers: true,
  indentUnit: 4,
  tabSize: 4,
  indentWithTabs: false,
  lineWrapping: false,
  matchBrackets: true,
  autoCloseBrackets: true,
  extraKeys: { Tab: cm => cm.execCommand('indentMore') },
  value: `# Welcome to AI Coding Assistant
# Write or paste Python code here, then use the toolbar or chat

def fibonacci(n):
    """Return the nth Fibonacci number."""
    if n <= 1:
        return n
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b

# Example usage
for i in range(10):
    print(f"fib({i}) = {fibonacci(i)}")
`,
});
editor.setValue(editor.getOption('value'));

editor.on('change', () => {
  localStorage.setItem('savedCode', editor.getValue());
});

// ── Chat state ──
let history = [];
let isWaiting = false;

// ── Resizable divider ──
(function() {
  const divider = document.getElementById('divider');
  const main = document.getElementById('main');
  const left = document.getElementById('left-panel');
  const right = document.getElementById('right-panel');
  let dragging = false, startX = 0, startLeft = 0;

  divider.addEventListener('mousedown', e => {
    dragging = true; startX = e.clientX;
    startLeft = left.getBoundingClientRect().width;
    document.body.style.userSelect = 'none';
    document.body.style.cursor = 'col-resize';
  });
  document.addEventListener('mousemove', e => {
    if (!dragging) return;
    const total = main.getBoundingClientRect().width - 4;
    const newLeft = Math.min(Math.max(startLeft + e.clientX - startX, 200), total - 200);
    left.style.flex = 'none'; right.style.flex = 'none';
    left.style.width = newLeft + 'px';
    right.style.width = (total - newLeft) + 'px';
  });
  document.addEventListener('mouseup', () => {
    dragging = false;
    document.body.style.userSelect = '';
    document.body.style.cursor = '';
  });
})();

// ── Auto-resize textarea ──
const chatInput = document.getElementById('chat-input');
chatInput.addEventListener('input', () => {
  chatInput.style.height = 'auto';
  chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
});
chatInput.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat(); }
});

// ── Render markdown-ish content ──
function renderContent(text) {
  return text.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
    const language = lang || 'plaintext';
    let highlighted;
    try {
      highlighted = hljs.highlight(code.trim(), { language }).value;
    } catch {
      highlighted = hljs.highlightAuto(code.trim()).value;
    }
    const id = 'cb-' + Math.random().toString(36).slice(2);
    return `<div class="code-block-wrap">
      <pre><code class="hljs language-${language}" id="${id}">${highlighted}</code></pre>
      <button class="copy-btn" onclick="copyCode('${id}', this)">Copy</button>
    </div>`;
  })
  .replace(/`([^`]+)`/g, '<code>$1</code>')
  .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  .replace(/\n/g, '<br/>');
}

function copyCode(id, btn) {
  const el = document.getElementById(id);
  if (!el) return;
  navigator.clipboard.writeText(el.innerText).then(() => {
    btn.textContent = 'Copied!';
    btn.classList.add('copied');
    setTimeout(() => { btn.textContent = 'Copy'; btn.classList.remove('copied'); }, 1800);
  });
}

// ── Append messages ──
function appendMessage(role, content, isHtml = false) {
  const container = document.getElementById('chat-messages');
  const div = document.createElement('div');
  div.className = `message ${role}`;
  const label = document.createElement('div');
  label.className = 'msg-label';
  label.textContent = role === 'user' ? 'You' : 'Assistant';
  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';
  if (isHtml) bubble.innerHTML = content;
  else bubble.textContent = content;
  div.appendChild(label);
  div.appendChild(bubble);
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
  return div;
}

function showTyping() {
  const container = document.getElementById('chat-messages');
  const div = document.createElement('div');
  div.className = 'message assistant';
  div.id = 'typing-indicator';
  const label = document.createElement('div');
  label.className = 'msg-label';
  label.textContent = 'Assistant';
  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';
  bubble.innerHTML = '<div class="typing-indicator"><div class="dot"></div><div class="dot"></div><div class="dot"></div></div>';
  div.appendChild(label);
  div.appendChild(bubble);
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function removeTyping() {
  const el = document.getElementById('typing-indicator');
  if (el) el.remove();
}

function setWaiting(val) {
  isWaiting = val;
  document.getElementById('send-btn').disabled = val;
  chatInput.disabled = val;
}

// ── Send chat (streaming) ──
async function sendChat(message, action = 'chat') {
  const msg = (message || chatInput.value).trim();
  if (!msg || isWaiting) return;

  chatInput.value = '';
  chatInput.style.height = 'auto';

  appendMessage('user', msg);
  history.push({ role: 'user', content: msg });
  localStorage.setItem('savedChat', JSON.stringify(history));
  setWaiting(true);
  showTyping();

  const code = editor.getValue();
  const payload = { message: msg, code, history: history.slice(-40), action };

  try {
    const res = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'Request failed');
    }

    removeTyping();

    const container = document.getElementById('chat-messages');
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message assistant';
    const label = document.createElement('div');
    label.className = 'msg-label';
    label.textContent = 'Assistant';
    const bubble = document.createElement('div');
    bubble.className = 'msg-bubble';
    msgDiv.appendChild(label);
    msgDiv.appendChild(bubble);
    container.appendChild(msgDiv);
    container.scrollTop = container.scrollHeight;

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let rawReply = '';
    let buf = '';

    outer: while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split('\n');
      buf = lines.pop();
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const data = line.slice(6);
        if (data === '[DONE]') break outer;
        if (data.startsWith('[ERROR]')) throw new Error(data.slice(8).trim());
        try {
          const text = JSON.parse(data);
          rawReply += text;
          bubble.innerHTML = renderContent(rawReply);
          container.scrollTop = container.scrollHeight;
        } catch {}
      }
    }

    history.push({ role: 'model', content: rawReply });
    localStorage.setItem('savedChat', JSON.stringify(history));

  } catch (e) {
    removeTyping();
    appendMessage('assistant', '⚠ Error: ' + e.message);
  } finally {
    setWaiting(false);
  }
}

// ── Toolbar actions ──
async function doAction(action) {
  const code = editor.getValue().trim();
  if (!code) { alert('Please write some code first.'); return; }
  const labels = { explain: 'Explain this code', debug: 'Debug this code', test: 'Write tests for this code', optimize: 'Optimize this code' };
  await sendChat(labels[action] || action, action);
}

// ── Quick chips ──
function sendChip(msg) { sendChat(msg, 'chat'); }

// ── Clear editor ──
function clearEditor() { editor.setValue(''); localStorage.removeItem('savedCode'); editor.focus(); }

// ── Clear chat ──
function clearChat() {
  history = [];
  localStorage.removeItem('savedChat');
  const c = document.getElementById('chat-messages');
  c.innerHTML = '';
  appendMessage('assistant', 'Chat cleared. Ready to help!');
}

// ── Run code ──
async function runCode() {
  const code = editor.getValue().trim();
  if (!code) { alert('Nothing to run.'); return; }

  const scroll = document.getElementById('output-scroll');
  const placeholder = document.getElementById('output-placeholder');
  const status = document.getElementById('output-status');

  if (placeholder) placeholder.style.display = 'none';
  scroll.innerHTML = '<span style="color:var(--text-muted);font-size:.8rem">Running…</span>';
  status.textContent = '';
  status.className = 'output-status';

  try {
    const res = await fetch('/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code, language: 'python', input: document.getElementById('stdin-input').value || null }),
    });
    const data = await res.json();
    scroll.innerHTML = '';

    if (data.output) {
      const pre = document.createElement('pre');
      pre.className = 'output-text';
      pre.textContent = data.output;
      scroll.appendChild(pre);
    }
    if (data.error) {
      const pre = document.createElement('pre');
      pre.className = 'output-text stderr';
      pre.textContent = data.error;
      scroll.appendChild(pre);
    }
    if (!data.output && !data.error) {
      scroll.innerHTML = '<span style="color:var(--text-muted);font-size:.8rem;font-style:italic">Program exited with no output.</span>';
    }

    if (data.error) {
      status.textContent = '● Error'; status.className = 'output-status err';
    } else {
      status.textContent = '● Success'; status.className = 'output-status ok';
    }
    scroll.scrollTop = scroll.scrollHeight;
  } catch (e) {
    scroll.innerHTML = `<pre class="output-text stderr">Failed to run: ${e.message}</pre>`;
    status.textContent = '● Error'; status.className = 'output-status err';
  }
}

// ── Init: restore persisted state ──
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('key-input').addEventListener('keydown', e => {
    if (e.key === 'Enter') saveKey();
    if (e.key === 'Escape') closeKeyModal();
  });

  const savedCode = localStorage.getItem('savedCode');
  if (savedCode !== null) {
    editor.setValue(savedCode);
    editor.clearHistory();
  }

  const stdinEl = document.getElementById('stdin-input');
  const savedStdin = localStorage.getItem('savedStdin');
  if (savedStdin !== null) stdinEl.value = savedStdin;
  stdinEl.addEventListener('input', () => localStorage.setItem('savedStdin', stdinEl.value));

  const savedChat = localStorage.getItem('savedChat');
  if (savedChat) {
    try {
      const msgs = JSON.parse(savedChat);
      if (Array.isArray(msgs) && msgs.length > 0) {
        history = msgs;
        msgs.forEach(m => {
          const displayRole = m.role === 'model' ? 'assistant' : 'user';
          const isAssistant = displayRole === 'assistant';
          appendMessage(displayRole, isAssistant ? renderContent(m.content) : m.content, isAssistant);
        });
      }
    } catch {}
  }

  const savedKey = localStorage.getItem('savedApiKey');
  if (savedKey) {
    document.getElementById('key-input').value = savedKey;
    fetch('/set-key', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ api_key: savedKey }),
    }).then(r => {
      if (r.ok) setKeyActive(true);
      else checkKeyStatus();
    }).catch(() => checkKeyStatus());
  } else {
    checkKeyStatus();
  }
});
