import os
import requests
import sqlite3
import tempfile
import time
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials
from google import genai
from google.genai import types
from system_prompt import SYSTEM_PROMPT, get_general_counselor_prompt

load_dotenv()

app = Flask(__name__)

# ─── Config ──────────────────────────────────────────────────────────────
try:
    if not firebase_admin._apps:
        cred = credentials.Certificate(os.path.join(os.getcwd(), "next123-dc2f7-firebase-adminsdk-fbsvc-8352fe0478.json"))
        firebase_admin.initialize_app(cred)
except Exception as e:
    print(f"Failed to initialize Firebase Admin: {e}")

UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DB_PATH    = os.path.join(os.getcwd(), "rag.db")
API_KEY    = os.getenv("GEMINI_API_KEY")
STORE_NAME = os.getenv("GEMINI_FILE_STORE")
MODEL      = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
BASE_URL   = "https://generativelanguage.googleapis.com/v1beta"

os.environ["GEMINI_API_KEY"] = API_KEY
client = genai.Client()

# ─── Supported File Types ────────────────────────────────────────────────
MIME_MAP = {
    # Documents
    ".pdf":  "application/pdf",
    ".txt":  "text/plain",
    ".md":   "text/markdown",
    ".html": "text/html",
    ".htm":  "text/html",
    ".csv":  "text/csv",
    ".json": "application/json",
    ".xml":  "application/xml",
    ".rtf":  "application/rtf",
    # Microsoft Office
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc":  "application/msword",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls":  "application/vnd.ms-excel",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".ppt":  "application/vnd.ms-powerpoint",
    # OpenDocument
    ".odt":  "application/vnd.oasis.opendocument.text",
    ".ods":  "application/vnd.oasis.opendocument.spreadsheet",
    ".odp":  "application/vnd.oasis.opendocument.presentation",
    # Code files
    ".py":   "text/x-python",
    ".js":   "application/javascript",
    ".ts":   "application/typescript",
    ".dart": "application/dart",
    ".java": "text/x-java-source",
    ".c":    "text/x-csrc",
    ".cpp":  "text/x-c++src",
    ".cs":   "text/x-csharp",
    ".go":   "text/x-go",
    ".rs":   "text/x-rustsrc",
    ".rb":   "text/x-ruby",
    ".php":  "application/x-php",
    ".sh":   "application/x-sh",
    ".sql":  "application/sql",
    ".yaml": "application/yaml",
    ".yml":  "application/yaml",
    ".toml": "application/toml",
    ".ini":  "text/plain",
    ".css":  "text/css",
}

SUPPORTED_EXTENSIONS = set(MIME_MAP.keys())

# ─── Database ─────────────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS uploads (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name   TEXT    NOT NULL,
            file_type   TEXT    NOT NULL,
            doc_name    TEXT    NOT NULL,
            uploaded_at TEXT    NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ─── Pages ────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat")
def chat():
    return render_template("chat.html")

@app.route("/auth")
def auth_page():
    return render_template("auth.html")

# ─── API: Upload File ─────────────────────────────────────────────────────
@app.route("/api/upload", methods=["POST"])
def api_upload():
    if "file" not in request.files:
        return jsonify({"error": "No file attached"}), 400

    f = request.files["file"]
    if f.filename == "":
        return jsonify({"error": "No file selected"}), 400

    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return jsonify({"error": f"Unsupported file type '{ext}'"}), 400

    display_name = f.filename
    tmp_path     = None

    try:
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=ext, dir=UPLOAD_FOLDER
        ) as tmp:
            f.save(tmp.name)
            tmp_path = tmp.name

        print(f"[Upload] Sending '{display_name}' to Gemini...")

        operation = client.file_search_stores.upload_to_file_search_store(
            file=tmp_path,
            file_search_store_name=STORE_NAME,
            config={"display_name": display_name},
        )

        print(f"[Upload] Waiting for indexing to complete...")

        # ── Poll until done ──────────────────────────────────────────────
        for attempt in range(75):
            if getattr(operation, "done", False):
                print(f"[Upload] Done after {attempt} polls.")
                break
            time.sleep(4)
            try:
                operation = client.operations.get(operation)
                print(f"[Poll {attempt}] done={getattr(operation, 'done', '?')}")
            except Exception as poll_err:
                print(f"[Poll {attempt}] error: {poll_err}")

        if not getattr(operation, "done", False):
            return jsonify({"error": "Upload timed out. Try again."}), 500

        # ── Get doc_name safely from response ────────────────────────────
        # Try all known response shapes — SDK versions differ
        doc_name = None
        resp = getattr(operation, "response", None)

        if resp is not None:
            # Shape 1: response.name
            if hasattr(resp, "name"):
                doc_name = resp.name
            # Shape 2: response.document.name
            elif hasattr(resp, "document") and hasattr(resp.document, "name"):
                doc_name = resp.document.name
            # Shape 3: response is a dict
            elif isinstance(resp, dict):
                doc_name = resp.get("name") or resp.get("document", {}).get("name")

        # ── Fallback: list documents and find by display_name ────────────
        if not doc_name:
            print(f"[Upload] response.name not found, listing documents...")
            try:
                docs = client.file_search_stores.documents.list(file_search_store_name=STORE_NAME)
                for doc in docs:
                    print(f"  Found doc: {doc.name} | display: {getattr(doc, 'display_name', '?')}")
                    if getattr(doc, "display_name", "") == display_name:
                        doc_name = doc.name
                        break
                # If still not found, take the most recently listed (first in list)
                if not doc_name:
                    docs_again = list(client.file_search_stores.documents.list(file_search_store_name=STORE_NAME))
                    if docs_again:
                        doc_name = docs_again[0].name
            except Exception as list_err:
                print(f"[Upload] list() fallback failed: {list_err}")

        if not doc_name:
            # Last resort: store as unknown but still track in DB
            doc_name = f"{STORE_NAME}/documents/unknown-{int(time.time())}"
            print(f"[Upload] ⚠️ Could not determine doc_name, using placeholder: {doc_name}")

        uploaded_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO uploads (file_name, file_type, doc_name, uploaded_at) VALUES (?, ?, ?, ?)",
            (display_name, ext.lstrip(".").upper(), doc_name, uploaded_at),
        )
        conn.commit()
        conn.close()

        print(f"[Upload] ✅ Saved: {display_name} → {doc_name}")

        return jsonify({
            "status":      "success",
            "file_name":   display_name,
            "file_type":   ext.lstrip(".").upper(),
            "doc_name":    doc_name,
            "uploaded_at": uploaded_at,
        })

    except Exception as e:
        print(f"[Upload] ❌ {e}")
        return jsonify({"error": str(e)}), 500

    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

