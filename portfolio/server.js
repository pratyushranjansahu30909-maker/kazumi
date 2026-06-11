const express = require('express');
const cors = require('cors');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const https = require('https');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 3000;

// Resolve the isa_memory directory dynamically to support persistent volume mounts on Hugging Face Spaces
const getIsaMemoryDir = () => {
  if (process.env.SPACE_ID && fs.existsSync('/data')) {
    try {
      fs.accessSync('/data', fs.constants.W_OK);
      const targetDir = '/data/isa_memory';
      if (!fs.existsSync(targetDir)) {
        fs.mkdirSync(targetDir, { recursive: true });
      }
      return targetDir;
    } catch (e) {
      console.warn('Hugging Face /data directory exists but is not writable. Falling back to default:', e.message);
    }
  }
  return path.join(__dirname, '..', 'isa_memory');
};

// Resolve the credentials file path dynamically to persist across Hugging Face redeployments
const getCredentialsFilePath = () => path.join(getIsaMemoryDir(), 'credentials.json');

app.use(cors());
app.use(express.json());

// Serve main page at root directly to prevent cross-origin iframe redirect blocks
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.get('/index.html', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.use(express.static(path.join(__dirname, 'public')));

// ----------------------------------------------------
// 🔐 Encryption / Decryption Helper Functions (AES-256-CBC)
// ----------------------------------------------------

// Generate a solid 32-byte key from the configured key using SHA-256
const getEncryptionKey = () => {
  const secret = process.env.ENCRYPTION_KEY || 'default_backup_secret_passphrase_for_portfolio';
  return crypto.createHash('sha256').update(secret).digest();
};

const encrypt = (text) => {
  if (!text) return null;
  const iv = crypto.randomBytes(16);
  const cipher = crypto.createCipheriv('aes-256-cbc', getEncryptionKey(), iv);
  let encrypted = cipher.update(text, 'utf8', 'hex');
  encrypted += cipher.final('hex');
  return {
    iv: iv.toString('hex'),
    content: encrypted
  };
};

const decrypt = (encryptedObj) => {
  if (!encryptedObj || !encryptedObj.iv || !encryptedObj.content) return null;
  try {
    const iv = Buffer.from(encryptedObj.iv, 'hex');
    const encryptedText = Buffer.from(encryptedObj.content, 'hex');
    const decipher = crypto.createDecipheriv('aes-256-cbc', getEncryptionKey(), iv);
    let decrypted = decipher.update(encryptedText, 'hex', 'utf8');
    decrypted += decipher.final('utf8');
    return decrypted;
  } catch (error) {
    console.error('Decryption failed:', error.message);
    return null;
  }
};

// ----------------------------------------------------
// 📁 Credentials Storage Operations
// ----------------------------------------------------

const readCredentials = () => {
  const filePath = getCredentialsFilePath();
  let exists = fs.existsSync(filePath);
  let readPath = filePath;
  if (!exists && fs.existsSync(filePath + '.bak')) {
    exists = true;
    readPath = filePath + '.bak';
  }
  if (!exists) {
    return { github: null, linkedin: null };
  }
  try {
    const raw = fs.readFileSync(readPath, 'utf8');
    return JSON.parse(raw);
  } catch (e) {
    if (readPath === filePath && fs.existsSync(filePath)) {
      const corruptedPath = `${filePath}.corrupted.${Math.floor(Date.now() / 1000)}`;
      try {
        fs.renameSync(filePath, corruptedPath);
      } catch (err) {}
    }
    if (fs.existsSync(filePath + '.bak')) {
      try {
        const raw = fs.readFileSync(filePath + '.bak', 'utf8');
        return JSON.parse(raw);
      } catch (inner) {}
    }
    return { github: null, linkedin: null };
  }
};

const saveCredentials = (creds) => {
  const filePath = getCredentialsFilePath();
  try {
    if (fs.existsSync(filePath)) {
      fs.copyFileSync(filePath, filePath + '.bak');
    }
    const tmpPath = filePath + '.tmp';
    const fd = fs.openSync(tmpPath, 'w');
    fs.writeSync(fd, JSON.stringify(creds, null, 2), null, 'utf8');
    fs.fsyncSync(fd);
    fs.closeSync(fd);
    fs.renameSync(tmpPath, filePath);
  } catch (e) {
    console.error('Failed to save credentials atomically:', e.message);
    const tmpPath = filePath + '.tmp';
    if (fs.existsSync(tmpPath)) {
      try { fs.unlinkSync(tmpPath); } catch (err) {}
    }
  }
};

// ----------------------------------------------------
// 🌐 Helper function for HTTPS Requests
// ----------------------------------------------------
const fetchUrl = (url, headers = {}) => {
  return new Promise((resolve, reject) => {
    const parsedUrl = new URL(url);
    const options = {
      hostname: parsedUrl.hostname,
      path: parsedUrl.pathname + parsedUrl.search,
      method: 'GET',
      timeout: 8000,
      headers: {
        'User-Agent': 'node.js-portfolio-server',
        ...headers
      }
    };

    const req = https.get(options, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        try {
          resolve({ status: res.statusCode, data: JSON.parse(data) });
        } catch (e) {
          resolve({ status: res.statusCode, data: data });
        }
      });
    });

    req.on('timeout', () => {
      req.destroy();
      reject(new Error('Request timeout'));
    });

    req.on('error', (err) => {
      reject(err);
    });
  });
};

