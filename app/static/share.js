const root = document.getElementById('share-bar');
if (root) {
  const url = root.dataset.url || window.location.href;
  const title = root.dataset.title || document.title;
  const copy = root.querySelector('[data-share-copy]');
  if (copy) {
    copy.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(url);
        copy.textContent = 'Lien copié';
      } catch (error) {
        copy.textContent = 'Copiez le lien à la main';
      }
    });
  }
  const native = root.querySelector('[data-share-native]');
  if (native) {
    if (!navigator.share) native.hidden = true;
    native.addEventListener('click', () => navigator.share({ title, url }));
  }
}
