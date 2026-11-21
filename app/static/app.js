'use strict';

const $ = (id) => document.getElementById(id);
const inspectForm = $('inspect-form');
const urlInput = $('url-input');
const analyzeButton = $('analyze-btn');
const analyzeText = $('analyze-btn-text');
const result = $('result-card');
const globalMessage = $('global-message');
const optionsNode = $('quality-options');
const downloadButton = $('download-btn');
const progressCard = $('progress-card');
let inspected = null;
let currentFormat = 'mp4';
let quality = 'best';
let pollingJob = null;

let activePlatform = 'neutral';
let inspectedUrl = null;
const modeDetails = {
  neutral: {
    title: 'Dans son univers.', subtitle: 'Choisissez votre réseau préféré. VYRA prend ses couleurs et vous accompagne jusqu’au bon format.',
    number: '— / 04', badge: 'TOUS LES RÉSEAUX', heading: 'Votre lien, c’est tout.',
    description: 'Copiez l’URL d’une vidéo publique. Nous nous occupons de repérer le contenu et les formats disponibles.',
    visualTitle: 'Un lien. Mille possibilités.', visualDescription: 'Sélectionnez un réseau pour personnaliser votre espace.',
    wordmark: 'YOUR MEDIA.', placeholder: 'https://youtube.com/watch?v=...', status: 'MODE VYRA', color: '#f7f8f7'
  },
  youtube: {
    title: 'Version YouTube.', subtitle: 'De vos vidéos préférées aux Shorts : retrouvez les formats disponibles dans une expérience rouge et blanche.',
    number: '01 / 04', badge: 'MODE YOUTUBE', heading: 'Votre vidéo YouTube.',
    description: 'Collez le lien d’une vidéo ou d’un Short public, puis sélectionnez le MP4 ou le MP3.',
    visualTitle: 'Cliquez. Regardez. Gardez.', visualDescription: 'Les vidéos et Shorts, dans votre format.',
    wordmark: 'YOUTUBE MODE', placeholder: 'https://www.youtube.com/watch?v=...', status: 'UNIVERS YOUTUBE', color: '#fff9f7'
  },
  instagram: {
    title: 'Version Instagram.', subtitle: 'L’univers des Reels et des vidéos Instagram : un dégradé vibrant qui suit votre sélection.',
    number: '02 / 04', badge: 'MODE INSTAGRAM', heading: 'Votre Reel Instagram.',
    description: 'Collez le lien d’un Reel ou d’une publication vidéo publique. VYRA détecte les formats accessibles.',
    visualTitle: 'Vos Reels. Votre style.', visualDescription: 'Des souvenirs aux idées qui inspirent.',
    wordmark: 'INSTAGRAM MODE', placeholder: 'https://www.instagram.com/reel/...', status: 'UNIVERS INSTAGRAM', color: '#fff7fa'
  },
  tiktok: {
    title: 'Version TikTok.', subtitle: 'Un espace noir et blanc, des touches cyan et rose : l’énergie TikTok jusque dans votre téléchargement.',
    number: '03 / 04', badge: 'MODE TIKTOK', heading: 'Votre vidéo TikTok.',
    description: 'Collez le lien direct d’une vidéo TikTok publique pour afficher les options de téléchargement.',
    visualTitle: 'Le rythme vous appartient.', visualDescription: 'Vidéos courtes. Formats à la carte.',
    wordmark: 'TIKTOK MODE', placeholder: 'https://www.tiktok.com/@createur/video/...', status: 'UNIVERS TIKTOK', color: '#0d0e12'
  },
  snapchat: {
    title: 'Version Snapchat.', subtitle: 'Tout passe au jaune Snap. Pour le moment, seuls certains liens publics pourront être analysés (bêta).',
    number: '04 / 04', badge: 'SNAPCHAT · BÊTA', heading: 'Votre contenu Snapchat.',
    description: 'Essayez un lien vers une Story ou un Spotlight public. Les contenus privés restent inaccessibles.',
    visualTitle: 'Un flash, un souvenir.', visualDescription: 'Stories publiques et Spotlight · expérimental.',
    wordmark: 'SNAPCHAT MODE', placeholder: 'https://www.snapchat.com/spotlight/...', status: 'UNIVERS SNAPCHAT · BÊTA', color: '#fffc00'
  }
};
const platformNames = { youtube: 'YouTube', instagram: 'Instagram', tiktok: 'TikTok', snapchat: 'Snapchat' };