// ----------------------------------------------------
// 🛰️ API Routing Endpoints
// ----------------------------------------------------

// 1. Save Settings (Encrypts tokens and stores them in credentials.json)
app.post('/api/settings', (req, res) => {
  const { githubToken, linkedinToken } = req.body;
  
  const creds = readCredentials();

  if (githubToken !== undefined) {
    creds.github = githubToken ? encrypt(githubToken) : null;
  }
  if (linkedinToken !== undefined) {
    creds.linkedin = linkedinToken ? encrypt(linkedinToken) : null;
  }

  saveCredentials(creds);
  res.json({ success: true, message: 'Settings securely encrypted and saved successfully!' });
});

// 2. Get Status (Return whether keys are set, without showing decrypted keys)
app.get('/api/settings/status', (req, res) => {
  const creds = readCredentials();
  res.json({
    githubSet: !!creds.github,
    linkedinSet: !!creds.linkedin,
    // Return the encrypted metadata for verification in frontend UI
    githubMetadata: creds.github ? { iv: creds.github.iv.substring(0, 8) + '...', contentLen: creds.github.content.length } : null,
    linkedinMetadata: creds.linkedin ? { iv: creds.linkedin.iv.substring(0, 8) + '...', contentLen: creds.linkedin.content.length } : null
  });
});

// 3. Clear Credentials
app.post('/api/settings/clear', (req, res) => {
  saveCredentials({ github: null, linkedin: null });
  res.json({ success: true, message: 'API Credentials cleared successfully.' });
});

// 3b. Reset Profile
app.post('/api/kazumi/reset', (req, res) => {
  const profilePath = path.join(getIsaMemoryDir(), 'profile.json');
  try {
    if (fs.existsSync(profilePath)) {
      fs.copyFileSync(profilePath, profilePath + '.bak');
      const data = JSON.parse(fs.readFileSync(profilePath, 'utf8'));
      data.cozy_points = 0;
      data.diary = [];
      if (data._is_default) {
        data._is_default = false;
      }
      
      const tmpPath = profilePath + '.tmp';
      const fd = fs.openSync(tmpPath, 'w');
      fs.writeSync(fd, JSON.stringify(data, null, 2), null, 'utf8');
      fs.fsyncSync(fd);
      fs.closeSync(fd);
      fs.renameSync(tmpPath, profilePath);
    }
    res.json({ success: true, message: 'Profile reset successfully.' });
  } catch (e) {
    res.json({ success: false, error: e.message });
  }
});

// 3c. Sync Profile Progress
app.post('/api/kazumi/profile', (req, res) => {
  const profilePath = path.join(getIsaMemoryDir(), 'profile.json');
  try {
    let profile = {};
    if (fs.existsSync(profilePath)) {
      fs.copyFileSync(profilePath, profilePath + '.bak');
      try {
        profile = JSON.parse(fs.readFileSync(profilePath, 'utf8'));
      } catch (err) {
        if (fs.existsSync(profilePath + '.bak')) {
          try {
            profile = JSON.parse(fs.readFileSync(profilePath + '.bak', 'utf8'));
          } catch (inner) {}
        }
      }
    }
    const body = req.body;
    for (const k in body) {
      profile[k] = body[k];
    }
    if (profile._is_default) {
      profile._is_default = false;
    }
    
    const tmpPath = profilePath + '.tmp';
    const fd = fs.openSync(tmpPath, 'w');
    fs.writeSync(fd, JSON.stringify(profile, null, 2), null, 'utf8');
    fs.fsyncSync(fd);
    fs.closeSync(fd);
    fs.renameSync(tmpPath, profilePath);
    
    res.json({ success: true, message: 'Profile synced successfully.' });
  } catch (e) {
    res.json({ success: false, error: e.message });
  }
});

