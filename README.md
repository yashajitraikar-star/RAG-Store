# 🧠 Gemini RAG Manager

A Python + Flask web app that lets you upload documents to a **Gemini File Search Store** as a knowledge base, and chat with them using the Gemini API.

---

## ✨ Features

- Upload PDFs, DOCX, XLSX, TXT, MD, CSV, JSON, HTML, code files & more
- Tracks every uploaded file with date & time in a local SQLite database
- Delete files from the knowledge base
- Built-in chatbot to test the knowledge base
- Drag & drop file upload UI
- Fully local — no external database needed

---

## 🖥️ Requirements

- Windows 10/11
- Python 3.10 or higher
- A Google Gemini API key (paid tier / billing enabled)
- Internet connection

---

## ⚙️ Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/yourname/gemini-rag-app.git
cd gemini-rag-app
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up your environment variables

Copy the example file:

```bash
copy .env.example .env
```

Open `.env` and fill in your values:

```ini
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_FILE_STORE=fileSearchStores/your_store_id_here
GEMINI_MODEL=gemini-2.5-flash
```

> ⚠️ Never commit your `.env` file. It is already in `.gitignore`.

---

### 5. Get a Gemini API Key

1. Go to [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. Click **"Create API key"**
3. Copy the key into your `.env` as `GEMINI_API_KEY`

> ⚠️ The File Search Store requires **billing to be enabled** on your Google Cloud project.  
> Enable it at [console.cloud.google.com/billing](https://console.cloud.google.com/billing)

---

### 6. Create your Gemini File Search Store (ONE TIME ONLY)

```bash
python setup_store.py
```

This will print something like:

```
✅  File Search Store created!
    Name: fileSearchStores/abc123xyz456

📋  Add this to your .env:
    GEMINI_FILE_STORE=fileSearchStores/abc123xyz456
```

Copy the printed store name into your `.env` file as `GEMINI_FILE_STORE`.

> ✅ Each team member needs their own API key, but you can **share one File Search Store** across the team by sharing the store name.

---

### 7. Run the app

```bash
python app.py
```

Or on Windows, double-click:

```
start.bat
```

Then open your browser at:

```
http://127.0.0.1:5000
```

---

## 📁 Project Structure

```
gemini_rag_app/
├── app.py              # Flask backend
├── setup_store.py      # One-time store creation script
├── requirements.txt    # Python dependencies
├── start.bat           # Windows launcher
├── .env.example        # Environment variable template
├── .gitignore          # Git ignore rules
├── rag.db              # SQLite upload log (auto-created, not committed)
├── uploads/            # Temp folder (auto-created, not committed)
├── templates/
│   ├── index.html      # Upload dashboard UI
│   └── chat.html       # Chatbot UI
├── static/
│   └── style.css       # Shared styles
└── README.md           # This file
```

---

## 🚀 Usage

### Upload a file
1. Open `http://127.0.0.1:5000`
2. Drag & drop or click to browse for a file
3. Click **"Upload to Gemini"**
4. Wait 30–60 seconds for Gemini to index the file

### Chat with your knowledge base
1. Click **"Open Chatbot"** or go to `http://127.0.0.1:5000/chat`
2. Type any question related to your uploaded files
3. Gemini will search your knowledge base and answer

### Delete a file
1. On the dashboard, find the file in the table
2. Click the 🗑 **Delete** button

---

## 📄 Supported File Types

| Category | Extensions |
|---|---|
| Documents | `.pdf` `.docx` `.doc` `.txt` `.md` `.rtf` |
| Spreadsheets | `.xlsx` `.xls` `.csv` `.ods` |
| Presentations | `.pptx` `.ppt` `.odp` |
| Web | `.html` `.htm` `.xml` `.json` |
| Code | `.py` `.js` `.ts` `.java` `.c` `.cpp` `.go` `.rs` `.sql` `.sh` and more |

---

## ❓ Troubleshooting

| Error | Fix |
|---|---|
| `API key not valid` | Check `GEMINI_API_KEY` in `.env` is correct |
| `Corpora does not exist` | Run `setup_store.py` first |
| `PERMISSION_DENIED` | Make sure `GEMINI_FILE_STORE` has the `fileSearchStores/` prefix |
| Upload stuck / no progress | Billing may not be enabled on your Google Cloud project |
| `Permission denied` on temp file | Check antivirus isn't blocking the `uploads/` folder |

---

## 🔑 Environment Variables Reference

| Variable | Description | Example |
|---|---|---|
| `GEMINI_API_KEY` | Your Gemini API key from AI Studio | `AIzaSy...` |
| `GEMINI_FILE_STORE` | Your File Search Store resource name | `fileSearchStores/abc123` |
| `GEMINI_MODEL` | Gemini model to use for chat | `gemini-2.5-flash` |

---

## 🛠️ Built With

- [Flask](https://flask.palletsprojects.com/) — Python web framework
- [Google Gemini API](https://ai.google.dev/) — LLM + File Search Store (RAG)
- [SQLite](https://www.sqlite.org/) — Local upload tracking
- Vanilla HTML/CSS/JS — No frontend framework needed
