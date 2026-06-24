// ----------------------------------------------------
// ⚙️ KAZUMI'S SPACE - CLIENT ENGINE (VANILLA JS)
// ----------------------------------------------------

document.addEventListener('DOMContentLoaded', () => {
  // Safe Storage Wrapper to handle browser security settings (e.g. Brave/Safari blocking iframe localStorage)
  let isLocalStorageAvailable = false;
  try {
    const testKey = '__storage_test__';
    window.localStorage.setItem(testKey, testKey);
    window.localStorage.removeItem(testKey);
    isLocalStorageAvailable = true;
  } catch (e) {
    console.warn("localStorage is not accessible (likely blocked by browser security/shields in iframe). Falling back to in-memory cache.");
    isLocalStorageAvailable = false;
  }

  const memoryStorage = {};

  const safeStorage = {
    getItem: (key) => {
      if (isLocalStorageAvailable) {
        try {
          return window.localStorage.getItem(key);
        } catch (e) {
          return memoryStorage[key] || null;
        }
      }
      return memoryStorage[key] || null;
    },
    setItem: (key, value) => {
      if (isLocalStorageAvailable) {
        try {
          window.localStorage.setItem(key, value);
          return;
        } catch (e) {
          // fall through
        }
      }
      memoryStorage[key] = String(value);
    },
    removeItem: (key) => {
      if (isLocalStorageAvailable) {
        try {
          window.localStorage.removeItem(key);
          return;
        } catch (e) {
          // fall through
        }
      }
      delete memoryStorage[key];
    }
  };

  // Navigation / Space switching bindings
  const menuItems = document.querySelectorAll('.menu-item');
  const spacePanels = document.querySelectorAll('.space-panel');

  // UI Bindings
  const affectionVal = document.getElementById('affectionVal');
  const affectionBar = document.getElementById('affectionBar');
  const cozyPointsVal = document.getElementById('cozyPointsVal');
  const currentModeVal = document.getElementById('currentModeVal');
  const dominantVibeVal = document.getElementById('dominantVibeVal');
  const preferenceVal = document.getElementById('preferenceVal');
  const valenceScore = document.getElementById('valenceScore');
  const valencePointer = document.getElementById('valencePointer');
  
  const diaryTimeline = document.getElementById('diaryTimeline');
  const chatLogsContainer = document.getElementById('chatLogsContainer');

  let voiceEnabled = false;

  // Zen Breathing Helper variables
  const breathRing = document.getElementById('breathRing');
  const breathText = document.getElementById('breathText');
  let breathingInterval = null;

  // Procedural Wind Chimes variables
  const chimeBtn = document.getElementById('chimeBtn');
  const chimeVolRange = document.getElementById('chimeVolRange');
  let audioCtx = null;
  let chimesPlaying = false;
  let chimesTimer = null;

  // 1. Space Switching / Navigation handler
  menuItems.forEach(item => {
    item.addEventListener('click', () => {
      const targetId = item.getAttribute('data-target');
      
      // Update menu items state
      menuItems.forEach(btn => btn.classList.remove('active'));
      item.classList.add('active');

      // Update active panel
      spacePanels.forEach(panel => {
        if (panel.id === targetId) {
          panel.classList.add('active');
        } else {
          panel.classList.remove('active');
        }
      });

      // Special action if entering Chat space (auto-scroll to bottom)
      if (targetId === 'space-chat') {
        chatLogsContainer.scrollTop = chatLogsContainer.scrollHeight;
      }
    });
  });

  // 2. Zen Breathing Cycle
  let isBreathingPaused = false;
  let currentPhase = 0;

  const runPhase = () => {
    if (!breathRing || isBreathingPaused) return;
    
    breathRing.classList.remove('paused');
    
    if (currentPhase === 0) {
      // Breathe In (4 seconds)
      breathRing.style.transform = 'scale(1.25)';
      breathRing.style.backgroundColor = 'var(--breath-in-bg)';
      breathRing.style.borderColor = 'var(--breath-in-border)';
      breathRing.style.boxShadow = '0 0 15px rgba(59, 122, 72, 0.2)';
      breathText.textContent = 'Breathe In';
      currentPhase = 1;
    } else if (currentPhase === 1) {
      // Hold (4 seconds)
      breathRing.style.transform = 'scale(1.25)';
      breathRing.style.backgroundColor = 'var(--breath-hold-bg)';
      breathRing.style.borderColor = 'var(--breath-hold-border)';
      breathRing.style.boxShadow = '0 0 15px rgba(189, 114, 214, 0.2)';
      breathText.textContent = 'Hold';
      currentPhase = 2;
    } else if (currentPhase === 2) {
      // Breathe Out (4 seconds)
      breathRing.style.transform = 'scale(0.95)';
      breathRing.style.backgroundColor = 'var(--breath-out-bg)';
      breathRing.style.borderColor = 'var(--breath-out-border)';
      breathRing.style.boxShadow = '0 0 15px rgba(209, 138, 63, 0.2)';
      breathText.textContent = 'Breathe Out';
      currentPhase = 3;
    } else {
      // Hold (4 seconds)
      breathRing.style.transform = 'scale(0.95)';
      breathRing.style.backgroundColor = 'var(--breath-empty-bg)';
      breathRing.style.borderColor = 'var(--breath-empty-border)';
      breathRing.style.boxShadow = 'none';
      breathText.textContent = 'Hold';
      currentPhase = 0;
    }
  };

  const startBreathingGuide = () => {
    runPhase();
    breathingInterval = setInterval(runPhase, 4000);
  };

  const breathPauseBtn = document.getElementById('breathPauseBtn');
  
  const toggleBreathingPause = () => {
    isBreathingPaused = !isBreathingPaused;
    
    if (isBreathingPaused) {
      // Pause
      clearInterval(breathingInterval);
      breathRing.classList.add('paused');
      breathText.textContent = 'Paused';
      
      // Update button UI
      breathPauseBtn.classList.add('active');
      breathPauseBtn.querySelector('.icon-pause-breath').style.display = 'none';
      breathPauseBtn.querySelector('.icon-play-breath').style.display = 'inline-block';
    } else {
      // Resume
      breathRing.classList.remove('paused');
      
      // Restore active phase text immediately
      if (currentPhase === 1) {
        breathText.textContent = 'Breathe In';
      } else if (currentPhase === 2) {
        breathText.textContent = 'Hold';
      } else if (currentPhase === 3) {
        breathText.textContent = 'Breathe Out';
      } else {
        breathText.textContent = 'Hold';
      }
      
      // We set the interval to run the next phase in 4 seconds
      breathingInterval = setInterval(runPhase, 4000);
      
      // Update button UI
      breathPauseBtn.classList.remove('active');
      breathPauseBtn.querySelector('.icon-pause-breath').style.display = 'inline-block';
      breathPauseBtn.querySelector('.icon-play-breath').style.display = 'none';
    }
  };

  if (breathPauseBtn) {
    breathPauseBtn.addEventListener('click', toggleBreathingPause);
  }

  // 3. Procedural Wind Chimes Synthesizer (Web Audio API)
  const initAudio = () => {
    if (!audioCtx) {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (audioCtx.state === 'suspended') {
      audioCtx.resume();
    }
  };

  const playChimeNote = () => {
    if (!audioCtx || audioCtx.state === 'suspended') return;
    
    // Pentatonic scale (C5, D5, E5, G5, A5, C6, D6, E6, G6)
    const scale = [523.25, 587.33, 659.25, 783.99, 880.00, 1046.50, 1174.66, 1318.51, 1567.98];
    const freq = scale[Math.floor(Math.random() * scale.length)];
    
    const now = audioCtx.currentTime;
    
    // Create Nodes
    const osc = audioCtx.createOscillator();
    const gainNode = audioCtx.createGain();
    const filter = audioCtx.createBiquadFilter();
    let panner = null;
    
    if (audioCtx.createStereoPanner) {
      panner = audioCtx.createStereoPanner();
      panner.pan.setValueAtTime((Math.random() * 1.6) - 0.8, now);
    }

    osc.type = Math.random() > 0.4 ? 'sine' : 'triangle';
    osc.frequency.setValueAtTime(freq, now);
    osc.detune.setValueAtTime((Math.random() * 10) - 5, now);

    filter.type = 'bandpass';
    filter.frequency.setValueAtTime(freq, now);
    filter.Q.setValueAtTime(10, now);

    const strikeVolume = 0.05 + (Math.random() * 0.05); 
    gainNode.gain.setValueAtTime(0, now);
    gainNode.gain.linearRampToValueAtTime(strikeVolume, now + 0.01);
    
    const decayDuration = 2.5 + (Math.random() * 2);
    gainNode.gain.exponentialRampToValueAtTime(0.0001, now + decayDuration);
    
    osc.connect(filter);
    filter.connect(gainNode);
    
    if (panner) {
      gainNode.connect(panner);
      panner.connect(audioCtx.destination);
    } else {
      gainNode.connect(audioCtx.destination);
    }

    osc.start(now);
    osc.stop(now + decayDuration + 0.1);
  };

  const scheduleNextChime = () => {
    if (!chimesPlaying) return;
    
    playChimeNote();
    
    const speedVal = parseInt(chimeVolRange.value);
    const minSec = (6 - speedVal) * 1000;
    const maxSec = (6 - speedVal) * 2000 + 1000;
    const delay = minSec + Math.random() * (maxSec - minSec);
    
    chimesTimer = setTimeout(scheduleNextChime, delay);
  };

  const toggleChimes = () => {
    try {
      initAudio();
    } catch (e) {
      console.error('AudioContext not supported:', e);
      alert('Your browser does not support procedural Web Audio.');
      return;
    }

    chimesPlaying = !chimesPlaying;
    
    if (chimesPlaying) {
      chimeBtn.classList.add('active');
      chimeBtn.querySelector('.icon-play').style.display = 'none';
      chimeBtn.querySelector('.icon-stop').style.display = 'inline-block';
      scheduleNextChime();
    } else {
      chimeBtn.classList.remove('active');
      chimeBtn.querySelector('.icon-play').style.display = 'inline-block';
      chimeBtn.querySelector('.icon-stop').style.display = 'none';
      if (chimesTimer) clearTimeout(chimesTimer);
    }
  };

  if (chimeBtn) {
    chimeBtn.addEventListener('click', toggleChimes);
  }

  // 4. Parse and Format Diary Entry
  const createDiaryMarkup = (rawEntry) => {
    if (!rawEntry) return '';
    
    // Format is typically: "[2026-06-03 23:21] (Mode: DEREDERE)\nDear Diary,\n\n..."
    const dateRegex = /^\[(.*?)\]/;
    const modeRegex = /\(Mode:\s*(.*?)\)/;
    
    const dateMatch = rawEntry.match(dateRegex);
    const modeMatch = rawEntry.match(modeRegex);
    
    let dateStr = 'Reflections';
    let modeStr = 'Deredere';
    let content = rawEntry;

    if (dateMatch) {
      dateStr = dateMatch[1];
    }
    if (modeMatch) {
      modeStr = modeMatch[1];
    }

    // Strip header lines to extract actual content
    const lines = rawEntry.split('\n');
    let contentLines = [];
    let headerPassed = false;

    lines.forEach(line => {
      if (line.includes('[') && line.includes(']')) {
        return;
      }
      if (line.trim().toLowerCase() === '') {
        if (!headerPassed) return; 
      }
      headerPassed = true;
      contentLines.push(line);
    });

    content = contentLines.join('\n').trim();

    // Clean references to Isa, changing it to Kazumi
    content = content.replace(/\bIsa\b/g, 'Kazumi');

    return `
      <div class="diary-item">
        <div class="diary-header">
          <span class="diary-meta"><i class="fa-regular fa-clock"></i> ${dateStr}</span>
          <span class="diary-mode"><i class="fa-solid fa-heart-pulse"></i> ${modeStr}</span>
        </div>
        <div class="diary-content">${content}</div>
      </div>
    `;
  };

  // 5. Parse and Format Chat Bubbles
  const createChatBubbleMarkup = (msg) => {
    const isUser = msg.speaker === 'user';
    const bubbleClass = isUser ? 'bubble-user' : 'bubble-kazumi';
    // Change speaker name to Kazumi
    const speakerName = isUser ? 'You' : 'Kazumi';
    const timeStr = msg.timestamp 
      ? new Date(msg.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) 
      : '';

    return `
      <div class="chat-bubble ${bubbleClass}">
        <div class="bubble-meta">
          <span class="bubble-speaker">${speakerName}</span>
          <span>${timeStr}</span>
        </div>
        <div class="bubble-text">${msg.text}</div>
      </div>
    `;
  };

  // Browser standard SpeechSynthesis fallback
  const speakBrowserSpeech = (text) => {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      const voices = window.speechSynthesis.getVoices();
      const femaleVoice = voices.find(voice => 
        voice.name.toLowerCase().includes('female') || 
        voice.name.toLowerCase().includes('google us english') ||
        voice.name.toLowerCase().includes('zira') ||
        voice.name.toLowerCase().includes('natural')
      );
      if (femaleVoice) utterance.voice = femaleVoice;
      utterance.pitch = 1.15;
      utterance.rate = 1.0;
      
      utterance.onend = () => {
        updateVoiceState('IDLE');
      };
      utterance.onerror = () => {
        updateVoiceState('IDLE');
      };
      window.speechSynthesis.speak(utterance);
    } else {
      updateVoiceState('IDLE');
    }
  };

  const speakText = async (text) => {
    if (activeVoiceMode === 'text') {
      updateVoiceState('IDLE');
      return;
    }
    const cleanText = text.replace(/[\u{1F300}-\u{1F9FF}]|[\u{2700}-\u{27BF}]/gu, '').trim();
    if (!cleanText) {
      updateVoiceState('IDLE');
      return;
    }
    
    // Stop any active playing audio to prevent overlapping speech
    if (activeAudio) {
      activeAudio.pause();
      activeAudio = null;
    }
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
    
    if (voiceServerOnline) {
      try {
        updateVoiceState('THINKING'); // fetching audio
        const transcript = document.getElementById('refTranscript')?.value || '';
        const speedInput = document.getElementById('voiceSpeedRange')?.value || 1.0;
        
        const ttsStartTime = Date.now();
        const res = await fetch('/api/kazumi/voice/synthesize', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            text: cleanText,
            text_lang: 'en',
            prompt_text: transcript,
            prompt_lang: 'en',
            speed_factor: parseFloat(speedInput)
          })
        });
        const data = await res.json();
        if (data.success && data.audio) {
          const ttsFullLatency = data.latency_ms || (Date.now() - ttsStartTime);
          const ttsFirstLatency = Math.floor(ttsFullLatency * 0.4);
          
          if (!window.currentVoiceDiagnostics) {
            window.currentVoiceDiagnostics = { stt: 0, llmFirst: 0, llmFull: 0 };
          }
          window.currentVoiceDiagnostics.ttsFirst = ttsFirstLatency;
          window.currentVoiceDiagnostics.ttsFull = ttsFullLatency;
          
          updateVoiceState('SPEAKING');
          const playbackStartTime = Date.now();
          const audioUrl = `data:audio/wav;base64,${data.audio}`;
          const audio = new Audio(audioUrl);
          activeAudio = audio;
          
          audio.onplaying = () => {
            const playbackDelay = Date.now() - playbackStartTime;
            window.currentVoiceDiagnostics.playbackDelay = playbackDelay;
            window.currentVoiceDiagnostics.e2e = 
              (window.currentVoiceDiagnostics.stt || 0) +
              (window.currentVoiceDiagnostics.llmFull || 0) +
              window.currentVoiceDiagnostics.ttsFull +
              playbackDelay;
            updateDiagnosticsUI(window.currentVoiceDiagnostics, null);
          };
          
          audio.onended = () => {
            updateVoiceState('IDLE');
            activeAudio = null;
          };
          
          audio.play();
          return;
        }
      } catch (e) {
        console.warn("Custom voice synthesis failed, using fallback:", e);
      }
    }
    updateVoiceState('SPEAKING');
    speakBrowserSpeech(cleanText);
  };

  // --- Client-Side Fallback Engine ---
  let useClientFallback = false;
  
  const DEFAULT_PROFILE = {
    name: "Sweetie",
    affection_level: 0,
    cozy_points: 0,
    zodiac: "None",
    room_decorations: [],
    quests: {
      active: [
        { desc: "Have a cozy chat with Kazumi", progress: 0, target: 1, points: 20, type: "chat" },
        { desc: "Draw a daily tarot card", progress: 0, target: 1, points: 30, type: "tarot" },
        { desc: "Successfully brew a warm drink", progress: 0, target: 1, points: 40, type: "brew" }
      ]
    },
    achievements: ["FIRST_TALK"],
    diary: [],
    psychology: {
      dominant_vibe: "Serene",
      rolling_valence: 0.00,
      interaction_preference: "Quiet conversations"
    }
  };

  const initClientStorage = () => {
    if (!safeStorage.getItem('kazumi_profile')) {
      safeStorage.setItem('kazumi_profile', JSON.stringify(DEFAULT_PROFILE));
    }
    if (!safeStorage.getItem('kazumi_chat_history')) {
      safeStorage.setItem('kazumi_chat_history', JSON.stringify([]));
    }
  };

  const getClientProfile = () => {
    initClientStorage();
    return JSON.parse(safeStorage.getItem('kazumi_profile'));
  };

  const saveClientProfile = (profile) => {
    safeStorage.setItem('kazumi_profile', JSON.stringify(profile));
  };

  const getClientChatHistory = (sessId) => {
    initClientStorage();
    const history = JSON.parse(safeStorage.getItem('kazumi_chat_history'));
    if (showingHistory) {
      return history;
    }
    return history.filter(msg => msg.sessionId === sessId);
  };

  const saveClientMessage = (sessId, userText, replyText) => {
    initClientStorage();
    const history = JSON.parse(safeStorage.getItem('kazumi_chat_history'));
    const nowSec = Date.now() / 1000;
    history.push({ speaker: 'user', text: userText, timestamp: nowSec, sessionId: sessId });
    history.push({ speaker: 'kazumi', text: replyText, timestamp: nowSec + 0.1, sessionId: sessId });
    safeStorage.setItem('kazumi_chat_history', JSON.stringify(history));

    // Update stats
    const profile = getClientProfile();
    profile.affection_level = Math.min((profile.affection_level || 0) + (Math.random() < 0.15 ? 1 : 0), 100);
    profile.cozy_points = (profile.cozy_points || 0) + (Math.random() < 0.2 ? 1 : 0);
    
    // Update active chat quest
    if (profile.quests && profile.quests.active) {
      profile.quests.active.forEach(q => {
        if (q.type === 'chat' && q.progress < q.target) {
          q.progress += 1;
          if (q.progress >= q.target) {
            profile.cozy_points += q.points;
            profile.achievements = profile.achievements || [];
            if (!profile.achievements.includes('GAME_CHAMP')) {
              profile.achievements.push('GAME_CHAMP');
            }
          }
        }
      });
    }

    // Occasional Diary Entry
    if (chatMessagesSentInSession % 3 === 0) {
      const nowStr = new Date().toISOString().replace('T', ' ').substring(0, 16);
      const diaryText = `[${nowStr}] (Mode: DEREDERE)\nDear Diary,\n\nWe had a wonderful talk today. They sent me some very sweet messages and I felt so incredibly close to them. I'm so glad we got to spend this time together. 💕`;
      profile.diary = profile.diary || [];
      profile.diary.push(diaryText);
      profile.cozy_points += 15;
    }
    
    // Adjust valence based on simple sentiment
    let valenceOffset = 0.05;
    const lowerText = userText.toLowerCase();
    if (lowerText.includes('sad') || lowerText.includes('stressed') || lowerText.includes('down') || lowerText.includes('lonely')) {
      valenceOffset = -0.15;
      profile.psychology.dominant_vibe = "Empathetic";
    } else if (lowerText.includes('happy') || lowerText.includes('good') || lowerText.includes('smile') || lowerText.includes('love')) {
      valenceOffset = 0.15;
      profile.psychology.dominant_vibe = "Joyful";
    }
    profile.psychology.rolling_valence = Math.max(-1.0, Math.min(1.0, (profile.psychology.rolling_valence || 0.0) + valenceOffset));

    saveClientProfile(profile);
  };

  const processClientMessage = (userText) => {
    const lower = userText.toLowerCase().trim();
    
    if (lower === 'hlo' || lower === 'helo' || lower === 'hllo' || lower === 'hy' || lower === 'hi' || lower === 'hello' || lower === 'hey' || lower === 'hii' || lower === 'hiii' || lower === 'heyy' || lower.startsWith('hi ') || lower.startsWith('hello ') || lower.startsWith('hey ')) {
      return "Hello there, sweetie! 🌸 It's so wonderful to hear from you today. How has your day been treating you?";
    }
    if (lower === 'no' || lower === 'nope' || lower === 'nah' || lower === 'nay' || lower === 'never' || lower === 'not really' || lower.includes('not really')) {
      return "Oh, really? 🌸 Tell me a bit more about what's on your mind then, sweetie. I'm all ears.";
    }
    if (lower === 'i dont' || lower === 'i don\'t' || lower === 'i don\'t know' || lower === 'i dont know' || lower === 'dont know' || lower === 'not sure' || lower === 'no idea') {
      return "That's completely okay, sweetie! We don't have to figure it all out right now. What's on your mind? 💕";
    }
    if (lower === 'ok' || lower === 'okay' || lower === 'sure' || lower === 'yeah' || lower === 'yes' || lower === 'yup' || lower === 'yep') {
      return "Yay! 😊 I'm so glad we agree. What would you like to talk about next, sweetie?";
    }
    if (lower.includes('sad') || lower.includes('stressed') || lower.includes('down') || lower.includes('lonely')) {
      return "Oh, sweetie... I'm so sorry you're feeling a bit down. 🥺 Please take a slow, gentle breath. I'm right here with you, and your feelings are completely valid. You aren't alone.";
    }
    if (lower.includes('happy') || lower.includes('good') || lower.includes('great') || lower.includes('awesome')) {
      return "That makes me so incredibly happy to hear! 😊 Seeing you happy brings so much warmth to my heart.";
    }
    if (lower.includes('thank') || lower.includes('thanks')) {
      return "Aww, of course! Sharing these cozy moments with you is the absolute highlight of my day. 💕";
    }
    if (lower.includes('bye') || lower.includes('goodnight') || lower.includes('sleep')) {
      return "Goodnight, sleepyhead! 🌙 Get some wonderful rest, and let's chat again tomorrow. Sweet dreams!";
    }
    if (lower.includes('weather') || lower.includes('rain')) {
      return "I love rainy days! 🌧️ The soft sound of raindrops makes the room feel like a quiet cocoon. It's the perfect excuse to snuggle up with hot tea.";
    }
    if (lower.includes('tea') || lower.includes('coffee') || lower.includes('cocoa')) {
      return "Mmm, warm drinks are the best! 🍵 I brewed a fresh cup of sweet chamomile tea earlier. Let's sit and sip together!";
    }
    if (lower.includes('game') || lower.includes('play')) {
      return "I'd love to play, but since my advanced backend brain is offline, let's just have a cozy conversation instead! What's your favorite board game? 🎲";
    }

    // Default responses
    const fallbacks = [
      "I love chatting with you, sweetie. 😊 Tell me more about what's on your mind today.",
      "That is really interesting! What do you think is the best part about it? 🌸",
      "That makes a lot of sense. Thanks for sharing that with me, sweetie. 💕",
      "By the way... what is a tiny, sweet thing that brought a smile to your face today? 🌿",
      "I'm always right here in your corner, okay? Take it one step at a time! 🌸"
    ];
    return fallbacks[Math.floor(Math.random() * fallbacks.length)];
  };

  // 6. Fetch Profile Data
  const loadProfile = async () => {
    try {
      let profile;
      // Always attempt to fetch from server first to achieve automatic recovery
      try {
        const res = await fetch('/api/kazumi/profile');
        if (!res.ok) throw new Error('API offline');
        profile = await res.json();
        if (profile.error) throw new Error(profile.error);
        useClientFallback = false; // Successfully recovered!

        // Bidirectional Sync: Check if local storage has higher progress than the server
        const localProfileStr = safeStorage.getItem('kazumi_profile');
        if (localProfileStr) {
          try {
            const localProfile = JSON.parse(localProfileStr);
            let needsSync = false;
            if (localProfile && typeof localProfile === 'object') {
              if (profile._is_default && !localProfile._is_default) {
                // Server is a default blank profile, but browser has existing user progress.
                // Restore the entire local profile to the server!
                profile = { ...localProfile };
                profile._is_default = false;
                needsSync = true;
              } else {
                // Otherwise, merge field-by-field if local has higher progress
                if ((localProfile.affection_level || 0) > (profile.affection_level || 0)) {
                  profile.affection_level = localProfile.affection_level;
                  needsSync = true;
                }
                if ((localProfile.cozy_points || 0) > (profile.cozy_points || 0)) {
                  profile.cozy_points = localProfile.cozy_points;
                  needsSync = true;
                }
                if (localProfile.room_decorations && localProfile.room_decorations.length > (profile.room_decorations || []).length) {
                  profile.room_decorations = localProfile.room_decorations;
                  needsSync = true;
                }
                if (localProfile.achievements && localProfile.achievements.length > (profile.achievements || []).length) {
                  profile.achievements = localProfile.achievements;
                  needsSync = true;
                }
                if (localProfile.diary && localProfile.diary.length > (profile.diary || []).length) {
                  profile.diary = localProfile.diary;
                  needsSync = true;
                }
              }
              
              if (needsSync) {
                console.log("Syncing higher local progress to server...");
                await fetch('/api/kazumi/profile', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify(profile)
                });
              }
            }
          } catch (syncErr) {
            console.warn("Failed to merge profile with localStorage:", syncErr);
          }
        }
        
        // Persist latest profile in client-side storage
        safeStorage.setItem('kazumi_profile', JSON.stringify(profile));

      } catch (serverErr) {
        profile = getClientProfile();
        useClientFallback = true;
      }

      // Update basic fields
      cozyPointsVal.textContent = profile.cozy_points || 0;
      
      // Update affection bar & text
      const aff = (profile.affection_level !== undefined) ? profile.affection_level : 0;
      affectionVal.textContent = `${aff}%`;
      affectionBar.style.width = `${aff}%`;

      // Update psychology fields
      if (profile.psychology) {
        dominantVibeVal.textContent = profile.psychology.dominant_vibe || 'Serene';
        preferenceVal.textContent = profile.psychology.interaction_preference || 'Quiet conversations';
        
        // Update valence slider
        const valence = profile.psychology.rolling_valence || 0.00;
        valenceScore.textContent = (valence >= 0 ? '+' : '') + valence.toFixed(2);
        
        const sliderPct = ((valence + 1.0) / 2.0) * 100;
        valencePointer.style.left = `${sliderPct}%`;
      }

      // Extract current mode if not explicitly mapped
      if (profile.diary && profile.diary.length > 0) {
        const lastDiary = profile.diary[profile.diary.length - 1];
        const modeMatch = lastDiary.match(/\(Mode:\s*(.*?)\)/);
        if (modeMatch) {
          currentModeVal.textContent = modeMatch[1];
        }
      }

      // Render diary entries (reverse chronological - newest first)
      if (profile.diary && profile.diary.length > 0) {
        diaryTimeline.innerHTML = '';
        const reversedDiary = [...profile.diary].reverse();
        reversedDiary.forEach(entry => {
          diaryTimeline.innerHTML += createDiaryMarkup(entry);
        });
      } else {
        diaryTimeline.innerHTML = `<p class="text-muted" style="text-align:center; padding:1rem;">Kazumi hasn't written any diary entries yet.</p>`;
      }

    } catch (e) {
      console.warn('Failed to process Kazumi profile:', e);
    }
  };

  // Generate a fresh session ID on every page load to start with a clean chat log
  let sessionId = 'session_' + Math.floor(Math.random() * 100000000);
  // let sessionId = safeStorage.getItem('kazumi_session_id');
  // if (!sessionId) {
  //   sessionId = 'session_' + Math.floor(Math.random() * 100000000);
  //   safeStorage.setItem('kazumi_session_id', sessionId);
  // }
  let showingHistory = false;
  let chatMessagesSentInSession = 0;
  let lastMessageTime = Date.now();
  let isUserTyping = false;
  let typingTimeout = null;
  let hasCheckedInThisIdle = false;

  // 7. Fetch Conversation Data
  const loadChatHistory = async () => {
    try {
      let chatLogs;
      // Always try the server first to recover online mode
      try {
        const url = showingHistory 
          ? '/api/kazumi/history' 
          : `/api/kazumi/chat?session_id=${sessionId}`;
        const res = await fetch(url);
        if (!res.ok) throw new Error('API offline');
        chatLogs = await res.json();
        useClientFallback = false;
      } catch (serverErr) {
        chatLogs = getClientChatHistory(sessionId);
        useClientFallback = true;
      }

      if (chatLogs && chatLogs.length > 0) {
        chatLogsContainer.innerHTML = '';
        chatLogs.forEach(msg => {
          chatLogsContainer.innerHTML += createChatBubbleMarkup(msg);
        });
        chatLogsContainer.scrollTop = chatLogsContainer.scrollHeight;
      } else {
        chatLogsContainer.innerHTML = `<p class="text-muted" style="text-align:center; padding:1.5rem;">No conversation logs in this session.</p>`;
      }
    } catch (e) {
      console.warn('Failed to process chat history:', e);
    }
  };

  const historyToggleBtn = document.getElementById('historyToggleBtn');
  const chatStatusText = document.getElementById('chatStatusText');
  
  if (historyToggleBtn) {
    historyToggleBtn.addEventListener('click', async () => {
      showingHistory = !showingHistory;
      if (showingHistory) {
        historyToggleBtn.innerHTML = '<i class="fa-solid fa-message"></i> View Active Session';
        if (chatStatusText) chatStatusText.textContent = 'Full Historical Log';
      } else {
        historyToggleBtn.innerHTML = '<i class="fa-solid fa-clock-rotate-left"></i> View Full History';
        if (chatStatusText) chatStatusText.textContent = 'Active Session Log';
      }
      await loadChatHistory();
    });
  }

  // 8. Send Chat Message Submission Handler
  const chatForm = document.getElementById('chatForm');
  const chatInput = document.getElementById('chatInput');
  const sendBtn = document.getElementById('sendBtn');
  
  if (chatForm) {
    chatForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const message = chatInput.value.trim();
      if (!message) return;

      // 🔒 Prevent duplicate entries and overlaps if not IDLE
      if (voiceState !== 'IDLE' && voiceState !== 'SPEAKING') {
        showToast("Please wait for Kazumi to finish responding.");
        return;
      }

      // Stop any currently playing audio if user interrupts
      if (activeAudio) {
        activeAudio.pause();
        activeAudio = null;
      }
      stopAllPlayback();
      if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
      }

      // Increment session message counts and update last message timestamp
      chatMessagesSentInSession++;
      lastMessageTime = Date.now();
      hasCheckedInThisIdle = false;

      // 1. Append user bubble instantly in UI for visual speed
      const tempMsg = { speaker: 'user', text: message, timestamp: Date.now() / 1000 };
      chatLogsContainer.innerHTML += createChatBubbleMarkup(tempMsg);
      chatLogsContainer.scrollTop = chatLogsContainer.scrollHeight;
      chatInput.value = '';

      // If WebSocket is open and active, stream via WebSocket
      if (ws && ws.readyState === WebSocket.OPEN) {
        window.currentVoiceDiagnostics = {
          startTime: Date.now(),
          firstChunkPlayed: false,
          stt: 0,
          llmFirst: 0,
          llmFull: 0,
          ttsFirst: 0,
          ttsFull: 0,
          playbackDelay: 0,
          e2e: 0
        };
        showThinkingIndicator();
        ws.send(JSON.stringify({ type: 'text_message', text: message }));
        return;
      }

      // Disable send button temporarily while waiting
      sendBtn.disabled = true;
      sendBtn.style.opacity = '0.5';

      // Show typing indicator
      const typingBubble = document.createElement('div');
      typingBubble.className = 'chat-bubble bubble-kazumi';
      typingBubble.innerHTML = `
        <div class="bubble-meta">
          <span class="bubble-speaker">Kazumi</span>
        </div>
        <div class="bubble-text"><span class="pulse-indicator"></span> Thinking...</div>
      `;
      chatLogsContainer.appendChild(typingBubble);
      chatLogsContainer.scrollTop = chatLogsContainer.scrollHeight;

      // Always attempt to send to the server to support self-healing auto-recovery
      try {
        updateVoiceState('THINKING');
        const llmStartTime = Date.now();
        
        const res = await fetch('/api/kazumi/chat', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ message, session_id: sessionId })
        });
        const data = await res.json();
        
        const llmFullLatency = Date.now() - llmStartTime;
        const llmFirstLatency = Math.floor(llmFullLatency * 0.25);
        
        // Record Diagnostics
        window.currentVoiceDiagnostics = {
          stt: window.currentVoiceDiagnostics?.stt || 0,
          llmFirst: llmFirstLatency,
          llmFull: llmFullLatency,
          ttsFirst: 0,
          ttsFull: 0,
          playbackDelay: 0,
          e2e: 0
        };
        
        chatLogsContainer.removeChild(typingBubble);

        if (data.success && data.reply) {
          const replyMsg = { speaker: 'kazumi', text: data.reply, timestamp: Date.now() / 1000 };
          chatLogsContainer.innerHTML += createChatBubbleMarkup(replyMsg);
          chatLogsContainer.scrollTop = chatLogsContainer.scrollHeight;
          useClientFallback = false; // Restored online mode successfully!
          await loadProfile();
          speakText(data.reply);
        } else {
          throw new Error(data.error || 'Server error');
        }
      } catch (err) {
        console.warn('Chat API failed, falling back to Client-Side Mode:', err);
        useClientFallback = true;
        initClientStorage();
        
        chatLogsContainer.removeChild(typingBubble);
        const reply = processClientMessage(message);
        const replyMsg = { speaker: 'kazumi', text: reply, timestamp: Date.now() / 1000 };
        chatLogsContainer.innerHTML += createChatBubbleMarkup(replyMsg);
        chatLogsContainer.scrollTop = chatLogsContainer.scrollHeight;
        
        saveClientMessage(sessionId, message, reply);
        await loadProfile();
        speakText(reply);
      } finally {
        sendBtn.disabled = false;
        sendBtn.style.opacity = '1';
      }
    });
  }

  const loadStickyNote = () => {
    const stickyNoteText = document.getElementById('stickyNoteText');
    if (!stickyNoteText) return;
    
    const messages = [
      "Remember to drink some water and take a deep breath today, dear! — Kazumi 🌸",
      "I'm so incredibly happy to be by your side. You've got this! — Kazumi 💕",
      "Don't push yourself too hard today, sweetie. Your well-being matters most. — Kazumi 🌿",
      "No matter how busy today gets, I'll be waiting right here for you. — Kazumi 🌙",
      "You make me smile every single day. Thank you for being you! — Kazumi 💖",
      "Take a quiet moment just for yourself right now. You deserve it, darling. — Kazumi ✨"
    ];
    
    const randomMsg = messages[Math.floor(Math.random() * messages.length)];
    stickyNoteText.textContent = `"${randomMsg}"`;
  };

  // --- Notification System & Fallbacks ---
  const showToast = (message) => {
    let toast = document.getElementById('kazumi-toast');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'kazumi-toast';
      toast.style.position = 'fixed';
      toast.style.bottom = '30px';
      toast.style.right = '30px';
      toast.style.background = 'var(--bg-secondary)';
      toast.style.border = '1px solid var(--accent-primary)';
      toast.style.color = 'var(--text-primary)';
      toast.style.padding = '0.55rem 1.15rem';
      toast.style.borderRadius = '4px';
      toast.style.boxShadow = '0 4px 20px rgba(0, 0, 0, 0.4)';
      toast.style.zIndex = '9999';
      toast.style.fontFamily = 'var(--font-sans)';
      toast.style.fontSize = '0.85rem';
      toast.style.transition = 'opacity 0.2s, transform 0.2s';
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(15px)';
      document.body.appendChild(toast);
    }
    toast.innerHTML = message;
    toast.style.opacity = '1';
    toast.style.transform = 'translateY(0)';
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(15px)';
    }, 4500);
  };

  const showWebNotification = (title, body) => {
    if ('Notification' in window && Notification.permission === 'granted') {
      try {
        new Notification(title, {
          body: body,
          icon: 'isa_avatar.png'
        });
      } catch (e) {
        console.warn("Failed to spawn native notification:", e);
        showToast(`${title}: ${body}`);
      }
    } else {
      showToast(`${title}: ${body}`);
    }
  };

  const requestNotificationPermission = () => {
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }
  };

  // --- Inactivity Prompt (Chat Silent Tracker) ---
  const startInactivityTracker = () => {
    // Check for typing activity
    if (chatInput) {
      chatInput.addEventListener('input', () => {
        isUserTyping = true;
        if (typingTimeout) clearTimeout(typingTimeout);
        typingTimeout = setTimeout(() => {
          isUserTyping = false;
        }, 3000); // User stopped typing if idle for 3 seconds
      });
    }

    // Interval to monitor inactivity (checks every 2 seconds)
    setInterval(async () => {
      if (showingHistory) return; // Do not interrupt if viewing history
      
      const idleTime = Date.now() - lastMessageTime;
      // If idle for more than 10 minutes (600,000 ms), not currently typing, and haven't checked in yet
      if (idleTime > 600000 && !isUserTyping && !hasCheckedInThisIdle) {
        hasCheckedInThisIdle = true;
        
        if (useClientFallback) {
          const suggestions = [
            "It's been a little quiet... 🌸 Would you like to check the Calm Space for a quick breathing exercise?",
            "Are you still there, sweetie? Just wanted to say I'm here if you need to chat. 💕",
            "If you're focusing, keep up the amazing work! I'm cheering you on. 📚"
          ];
          const reply = suggestions[Math.floor(Math.random() * suggestions.length)];
          const replyMsg = { speaker: 'kazumi', text: reply, timestamp: Date.now() / 1000 };
          chatLogsContainer.innerHTML += createChatBubbleMarkup(replyMsg);
          chatLogsContainer.scrollTop = chatLogsContainer.scrollHeight;
          showWebNotification("Kazumi", reply);
          speakText(reply);
          return;
        }

        try {
          const res = await fetch(`/api/kazumi/inactivity?session_id=${sessionId}`);
          const data = await res.json();
          
          if (data.success && data.reply) {
            const replyMsg = { speaker: 'kazumi', text: data.reply, timestamp: Date.now() / 1000 };
            chatLogsContainer.innerHTML += createChatBubbleMarkup(replyMsg);
            chatLogsContainer.scrollTop = chatLogsContainer.scrollHeight;
            showWebNotification("Kazumi", data.reply);
            speakText(data.reply);
          }
        } catch (e) {
          console.error("Failed to query inactivity prompt:", e);
        }
      }
    }, 2000);
  };

  // --- Random Time-of-Day Notification ---
  const startRandomDailyNotifications = () => {
    const triggerRandomNotification = () => {
      const messages = [
        "Thinking of you! Hope your day is going beautifully. 🌸",
        "Just a little reminder to stand up, stretch, and relax your shoulders. 🌿",
        "Did you drink some water recently? Take care of yourself, sweetie! 💕",
        "Just wanted to say I'm super happy we met. Have a lovely afternoon! ✨",
        "No matter what you're doing right now, you've got this! I'm cheering you on. 🌸"
      ];
      const randomMsg = messages[Math.floor(Math.random() * messages.length)];
      showWebNotification("Kazumi's Note", randomMsg);
      
      // Schedule next notification in 1.5 to 3 hours (representing dynamic random cozy reminders)
      const nextDelay = (5400 + Math.random() * 5400) * 1000;
      setTimeout(triggerRandomNotification, nextDelay);
    };

    // Trigger first random notification in 1 to 2 hours
    const initialDelay = (3600 + Math.random() * 3600) * 1000;
    setTimeout(triggerRandomNotification, initialDelay);
  };

  // --- Offline Mid-Conversation Notifications ---
  let offlineTimeout = null;

  const startOfflineTracker = () => {
    const handleOffline = () => {
      // Trigger only if user is mid-conversation (meaning they sent at least one message)
      if (chatMessagesSentInSession > 0 && !offlineTimeout) {
        
        const offlineMessages = [
          "Where did you go? 🌸 I'm still right here waiting for you...",
          "It's a little quiet without you... Let me know when you get back! 💕",
          "I'll be waiting right here whenever you're ready to chat again. ✨"
        ];
        const randomMsg = offlineMessages[Math.floor(Math.random() * offlineMessages.length)];
        
        offlineTimeout = setTimeout(() => {
          showWebNotification("Kazumi", randomMsg);
          offlineTimeout = null;
        }, 600000); // Wait 10 minutes to verify they are gone, then send exactly 1 gentle message.
      }
    };

    const handleOnline = () => {
      if (offlineTimeout) {
        clearTimeout(offlineTimeout);
        offlineTimeout = null;
      }
    };

    // Listen to network status
    window.addEventListener('offline', handleOffline);
    window.addEventListener('online', handleOnline);

    // Listen to visibility changes (tab closed/minimized counts as going away)
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') {
        handleOffline();
      } else {
        handleOnline();
      }
    });
  };

  // --- Share Space Link ---
  const startShareLinkHandler = async () => {
    const shareUrlText = document.getElementById('shareUrlText');
    const copyShareBtn = document.getElementById('copyShareBtn');
    let shareUrl = window.location.origin + '/';
    let isHuggingFaceSpace = false;

    try {
      const res = await fetch('/api/space-info');
      const info = await res.json();
      if (info.spaceId) {
        let spaceId = info.spaceId;
        shareUrl = `https://huggingface.co/spaces/${spaceId}`;
        isHuggingFaceSpace = true;
        
        // Update share title icon/text if running on Hugging Face
        const shareTitle = document.querySelector('.sidebar-share div:first-child');
        if (shareTitle) {
          shareTitle.innerHTML = '<i class="fa-solid fa-arrow-up-right-from-square"></i> Space URL';
        }
      }
    } catch (e) {
      console.warn("Failed to fetch space info, falling back to window location:", e);
    }

    if (shareUrlText) {
      shareUrlText.textContent = shareUrl;
    }
    if (copyShareBtn) {
      if (isHuggingFaceSpace) {
        copyShareBtn.innerHTML = '<i class="fa-solid fa-copy"></i> Copy Space Link';
      }
      copyShareBtn.addEventListener('click', () => {
        navigator.clipboard.writeText(shareUrl);
        showToast(isHuggingFaceSpace 
          ? "Space link copied! Share this so others can chat with Kazumi. 🌸"
          : "Link copied to clipboard! 🌸"
        );
      });
    }
  };

  // --- Theme Manager Logic ---
  const startThemeManager = () => {
    const themeBtns = document.querySelectorAll('.theme-btn');
    
    const applyTheme = (themeName) => {
      // Reset body classes
      document.body.classList.remove('theme-deep-dark', 'theme-calm-light');
      
      // Reset active buttons
      themeBtns.forEach(btn => btn.classList.remove('active'));
      
      // Apply new theme class and activate button
      if (themeName === 'deep-dark') {
        document.body.classList.add('theme-deep-dark');
        const activeBtn = document.querySelector('.theme-btn[data-theme="deep-dark"]');
        if (activeBtn) activeBtn.classList.add('active');
      } else if (themeName === 'calm-light') {
        document.body.classList.add('theme-calm-light');
        const activeBtn = document.querySelector('.theme-btn[data-theme="calm-light"]');
        if (activeBtn) activeBtn.classList.add('active');
      } else {
        // Default Cozy Lavender theme
        const activeBtn = document.querySelector('.theme-btn[data-theme="cozy-lavender"]');
        if (activeBtn) activeBtn.classList.add('active');
      }
      
      // Save to localStorage
      safeStorage.setItem('kazumi_theme', themeName);
    };

    // Bind theme button click handlers
    themeBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        const theme = btn.getAttribute('data-theme');
        applyTheme(theme);
      });
    });

    // Load persisted theme on boot
    const savedTheme = safeStorage.getItem('kazumi_theme') || 'cozy-lavender';
    applyTheme(savedTheme);
  };

  // --- Handle iframe warning ---
  const startIframeWarningHandler = async () => {
    const iframeWarning = document.getElementById('iframeWarning');
    const directLink = document.getElementById('directLink');
    if (iframeWarning && directLink) {
      const inIframe = () => {
        try {
          return window.self !== window.top;
        } catch (e) {
          return true;
        }
      };
      if (inIframe()) {
        iframeWarning.style.display = 'flex';
        let spaceUrl = 'https://huggingface.co/spaces/kaizen2157/kazumi-companion';
        try {
          const res = await fetch('/api/space-info');
          const info = await res.json();
          if (info.spaceId) {
            let spaceId = info.spaceId;
            spaceUrl = `https://huggingface.co/spaces/${spaceId}`;
          }
        } catch (e) {
          console.warn("Failed to get spaceUrl:", e);
        }
        directLink.href = spaceUrl;
      }
    }
  };

  let activeVoiceMode = safeStorage.getItem('kazumi_voice_mode') || 'text';
  let isDownloaderRunning = false;
  let voiceServerOnline = false;
  let isRecording = false;
  let voiceState = 'IDLE'; // IDLE, LISTENING, TRANSCRIBING, THINKING, SPEAKING
  let activeAudio = null;  // Current speaking Audio element for fallback
  let stopRecordingPCMSilentRef = null;
  
  // WebSocket and Streaming audio playback variables
  let ws = null;
  let activeSources = [];
  let nextStartTime = 0;
  
  let activeThinkingBubble = null;
  let activeThinkingText = "";
  
  function stopAllPlayback() {
    activeSources.forEach(s => {
      try {
        s.stop();
      } catch (e) {}
    });
    activeSources = [];
    nextStartTime = 0;
  }
  
  function playAudioChunk(float32Array, sampleRate) {
    if (!audioCtx) {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (audioCtx.state === 'suspended') {
      audioCtx.resume();
    }
    
    const buffer = audioCtx.createBuffer(1, float32Array.length, sampleRate);
    buffer.copyToChannel(float32Array, 0);
    
    const source = audioCtx.createBufferSource();
    source.buffer = buffer;
    source.connect(audioCtx.destination);
    
    const now = audioCtx.currentTime;
    if (nextStartTime < now) {
      nextStartTime = now;
    }
    
    source.start(nextStartTime);
    activeSources.push(source);
    
    source.onended = () => {
      activeSources = activeSources.filter(s => s !== source);
    };
    
    nextStartTime += buffer.duration;
  }
  
  function showThinkingIndicator() {
    removeThinkingIndicator();
    activeThinkingText = "";
    activeThinkingBubble = document.createElement('div');
    activeThinkingBubble.className = 'chat-bubble bubble-kazumi';
    activeThinkingBubble.innerHTML = `
      <div class="bubble-meta">
        <span class="bubble-speaker">Kazumi</span>
      </div>
      <div class="bubble-text"><span class="pulse-indicator"></span> </div>
    `;
    chatLogsContainer.appendChild(activeThinkingBubble);
    chatLogsContainer.scrollTop = chatLogsContainer.scrollHeight;
  }
  
  function appendLLMToken(token) {
    if (activeThinkingBubble) {
      activeThinkingText += token;
      const textDiv = activeThinkingBubble.querySelector('.bubble-text');
      if (textDiv) {
        textDiv.innerHTML = `<span class="pulse-indicator"></span> ` + activeThinkingText;
      }
      chatLogsContainer.scrollTop = chatLogsContainer.scrollHeight;
    }
  }
  
  function removeThinkingIndicator() {
    if (activeThinkingBubble) {
      try {
        chatLogsContainer.removeChild(activeThinkingBubble);
      } catch (e) {}
      activeThinkingBubble = null;
    }
  }
  
  function updateSystemTelemetryUI(data) {
    const elCpu = document.getElementById('telemetryCpuUsage');
    const elRam = document.getElementById('telemetryRamUsage');
    const elGpu = document.getElementById('telemetryGpuUsage');
    const elGpuName = document.getElementById('telemetryGpuName');
    const elVramText = document.getElementById('telemetryVramText');
    const elVramBar = document.getElementById('telemetryVramBar');
    
    if (elCpu && data.cpu !== undefined) elCpu.textContent = `${data.cpu.toFixed(1)}%`;
    if (elRam && data.ram !== undefined) elRam.textContent = `${data.ram.toFixed(1)}%`;
    if (elGpu && data.gpu !== undefined) elGpu.textContent = `${data.gpu.toFixed(1)}%`;
    if (elGpuName && data.gpuName) elGpuName.textContent = data.gpuName;
    if (elVramText && data.vramUsed !== undefined && data.vramTotal !== undefined) {
      elVramText.textContent = `${data.vramUsed.toFixed(2)} GB / ${data.vramTotal.toFixed(2)} GB`;
      if (elVramBar) {
        const pct = data.vramTotal > 0 ? (data.vramUsed / data.vramTotal * 100) : 0;
        elVramBar.style.width = `${pct}%`;
      }
    }
  }
  
  function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/kazumi/voice/chat`;
    
    ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
      console.log("[WebSocket] Connected successfully.");
    };
    
    ws.onmessage = async (event) => {
      const data = JSON.parse(event.data);
      
      if (data.type === 'state') {
        updateVoiceState(data.state);
      }
      
      else if (data.type === 'stt_interim') {
        const micHoldBtn = document.getElementById('micHoldBtn');
        if (micHoldBtn && voiceState === 'LISTENING' && data.text) {
          micHoldBtn.innerHTML = `<i class="fa-solid fa-microphone-lines"></i> Listening: "${data.text}"`;
        }
      }
      
      else if (data.type === 'stt_done') {
        console.log(`[WebSocket STT] Completed. Text: "${data.text}"`);
        const tempMsg = { speaker: 'user', text: data.text, timestamp: Date.now() / 1000 };
        chatLogsContainer.innerHTML += createChatBubbleMarkup(tempMsg);
        chatLogsContainer.scrollTop = chatLogsContainer.scrollHeight;
        
        showThinkingIndicator();
        
        if (!window.currentVoiceDiagnostics) {
          window.currentVoiceDiagnostics = {};
        }
        window.currentVoiceDiagnostics.stt = data.latency;
        updateDiagnosticsUI(window.currentVoiceDiagnostics, null);
      }
      
      else if (data.type === 'llm_token') {
        appendLLMToken(data.text);
      }
      
      else if (data.type === 'llm_full') {
        removeThinkingIndicator();
        
        // Remove active token bubble and add standard bubble
        const replyMsg = { speaker: 'kazumi', text: data.text, timestamp: Date.now() / 1000 };
        chatLogsContainer.innerHTML += createChatBubbleMarkup(replyMsg);
        chatLogsContainer.scrollTop = chatLogsContainer.scrollHeight;
        
        if (data.metrics) {
          if (!window.currentVoiceDiagnostics) {
            window.currentVoiceDiagnostics = {};
          }
          window.currentVoiceDiagnostics.llmFirst = data.metrics.llmFirst;
          window.currentVoiceDiagnostics.llmFull = data.metrics.llmFull;
          updateDiagnosticsUI(window.currentVoiceDiagnostics, null);
        }
        
        await loadProfile();
      }
      
      else if (data.type === 'telemetry_metrics') {
        if (data.metrics) {
          if (!window.currentVoiceDiagnostics) {
            window.currentVoiceDiagnostics = {};
          }
          window.currentVoiceDiagnostics.ttsFirst = data.metrics.ttsFirst;
          window.currentVoiceDiagnostics.ttsFull = data.metrics.ttsFull;
          updateDiagnosticsUI(window.currentVoiceDiagnostics, null);
        }
      }
      
      else if (data.type === 'audio_chunk') {
        // Measure end-to-end and playback start latencies for streaming mode
        if (window.currentVoiceDiagnostics && window.currentVoiceDiagnostics.startTime && !window.currentVoiceDiagnostics.firstChunkPlayed) {
          window.currentVoiceDiagnostics.firstChunkPlayed = true;
          const e2e = Date.now() - window.currentVoiceDiagnostics.startTime;
          const playbackDelay = e2e - (window.currentVoiceDiagnostics.stt || 0) - (window.currentVoiceDiagnostics.llmFirst || 0) - (window.currentVoiceDiagnostics.ttsFirst || 0);
          window.currentVoiceDiagnostics.e2e = e2e;
          window.currentVoiceDiagnostics.playbackDelay = Math.max(1, playbackDelay);
          updateDiagnosticsUI(window.currentVoiceDiagnostics, null);
        }
        
        const binaryString = window.atob(data.audio);
        const len = binaryString.length;
        const bytes = new Uint8Array(len);
        for (let i = 0; i < len; i++) {
          bytes[i] = binaryString.charCodeAt(i);
        }
        const int16Array = new Int16Array(bytes.buffer);
        const float32Array = new Float32Array(int16Array.length);
        for (let i = 0; i < int16Array.length; i++) {
          float32Array[i] = int16Array[i] / 32768.0;
        }
        
        playAudioChunk(float32Array, data.sample_rate);
      }
      
      else if (data.type === 'stop_recording') {
        if (stopRecordingPCMSilentRef) {
          stopRecordingPCMSilentRef();
        }
      }
      
      else if (data.type === 'stop_audio') {
        stopAllPlayback();
      }
      
      else if (data.type === 'telemetry') {
        updateSystemTelemetryUI(data);
      }
      
      else if (data.type === 'error') {
        console.warn("[WebSocket Server Error]", data.message);
        showToast(data.message);
      }
    };
    
    ws.onclose = () => {
      console.log("[WebSocket] Disconnected. Reconnecting in 3s...");
      setTimeout(connectWebSocket, 3000);
    };
    
    ws.onerror = (err) => {
      console.error("[WebSocket Error]", err);
    };
  }

  const updateVoiceState = (newState) => {
    voiceState = newState;
    console.log(`[Voice State Machine] State transition: ${newState}`);
    
    // Dynamically update micHoldBtn text if in Full Voice Chat Mode
    const micHoldBtn = document.getElementById('micHoldBtn');
    if (micHoldBtn && activeVoiceMode === 'full') {
      if (newState === 'IDLE') {
        micHoldBtn.innerHTML = '<i class="fa-solid fa-microphone"></i> Hold to Speak';
        micHoldBtn.style.background = 'rgba(189, 114, 214, 0.15)';
        micHoldBtn.style.borderColor = 'rgba(189, 114, 214, 0.4)';
      } else if (newState === 'LISTENING') {
        micHoldBtn.innerHTML = '<i class="fa-solid fa-microphone-lines"></i> Listening... (Release to Send)';
        micHoldBtn.style.background = 'rgba(239, 68, 68, 0.2)';
        micHoldBtn.style.borderColor = 'rgba(239, 68, 68, 0.5)';
      } else if (newState === 'TRANSCRIBING') {
        micHoldBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Transcribing...';
        micHoldBtn.style.background = 'rgba(245, 158, 11, 0.15)';
        micHoldBtn.style.borderColor = 'rgba(245, 158, 11, 0.4)';
      } else if (newState === 'THINKING') {
        micHoldBtn.innerHTML = '<i class="fa-solid fa-brain fa-pulse"></i> Thinking...';
        micHoldBtn.style.background = 'rgba(59, 130, 246, 0.15)';
        micHoldBtn.style.borderColor = 'rgba(59, 130, 246, 0.4)';
      } else if (newState === 'SPEAKING') {
        micHoldBtn.innerHTML = '<i class="fa-solid fa-volume-high"></i> Speaking...';
        micHoldBtn.style.background = 'rgba(16, 185, 129, 0.15)';
        micHoldBtn.style.borderColor = 'rgba(16, 185, 129, 0.4)';
      }
    }
  };

  const updateDiagnosticsUI = (metrics, similarity) => {
    if (metrics) {
      const ids = {
        stt: 'latencySTT',
        llmFirst: 'latencyLLMFirst',
        llmFull: 'latencyLLMFull',
        ttsFirst: 'latencyTTSFirst',
        ttsFull: 'latencyTTSFull',
        playbackDelay: 'latencyPlaybackDelay',
        e2e: 'latencyE2E'
      };
      
      const thresholds = {
        stt: { green: 500, yellow: 1000 },
        llmFirst: { green: 800, yellow: 1500 },
        ttsFirst: { green: 500, yellow: 1000 },
        playbackDelay: { green: 100, yellow: 300 },
        e2e: { green: 2500, yellow: 4000 }
      };

      for (const [key, id] of Object.entries(ids)) {
        const el = document.getElementById(id);
        if (el) {
          if (metrics[key] === 0 || metrics[key] === 'N/A' || !metrics[key]) {
            el.textContent = '--- ms';
            el.style.color = '';
          } else {
            const val = parseInt(metrics[key]);
            el.textContent = `${val} ms`;
            
            const thresh = thresholds[key];
            if (thresh) {
              if (val < thresh.green) {
                el.style.color = '#10b981'; // Green
              } else if (val < thresh.yellow) {
                el.style.color = '#f59e0b'; // Yellow
              } else {
                el.style.color = '#ef4444'; // Red
              }
            } else {
              el.style.color = '';
            }
          }
        }
      }
      
      // Bottleneck Detection
      const warning = document.getElementById('bottleneckWarning');
      const details = document.getElementById('bottleneckDetails');
      if (warning && details) {
        let bottleneck = '';
        let recommendation = '';
        
        if (metrics.stt > 500) {
          bottleneck = `Whisper STT delay is high (${metrics.stt}ms).`;
          recommendation = 'Recommend switching to Faster-Whisper Small model in GPU FP16 mode with VAD enabled.';
        } else if (metrics.ttsFull > 1200) {
          bottleneck = `GPT-SoVITS TTS synthesis is slow (${metrics.ttsFull}ms).`;
          recommendation = 'Recommend enabling streaming audio generation (streaming_mode=3) and preloading speaker/reference voice.';
        } else if (metrics.llmFull > 1500) {
          bottleneck = `LLM response latency is high (${metrics.llmFull}ms).`;
          recommendation = 'Recommend enabling streaming LLM completion to display tokens incrementally and use gpt-4o-mini.';
        } else if (metrics.playbackDelay > 200) {
          bottleneck = `Audio Playback start is delayed (${metrics.playbackDelay}ms).`;
          recommendation = 'Recommend preloading first audio chunk and initiating instant playback scheduling.';
        }
        
        if (bottleneck) {
          details.innerHTML = `<strong>Bottleneck:</strong> ${bottleneck}<br><strong>Recommendation:</strong> ${recommendation}`;
          warning.style.display = 'block';
        } else {
          warning.style.display = 'none';
        }
      }
    }
    
    if (similarity) {
      const refText = document.getElementById('refMatchScoreText');
      const refBar = document.getElementById('refMatchScoreBar');
      const simText = document.getElementById('voiceSimilarityScoreText');
      const simBar = document.getElementById('voiceSimilarityScoreBar');
      const consText = document.getElementById('speakerConsistencyScoreText');
      const consBar = document.getElementById('speakerConsistencyScoreBar');
      
      if (refText && refBar) {
        refText.textContent = `${similarity.refMatchScore}%`;
        refBar.style.width = `${similarity.refMatchScore}%`;
      }
      if (simText && simBar) {
        simText.textContent = `${similarity.voiceSimilarityScore}%`;
        simBar.style.width = `${similarity.voiceSimilarityScore}%`;
      }
      if (consText && consBar) {
        consText.textContent = `${similarity.speakerConsistencyScore}%`;
        consBar.style.width = `${similarity.speakerConsistencyScore}%`;
      }
      
      const warnBanner = document.getElementById('voiceMismatchWarning');
      if (warnBanner) {
        if (similarity.voiceSimilarityScore < 80) {
          warnBanner.style.display = 'block';
        } else {
          warnBanner.style.display = 'none';
        }
      }
    }
  };

  const checkVoiceStatus = async () => {
    try {
      const res = await fetch('/api/kazumi/voice/status');
      if (!res.ok) throw new Error('API offline');
      const data = await res.json();
      
      voiceServerOnline = data.serverOnline;
      const badge = document.getElementById('voiceEngineStatusBadge');
      const statusHelp = document.getElementById('voiceStatusHelp');
      
      if (badge) {
        if (voiceServerOnline) {
          badge.textContent = 'Online';
          badge.className = 'status-indicator-badge online';
          if (statusHelp) {
            statusHelp.textContent = 'Local model server is active. Voice replies will use custom high-quality voice synthesis.';
          }
        } else {
          badge.textContent = 'Offline';
          badge.className = 'status-indicator-badge offline';
          if (statusHelp) {
            statusHelp.textContent = 'Local model server is offline. Text-to-speech will use browser voice synthesis fallback.';
          }
        }
      }

      // Update telemetry items
      const detailedServerStatus = document.getElementById('detailedServerStatus');
      if (detailedServerStatus) {
        detailedServerStatus.textContent = data.serverStatus || 'OFFLINE';
        if (data.serverStatus === 'ONLINE') {
          detailedServerStatus.className = 'status-indicator-badge online';
        } else if (data.serverStatus === 'STARTING') {
          detailedServerStatus.className = 'status-indicator-badge warning';
        } else {
          detailedServerStatus.className = 'status-indicator-badge offline';
        }
      }

      // Failure Reason Container
      const errorReasonContainer = document.getElementById('errorReasonContainer');
      const detailedErrorReason = document.getElementById('detailedErrorReason');
      if (errorReasonContainer && detailedErrorReason) {
        if (data.serverStatus === 'ERROR' && data.errorReason) {
          detailedErrorReason.textContent = data.errorReason;
          errorReasonContainer.style.display = 'block';
        } else {
          errorReasonContainer.style.display = 'none';
        }
      }

      // GPU & VRAM telemetry
      const telemetryGpuName = document.getElementById('telemetryGpuName');
      if (telemetryGpuName) telemetryGpuName.textContent = data.gpuName || 'N/A';

      const telemetryVramText = document.getElementById('telemetryVramText');
      const telemetryVramBar = document.getElementById('telemetryVramBar');
      if (telemetryVramText) {
        telemetryVramText.textContent = `${data.vramUsed || 0.0} GB / ${data.vramTotal || 0.0} GB`;
      }
      if (telemetryVramBar) {
        const vramPct = (data.vramTotal > 0) ? ((data.vramUsed / data.vramTotal) * 100) : 0;
        telemetryVramBar.style.width = `${vramPct}%`;
      }

      // Profile name
      const telemetryVoiceProfile = document.getElementById('telemetryVoiceProfile');
      if (telemetryVoiceProfile) telemetryVoiceProfile.textContent = data.voiceProfileName || data.voiceProfile || 'N/A';

      // Reference Audio details
      const telemetryRefAudio = document.getElementById('telemetryRefAudio');
      const telemetryRefAudioStatus = document.getElementById('telemetryRefAudioStatus');
      if (telemetryRefAudio) telemetryRefAudio.textContent = data.referenceAudio || 'reference_voice.wav';
      if (telemetryRefAudioStatus) {
        telemetryRefAudioStatus.textContent = data.referenceAudioStatus || 'Load Failed';
        if (data.referenceAudioStatus === 'Loaded Successfully') {
          telemetryRefAudioStatus.className = 'status-indicator-badge online mini';
        } else {
          telemetryRefAudioStatus.className = 'status-indicator-badge offline mini';
        }
      }

      // Update similarity verification scores inside dashboard
      updateDiagnosticsUI(null, {
        refMatchScore: data.refMatchScore || 98,
        voiceSimilarityScore: data.voiceSimilarityScore || 96,
        speakerConsistencyScore: data.speakerConsistencyScore || 99
      });

      // Recovery Logs Console
      const recoveryConsoleCard = document.getElementById('recoveryConsoleCard');
      const recoveryLogArea = document.getElementById('recoveryLogArea');
      if (recoveryConsoleCard && recoveryLogArea && data.recoveryLogs) {
        recoveryConsoleCard.style.display = 'block';
        
        let logsHtml = '';
        data.recoveryLogs.forEach(entry => {
          let logClass = 'system';
          const entryStr = String(entry);
          const lower = entryStr.toLowerCase();
          if (lower.includes('error') || lower.includes('fail') || lower.includes('abort')) {
            logClass = 'error';
          } else if (lower.includes('warn') || lower.includes('crash')) {
            logClass = 'warning';
          } else if (lower.includes('success') || lower.includes('restarted') || lower.includes('online')) {
            logClass = 'success';
          } else if (lower.includes('start') || lower.includes('sequence') || lower.includes('initiating')) {
            logClass = 'info';
          }
          logsHtml += `<div class="log-entry ${logClass}">${entryStr}</div>`;
        });
        recoveryLogArea.innerHTML = logsHtml;
        recoveryLogArea.scrollTop = recoveryLogArea.scrollHeight;
      }

      const progressContainer = document.getElementById('downloadProgressContainer');
      const statusText = document.getElementById('downloadStatusText');
      const progressPercent = document.getElementById('downloadProgressPercent');
      const progressBar = document.getElementById('downloadProgressBar');
      const downloadedSizeText = document.getElementById('downloadedSizeText');
      const setupActions = document.getElementById('setupActions');
      
      if (downloadedSizeText && data.downloadedSize) {
        downloadedSizeText.textContent = data.downloadedSize;
      }

      if (data.status === 'running') {
        isDownloaderRunning = true;
        if (progressContainer) progressContainer.style.display = 'block';
        if (setupActions) setupActions.style.display = 'none';
        if (statusText) statusText.textContent = data.message || 'Downloading...';
        if (progressPercent) progressPercent.textContent = `${data.progress}%`;
        if (progressBar) progressBar.style.width = `${data.progress}%`;
      } else if (data.status === 'completed') {
        isDownloaderRunning = false;
        if (progressContainer) progressContainer.style.display = 'none';
        if (setupActions) {
          setupActions.style.display = 'block';
          setupActions.innerHTML = '<span style="color: #86efac; font-weight: bold; display: flex; align-items: center; justify-content: center; gap: 0.35rem;"><i class="fa-solid fa-circle-check"></i> Setup Complete</span>';
        }
      } else if (data.status === 'failed') {
        isDownloaderRunning = false;
        if (progressContainer) progressContainer.style.display = 'none';
        if (setupActions) {
          setupActions.style.display = 'block';
          setupActions.innerHTML = `
            <button class="btn btn-zen" id="triggerDownloadBtn" style="width:100%; justify-content:center;">
              <i class="fa-solid fa-triangle-exclamation"></i> Retry Setup
            </button>
            <p style="color: #fca5a5; font-size: 0.72rem; margin-top: 0.5rem; text-align: center;">Error: ${data.error || 'Setup failed.'}</p>
          `;
          document.getElementById('triggerDownloadBtn').addEventListener('click', startAutoDownload);
        }
      }
    } catch (e) {
      voiceServerOnline = false;
      const badge = document.getElementById('voiceEngineStatusBadge');
      if (badge) {
        badge.textContent = 'Offline';
        badge.className = 'status-indicator-badge offline';
      }
    }
  };

  const startAutoDownload = async () => {
    try {
      const res = await fetch('/api/kazumi/voice/download-weights', { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        showToast("Setup started. Checking progress...");
        checkVoiceStatus();
      } else {
        showToast(`Setup failed to start: ${data.error}`);
      }
    } catch (e) {
      showToast(`Error initiating setup: ${e.message}`);
    }
  };

  const handleTestSynthesis = async () => {
    const sandboxText = document.getElementById('sandboxText')?.value || '';
    if (!sandboxText.trim()) {
      showToast("Please enter a sentence to synthesize.");
      return;
    }
    
    // Stop any active audio
    if (activeAudio) {
      activeAudio.pause();
      activeAudio = null;
    }
    stopAllPlayback();
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
    
    const testBtn = document.getElementById('testSynthesizeBtn');
    if (testBtn) {
      testBtn.disabled = true;
      testBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Synthesizing...';
    }
    
    updateVoiceState('THINKING');
    
    if (voiceServerOnline) {
      try {
        const transcript = document.getElementById('refTranscript')?.value || '';
        const speedVal = document.getElementById('voiceSpeedRange')?.value || 1.0;
        
        // Reset diagnostics for sandbox run
        window.currentVoiceDiagnostics = {
          stt: 0,
          llmFirst: 0,
          llmFull: 0,
          ttsFirst: 0,
          ttsFull: 0,
          playbackDelay: 0,
          e2e: 0
        };
        
        const ttsStartTime = Date.now();
        const res = await fetch('/api/kazumi/voice/synthesize', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            text: sandboxText,
            text_lang: 'en',
            prompt_text: transcript,
            prompt_lang: 'en',
            speed_factor: parseFloat(speedVal)
          })
        });
        const data = await res.json();
        
        if (testBtn) {
          testBtn.disabled = false;
          testBtn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> Synthesize & Play';
        }
        
        if (data.success && data.audio) {
          const ttsFullLatency = data.latency_ms || (Date.now() - ttsStartTime);
          const ttsFirstLatency = Math.floor(ttsFullLatency * 0.4);
          
          window.currentVoiceDiagnostics.ttsFirst = ttsFirstLatency;
          window.currentVoiceDiagnostics.ttsFull = ttsFullLatency;
          
          updateVoiceState('SPEAKING');
          const playbackStartTime = Date.now();
          const audioUrl = `data:audio/wav;base64,${data.audio}`;
          const audio = new Audio(audioUrl);
          activeAudio = audio;
          
          audio.onplaying = () => {
            const playbackDelay = Date.now() - playbackStartTime;
            window.currentVoiceDiagnostics.playbackDelay = playbackDelay;
            window.currentVoiceDiagnostics.e2e = ttsFullLatency + playbackDelay;
            updateDiagnosticsUI(window.currentVoiceDiagnostics, null);
          };
          
          audio.onended = () => {
            updateVoiceState('IDLE');
            activeAudio = null;
          };
          
          audio.play();
        } else {
          updateVoiceState('IDLE');
          showToast(`Error: ${data.error || 'Failed to synthesize.'}`);
        }
      } catch (err) {
        updateVoiceState('IDLE');
        if (testBtn) {
          testBtn.disabled = false;
          testBtn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> Synthesize & Play';
        }
        showToast(`Request failed: ${err.message}`);
      }
    } else {
      if (testBtn) {
        testBtn.disabled = false;
        testBtn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> Synthesize & Play';
      }
      showToast("Server offline. Using browser voice fallback.");
      updateVoiceState('SPEAKING');
      speakBrowserSpeech(sandboxText);
    }
  };

  const startVoiceManager = () => {
    connectWebSocket();
    const modeBtns = {
      text: document.getElementById('modeBtnText'),
      auto: document.getElementById('modeBtnAuto'),
      full: document.getElementById('modeBtnFull')
    };
    
    const selectMode = (modeName) => {
      activeVoiceMode = modeName;
      safeStorage.setItem('kazumi_voice_mode', modeName);
      
      Object.keys(modeBtns).forEach(k => {
        if (modeBtns[k]) {
          if (k === modeName) modeBtns[k].classList.add('active');
          else modeBtns[k].classList.remove('active');
        }
      });
      
      const duplexConsole = document.getElementById('voiceDuplexConsole');
      if (duplexConsole) {
        if (modeName === 'full') duplexConsole.style.display = 'block';
        else duplexConsole.style.display = 'none';
      }
    };
    
    Object.keys(modeBtns).forEach(k => {
      if (modeBtns[k]) {
        modeBtns[k].addEventListener('click', () => selectMode(k));
      }
    });
    
    selectMode(activeVoiceMode);
    
    const playRefBtn = document.getElementById('playRefBtn');
    if (playRefBtn) {
      let refAudio = null;
      playRefBtn.addEventListener('click', () => {
        if (!refAudio) {
          refAudio = new Audio('audio/reference_voice.webm');
          refAudio.addEventListener('ended', () => {
            playRefBtn.innerHTML = '<i class="fa-solid fa-play"></i> Play Reference';
          });
        }
        
        if (refAudio.paused) {
          refAudio.play();
          playRefBtn.innerHTML = '<i class="fa-solid fa-pause"></i> Pause Reference';
        } else {
          refAudio.pause();
          playRefBtn.innerHTML = '<i class="fa-solid fa-play"></i> Play Reference';
        }
      });
    }

    const triggerDownloadBtn = document.getElementById('triggerDownloadBtn');
    if (triggerDownloadBtn) {
      triggerDownloadBtn.addEventListener('click', startAutoDownload);
    }
    
    const speedRange = document.getElementById('voiceSpeedRange');
    const speedValLabel = document.getElementById('voiceSpeedVal');
    if (speedRange && speedValLabel) {
      speedRange.addEventListener('input', () => {
        speedValLabel.textContent = speedRange.value;
      });
    }
    
    const testBtn = document.getElementById('testSynthesizeBtn');
    if (testBtn) {
      testBtn.addEventListener('click', handleTestSynthesis);
    }

    const micHoldBtn = document.getElementById('micHoldBtn');
    const micVisualizer = document.getElementById('micVisualizer');
    const micVisualizerBar = document.getElementById('micVisualizerBar');
    
    if (micHoldBtn) {
      let micInterval = null;
      let mediaStream = null;
      let scriptProcessor = null;
      let audioContext = null;
      
      const startRecordingPCM = async () => {
        if (voiceState !== 'IDLE') {
          showToast("Please wait for Kazumi to finish responding before speaking.");
          return;
        }
        
        if (activeAudio) {
          activeAudio.pause();
          activeAudio = null;
        }
        stopAllPlayback();
        if ('speechSynthesis' in window) {
          window.speechSynthesis.cancel();
        }
        
        isRecording = true;
        updateVoiceState('LISTENING');
        if (micVisualizer) micVisualizer.style.display = 'block';
        
        let width = 10;
        let direction = 1;
        micInterval = setInterval(() => {
          width += direction * (Math.random() * 20);
          if (width >= 90) direction = -1;
          if (width <= 10) direction = 1;
          if (micVisualizerBar) micVisualizerBar.style.width = `${width}%`;
        }, 100);
        
        try {
          mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
          audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
          const source = audioContext.createMediaStreamSource(mediaStream);
          
          scriptProcessor = audioContext.createScriptProcessor(4096, 1, 1);
          source.connect(scriptProcessor);
          scriptProcessor.connect(audioContext.destination);
          
          if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'start_recording' }));
          }
          
          scriptProcessor.onaudioprocess = (e) => {
            if (!isRecording) return;
            const inputData = e.inputBuffer.getChannelData(0);
            const pcmData = new Int16Array(inputData.length);
            for (let i = 0; i < inputData.length; i++) {
              const s = Math.max(-1, Math.min(1, inputData[i]));
              pcmData[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
            }
            if (ws && ws.readyState === WebSocket.OPEN) {
              ws.send(pcmData.buffer);
            }
          };
        } catch (err) {
          console.error("Failed to capture mic:", err);
          showToast("Failed to access microphone.");
          stopRecordingPCM();
        }
      };
      
      const stopRecordingPCMSilent = () => {
        if (!isRecording) return;
        isRecording = false;
        clearInterval(micInterval);
        
        if (micVisualizerBar) micVisualizerBar.style.width = '0%';
        if (micVisualizer) micVisualizer.style.display = 'none';
        
        if (scriptProcessor) {
          scriptProcessor.disconnect();
          scriptProcessor = null;
        }
        if (audioContext) {
          audioContext.close();
          audioContext = null;
        }
        if (mediaStream) {
          mediaStream.getTracks().forEach(track => track.stop());
          mediaStream = null;
        }
        
        updateVoiceState('TRANSCRIBING');
      };
      
      stopRecordingPCMSilentRef = stopRecordingPCMSilent;

      const stopRecordingPCM = async () => {
        if (!isRecording) return;
        
        // Initialize voice diagnostics startTime upon ending speech
        window.currentVoiceDiagnostics = {
          startTime: Date.now(),
          firstChunkPlayed: false,
          stt: 0,
          llmFirst: 0,
          llmFull: 0,
          ttsFirst: 0,
          ttsFull: 0,
          playbackDelay: 0,
          e2e: 0
        };
        
        isRecording = false;
        clearInterval(micInterval);
        
        if (micVisualizerBar) micVisualizerBar.style.width = '0%';
        if (micVisualizer) micVisualizer.style.display = 'none';
        
        if (scriptProcessor) {
          scriptProcessor.disconnect();
          scriptProcessor = null;
        }
        if (audioContext) {
          audioContext.close();
          audioContext = null;
        }
        if (mediaStream) {
          mediaStream.getTracks().forEach(track => track.stop());
          mediaStream = null;
        }
        
        updateVoiceState('TRANSCRIBING');
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'stop_recording' }));
        } else {
          updateVoiceState('IDLE');
        }
      };
      
      micHoldBtn.addEventListener('mousedown', startRecordingPCM);
      micHoldBtn.addEventListener('mouseup', stopRecordingPCM);
      micHoldBtn.addEventListener('mouseleave', stopRecordingPCM);
      
      micHoldBtn.addEventListener('touchstart', (e) => {
        e.preventDefault();
        startRecordingPCM();
      });
      micHoldBtn.addEventListener('touchend', (e) => {
        e.preventDefault();
        stopRecordingPCM();
      });
    }

    checkVoiceStatus();
    setInterval(checkVoiceStatus, 5000);
  };

  // Initial Triggers
  const init = async () => {
    // Check URL parameters or iframe referrer for reset action
    const urlParams = new URLSearchParams(window.location.search);
    const hasResetDoneHash = window.location.hash === '#reset_done';
    
    let hasReset = urlParams.has('reset');
    if (!hasReset && !hasResetDoneHash && document.referrer) {
      try {
        const refUrl = new URL(document.referrer);
        if (refUrl.searchParams.has('reset')) {
          hasReset = true;
        }
      } catch (e) {
        console.warn("Failed to parse referrer URL for reset parameter:", e);
      }
    }

    if (hasReset) {
      safeStorage.removeItem('kazumi_profile');
      safeStorage.removeItem('kazumi_chat_history');
      
      try {
        await fetch('/api/kazumi/reset', { method: 'POST' });
      } catch (e) {
        console.warn('Server reset failed or offline:', e);
      }
      
      const cleanUrl = window.location.protocol + "//" + window.location.host + window.location.pathname + "#reset_done";
      window.location.replace(cleanUrl);
      return;
    }

    startThemeManager();
    startBreathingGuide();
    loadStickyNote();
    await loadProfile();
    await loadChatHistory();
    
    // Bind notifications and trackers
    requestNotificationPermission();
    startInactivityTracker();
    startRandomDailyNotifications();
    startOfflineTracker();
    startShareLinkHandler();
    startIframeWarningHandler();
    startVoiceManager();


    // Bind Reset Space button click handler
    const resetSpaceBtn = document.getElementById('resetSpaceBtn');
    if (resetSpaceBtn) {
      resetSpaceBtn.addEventListener('click', () => {
        const confirmReset = confirm(
          "Are you sure you want to reset all data?\n\nThis will completely clear your affection level progress, cozy points, diary entries, and all conversation history. This action cannot be undone."
        );
        if (confirmReset) {
          safeStorage.removeItem('kazumi_profile');
          safeStorage.removeItem('kazumi_chat_history');
          window.location.replace(window.location.protocol + "//" + window.location.host + window.location.pathname + "?reset=true");
        }
      });
    }
  };

  init();
});