// 4. Fetch GitHub Repositories (Proxy)
app.get('/api/github/repos', async (req, res) => {
  const creds = readCredentials();
  const token = decrypt(creds.github);

  if (!token) {
    console.log('No GitHub Token saved. Using premium fallback mock repos.');
    return res.json(getFallbackRepos());
  }

  try {
    const headers = { 'Authorization': `token ${token}` };
    const response = await fetchUrl('https://api.github.com/user/repos?sort=updated&per_page=6', headers);
    
    if (response.status === 200 && Array.isArray(response.data)) {
      const mapped = response.data.map(repo => ({
        name: repo.name,
        description: repo.description || 'No description provided.',
        stars: repo.stargazers_count,
        language: repo.language || 'HTML/JS',
        url: repo.html_url,
        isMock: false
      }));
      return res.json(mapped);
    } else {
      console.warn('Failed to fetch from GitHub API. Falling back to mock repos. Code:', response.status);
      return res.json(getFallbackRepos());
    }
  } catch (error) {
    console.error('Error fetching repos:', error.message);
    return res.json(getFallbackRepos());
  }
});

// 5. Fetch LinkedIn Posts (Proxy)
app.get('/api/linkedin/posts', async (req, res) => {
  const creds = readCredentials();
  const token = decrypt(creds.linkedin);

  if (!token) {
    console.log('No LinkedIn Token saved. Using premium fallback mock posts.');
    return res.json(getFallbackPosts());
  }

  try {
    // Attempting to query the LinkedIn URN / share API
    const headers = { 'Authorization': `Bearer ${token}` };
    const response = await fetchUrl('https://api.linkedin.com/v2/shares?q=owners&owners=urn:li:person:me&count=3', headers);
    
    if (response.status === 200 && response.data && Array.isArray(response.data.elements)) {
      const mapped = response.data.elements.map(post => ({
        text: post.text?.text || 'No post content.',
        date: new Date(post.created?.time || Date.now()).toLocaleDateString(),
        url: `https://www.linkedin.com/feed/update/${post.activity || ''}`,
        isMock: false
      }));
      return res.json(mapped);
    } else {
      console.warn('Failed to fetch from LinkedIn API. Falling back to mock posts. Code:', response.status);
      return res.json(getFallbackPosts());
    }
  } catch (error) {
    console.error('Error fetching LinkedIn posts:', error.message);
    return res.json(getFallbackPosts());
  }
});

// ----------------------------------------------------
// 🌟 Premium Mock Fallback Data (For default demo mode)
// ----------------------------------------------------

const getFallbackRepos = () => [
  {
    name: 'kazumi-ai-companion',
    description: 'A sweet, highly empathetic conversational AI assistant running on Windows console with persistent JSON semantic memory, custom zodiac horoscopes, and multi-archetype support.',
    stars: 128,
    language: 'Python',
    url: 'https://github.com',
    isMock: true
  },
  {
    name: 'secure-vault-aes256',
    description: 'A Node.js & Electron dashboard for encrypting sensitive developer keys and configurations locally using secure AES-256-CBC cryptographic tunnels.',
    stars: 84,
    language: 'JavaScript',
    url: 'https://github.com',
    isMock: true
  },
  {
    name: 'starlight-tarot-engine',
    description: 'An interactive React-based digital tarot deck projecting stardust chimes and providing daily alignment horoscopes by pulling from cosmic JSON maps.',
    stars: 52,
    language: 'TypeScript',
    url: 'https://github.com',
    isMock: true
  },
  {
    name: 'quantum-key-distributor',
    description: 'A simulation of secure cryptographic key exchange using C++ and visual graph layers to demonstrate quantum cryptography principles.',
    stars: 42,
    language: 'C++',
    url: 'https://github.com',
    isMock: true
  }
];

const getFallbackPosts = () => [
  {
    text: '🚀 Excited to share my latest open-source project! I built a local secure vault using Node\'s crypto API to encrypt developer credentials on the fly. Security should always be a first-class citizen in full-stack applications. Check it out and let me know your thoughts!',
    date: 'Jun 3, 2026',
    url: 'https://linkedin.com',
    isMock: true
  },
  {
    text: '🌸 Adding a touch of empathy to computing! Just completed a major feature update for Kazumi, my desktop companion bot. By implementing rolling emotional valence, she can now detect a user\'s frustration levels and offer guided breathing exercises or tuck them in with a soft body scan. Interactive companions are the future of cozy computing. 🧸✨',
    date: 'May 28, 2026',
    url: 'https://linkedin.com',
    isMock: true
  },
  {
    text: '🔑 Demystifying AES Encryption: A quick look at why unique Initialization Vectors (IVs) are essential. When you encrypt data with AES-256-CBC, repeating the same key-IV combo creates vulnerable patterns. By generating a fresh, cryptographically strong random IV for every entry, we secure the ciphertext against replay attacks. Simple principles make solid security!',
    date: 'May 15, 2026',
    url: 'https://linkedin.com',
    isMock: true
  }
];

