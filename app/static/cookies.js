(function () {
  var key = 'joinly-cookie-notice';
  var banner = document.getElementById('cookie-banner');
  if (!banner) return;
  try {
    if (window.localStorage.getItem(key) === 'dismissed') return;
  } catch (error) {
    return;
  }
  banner.hidden = false;
  var button = document.getElementById('cookie-dismiss');
  if (!button) return;
  button.addEventListener('click', function () {
    try {
      window.localStorage.setItem(key, 'dismissed');
    } catch (error) {
      /* The notice stays hidden for this visit only. */
    }
    banner.hidden = true;
  });
})();