function platformFromLink(rawValue) {
  try {
    const url = new URL(rawValue.trim());
    if (url.protocol !== 'https:' || url.username || url.password || url.port) return null;
    const host = url.hostname.toLowerCase().replace(/\.$/, '');
    const allowed = {
      youtube: ['youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com', 'youtu.be', 'www.youtu.be'],
      instagram: ['instagram.com', 'www.instagram.com', 'm.instagram.com'],
      tiktok: ['tiktok.com', 'www.tiktok.com', 'm.tiktok.com', 'vm.tiktok.com', 'vt.tiktok.com'],
      snapchat: ['snapchat.com', 'www.snapchat.com', 't.snapchat.com']
    };
    return Object.keys(allowed).find(key => allowed[key].includes(host)) || null;
  } catch (_) { return null; }
}

function setTheme(platform, options = {}) {
  const { announce = true } = options;
  if (!modeDetails[platform]) return;
  const change = activePlatform !== platform;
  activePlatform = platform;
  const mode = modeDetails[platform];
  document.documentElement.dataset.theme = platform;
  document.querySelector('meta[name="theme-color"]').setAttribute('content', mode.color);
  document.querySelectorAll('.platform').forEach(button => {
    const isCurrent = platform === button.dataset.platform;
    button.setAttribute('aria-pressed', String(isCurrent));
  });
  $('hero-title-accent').textContent = mode.title;
  $('hero-subtitle').textContent = mode.subtitle;
  $('tool-title').textContent = mode.heading;
  $('tool-description').textContent = mode.description;
  $('tool-badge').lastChild.textContent = ' ' + mode.badge;
  $('visual-headline').textContent = mode.visualTitle;
  $('visual-description').textContent = mode.visualDescription;
  $('visual-wordmark').textContent = mode.wordmark;
  $('visual-mode').textContent = mode.status;
  document.querySelector('.visual-number').textContent = mode.number;
  urlInput.placeholder = mode.placeholder;
  const spotlight = document.querySelector('.spotlight-logo');
  spotlight.classList.toggle('neutral', platform === 'neutral');
  $('spotlight-use').setAttribute('href', `#icon-${platform === 'neutral' ? 'youtube' : platform}`);
  if (change) {
    ['hero-title-accent', 'hero-subtitle'].forEach(id => {
      const node = $(id);
      node.classList.remove('switching');
      void node.offsetWidth;
      node.classList.add('switching');
    });
    spotlight.classList.remove('popping');
    void spotlight.offsetWidth;
    spotlight.classList.add('popping');
  }
  if (announce && change) $('theme-announcement').textContent = platform === 'neutral'
    ? 'Mode général VYRA.' : `Interface ${platformNames[platform]} activée.`;
}
function detectFromInput() {
  const detected = platformFromLink(urlInput.value);
  const message = $('detected-message');
  if (detected) {
    setTheme(detected);
    message.textContent = `${platformNames[detected]} détecté automatiquement dans le lien${detected === 'snapchat' ? ' · Compatibilité expérimentale' : ''}.`;
    message.classList.add('matched');
  } else {
    message.textContent = activePlatform === 'neutral'
      ? 'Un lien YouTube, Instagram, TikTok ou Snapchat public.'
      : `Collez un lien ${platformNames[activePlatform]} public pour commencer.`;
    message.classList.remove('matched');
  }
  if (inspectedUrl !== null && urlInput.value.trim() !== inspectedUrl) {
    inspectedUrl = null;
    inspected = null;
    result.hidden = true;
    progressCard.hidden = true;
    pollingJob = null;
  }
}
document.querySelectorAll('.platform').forEach(button => button.addEventListener('click', () => {
  const selection = button.dataset.platform;
  setTheme(selection);
  const detected = platformFromLink(urlInput.value);
  const message = $('detected-message');
  if (detected && detected !== selection) {
    message.textContent = `Le lien actuel provient de ${platformNames[detected]} : le thème s’ajustera à l’analyse.`;
  } else {
    message.textContent = `Collez un lien ${platformNames[selection]} public pour commencer.`;
  }
  message.classList.remove('matched');
}));
urlInput.addEventListener('input', () => { clearError(); detectFromInput(); });
setTheme('neutral', {announce:false});

