(() => {
  'use strict';
  const root = document.getElementById('joinly-chat');
  if (!root) return;
  const panel = document.getElementById('chat-panel');
  const toggle = document.getElementById('chat-toggle');
  const close = document.getElementById('chat-close');
  const form = document.getElementById('chat-form');
  const input = document.getElementById('chat-input');
  const send = document.getElementById('chat-send');
  const consent = document.getElementById('chat-consent');
  const profile = document.getElementById('chat-profile');
  const bookings = document.getElementById('chat-bookings');
  const log = document.getElementById('chat-messages');
  const status = document.getElementById('chat-status');
  const clear = document.getElementById('chat-clear');
  const suggestions = document.getElementById('chat-suggestions');
  const greeting = log.firstElementChild.cloneNode(true);
  let history = [];
  let busy = false;
  let controller = null;
  let generation = 0;

  function openChat(open) {
    panel.hidden = !open;
    toggle.setAttribute('aria-expanded', String(open));
    toggle.setAttribute('aria-label', open ? 'Fermer l’assistant Joinly' : 'Ouvrir l’assistant Joinly');
    if (open) (consent.checked ? input : consent).focus();
    else toggle.focus();
  }
  toggle.addEventListener('click', () => openChat(panel.hidden));
  close.addEventListener('click', () => openChat(false));
  root.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !panel.hidden) { event.preventDefault(); openChat(false); }
  });
  input.addEventListener('keydown', event => {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      form.requestSubmit();
    }
  });

  function addMessage(text, role, links = {}) {
    const bubble = document.createElement('div');
    bubble.className = 'chat-message chat-' + role;
    const speaker = document.createElement('span');
    speaker.className = 'chat-speaker';
    speaker.textContent = role === 'user' ? 'Vous' : 'Joinly';
    const body = document.createElement('p');
    // Model output is always text. Only server-allowlisted internal links become anchors.
    const regex = /\[([^\]\n]{1,180})\]\((\/[^\s)]+)\)/g;
    let offset = 0;
    for (const match of text.matchAll(regex)) {
      body.append(document.createTextNode(text.slice(offset, match.index)));
      if (Object.hasOwn(links, match[2])) {
        const anchor = document.createElement('a');
        anchor.textContent = match[1];
        anchor.setAttribute('href', match[2]);
        body.append(anchor);
      } else body.append(document.createTextNode(match[1]));
      offset = match.index + match[0].length;
    }
    body.append(document.createTextNode(text.slice(offset)));
    bubble.append(speaker, body);
    log.append(bubble);
    log.scrollTop = log.scrollHeight;
  }
  function setBusy(value) {
    busy = value;
    send.disabled = value;
    input.disabled = value;
    log.setAttribute('aria-busy', String(value));
    send.textContent = value ? '…' : '↑';
  }
  function reset() {
    generation += 1;
    if (controller) controller.abort();
    history = [];
    log.replaceChildren(greeting.cloneNode(true));
    input.value = '';
    suggestions.hidden = false;
    setBusy(false);
    status.textContent = 'Conversation effacée de cette page.';
  }
  clear.addEventListener('click', reset);
  // Revoking either consent also removes previously shared context from local history.
  consent.addEventListener('change', () => { if (!consent.checked) reset(); });
  if (profile) profile.addEventListener('change', reset);
  if (bookings) bookings.addEventListener('change', reset);
  suggestions.addEventListener('click', event => {
    const button = event.target.closest('[data-prompt]');
    if (!button || busy) return;
    input.value = button.dataset.prompt;
    if (consent.checked) form.requestSubmit();
    else { consent.focus(); status.textContent = 'Acceptez l’envoi des messages, puis cliquez sur Envoyer.'; }
  });
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (busy || !consent.checked || !input.value.trim()) return;
    const message = input.value.trim();
    const current = ++generation;
    const previous = history.slice(-6).map(item => ({role:item.role, content:item.content.slice(0,1200)}));
    addMessage(message, 'user');
    input.value = '';
    suggestions.hidden = true;
    setBusy(true);
    status.textContent = 'Joinly prépare une réponse…';
    controller = new AbortController();
    const activeController = controller;
    const timer = window.setTimeout(() => activeController.abort(), 23000);
    try {
      const response = await fetch(root.dataset.endpoint, {
        method:'POST', credentials:'same-origin', signal:controller.signal,
        headers:{'Content-Type':'application/json', 'X-CSRFToken':form.elements.csrf_token.value},
        body:JSON.stringify({message, history:previous, consent:true, use_profile:Boolean(profile && profile.checked), use_bookings:Boolean(bookings && bookings.checked)})
      });
      const data = await response.json().catch(() => ({}));
      if (current !== generation) return;
      if (!response.ok || typeof data.answer !== 'string') {
        throw new Error(data.error || (response.status === 400 ? 'Session expirée. Rechargez la page puis réessayez.' : 'Le service est indisponible. Réessayez dans un instant.'));
      }
      addMessage(data.answer, 'assistant', data.links || {});
      for (const action of (data.actions || [])) {
        if (!data.links || !Object.hasOwn(data.links, action.url)) continue;
        const link = document.createElement('a');
        link.className = 'button small chat-booking-action';
        link.href = action.url;
        link.textContent = action.label;
        log.lastElementChild.append(link);
      }
      log.scrollTop = log.scrollHeight;
      history = [...previous, {role:'user',content:message}, {role:'assistant',content:data.answer}].slice(-8);
      status.textContent = data.bookings_access ? 'Accès à vos inscriptions autorisé pour cet échange.' : (data.profile_used ? 'Réponse avec vos préférences autorisées.' : 'Réponse avec le contexte public de Joinly.');
    } catch (error) {
      if (current !== generation) return;
      addMessage(error.name === 'AbortError' ? 'La réponse prend trop de temps. Réessayez dans un instant.' : error.message, 'assistant');
      input.value = message;
      status.textContent = 'Votre message est prêt à être renvoyé.';
    } finally {
      window.clearTimeout(timer);
      if (current === generation) { setBusy(false); input.focus(); }
    }
  });
})();
