document.querySelectorAll('[data-interest-grid]').forEach((grid) => {
  const form = grid.closest('form');
  if (!form) return;
  const minimum = Number(grid.dataset.minimum || 0);
  const button = form.querySelector('[data-interest-submit]');
  const status = form.querySelector('[data-interest-count]');
  const refresh = () => {
    const count = grid.querySelectorAll('input[type="checkbox"]:checked').length;
    if (status) {
      const label = count > 1 ? `${count} sélectionnés` : `${count} sélectionné`;
      status.textContent = minimum ? `${label} · ${minimum} minimum` : label;
    }
    if (button && minimum) button.disabled = count < minimum;
  };
  grid.addEventListener('change', refresh);
  refresh();
});
