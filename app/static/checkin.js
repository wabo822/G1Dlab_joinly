const form = document.getElementById('checkin-form');
const input = document.getElementById('ticket-code');
const camera = document.getElementById('checkin-camera');
let sent = false;

function submitCode(value) {
  if (sent || !value || !form || !input) return;
  sent = true;
  input.value = value;
  form.submit();
}

async function startBarcodeDetector() {
  if (!('BarcodeDetector' in window) || !navigator.mediaDevices) return false;
  const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
  const video = document.createElement('video');
  video.setAttribute('playsinline', '');
  video.srcObject = stream;
  camera.appendChild(video);
  await video.play();
  const detector = new BarcodeDetector({ formats: ['qr_code'] });
  const tick = async () => {
    if (sent) return;
    try {
      const codes = await detector.detect(video);
      if (codes.length) {
        submitCode(codes[0].rawValue);
        return;
      }
    } catch (error) {
      return;
    }
    requestAnimationFrame(tick);
  };
  tick();
  return true;
}

async function startHtml5() {
  if (!window.Html5Qrcode) return;
  const scanner = new Html5Qrcode('checkin-camera');
  await scanner.start({ facingMode: 'environment' }, { fps: 8, qrbox: 220 }, submitCode);
}

if (camera) {
  startBarcodeDetector().then((started) => {
    if (!started) startHtml5();
  }).catch(() => startHtml5());
}
