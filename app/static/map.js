const box = document.getElementById('activity-map');
if (box && window.L) {
  const latitude = Number(box.dataset.lat);
  const longitude = Number(box.dataset.lng);
  const map = L.map(box, { scrollWheelZoom: false }).setView([latitude, longitude], 15);
  // Official tile.openstreetmap.org blocks browser requests with no Referer.
  // CARTO public raster tiles now require an API key. OSM France serves
  // the same data with attribution and works with or without a Referer.
  L.tileLayer('https://{s}.tile.openstreetmap.fr/osmfr/{z}/{x}/{y}.png', {
    maxZoom: 20,
    subdomains: 'abc',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://www.openstreetmap.fr/">OSM France</a>',
  }).addTo(map);
  L.marker([latitude, longitude]).addTo(map);
}