function showError(text) {
  globalMessage.textContent = text;
  globalMessage.hidden = false;
  globalMessage.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}
function clearError() {
  globalMessage.hidden = true;
  globalMessage.textContent = '';
}
function setBusy(button, isBusy) {
  button.disabled = isBusy;
  button.setAttribute('aria-busy', isBusy ? 'true' : 'false');
}
async function apiFetch(path, options = {}) {
  let response;
  try {
    response = await fetch(path, {
      ...options,
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) }
    });
  } catch (_) {
    throw new Error('Connexion impossible. Vérifiez que le serveur VYRA est démarré.');
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(typeof data.detail === 'string' ? data.detail : 'Un problème est survenu. Réessayez.');
  }
  return data;
}
function formatTime(total) {
  if (total === null || total === undefined || !Number.isFinite(Number(total))) return '';
  const seconds = Math.floor(Number(total));
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = String(seconds % 60).padStart(2, '0');
  return h > 0 ? `${h}:${String(m).padStart(2, '0')}:${s}` : `${m}:${s}`;
}
function createPill(label, value, highlight = false) {
  const pill = document.createElement('button');
  pill.type = 'button';
  pill.className = 'quality-pill' + (quality === value ? ' selected' : '');
  pill.setAttribute('aria-pressed', String(quality === value));
  pill.append(document.createTextNode(label));
  if (highlight) {
    const tag = document.createElement('small');
    tag.textContent = ' HD';
    pill.append(tag);
  }
  pill.addEventListener('click', () => {
    quality = value;
    updateQualities();
  });
  return pill;
}
function updateQualities() {
  optionsNode.replaceChildren();
  if (!inspected) return;
  const video = currentFormat === 'mp4';
  $('quality-label').textContent = video ? 'Résolution vidéo' : 'Qualité audio';
  $('quality-caption').textContent = video ? 'Selon la vidéo d’origine' : 'Conversion MP3 · 192 kb/s cible';
  $('format-note').textContent = video
    ? 'Seules les résolutions détectées sont proposées. Le MP4 inclut le son lorsque la source en contient.'
    : 'Le MP3 conserve uniquement l’audio. Une conversion à 192 kb/s n’améliore pas la qualité de la source.';
  if (!video) {
    quality = 'audio';
    optionsNode.append(createPill('MP3 · 192 kb/s', 'audio'));
    return;
  }
  const heights = inspected.heights || [];
  if (!['best', ...heights.map(String)].includes(quality)) quality = 'best';
  optionsNode.append(createPill('Meilleure', 'best'));
  for (const h of heights) optionsNode.append(createPill(`${h}p`, String(h), h >= 720));
}
function setFormat(fmt) {
  currentFormat = fmt;
  quality = fmt === 'mp4' ? 'best' : 'audio';
  document.querySelectorAll('.format-tab').forEach(tab => {
    const selected = tab.dataset.format === fmt;
    tab.classList.toggle('active', selected);
    tab.setAttribute('aria-pressed', String(selected));
  });
  updateQualities();
}
function renderResult(data) {
  inspected = data;
  inspectedUrl = urlInput.value.trim();
  const network = String(data.platform || '').toLowerCase();
  const fromResponse = ['youtube', 'instagram', 'tiktok', 'snapchat'].find(k => network.includes(k));
  if (fromResponse) setTheme(fromResponse);
  $('result-platform').textContent = data.platform || 'Vidéo';
  $('video-title').textContent = data.title || 'Vidéo sans titre';
  $('video-creator').textContent = data.creator || '';
  $('video-duration').textContent = formatTime(data.duration);
  const count = (data.heights || []).length;
  $('quality-count').textContent = count ? `${count} résolution${count > 1 ? 's' : ''} détectée${count > 1 ? 's' : ''}` : 'Qualité automatique';
  const image = $('video-thumbnail');
  image.removeAttribute('src');
  image.hidden = true;
  if (data.thumbnail) {
    image.onload = () => { image.hidden = false; };
    image.onerror = () => { image.hidden = true; };
    image.src = data.thumbnail;
  }
  result.hidden = false;
  progressCard.hidden = true;
  setBusy(downloadButton, false);
  setFormat('mp4');
  result.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

inspectForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  clearError();
  const url = urlInput.value.trim();
  if (!url) return showError('Collez d’abord le lien vers une vidéo.');
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== 'https:') return showError('Utilisez un lien public commençant par https://');
  } catch (_) {
    return showError('Ce lien est invalide. Copiez une URL complète.');
  }
  const detected = platformFromLink(url);
  if (detected) setTheme(detected);
  inspected = null;
  inspectedUrl = null;
  result.hidden = true;
  progressCard.hidden = true;
  pollingJob = null;
  setBusy(analyzeButton, true);
  analyzeText.textContent = 'Analyse en cours…';
  try {
    const data = await apiFetch('/api/inspect', { method: 'POST', body: JSON.stringify({ url }) });
    if (urlInput.value.trim() === url) renderResult(data);
  } catch (e) {
    showError(e.message);
  } finally {
    setBusy(analyzeButton, false);
    analyzeText.textContent = 'Analyser le lien';
  }
});

