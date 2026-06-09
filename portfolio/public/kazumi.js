// ----------------------------------------------------
// ⚙️ KAZUMI'S SPACE - CLIENT ENGINE (VANILLA JS)
// ----------------------------------------------------

document.addEventListener('DOMContentLoaded', () => {
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
      breathRing.style.backgroundColor = '#eef4ec';
      breathRing.style.borderColor = '#7d967a';
      breathRing.style.boxShadow = 'none';
      breathText.textContent = 'Breathe In';
      currentPhase = 1;
    } else if (currentPhase === 1) {
      // Hold (4 seconds)
      breathRing.style.transform = 'scale(1.25)';
      breathRing.style.backgroundColor = '#f6f0fa';
      breathRing.style.borderColor = '#855fa3';
      breathRing.style.boxShadow = 'none';
      breathText.textContent = 'Hold';
      currentPhase = 2;
    } else if (currentPhase === 2) {
      // Breathe Out (4 seconds)
      breathRing.style.transform = 'scale(0.95)';
      breathRing.style.backgroundColor = '#faf5eb';
      breathRing.style.borderColor = '#cca16a';
      breathRing.style.boxShadow = 'none';
      breathText.textContent = 'Breathe Out';
      currentPhase = 3;
    } else {
      // Hold (4 seconds)
      breathRing.style.transform = 'scale(0.95)';
      breathRing.style.backgroundColor = '#ffffff';
      breathRing.style.borderColor = '#eae5f2';
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

  // --- Client-Side Fallback Engine ---
  let useClientFallback = false;
  
  const DEFAULT_PROFILE = {
    name: "Sweetie",
    affection_level: 0,
    cozy_points: 120,
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
    diary: [
      "[2026-06-05 21:00] (Mode: DEREDERE)\nDear Diary,\n\nI was dreaming about clouds and tea bubbles today... and my favorite person was right there in my thoughts. Talking to them feels like floating in a beautiful, warm sky. 💕"
    ],
    psychology: {
      dominant_vibe: "Serene",
      rolling_valence: 0.00,
      interaction_preference: "Quiet conversations"
    }
  };

  const initClientStorage = () => {
    if (!localStorage.getItem('kazumi_profile')) {
      localStorage.setItem('kazumi_profile', JSON.stringify(DEFAULT_PROFILE));
    }
    if (!localStorage.getItem('kazumi_chat_history')) {
      localStorage.setItem('kazumi_chat_history', JSON.stringify([]));
    }
  };

  const getClientProfile = () => {
    initClientStorage();
    return JSON.parse(localStorage.getItem('kazumi_profile'));
  };

  const saveClientProfile = (profile) => {
    localStorage.setItem('kazumi_profile', JSON.stringify(profile));
  };

  const getClientChatHistory = (sessId) => {
    initClientStorage();
    const history = JSON.parse(localStorage.getItem('kazumi_chat_history'));
    if (showingHistory) {
      return history;
    }
    return history.filter(msg => msg.sessionId === sessId);
  };

  const saveClientMessage = (sessId, userText, replyText) => {
    initClientStorage();
    const history = JSON.parse(localStorage.getItem('kazumi_chat_history'));
    const nowSec = Date.now() / 1000;
    history.push({ speaker: 'user', text: userText, timestamp: nowSec, sessionId: sessId });
    history.push({ speaker: 'kazumi', text: replyText, timestamp: nowSec + 0.1, sessionId: sessId });
    localStorage.setItem('kazumi_chat_history', JSON.stringify(history));

    // Update stats
    const profile = getClientProfile();
    profile.affection_level = Math.min((profile.affection_level || 0) + (Math.random() < 0.15 ? 1 : 0), 100);
    profile.cozy_points = (profile.cozy_points || 120) + (Math.random() < 0.2 ? 1 : 0);
    
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

  let sessionId = localStorage.getItem('kazumi_session_id');
  if (!sessionId) {
    sessionId = 'session_' + Math.floor(Math.random() * 100000000);
    localStorage.setItem('kazumi_session_id', sessionId);
  }
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

      // Increment session message counts and update last message timestamp
      chatMessagesSentInSession++;
      lastMessageTime = Date.now();
      hasCheckedInThisIdle = false;

      // 1. Append user bubble instantly in UI for visual speed
      const tempMsg = { speaker: 'user', text: message, timestamp: Date.now() / 1000 };
      chatLogsContainer.innerHTML += createChatBubbleMarkup(tempMsg);
      chatLogsContainer.scrollTop = chatLogsContainer.scrollHeight;
      chatInput.value = '';

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
        const res = await fetch('/api/kazumi/chat', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ message, session_id: sessionId })
        });
        const data = await res.json();
        
        chatLogsContainer.removeChild(typingBubble);

        if (data.success && data.reply) {
          const replyMsg = { speaker: 'kazumi', text: data.reply, timestamp: Date.now() / 1000 };
          chatLogsContainer.innerHTML += createChatBubbleMarkup(replyMsg);
          chatLogsContainer.scrollTop = chatLogsContainer.scrollHeight;
          useClientFallback = false; // Restored online mode successfully!
          await loadProfile();
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
      toast.style.background = '#ffffff';
      toast.style.border = '1px solid #9c78b8';
      toast.style.color = '#553b70';
      toast.style.padding = '0.55rem 1.15rem';
      toast.style.borderRadius = '4px';
      toast.style.boxShadow = '0 4px 15px rgba(116, 75, 140, 0.12)';
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
    let isDuplicationLink = false;

    try {
      const res = await fetch('/api/space-info');
      const info = await res.json();
      if (info.spaceId) {
        shareUrl = `https://huggingface.co/spaces/${info.spaceId}?duplicate=true`;
        isDuplicationLink = true;
        
        // Update share title icon/text if running on Hugging Face
        const shareTitle = document.querySelector('.sidebar-share div:first-child');
        if (shareTitle) {
          shareTitle.innerHTML = '<i class="fa-solid fa-clone"></i> Duplicate Space';
        }
      }
    } catch (e) {
      console.warn("Failed to fetch space info, falling back to window location:", e);
    }

    if (shareUrlText) {
      shareUrlText.textContent = shareUrl;
    }
    if (copyShareBtn) {
      if (isDuplicationLink) {
        copyShareBtn.innerHTML = '<i class="fa-solid fa-clone"></i> Copy Duplicate Link';
      }
      copyShareBtn.addEventListener('click', () => {
        navigator.clipboard.writeText(shareUrl);
        showToast(isDuplicationLink 
          ? "Duplication link copied! Share this so others can run their own private server. 🌸"
          : "Link copied to clipboard! Share it with others. 🌸"
        );
      });
    }
  };

  // Initial Triggers
  const init = async () => {
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
  };

  init();
});
