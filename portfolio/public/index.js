// ----------------------------------------------------
// ⚙️ SECURE PORTFOLIO CLIENT ENGINE (VANILLA JS)
// ----------------------------------------------------

document.addEventListener('DOMContentLoaded', () => {
  // UI Elements
  const settingsForm = document.getElementById('settingsForm');
  const clearBtn = document.getElementById('clearBtn');
  const githubTokenInput = document.getElementById('githubToken');
  const linkedinTokenInput = document.getElementById('linkedinToken');
  
  const reposGrid = document.getElementById('reposGrid');
  const postsGrid = document.getElementById('postsGrid');
  
  const githubStatus = document.getElementById('githubStatus');
  const linkedinStatus = document.getElementById('linkedinStatus');
  
  const githubInd = document.getElementById('githubInd');
  const linkedinInd = document.getElementById('linkedinInd');
  
  const githubIv = document.getElementById('githubIv');
  const githubLen = document.getElementById('githubLen');
  const linkedinIv = document.getElementById('linkedinIv');
  const linkedinLen = document.getElementById('linkedinLen');

  const toast = document.getElementById('toast');

  // Helper: Show Toast Notification
  const showToast = (message, isError = false) => {
    toast.textContent = message;
    toast.style.borderColor = isError ? 'rgba(239, 68, 68, 0.4)' : 'rgba(0, 229, 255, 0.3)';
    toast.classList.add('show');
    setTimeout(() => {
      toast.classList.remove('show');
    }, 3000);
  };

  // Helper: Get Language Class
  const getLangClass = (lang) => {
    if (!lang) return 'default';
    const clean = lang.toLowerCase();
    if (clean === 'python') return 'python';
    if (clean === 'javascript') return 'javascript';
    if (clean === 'typescript') return 'typescript';
    if (clean === 'c++' || clean === 'cpp') return 'cpp';
    return 'default';
  };

  // 1. Fetch & Update Credentials Encryption Status
  const updateCredentialsStatus = async () => {
    try {
      const res = await fetch('/api/settings/status');
      if (!res.ok) throw new Error('API offline');
      const data = await res.json();
      
      // Update GitHub status
      if (data.githubSet) {
        githubStatus.textContent = 'Configured & Active';
        githubStatus.style.color = 'rgb(0, 229, 255)';
        githubInd.classList.add('active');
        document.getElementById('githubMeta').style.display = 'flex';
        githubIv.textContent = data.githubMetadata?.iv || '--';
        githubLen.textContent = data.githubMetadata?.contentLen || '0';
      } else {
        githubStatus.textContent = 'Not Configured';
        githubStatus.style.color = '';
        githubInd.classList.remove('active');
        document.getElementById('githubMeta').style.display = 'none';
      }
      
      // Update LinkedIn status
      if (data.linkedinSet) {
        linkedinStatus.textContent = 'Configured & Active';
        linkedinStatus.style.color = 'rgb(187, 77, 240)';
        linkedinInd.classList.add('active');
        document.getElementById('linkedinMeta').style.display = 'flex';
        linkedinIv.textContent = data.linkedinMetadata?.iv || '--';
        linkedinLen.textContent = data.linkedinMetadata?.contentLen || '0';
      } else {
        linkedinStatus.textContent = 'Not Configured';
        linkedinStatus.style.color = '';
        linkedinInd.classList.remove('active');
        document.getElementById('linkedinMeta').style.display = 'none';
      }
    } catch (e) {
      console.warn('Credentials status check failed:', e);
      githubStatus.textContent = 'Unknown (Offline)';
      linkedinStatus.textContent = 'Unknown (Offline)';
    }
  };

  // 2. Fetch and render GitHub Repositories
  const loadRepos = async () => {
    try {
      const res = await fetch('/api/github/repos');
      if (!res.ok) throw new Error('API offline');
      const repos = await res.json();
      
      if (repos && repos.length > 0) {
        reposGrid.innerHTML = '';
        repos.forEach(repo => {
          const langClass = getLangClass(repo.language);
          const mockBadge = repo.isMock ? ' <span class="badge badge-accent" style="font-size:0.65rem; padding:0.1rem 0.4rem; margin-left:0.4rem;">Demo</span>' : '';
          
          reposGrid.innerHTML += `
            <div class="glass-card repo-card">
              <div class="repo-main">
                <h4 class="repo-name">${repo.name}${mockBadge}</h4>
                <p class="repo-desc">${repo.description}</p>
              </div>
              <div class="repo-footer">
                <div class="repo-stats">
                  <span class="repo-stars"><i class="fa-solid fa-star"></i> ${repo.stars}</span>
                  <span class="lang-badge lang-${langClass}">
                    <span class="lang-dot"></span>${repo.language || 'HTML/JS'}
                  </span>
                </div>
                <a href="${repo.url}" target="_blank" class="repo-link">View Repo <i class="fa-solid fa-arrow-up-right-from-square"></i></a>
              </div>
            </div>
          `;
        });
      } else {
        reposGrid.innerHTML = `<p class="text-muted" style="grid-column: 1/-1; text-align: center; padding: 2rem;">No repositories found.</p>`;
      }
    } catch (e) {
      console.error('Failed to load GitHub repos:', e);
      reposGrid.innerHTML = `<p class="text-muted" style="grid-column: 1/-1; text-align: center; padding: 2rem;">Unable to load projects database. Server might be offline.</p>`;
    }
  };

  // 3. Fetch and render LinkedIn posts
  const loadPosts = async () => {
    try {
      const res = await fetch('/api/linkedin/posts');
      if (!res.ok) throw new Error('API offline');
      const posts = await res.json();
      
      if (posts && posts.length > 0) {
        postsGrid.innerHTML = '';
        posts.forEach(post => {
          const mockBadge = post.isMock ? ' <span class="badge badge-accent" style="font-size:0.65rem; padding:0.1rem 0.4rem; margin-left:0.4rem;">Demo</span>' : '';
          
          postsGrid.innerHTML += `
            <div class="glass-card post-card">
              <p class="post-body">${post.text}</p>
              <div class="post-footer">
                <span class="post-date"><i class="fa-regular fa-calendar-days"></i> ${post.date}${mockBadge}</span>
                <a href="${post.url}" target="_blank" class="post-link">Read Post <i class="fa-solid fa-arrow-up-right-from-square"></i></a>
              </div>
            </div>
          `;
        });
      } else {
        postsGrid.innerHTML = `<p class="text-muted" style="grid-column: 1/-1; text-align: center; padding: 2rem;">No activity log posts found.</p>`;
      }
    } catch (e) {
      console.error('Failed to load LinkedIn posts:', e);
      postsGrid.innerHTML = `<p class="text-muted" style="grid-column: 1/-1; text-align: center; padding: 2rem;">Unable to load activity logs feed. Server might be offline.</p>`;
    }
  };

  // 4. Handle settings submission (encrypt and save tokens)
  if (settingsForm) {
    settingsForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      
      const githubToken = githubTokenInput.value.trim();
      const linkedinToken = linkedinTokenInput.value.trim();
      
      if (!githubToken && !linkedinToken) {
        showToast('Please enter at least one API token to save.', true);
        return;
      }
      
      try {
        const res = await fetch('/api/settings', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ githubToken, linkedinToken })
        });
        
        const data = await res.json();
        if (data.success) {
          showToast(data.message || 'Credentials securely encrypted & saved.');
          githubTokenInput.value = '';
          linkedinTokenInput.value = '';
          
          // Refresh credentials status and re-fetch feeds
          await updateCredentialsStatus();
          await loadRepos();
          await loadPosts();
        } else {
          throw new Error(data.error || 'Server error');
        }
      } catch (err) {
        console.error('Save credentials failed:', err);
        showToast('Failed to save settings. Please try again.', true);
      }
    });
  }

  // 5. Handle clear settings request
  if (clearBtn) {
    clearBtn.addEventListener('click', async () => {
      if (!confirm('Are you sure you want to clear and delete all saved credentials? This will wipe the encrypted local vault.')) {
        return;
      }
      
      try {
        const res = await fetch('/api/settings/clear', {
          method: 'POST'
        });
        const data = await res.json();
        if (data.success) {
          showToast(data.message || 'Credentials deleted successfully.');
          
          // Refresh credentials status and re-fetch feeds
          await updateCredentialsStatus();
          await loadRepos();
          await loadPosts();
        } else {
          throw new Error(data.error || 'Server error');
        }
      } catch (err) {
        console.error('Clear credentials failed:', err);
        showToast('Failed to clear credentials. Please try again.', true);
      }
    });
  }

  // Initialize
  const init = async () => {
    await updateCredentialsStatus();
    await loadRepos();
    await loadPosts();
  };

  init();
});
