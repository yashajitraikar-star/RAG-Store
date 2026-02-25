This is because the chatbot currently sends **only the current message** to Gemini — it has no memory of previous messages. The fix is to send the full **conversation history** with every request.

## Fix 1 — Update `/api/chat` in `app.py`

Replace the `api_chat` function:

```python
@app.route("/api/chat", methods=["POST"])
def api_chat():
    data    = request.get_json(force=True)
    message = data.get("message", "").strip()
    history = data.get("history", [])   # list of previous messages

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

        response = client.models.generate_content(
            model=MODEL,
            contents=contents,
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
```

***

## Fix 2 — Update `templates/chat.html`

Replace the entire `<script>` block:

```html
<script>
  const chatLog  = document.getElementById('chat-log');
  const msgInput = document.getElementById('msg-input');
  const sendBtn  = document.getElementById('send-btn');

  // ── Conversation history stored in memory ──────────────────────────────
  let history = [];

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
      const res = await fetch('/api/chat', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({
          message: msg,
          history: history        // ← send full history every time
        })
      });

      const data = await res.json();
      chatLog.removeChild(thinking);

      if (!res.ok) throw new Error(data.error || 'Chat failed');

      // ── Save to history ──────────────────────────────────────────────
      history.push({ role: "user",  text: msg });
      history.push({ role: "model", text: data.answer });

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
```

***

## Also add a "Clear Chat" button in `chat.html`

Add this button next to the chatbot title in the `chat-info-bar`:

```html
<div class="chat-info-bar" style="display:flex; justify-content:space-between; align-items:center;">
  <span>🔍 Answers are grounded in your uploaded files</span>
  <button class="btn btn-ghost" style="font-size:0.8rem; padding:4px 12px;"
    onclick="history=[]; chatLog.innerHTML=''; addMsg('🧹 Chat cleared. Start a new conversation!', 'bot-msg')">
    🧹 Clear Chat
  </button>
</div>
```

***

## What changed

| Before | After |
|---|---|
| Sent only current message | Sends full conversation history |
| No memory of previous turns | Remembers names, context, follow-ups |
| History lost on page refresh | History kept for current session (clears on refresh — by design) |

Now if you say **"my name is Yash"** and later ask **"what is my name"**, it will correctly answer **Yash**. Restart with `python app.py` to apply.