<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# no give me every code and folder structure

Here is the **complete app** — every file, ready to copy-paste.

***

## Folder Structure

```
gemini_rag_app/
├── app.py
├── setup_store.py      ← Run ONCE to create Gemini File Search Store
├── requirements.txt
├── .env
├── start.bat           ← Double-click to launch on Windows
├── rag.db              ← Auto-created (SQLite upload log)
├── uploads/            ← Auto-created (temp files)
├── templates/
│   ├── index.html      ← Upload dashboard
│   └── chat.html       ← Chatbot UI
└── static/
    └── style.css       ← Shared styles
```


***

## `requirements.txt`

```
flask>=3.0.0
python-dotenv>=1.0.0
google-genai>=1.0.0
```


***

## `.env`

```ini
GEMINI_API_KEY=YOUR_API_KEY_HERE
GEMINI_FILE_STORE=fileSearchStores/YOUR_STORE_ID_HERE
GEMINI_MODEL=gemini-2.5-pro
```

> ⚠️ Fill in `GEMINI_FILE_STORE` after running `setup_store.py` below.

***

## `setup_store.py` ← Run this ONCE

```python
"""
Run this script ONE TIME to create your Gemini File Search Store.
It will print the store name. Paste it into your .env file.
"""
import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
os.environ["GEMINI_API_KEY"] = os.getenv("GEMINI_API_KEY")
client = genai.Client()

store = client.file_search_stores.create(
    config={"display_name": "My RAG Knowledge Base"}
)

print("\n✅  File Search Store created!")
print(f"    Name: {store.name}")
print(f"\n📋  Add this to your .env:")
print(f"    GEMINI_FILE_STORE={store.name}")
print("\nNow run: python app.py")
```


***

## `app.py`

```python
import os
import sqlite3
import tempfile
import time
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

app = Flask(__name__)

# ─── Config ────────────────────────────────────────────────────────────
UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DB_PATH    = os.path.join(os.getcwd(), "rag.db")
API_KEY    = os.getenv("GEMINI_API_KEY")
STORE_NAME = os.getenv("GEMINI_FILE_STORE")
MODEL      = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")

os.environ["GEMINI_API_KEY"] = API_KEY
client = genai.Client()

# ─── Database ───────────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS uploads (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name   TEXT    NOT NULL,
            doc_name    TEXT    NOT NULL,
            uploaded_at TEXT    NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ─── Pages ──────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat")
def chat():
    return render_template("chat.html")

# ─── API: Upload PDF ────────────────────────────────────────────────────
@app.route("/api/upload", methods=["POST"])
def api_upload():
    if "file" not in request.files:
        return jsonify({"error": "No file attached"}), 400

    f = request.files["file"]
    if f.filename == "":
        return jsonify({"error": "No file selected"}), 400
    if not f.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are supported"}), 400

    display_name = f.filename
    tmp_path = None

    try:
        # Save to disk first — Windows-safe NamedTemporaryFile pattern
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".pdf", dir=UPLOAD_FOLDER
        ) as tmp:
            f.save(tmp.name)
            tmp_path = tmp.name

        # Upload directly to Gemini File Search Store
        operation = client.file_search_stores.upload_to_file_search_store(
            file=tmp_path,
            file_search_store_name=STORE_NAME,
            config={"display_name": display_name},
        )

        # Poll until Gemini finishes indexing (max ~5 minutes)
        for _ in range(60):
            if operation.done:
                break
            time.sleep(5)
            operation = client.operations.get(operation)

        if not operation.done:
            return jsonify({"error": "Upload timed out. Try again."}), 500

        doc_name = operation.response.name

        # Save to SQLite with timestamp
        uploaded_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO uploads (file_name, doc_name, uploaded_at) VALUES (?, ?, ?)",
            (display_name, doc_name, uploaded_at),
        )
        conn.commit()
        conn.close()

        return jsonify({
            "status":      "success",
            "file_name":   display_name,
            "doc_name":    doc_name,
            "uploaded_at": uploaded_at,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

# ─── API: List Uploads ──────────────────────────────────────────────────
@app.route("/api/list")
def api_list():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, file_name, doc_name, uploaded_at FROM uploads ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return jsonify([
        {"id": r[^0], "file_name": r[^1], "doc_name": r[^2], "uploaded_at": r[^3]}
        for r in rows
    ])

# ─── API: Delete Upload ─────────────────────────────────────────────────
@app.route("/api/delete/<int:row_id>", methods=["DELETE"])
def api_delete(row_id):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT doc_name FROM uploads WHERE id = ?", (row_id,)
    ).fetchone()

    if not row:
        conn.close()
        return jsonify({"error": "Record not found"}), 404

    doc_name = row[^0]

    try:
        client.file_search_stores.documents.delete(name=doc_name)
    except Exception as e:
        print(f"[Gemini delete warning] {e}")

    conn.execute("DELETE FROM uploads WHERE id = ?", (row_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "deleted"})

# ─── API: Chat ──────────────────────────────────────────────────────────
@app.route("/api/chat", methods=["POST"])
def api_chat():
    data    = request.get_json(force=True)
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"error": "Empty message"}), 400

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=[message],
            config=types.GenerateContentConfig(
                tools=[
                    types.Tool(
                        file_search=types.FileSearch(
                            file_search_store_names=[STORE_NAME]
                        )
                    )
                ]
            ),
        )
        return jsonify({"answer": response.text})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─── Run ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 46)
    print("  🧠  Gemini RAG App")
    print("  🌐  http://127.0.0.1:5000")
    print("=" * 46)
    app.run(host="127.0.0.1", port=5000, debug=True)
```


