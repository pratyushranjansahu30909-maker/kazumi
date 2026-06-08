# 🌸 Kazumi AI Companion & Calm Space

Kazumi is a sweet, highly empathetic conversational AI companion designed for desktop interactions, paired with a web-based mindfulness dashboard named **Kazumi Space**. The project blends local conversational AI intelligence, secure credential storage, and cozy ambient exercises to create a soothing digital environment.

---

## 🚀 Core Features

### 1. Empathetic Python AI Core (`kazumi.py`)
- **Conversational Intelligence**: Empathetic, supportive, and context-aware responses utilizing OpenAI API backend integrations.
- **Dynamic Mood & Valence Tracking**: Computes a rolling emotional valence score. Her dialogue styling, interaction preferences, and vocabulary change dynamically depending on the user's input sentiments and past chats.
- **Pure-Python Semantic Memory (`ChromaMemory`)**: Local persistent JSON memory system tracking conversation history, affection levels, cozy points, and user preferences.
- **Cozy Games & Astrological Logs**: Supports custom zodiac horoscope readings, text adventures, and warm mini-games.

### 2. Kazumi Space Mindfulness Dashboard (`portfolio/public/`)
A warm, human-designed lavender and pastel themed frontend workspace:
- **Overview Area**: Displays live companion metrics—Affection Level progress bars, Cozy Points badges, dominant emotional vibe gauges, and an interactive Valence Slider.
- **Calm Space Garden**:
  - **Procedural Wind Chimes**: Uses the Web Audio API to generate randomized pentatonic wind chime melodies in real-time, complete with wind speed/frequency settings.
  - **Zen Breathing Guide**: A responsive, pulsing breathing ring displaying visual inhale, hold, and exhale cues to help users center their thoughts.
- **Kazumi's Journal (Diary Space)**: Displays her personal journal timeline reflections dynamically written by the companion core.
- **Dialogue Console (Chat Space)**: Client interface to view active chats, review history, and chat with your companion.

### 3. Double-Backed Secure Servers (`portfolio/`)
- Runs identically on both **Node.js (Express)** via `server.js` or **Python 3** via `server.py`.
- **Zero-Plaintext Vault**: Features a secure settings panel that encrypts and stores GitHub/LinkedIn developer credentials locally using AES-256-CBC and SHA-256 keystream ciphers, proxying API calls dynamically to avoid key leaks.

---

## 🛠️ Technology Stack
- **Frontend**: Vanilla HTML5, CSS3 (lavender design tokens, responsive CSS grids, CSS custom variables), Vanilla JavaScript (Web Audio API, localStorage caches).
- **Backend Servers**: Node.js Express, Python `ThreadingHTTPServer`.
- **AI Core**: Python 3, `openai` library, custom persistent JSON structures.

---

## 🏁 How to Run Locally

### 1. Python Interactive Console Chat
To chat with Kazumi directly in your system command line:
```bash
# Install required dependencies
pip install -r requirements.txt

# Run the interactive bot
python kazumi.py
```

### 2. Launching the Web Dashboard
You can run the web server using either Python or Node.js.

#### Option A: Running with Python
```bash
# Start the HTTP server
python portfolio/server.py
```
Open `http://localhost:3000/` in your browser.

#### Option B: Running with Node.js
```bash
cd portfolio
npm install
npm start
```
Open `http://localhost:3000/` in your browser.
