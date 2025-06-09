const form = document.getElementById('chat-form');
const box = document.getElementById('chat-box');
const autoBtn = document.getElementById('auto-btn');
const tokenInput = document.querySelector('input[name="csrf_token"]');
const csrfToken = tokenInput ? tokenInput.value : '';

const sendUrl = typeof TELEGRAM !== 'undefined' ? `/send/${CHAT_ID}` : '/send';
const autoUrl = typeof TELEGRAM !== 'undefined' ? `/auto_reply/${CHAT_ID}` : '/auto_reply';

form.addEventListener('submit', async e => {
  e.preventDefault();
  const message = document.getElementById('message').value;
  const resp = await fetch(sendUrl, {
    method: 'POST',
    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
    body: new URLSearchParams({message, csrf_token: csrfToken})
  });
  const data = await resp.json();
  const userDiv = document.createElement('div');
  userDiv.className = 'msg user';
  userDiv.textContent = message;
  box.appendChild(userDiv);
  if (data.reply) {
    const botDiv = document.createElement('div');
    botDiv.className = 'msg assistant';
    botDiv.textContent = data.reply;
    box.appendChild(botDiv);
  }
  form.reset();
});

if (autoBtn) {
  autoBtn.addEventListener('click', async () => {
    const resp = await fetch(autoUrl, {
      method: 'POST',
      headers: {'Content-Type': 'application/x-www-form-urlencoded'},
      body: new URLSearchParams({csrf_token: csrfToken})
    });
    const data = await resp.json();
    const botDiv = document.createElement('div');
    botDiv.className = 'msg assistant';
    botDiv.textContent = data.reply;
    box.appendChild(botDiv);
  });
}
