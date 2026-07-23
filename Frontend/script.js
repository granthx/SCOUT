/* ──────────────────────────────────────────────
   SCOUT — script.js
   Ferrari Design System
────────────────────────────────────────────── */

/* Scroll reveal using IntersectionObserver */
function initReveal() {
  const reveals = document.querySelectorAll('.reveal');
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1 });

  reveals.forEach(el => observer.observe(el));
}

let currentSessionId = null;

/* Real Chat Integration */
function initChat() {
  const input = document.querySelector('.chat-input');
  const send  = document.querySelector('.chat-send');
  if (!input || !send) return;

  input.removeAttribute('readonly');

  const handleSend = async () => {
    const message = input.value.trim();
    if (!message) return;
    
    input.value = '';
    input.placeholder = 'Processing...';
    
    const chatBody = document.querySelector('.chat-body');
    // Clear the existing static demo items
    chatBody.innerHTML = '';
    
    // 1. Add user message
    const userMsg = document.createElement('div');
    userMsg.className = 'msg-user';
    userMsg.textContent = message;
    chatBody.appendChild(userMsg);
    
    // 2. Add thinking row container
    const thinkingRow = document.createElement('div');
    thinkingRow.className = 'thinking-row';
    chatBody.appendChild(thinkingRow);
    
    // 3. Prepare AI reply container (hidden initially)
    const aiReply = document.createElement('div');
    aiReply.className = 'ai-reply body-md';
    aiReply.style.display = 'none';
    const aiCursor = document.createElement('span');
    aiCursor.className = 'ai-cursor';
    aiReply.appendChild(aiCursor);

    try {
      // Determine API URL based on environment
      const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
      // Replace this placeholder with your actual Railway URL once you have it
      const API_BASE_URL = isLocal ? 'http://localhost:8000' : 'https://scout-five-pied.vercel.app';
      
      const res = await fetch(`${API_BASE_URL}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: message, session_id: currentSessionId })
      });

      if (!res.ok) {
        throw new Error('API error: ' + res.statusText);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop(); // Keep partial line in buffer

        let eventType = null;
        for (let i = 0; i < lines.length; i++) {
          const line = lines[i];
          if (line.startsWith('event:')) {
            eventType = line.substring(6).trim();
          } else if (line.startsWith('data:')) {
            const dataStr = line.substring(5).trim();
            if (dataStr && eventType) {
              const payload = JSON.parse(dataStr);
              handleEvent(eventType, payload, thinkingRow, aiReply, chatBody);
            }
          }
        }
      }
    } catch (err) {
      console.error('Chat request failed:', err);
      const errorMsg = document.createElement('div');
      errorMsg.className = 'ai-reply body-md';
      errorMsg.style.color = 'var(--primary)';
      errorMsg.textContent = 'Error connecting to the backend API.';
      chatBody.appendChild(errorMsg);
    } finally {
      input.placeholder = 'Ask about any product…';
    }
  };

  send.addEventListener('click', handleSend);
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter') handleSend();
  });
}

function handleEvent(type, payload, thinkingRow, aiReply, chatBody) {
  const data = payload.data;
  
  if (type === 'thinking' || type === 'intent') {
    const badge = document.createElement('div');
    badge.className = 'thinking-badge';
    badge.innerHTML = `
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
        <circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>
      </svg>
      ${type === 'intent' ? 'PARSED INTENT' : (data.message || 'THINKING...')}
    `;
    thinkingRow.appendChild(badge);
  } 
  else if (type === 'products') {
    let productsGrid = chatBody.querySelector('.products-grid');
    if (!productsGrid) {
      productsGrid = document.createElement('div');
      productsGrid.className = 'products-grid';
      // Insert before aiReply if it's already in the DOM, otherwise append
      if (aiReply.parentNode) {
        chatBody.insertBefore(productsGrid, aiReply);
      } else {
        chatBody.appendChild(productsGrid);
      }
    }
    const products = data.products || data;
    if (Array.isArray(products)) {
      productsGrid.innerHTML = products.map(p => {
        const score = p.score || 0;
        const rating = p.rating || 0;
        const stars = '★'.repeat(Math.round(rating)) + '☆'.repeat(5 - Math.round(rating));
        const productUrl = p.affiliate_url || p.product_url || '#';
        return `
          <a href="${productUrl}" target="_blank" rel="noopener noreferrer" class="product-card-link" style="text-decoration:none;color:inherit;">
            <div class="product-card">
              <span class="product-platform">${p.platform}</span>
              <span class="product-name">${p.title}</span>
              <span class="product-price">${p.price_display}</span>
              <div class="score-bar-wrap">
                <div class="score-bar"><div class="score-fill" style="width:${score}%"></div></div>
                <span class="score-label">${score ? Math.round(score) : 0} / 100</span>
              </div>
              <div class="product-meta">
                <span class="product-stars">${stars}</span> ${rating ? rating.toFixed(1) : 'N/A'}
                <span style="margin-left:auto" class="product-delivery">▸ ${(p.delivery_label || 'STANDARD').toUpperCase()}</span>
              </div>
            </div>
          </a>
        `;
      }).join('');
    }
  } 
  else if (type === 'text') {
    if (!aiReply.parentNode) {
      chatBody.appendChild(aiReply);
    }
    aiReply.style.display = 'block';
    const textNode = document.createTextNode(data);
    const cursor = aiReply.querySelector('.ai-cursor');
    if (cursor) {
      aiReply.insertBefore(textNode, cursor);
    } else {
      aiReply.appendChild(textNode);
    }
  } 
  else if (type === 'done') {
    if (payload.session_id) {
      currentSessionId = payload.session_id;
    }
    const cursor = aiReply.querySelector('.ai-cursor');
    if (cursor) cursor.remove();
  }
}

/* Init on DOM ready */
document.addEventListener('DOMContentLoaded', () => {
  initReveal();
  initChat();
});