document.querySelectorAll('.format-tab').forEach(tab => tab.addEventListener('click', () => setFormat(tab.dataset.format)));

$('paste-btn').addEventListener('click', async () => {
  try {
    const text = await navigator.clipboard.readText();
    if (!text) return showError('Le presse-papiers est vide.');
    urlInput.value = text.trim();
    detectFromInput();
    urlInput.focus();
    clearError();
  } catch (_) {
    showError('Le collage automatique n’est pas autorisé ici. Utilisez Ctrl+V ou Cmd+V.');
  }
});

async function poll(id) {
  if (pollingJob !== id) return;
  try {
    const job = await apiFetch(`/api/jobs/${encodeURIComponent(id)}`);
    $('progress-description').textContent = job.message || 'En cours…';
    $('progress-bar').style.width = `${Math.max(0, Math.min(100, job.progress || 0))}%`;
    $('progress-percent').textContent = `${job.progress || 0} %`;
    if (job.status === 'ready') {
      $('progress-title').textContent = 'Votre fichier est prêt !';
      $('progress-description').textContent = 'Cliquez ci-dessous pour enregistrer le fichier.';
      $('file-link').href = job.download_url;
      $('file-link').hidden = false;
      pollingJob = null;
      setBusy(downloadButton, false);
      return;
    }
    if (job.status === 'error') {
      $('progress-title').textContent = 'Téléchargement impossible';
      $('progress-description').textContent = job.error || 'Le traitement a échoué.';
      pollingJob = null;
      setBusy(downloadButton, false);
      return;
    }
    window.setTimeout(() => poll(id), 1000);
  } catch (e) {
    $('progress-description').textContent = e.message;
    pollingJob = null;
    setBusy(downloadButton, false);
  }
}

downloadButton.addEventListener('click', async () => {
  if (!inspected) return;
  clearError();
  setBusy(downloadButton, true);
  $('file-link').hidden = true;
  $('progress-title').textContent = 'Préparation du fichier';
  $('progress-description').textContent = 'Création de votre téléchargement…';
  $('progress-bar').style.width = '0%';
  $('progress-percent').textContent = '0 %';
  progressCard.hidden = false;
  progressCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  try {
    const job = await apiFetch('/api/download', {
      method: 'POST',
      body: JSON.stringify({ inspection_id: inspected.inspection_id, format: currentFormat, quality })
    });
    pollingJob = job.job_id;
    poll(job.job_id);
  } catch (e) {
    progressCard.hidden = true;
    showError(e.message);
    setBusy(downloadButton, false);
  }
});