const { spawn } = require('child_process');

// 1. Get Profile
app.get('/api/kazumi/profile', async (req, res) => {
  const profilePath = path.join(getIsaMemoryDir(), 'profile.json');
  let exists = fs.existsSync(profilePath);
  let readPath = profilePath;
  if (!exists && fs.existsSync(profilePath + '.bak')) {
    exists = true;
    readPath = profilePath + '.bak';
  }
  if (!exists) {
    try {
      const result = await callPythonHelper(['profile', 'None']);
      return res.json(result);
    } catch (e) {
      return res.json({ error: 'Failed to initialize profile: ' + e.message });
    }
  }
  try {
    const data = fs.readFileSync(readPath, 'utf8');
    res.json(JSON.parse(data));
  } catch (e) {
    if (readPath === profilePath && fs.existsSync(profilePath + '.bak')) {
      try {
        const data = fs.readFileSync(profilePath + '.bak', 'utf8');
        return res.json(JSON.parse(data));
      } catch (inner) {}
    }
    res.json({ error: 'Failed to read profile: ' + e.message });
  }
});

// 2. Get Chat (Session) - Returns existing chat logs (does not reset)
app.get('/api/kazumi/chat', (req, res) => {
  const chatPath = path.join(getIsaMemoryDir(), 'conversations.json');
  if (!fs.existsSync(chatPath)) {
    return res.json([]);
  }
  try {
    let data = JSON.parse(fs.readFileSync(chatPath, 'utf8'));
    const sessionId = req.query.session_id;
    if (sessionId) {
      data = data.filter(msg => msg.session_id === sessionId);
    }
    res.json(data);
  } catch (e) {
    res.json({ error: 'Failed to read chat: ' + e.message });
  }
});

// 3. Get History (All)
app.get('/api/kazumi/history', (req, res) => {
  const chatPath = path.join(getIsaMemoryDir(), 'conversations.json');
  if (!fs.existsSync(chatPath)) {
    return res.json([]);
  }
  try {
    const data = JSON.parse(fs.readFileSync(chatPath, 'utf8'));
    res.json(data);
  } catch (e) {
    res.json({ error: 'Failed to read history: ' + e.message });
  }
});

// Helper function to call Python helper
const callPythonHelper = (args) => {
  return new Promise((resolve, reject) => {
    const py = spawn('python', [path.join(__dirname, 'kazumi_helper.py'), ...args]);
    let stdout = '';
    let stderr = '';
    
    // Set a safety timeout of 15 seconds to terminate hung subprocesses
    const killTimeout = setTimeout(() => {
      py.kill('SIGTERM');
      reject(new Error('Python execution timeout (15s exceeded)'));
    }, 15000);

    py.stdout.on('data', (data) => { stdout += data; });
    py.stderr.on('data', (data) => { stderr += data; });
    
    py.on('close', (code) => {
      clearTimeout(killTimeout);
      if (code !== 0) {
        reject(new Error(stderr || `Python helper exited with code ${code}`));
      } else {
        try {
          resolve(JSON.parse(stdout));
        } catch (e) {
          reject(new Error('Failed to parse Python helper output: ' + stdout + '\nError: ' + e.message));
        }
      }
    });
  });
};

// 4. Chat Post
app.post('/api/kazumi/chat', async (req, res) => {
  const { message, session_id } = req.body;
  if (!message) {
    return res.json({ success: false, error: 'Message is empty' });
  }
  try {
    const result = await callPythonHelper(['chat', session_id || 'None', message]);
    res.json(result);
  } catch (e) {
    console.error('Chat API Error:', e.message);
    res.json({ success: false, error: e.message });
  }
});

// 5. Inactivity Get
app.get('/api/kazumi/inactivity', async (req, res) => {
  const sessionId = req.query.session_id;
  try {
    const result = await callPythonHelper(['inactivity', sessionId || 'None']);
    res.json(result);
  } catch (e) {
    console.error('Inactivity API Error:', e.message);
    res.json({ success: false, error: e.message });
  }
});

// 6. Get Hugging Face Space Info for visitor duplication link
app.get('/api/space-info', (req, res) => {
  res.json({
    spaceId: process.env.SPACE_ID || null
  });
});

app.listen(PORT, () => {
  console.log(`====================================================`);
  console.log(`🚀 Secure Portfolio Server running on http://localhost:${PORT}`);
  console.log(`🔐 Cryptography key status: Loaded (aes-256-cbc active)`);
  console.log(`====================================================`);
});