***

## `templates/index.html`

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Gemini RAG — Knowledge Base</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <nav class="navbar">
    <div class="nav-brand">🧠 Gemini RAG Manager</div>
    <a href="/chat" class="nav-btn">💬 Open Chatbot</a>
  </nav>

  <main class="container">

    <!-- Upload Card -->
    <div class="card">
      <div class="card-title">📄 Upload PDF to Knowledge Base</div>

      <div class="upload-zone" id="upload-zone">
        <div class="upload-icon">📂</div>
        <p class="upload-text">Drag & drop a PDF here, or <span class="link-text">click to browse</span></p>
        <p class="upload-hint">PDF only · Max 100 MB per file</p>
        <input type="file" id="file-input" accept="application/pdf">
      </div>

      <div class="file-preview" id="file-preview">
        <span>📄</span>
        <div>
          <div class="preview-name" id="preview-name"></div>
          <div class="preview-size" id="preview-size"></div>
        </div>
        <button class="clear-btn" id="clear-btn" title="Remove">✕</button>
      </div>

      <div class="progress-wrap" id="progress-wrap">
        <div class="progress-track">
          <div class="progress-bar" id="progress-bar"></div>
        </div>
        <p class="progress-label">Uploading & indexing… this can take 30–60 seconds</p>
      </div>

      <div class="upload-actions">
        <button class="btn btn-primary" id="upload-btn" disabled>⬆️ Upload to Gemini</button>
      </div>

      <div class="alert" id="upload-alert"></div>
    </div>

    <!-- Files Table Card -->
    <div class="card">
      <div class="card-header-row">
        <div class="card-title">📚 Uploaded PDFs — Knowledge Base</div>
        <button class="btn btn-ghost" onclick="loadList()">🔄 Refresh</button>
      </div>

      <div class="empty-state" id="empty-state">No PDFs uploaded yet.</div>

      <table id="files-table" style="display:none">
        <thead>
          <tr>
            <th>#</th>
            <th>File Name</th>
            <th>Gemini Document ID</th>
            <th>Uploaded At (UTC)</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody id="files-tbody"></tbody>
      </table>
    </div>

  </main>

  <script>
    const uploadZone   = document.getElementById('upload-zone');
    const fileInput    = document.getElementById('file-input');
    const uploadBtn    = document.getElementById('upload-btn');
    const filePreview  = document.getElementById('file-preview');
    const clearBtn     = document.getElementById('clear-btn');
    const previewName  = document.getElementById('preview-name');
    const previewSize  = document.getElementById('preview-size');
    const progressWrap = document.getElementById('progress-wrap');
    const progressBar  = document.getElementById('progress-bar');
    const uploadAlert  = document.getElementById('upload-alert');
    const emptyState   = document.getElementById('empty-state');
    const filesTable   = document.getElementById('files-table');
    const filesTbody   = document.getElementById('files-tbody');

    let selectedFile = null;

    // ── Drag & Drop + Click ─────────────────────────────
    uploadZone.addEventListener('click', () => fileInput.click());

    uploadZone.addEventListener('dragover', e => {
      e.preventDefault();
      uploadZone.classList.add('dragover');
    });
    uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));
    uploadZone.addEventListener('drop', e => {
      e.preventDefault();
      uploadZone.classList.remove('dragover');
      if (e.dataTransfer.files.length) pickFile(e.dataTransfer.files[^0]);
    });

    fileInput.addEventListener('change', () => {
      if (fileInput.files.length) pickFile(fileInput.files[^0]);
    });

    function pickFile(file) {
      if (!file.name.toLowerCase().endsWith('.pdf')) {
        showAlert('error', '❌ Only PDF files are supported.');
        return;
      }
      selectedFile = file;
      previewName.textContent = file.name;
      previewSize.textContent = fmtBytes(file.size);
      filePreview.style.display = 'flex';
      uploadBtn.disabled = false;
      clearAlert();
    }

    clearBtn.addEventListener('click', () => {
      selectedFile = null;
      fileInput.value = '';
      filePreview.style.display = 'none';
      uploadBtn.disabled = true;
      clearAlert();
    });

    function fmtBytes(b) {
      if (b < 1024) return b + ' B';
      if (b < 1024 * 1024) return (b / 1024).toFixed(1) + ' KB';
      return (b / (1024 * 1024)).toFixed(1) + ' MB';
    }

    // ── Upload ──────────────────────────────────────────
    uploadBtn.addEventListener('click', async () => {
      if (!selectedFile) return;
      uploadBtn.disabled = true;
      progressWrap.style.display = 'block';
      clearAlert();

      progressBar.style.width = '0%';
      let prog = 0;
      const tick = setInterval(() => {
        prog = Math.min(prog + 1.2, 88);
        progressBar.style.width = prog + '%';
      }, 600);

      const form = new FormData();
      form.append('file', selectedFile);

      try {
        const res  = await fetch('/api/upload', { method: 'POST', body: form });
        const data = await res.json();
        clearInterval(tick);

        if (!res.ok) throw new Error(data.error || 'Upload failed');

        progressBar.style.transition = 'width 0.4s';
        progressBar.style.width = '100%';
        await new Promise(r => setTimeout(r, 600));
        progressWrap.style.display = 'none';
        progressBar.style.width = '0%';
        progressBar.style.transition = '';

        showAlert('success', `✅ "${data.file_name}" uploaded & indexed — ${data.uploaded_at}`);
        clearBtn.click();
        loadList();
      } catch (err) {
        clearInterval(tick);
        progressWrap.style.display = 'none';
        showAlert('error', '❌ ' + err.message);
        uploadBtn.disabled = false;
      }
    });

    // ── List ────────────────────────────────────────────
    async function loadList() {
      try {
        const res  = await fetch('/api/list');
        const rows = await res.json();
        filesTbody.innerHTML = '';

        if (!rows.length) {
          emptyState.style.display = 'block';
          filesTable.style.display = 'none';
          return;
        }

        emptyState.style.display = 'none';
        filesTable.style.display = 'table';

        rows.forEach((r, i) => {
          const shortId = r.doc_name.split('/').pop() || r.doc_name;
          const tr = document.createElement('tr');
          tr.innerHTML = `
            <td>${i + 1}</td>
            <td>📄 ${esc(r.file_name)}</td>
            <td class="doc-id" title="${esc(r.doc_name)}">${esc(shortId)}</td>
            <td>${esc(r.uploaded_at)}</td>
            <td>
              <button class="btn btn-danger btn-sm"
                onclick="deleteRow(${r.id}, this)">🗑 Delete</button>
            </td>
          `;
          filesTbody.appendChild(tr);
        });
      } catch (err) {
        console.error('List error:', err);
      }
    }

    async function deleteRow(id, btn) {
      if (!confirm('Remove this PDF from the knowledge base?')) return;
      btn.disabled = true;
      btn.textContent = '…';
      try {
        const res  = await fetch('/api/delete/' + id, { method: 'DELETE' });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Delete failed');
        loadList();
      } catch (err) {
        alert('Error: ' + err.message);
        btn.disabled = false;
        btn.textContent = '🗑 Delete';
      }
    }

    function showAlert(type, msg) {
      uploadAlert.className = 'alert ' + type;
      uploadAlert.textContent = msg;
    }
    function clearAlert() {
      uploadAlert.className = 'alert';
      uploadAlert.textContent = '';
    }
    function esc(s) {
      return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
    }

    window.addEventListener('load', loadList);
  </script>
