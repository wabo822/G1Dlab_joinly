const box = document.getElementById('activity-map');
if (box && window.L) {
  const latitude = Number(box.dataset.lat);
  const longitude = Number(box.dataset.lng);
  const map = L.map(box, { scrollWheelZoom: false }).setView([latitude, longitude], 15);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap',
  }).addTo(map);
  L.marker([latitude, longitude]).addTo(map);
}
