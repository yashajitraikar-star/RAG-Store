Create a `.gitignore` file in your project root folder with this content:

## `.gitignore`

```gitignore
# ── Environment & Secrets ──────────────────
.env
.env.*
*.env

# ── Database (local upload log) ────────────
rag.db
rag.db-shm
rag.db-wal

# ── Temp uploads folder ────────────────────
uploads/

# ── Python cache ───────────────────────────
__pycache__/
*.py[cod]
*.pyo
*.pyd
.Python

# ── Virtual environment ─────────────────────
venv/
env/
.venv/
.env/
ENV/

# ── IDE / Editor ───────────────────────────
.vscode/
.idea/
*.sublime-project
*.sublime-workspace

# ── Windows junk ───────────────────────────
Thumbs.db
desktop.ini
$RECYCLE.BIN/

# ── Logs ───────────────────────────────────
*.log
logs/

# ── Distribution / build ───────────────────
dist/
build/
*.egg-info/
.eggs/
```

***

## Also create a `.env.example` file

This is a **safe template** you CAN commit — it shows others what variables are needed without exposing your real values:

```ini
# Copy this file to .env and fill in your values
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_FILE_STORE=fileSearchStores/your_store_id_here
GEMINI_MODEL=gemini-2.0-flash
```

***

## Final folder structure for Git

```
gemini_rag_app/
├── .gitignore          ✅ committed
├── .env.example        ✅ committed  (safe template)
├── .env                ❌ ignored    (your real secrets)
├── rag.db              ❌ ignored    (local data)
├── uploads/            ❌ ignored    (temp files)
├── app.py              ✅ committed
├── setup_store.py      ✅ committed
├── requirements.txt    ✅ committed
├── start.bat           ✅ committed
├── templates/          ✅ committed
└── static/             ✅ committed
```



The `.env` file with your API key and store ID will **never be uploaded**. ✅