</body>
</html>
```


***

## `templates/chat.html`

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Gemini RAG — Chatbot</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <nav class="navbar">
    <div class="nav-brand">💬 Gemini RAG Chatbot</div>
    <a href="/" class="nav-btn">📚 Back to Dashboard</a>
  </nav>

  <div class="chat-page">
    <div class="chat-card">

      <div class="chat-info-bar">
        🔍 Answers are grounded in your uploaded PDFs
      </div>

      <div id="chat-log" class="chat-log">
        <div class="msg bot-msg">
          <div class="msg-bubble">
            👋 Hi! I'm your Gemini RAG assistant. Ask me anything about your uploaded PDFs!
          </div>
        </div>
      </div>

      <div class="chat-footer">
        <div class="chat-input-row">
          <input
            type="text"
            id="msg-input"
            class="chat-input"
            placeholder="Ask a question from your PDFs…"
            autocomplete="off"
          >
          <button class="btn btn-primary" id="send-btn">Send ➤</button>
        </div>
        <p class="chat-hint">Press Enter to send · Shift+Enter for new line</p>
      </div>

    </div>
  </div>

  <script>
    const chatLog  = document.getElementById('chat-log');
    const msgInput = document.getElementById('msg-input');
    const sendBtn  = document.getElementById('send-btn');

    function addMsg(text, cls) {
      const wrap   = document.createElement('div');
      wrap.className = 'msg ' + cls;
      const bubble = document.createElement('div');
      bubble.className = 'msg-bubble';
      bubble.textContent = text;
      wrap.appendChild(bubble);
      chatLog.appendChild(wrap);
      chatLog.scrollTop = chatLog.scrollHeight;
      return wrap;
    }

    async function send() {
      const msg = msgInput.value.trim();
      if (!msg) return;

      addMsg(msg, 'user-msg');
      msgInput.value = '';
      sendBtn.disabled = true;
      msgInput.disabled = true;

      const thinking = addMsg('⏳ Searching knowledge base…', 'bot-msg thinking');

      try {
        const res  = await fetch('/api/chat', {
          method:  'POST',
          headers: { 'Content-Type': 'application/json' },
          body:    JSON.stringify({ message: msg })
        });
        const data = await res.json();
        chatLog.removeChild(thinking);

        if (!res.ok) throw new Error(data.error || 'Chat failed');
        addMsg(data.answer, 'bot-msg');

      } catch (err) {
        chatLog.removeChild(thinking);
        addMsg('❌ Error: ' + err.message, 'bot-msg error-msg');
      } finally {
        sendBtn.disabled = false;
        msgInput.disabled = false;
        msgInput.focus();
      }
    }

    sendBtn.addEventListener('click', send);
    msgInput.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        send();
      }
    });
  </script>
</body>
</html>
```