# ─── API: List Uploads ─────────────────────────────────────────────────────
@app.route("/api/list")
def api_list():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, file_name, file_type, doc_name, uploaded_at FROM uploads ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return jsonify([
        {
            "id":          r[0],
            "file_name":   r[1],
            "file_type":   r[2],
            "doc_name":    r[3],
            "uploaded_at": r[4],
        }
        for r in rows
    ])

# ─── API: Delete Upload ────────────────────────────────────────────────────
@app.route("/api/delete/<int:row_id>", methods=["DELETE"])
def api_delete(row_id):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT doc_name FROM uploads WHERE id = ?", (row_id,)
    ).fetchone()

    if not row:
        conn.close()
        return jsonify({"error": "Record not found"}), 404

    doc_name = row[0]

    try:
        resp = requests.delete(f"{BASE_URL}/{doc_name}?force=true&key={API_KEY}")
        if resp.status_code != 200:
            print(f"[Gemini force-delete warning] {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"[Gemini delete exception] {e}")

    conn.execute("DELETE FROM uploads WHERE id = ?", (row_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "deleted"})

# ─── API: Gemini Store Live Listing ────────────────────────────────────────
@app.route("/api/store-docs")
def api_store_docs():
    try:
        docs = list(client.file_search_stores.documents.list(parent=STORE_NAME))
        result = []
        for doc in docs:
            result.append({
                "name": doc.name,
                "display_name": getattr(doc, 'display_name', None) or doc.name,
                "create_time": str(getattr(doc, 'create_time', ''))
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─── API: Force Delete Gemini Doc ──────────────────────────────────────────
@app.route("/api/store-delete", methods=["POST"])
def api_store_delete():
    data = request.get_json()
    doc_name = data.get("doc_name")
    if not doc_name:
        return jsonify({"error": "Missing doc_name"}), 400

    resp = requests.delete(f"{BASE_URL}/{doc_name}?force=true&key={API_KEY}")
    if resp.status_code == 200:
        # Also clean up local DB if tracked
        conn = sqlite3.connect(DB_PATH)
        conn.execute("DELETE FROM uploads WHERE doc_name = ?", (doc_name,))
        conn.commit()
        conn.close()
        return jsonify({"status": "deleted"})
    else:
        return jsonify({"error": f"Failed: {resp.status_code} {resp.text}"}), 500

# ─── API: Chat ─────────────────────────────────────────────────────────────
@app.route("/api/chat", methods=["POST"])
def api_chat():
    data    = request.get_json(force=True)
    message = data.get("message", "").strip()
    history = data.get("history", [])   # list of previous messages
    user_name = data.get("userName", "User")
    user_profile = data.get("userProfile", None)

    if not message:
        return jsonify({"error": "Empty message"}), 400

    try:
        # Build contents array from history + current message
        contents = []
        for entry in history:
            contents.append(
                types.Content(
                    role=entry["role"],   # "user" or "model"
                    parts=[types.Part(text=entry["text"])]
                )
            )
        # Add current user message
        contents.append(
            types.Content(
                role="user",
                parts=[types.Part(text=message)]
            )
        )

        dynamic_prompt = get_general_counselor_prompt(user_name, user_profile)
        
        response = client.models.generate_content(
            model=MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=dynamic_prompt,
                tools=[
                    types.Tool(
                        file_search=types.FileSearch(
                            file_search_store_names=[STORE_NAME]
                        )
                    )
                ]
            ),
        )

        # Safely extract text - response.text can be None if model only made tool calls
        answer = None
        if response.text:
            answer = response.text
        elif response.candidates:
            for candidate in response.candidates:
                if candidate.content and candidate.content.parts:
                    for part in candidate.content.parts:
                        if hasattr(part, 'text') and part.text:
                            answer = part.text
                            break
                if answer:
                    break

        if not answer:
            answer = "I found some relevant information but couldn't compose a response. Please try rephrasing your question."

        return jsonify({"answer": answer})

    except Exception as e:
        print(f"[Chat] ❌ Error: {e}")
        return jsonify({"error": str(e)}), 500

# ─── Run ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 46)
    print("  🧠  Gemini RAG App")
    print("  🌐  http://127.0.0.1:7000")
    print("=" * 46)
    app.run(host="127.0.0.1", port=7000, debug=True)