***

## `static/style.css`

```css
/* ═══════════════════════════════════════════
   Gemini RAG App — Shared Styles
═══════════════════════════════════════════ */

*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  background: #f0f2f5;
  color: #1a1a2e;
  min-height: 100vh;
}

/* ── Navbar ─────────────────────────────── */
.navbar {
  background: #1a1a2e;
  color: white;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 28px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.18);
}

.nav-brand {
  font-size: 1.15rem;
  font-weight: 700;
}

.nav-btn {
  background: rgba(255,255,255,0.12);
  color: white;
  text-decoration: none;
  padding: 8px 18px;
  border-radius: 8px;
  font-size: 0.88rem;
  font-weight: 600;
  transition: background 0.2s;
}

.nav-btn:hover {
  background: rgba(255,255,255,0.22);
}

/* ── Container ──────────────────────────── */
.container {
  max-width: 960px;
  margin: 30px auto;
  padding: 0 20px;
}

/* ── Card ───────────────────────────────── */
.card {
  background: white;
  border-radius: 14px;
  padding: 28px;
  margin-bottom: 24px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.07);
}

.card-title {
  font-size: 1.05rem;
  font-weight: 700;
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 2px solid #f0f2f5;
}

.card-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 2px solid #f0f2f5;
}

.card-header-row .card-title {
  margin-bottom: 0;
  padding-bottom: 0;
  border-bottom: none;
}

/* ── Buttons ────────────────────────────── */
.btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 10px 20px;
  border: none;
  border-radius: 8px;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.18s;
  font-family: inherit;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: #4361ee;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #3450d4;
  transform: translateY(-1px);
}

.btn-ghost {
  background: #f0f2f5;
  color: #555;
}

.btn-ghost:hover {
  background: #e2e6ea;
}

.btn-danger {
  background: #e74c3c;
  color: white;
}

.btn-danger:hover:not(:disabled) {
  background: #c0392b;
}

.btn-sm {
  padding: 5px 12px;
  font-size: 0.8rem;
}

/* ── Upload Zone ────────────────────────── */
.upload-zone {
  border: 2.5px dashed #c5cfe0;
  border-radius: 12px;
  padding: 36px 20px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
  background: #f9faff;
  user-select: none;
}

.upload-zone:hover,
.upload-zone.dragover {
  border-color: #4361ee;
  background: #eef1ff;
}

.upload-zone input[type="file"] { display: none; }

.upload-icon { font-size: 2.5rem; margin-bottom: 10px; }

.upload-text {
  font-size: 0.97rem;
  color: #444;
  margin-bottom: 6px;
}

.link-text {
  color: #4361ee;
  font-weight: 600;
  text-decoration: underline;
}

.upload-hint {
  font-size: 0.8rem;
  color: #9aa4b4;
}

/* ── File Preview ───────────────────────── */
.file-preview {
  display: none;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: #eef1ff;
  border-radius: 10px;
  margin-top: 14px;
  font-size: 1.2rem;
}

.preview-name {
  font-weight: 600;
  font-size: 0.9rem;
}

.preview-size {
  font-size: 0.78rem;
  color: #888;
  margin-top: 2px;
}

.clear-btn {
  margin-left: auto;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 1rem;
  color: #aaa;
  padding: 4px 8px;
  border-radius: 50%;
  transition: color 0.2s;
}

.clear-btn:hover { color: #e74c3c; }

/* ── Progress ───────────────────────────── */
.progress-wrap { display: none; margin-top: 14px; }

.progress-track {
  background: #e8ecf0;
  border-radius: 6px;
  height: 8px;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  background: linear-gradient(90deg, #4361ee, #7c3aed);
  border-radius: 6px;
  width: 0%;
  transition: width 0.5s ease;
}

.progress-label {
  font-size: 0.8rem;
  color: #777;
  margin-top: 7px;
}

.upload-actions { margin-top: 16px; }

/* ── Alert ──────────────────────────────── */
.alert {
  margin-top: 14px;
  padding: 11px 15px;
  border-radius: 8px;
  font-size: 0.9rem;
  line-height: 1.4;
}

.alert:empty { display: none; }

.alert.success {
  background: #d4edda;
  color: #155724;
  border-left: 4px solid #28a745;
}

.alert.error {
  background: #f8d7da;
  color: #721c24;
  border-left: 4px solid #dc3545;
}

/* ── Table ──────────────────────────────── */
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.88rem;
}

thead {
  background: #1a1a2e;
  color: white;
}

th, td {
  padding: 12px 14px;
  text-align: left;
  border-bottom: 1px solid #edf0f5;
}

th {
  font-size: 0.8rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.4px;
}

tbody tr:hover { background: #f7f9fc; }

.doc-id {
  font-family: 'Courier New', monospace;
  font-size: 0.78rem;
  color: #888;
  cursor: help;
}

.empty-state {
  text-align: center;
  color: #aab;
  padding: 36px;
  font-size: 0.95rem;
}

/* ══════════════════════════════════════════
   Chat Page
══════════════════════════════════════════ */
.chat-page {
  display: flex;
  justify-content: center;
  padding: 20px 16px;
  height: calc(100vh - 60px);
}

.chat-card {
  background: white;
  border-radius: 16px;
  box-shadow: 0 3px 16px rgba(0,0,0,0.09);
  display: flex;
  flex-direction: column;
  width: 100%;
  max-width: 860px;
  overflow: hidden;
}

.chat-info-bar {
  background: #eef1ff;
  color: #4361ee;
  font-size: 0.82rem;
  font-weight: 600;
  padding: 9px 18px;
  border-bottom: 1px solid #dce3ff;
}

.chat-log {
  flex: 1;
  overflow-y: auto;
  padding: 20px 18px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: #f8f9fb;
}

.msg { display: flex; }

.msg-bubble {
  max-width: 78%;
  padding: 12px 16px;
  border-radius: 16px;
  font-size: 0.93rem;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
}

.user-msg { justify-content: flex-end; }

.user-msg .msg-bubble {
  background: #4361ee;
  color: white;
  border-bottom-right-radius: 4px;
}

.bot-msg .msg-bubble {
  background: white;
  color: #222;
  border-bottom-left-radius: 4px;
  box-shadow: 0 1px 5px rgba(0,0,0,0.08);
}

.thinking .msg-bubble {
  background: #eef1ff;
  color: #7a8bb5;
  font-style: italic;
}

.error-msg .msg-bubble {
  background: #fff0f0;
  color: #c00;
}

.chat-footer {
  padding: 14px 18px 10px;
  border-top: 1px solid #edf0f5;
  background: white;
}

.chat-input-row {
  display: flex;
  gap: 10px;
}

.chat-input {
  flex: 1;
  padding: 11px 16px;
  border: 2px solid #dde2ec;
  border-radius: 10px;
  font-size: 0.93rem;
  outline: none;
  transition: border-color 0.18s;
  font-family: inherit;
}

.chat-input:focus { border-color: #4361ee; }

.chat-hint {
  font-size: 0.75rem;
  color: #bbb;
  margin-top: 6px;
  text-align: right;
}
```


***

## `start.bat`

```bat
@echo off
title Gemini RAG App
echo.
echo  =============================================
echo    Gemini RAG Manager
echo    Opening at: http://127.0.0.1:5000
echo  =============================================
echo.
start /min "" cmd /c "timeout /t 2 >nul && start http://127.0.0.1:5000"
python app.py
pause
```


***

## Setup \& Run (step by step)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Add your GEMINI_API_KEY to .env

# 3. Create File Search Store (ONE TIME ONLY)
python setup_store.py
# → Copy the printed store name into .env as GEMINI_FILE_STORE=...

# 4. Start the app
python app.py
# Or double-click start.bat
```

Then open `http://127.0.0.1:5000` — upload PDFs on the dashboard, then go to `/chat` to test the knowledge base.[^1]

***

## Important Notes

- **Upload takes 30–60 seconds** — Gemini needs to chunk, embed, and index the PDF before it's queryable.[^1]
- **Supported models for File Search** are `gemini-2.5-pro`, `gemini-2.5-flash-lite`, and the Gemini 3 preview models only.[^1]
- **SQLite `rag.db`** is your local upload log; deleting a row also removes the document from Gemini's store.[^2]
- If you get a `Permission denied` temp file error on Windows, make sure no antivirus is locking the `uploads/` folder.[^3]

<div align="center">⁂</div>

[^1]: https://ai.google.dev/gemini-api/docs/file-search

[^2]: https://www.perplexity.ai/search/dd36f557-1cf3-4f7c-bff1-171549126488

[^3]: https://www.perplexity.ai/search/27abb6a6-2a65-4ff3-ac78-ffe305195214

