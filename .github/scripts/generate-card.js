#!/usr/bin/env node
/**
 * Guild Card generator
 * ---------------------
 * Fetches public GitHub data for a user, computes RPG-style stats, and
 * renders a self-contained SVG "adventurer card" — no browser required.
 * Also drops the card into README.md between two marker comments.
 *
 * Env vars:
 *   GITHUB_USERNAME   - github login to summon (falls back to GITHUB_REPOSITORY owner)
 *   OUTPUT_SVG        - output path for the card (default: guild-card.svg)
 *   README_PATH       - path to the README to update (default: README.md)
 *
 * Requires Node 18+ (uses global fetch).
 */

const fs = require('fs');
const path = require('path');

const USERNAME =
  process.env.GITHUB_USERNAME ||
  process.argv[2] ||
  (process.env.GITHUB_REPOSITORY ? process.env.GITHUB_REPOSITORY.split('/')[0] : null);

const OUTPUT_SVG = process.env.OUTPUT_SVG || 'guild-card.svg';

if (!USERNAME) {
  console.error('No username provided. Set GITHUB_USERNAME or pass one as an argument.');
  process.exit(1);
}

// ---------- lore data (same rules as the web version) ----------

const LANGUAGE_CLASSES = {
  JavaScript: ['Arcane Scripter', 'one who bends logic into spells the browser obeys'],
  TypeScript: ['Runeforged Tactician', 'a scripter who binds every spell with a contract'],
  Python: ['Serpent Sage', 'keeper of quiet, readable incantations'],
  Java: ['Iron Paladin', 'clad in verbose but unbreakable armor'],
  'C++': ['Dragonsmith', 'forger of engines too fast to question'],
  C: ['Stonebound Artificer', "works closest to the machine's bones"],
  'C#': ['Spellblade of the Twin Towers', 'balances elegance and raw force'],
  Go: ['Windrunner Scout', 'travels light, concurrent, and fast'],
  Rust: ['Ember Warden', 'refuses to let a single spell misfire'],
  Ruby: ['Bloodgem Alchemist', 'brews expressive, joyful transmutations'],
  PHP: ['Wandering Merchant', "has kept the realm's markets running for decades"],
  HTML: ['Glyph Weaver', 'shapes the structure all other magic rests on'],
  CSS: ['Tapestry Warden', "paints the realm's every visible surface"],
  Swift: ['Sky Corsair', 'sails the walled gardens of a single kingdom'],
  Kotlin: ['Shadow Ranger', 'moves between old and new realms unseen'],
  Shell: ['Ritual Caller', 'automates the incantations others repeat by hand'],
  Vue: ['Reactive Oracle', 'reads the state of the world before it changes'],
  Dart: ['Twinflame Courier', 'delivers one spell to many kingdoms at once'],
};
const DEFAULT_CLASS = ['Wandering Novice', 'has not yet chosen a discipline — every path remains open'];

const RANK_MEANING = {
  SS: 'a name spoken of in every guild hall',
  S: "trusted with the realm's hardest contracts",
  A: 'a seasoned hand few dare challenge',
  B: 'reliable in most any expedition',
  C: 'proven capable, still climbing',
  D: 'newly licensed, eager for work',
  E: 'fresh from the guild gate',
  F: 'yet to take a first quest',
};

function pickClass(topLanguage) {
  return LANGUAGE_CLASSES[topLanguage] || DEFAULT_CLASS;
}

function rankFromTotal(total) {
  if (total >= 340) return 'SS';
  if (total >= 280) return 'S';
  if (total >= 220) return 'A';
  if (total >= 160) return 'B';
  if (total >= 100) return 'C';
  if (total >= 50) return 'D';
  if (total >= 20) return 'E';
  return 'F';
}

function yearsSince(dateStr) {
  const then = new Date(dateStr);
  const now = new Date();
  return (now - then) / (1000 * 60 * 60 * 24 * 365.25);
}

// ---------- GitHub data fetching ----------

async function ghFetch(url) {
  const res = await fetch(url, {
    headers: {
      'User-Agent': 'guild-card-generator',
      Accept: 'application/vnd.github+json',
      ...(process.env.GH_TOKEN ? { Authorization: `Bearer ${process.env.GH_TOKEN}` } : {}),
    },
  });
  return res;
}

async function fetchUser(username) {
  const res = await ghFetch(`https://api.github.com/users/${encodeURIComponent(username)}`);
  if (res.status === 404) throw new Error(`No such GitHub user: ${username}`);
  if (!res.ok) throw new Error(`GitHub API error ${res.status} fetching user`);
  return res.json();
}

async function fetchAllRepos(username) {
  const repos = [];
  let page = 1;
  while (page <= 5) {
    const res = await ghFetch(
      `https://api.github.com/users/${encodeURIComponent(username)}/repos?per_page=100&page=${page}&sort=updated`
    );
    if (!res.ok) break;
    const data = await res.json();
    repos.push(...data);
    if (data.length < 100) break;
    page++;
  }
  return repos;
}

async function fetchTotalContributions(username) {
  try {
    const res = await fetch(`https://github-contributions-api.jogruber.de/v4/${encodeURIComponent(username)}?y=all`);
    if (!res.ok) return 0;
    const data = await res.json();
    const totals = data && data.total ? Object.values(data.total) : [];
    return totals.reduce((sum, n) => sum + (Number(n) || 0), 0);
  } catch (err) {
    return 0; // contribution archive unreachable — proceed without this stat
  }
}

async function fetchAvatarDataUri(url) {
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error('bad avatar response');
    const contentType = res.headers.get('content-type') || 'image/png';
    const buf = Buffer.from(await res.arrayBuffer());
    return `data:${contentType};base64,${buf.toString('base64')}`;
  } catch (err) {
    return null;
  }
}

// ---------- profile / stats ----------

function buildProfile(user, repos, totalContributions) {
  const totalStars = repos.reduce((s, r) => s + (r.stargazers_count || 0), 0);
  const langCounts = {};
  repos.forEach((r) => {
    if (r.language) langCounts[r.language] = (langCounts[r.language] || 0) + 1;
  });
  const languages = Object.keys(langCounts);
  const topLanguage = languages.sort((a, b) => langCounts[b] - langCounts[a])[0] || null;
  const [className, classDesc] = pickClass(topLanguage);

  const accountAgeYears = yearsSince(user.created_at);

  const STR = Math.round(totalStars * 1.5);
  const INT = Math.round((user.public_repos || 0) * 2 + languages.length * 5);
  const VIT = Math.round(accountAgeYears * 12);
  const LUK = Math.round((user.followers || 0) * 1.2);
  const CON = Math.round(totalContributions * 0.05);

  const total = STR + INT + VIT + LUK + CON;
  const rank = rankFromTotal(total);

  return {
    className,
    classDesc,
    topLanguage,
    stats: { STR, INT, VIT, LUK, CON },
    rank,
    totalStars,
    totalContributions,
    accountAgeYears,
  };
}

// ---------- SVG rendering (plain SVG only — no foreignObject/HTML, so it
// renders reliably as a plain <img> in READMEs everywhere) ----------

const COLORS = {
  ink: '#2a2013',
  inkSoft: '#4a3c26',
  parchment: '#ece0c2',
  parchmentDim: '#d9c89f',
  gold: '#c9a227',
  goldBright: '#e6c65c',
  teal: '#3f8f8a',
  blood: '#8b3038',
  bloodBright: '#b5454f',
};

function esc(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function wordWrap(text, maxChars) {
  const words = text.split(' ');
  const lines = [];
  let current = '';
  for (const word of words) {
    const candidate = current ? `${current} ${word}` : word;
    if (candidate.length > maxChars && current) {
      lines.push(current);
      current = word;
    } else {
      current = candidate;
    }
  }
  if (current) lines.push(current);
  return lines;
}

function statBar(x, y, width, label, value, maxValue) {
  const barW = width;
  const fillW = Math.max(4, Math.min(1, value / maxValue) * barW);
  return `
    <g>
      <text x="${x}" y="${y}" font-family="Consolas, Menlo, monospace" font-size="11" letter-spacing="0.5"
        fill="${COLORS.inkSoft}">${label}</text>
      <text x="${x + barW}" y="${y}" font-family="Consolas, Menlo, monospace" font-size="11" font-weight="700"
        text-anchor="end" fill="${COLORS.ink}">${value}</text>
      <rect x="${x}" y="${y + 7}" width="${barW}" height="7" rx="3.5" fill="rgba(42,32,19,0.15)"/>
      <rect x="${x}" y="${y + 7}" width="${fillW}" height="7" rx="3.5" fill="url(#barGradient)"/>
    </g>`;
}

function buildSvg({ user, profile }, avatarDataUri) {
  const W = 560;
  const PAD = 30;
  const AVATAR = 84;
  const contentW = W - PAD * 2;

  const name = esc(user.name || user.login);
  const bindingYear = new Date(user.created_at).getFullYear();
  const ageYears = Math.max(0, Math.floor(profile.accountAgeYears));

  const flavorText =
    `Bound to this realm since ${bindingYear}, the ${profile.className} ${profile.classDesc}. ` +
    `${ageYears} year${ageYears === 1 ? '' : 's'} into their journey, they are ${RANK_MEANING[profile.rank]} — ` +
    `${profile.totalStars} traveler${profile.totalStars === 1 ? '' : 's'} have marked their deeds with a star, ` +
    `and ${profile.totalContributions.toLocaleString()} contribution${profile.totalContributions === 1 ? '' : 's'} are etched into the ledger.`;

  const flavorLines = wordWrap(flavorText, 78);
  const flavorLineHeight = 17;

  let y = PAD;
  const parts = [];

  // --- top row: avatar + name/class ---
  const avatarX = PAD;
  const avatarY = y;
  parts.push(`
    <rect x="${avatarX - 3}" y="${avatarY - 3}" width="${AVATAR + 6}" height="${AVATAR + 6}" rx="9"
      fill="${COLORS.gold}"/>
    <rect x="${avatarX - 1}" y="${avatarY - 1}" width="${AVATAR + 2}" height="${AVATAR + 2}" rx="7"
      fill="${COLORS.ink}"/>`);
  if (avatarDataUri) {
    parts.push(`
      <clipPath id="avatarClip"><rect x="${avatarX}" y="${avatarY}" width="${AVATAR}" height="${AVATAR}" rx="6"/></clipPath>
      <image href="${avatarDataUri}" x="${avatarX}" y="${avatarY}" width="${AVATAR}" height="${AVATAR}"
        clip-path="url(#avatarClip)" preserveAspectRatio="xMidYMid slice"/>`);
  }

  const textX = avatarX + AVATAR + 18;
  parts.push(`
    <text x="${textX}" y="${avatarY + 14}" font-family="Consolas, Menlo, monospace" font-size="10"
      letter-spacing="0.5" fill="${COLORS.inkSoft}">Adventurer's License · @${esc(user.login)}</text>
    <text x="${textX}" y="${avatarY + 36}" font-family="Georgia, 'Times New Roman', serif" font-weight="700"
      font-size="20" fill="${COLORS.ink}">${name}</text>
    <text x="${textX}" y="${avatarY + 56}" font-family="Georgia, serif" font-style="italic" font-size="13.5"
      fill="${COLORS.inkSoft}">${esc(profile.className)}</text>`);

  // --- rank seal (top-right) ---
  const sealCx = W - PAD - 39;
  const sealCy = PAD + 39;
  parts.push(`
    <circle cx="${sealCx}" cy="${sealCy}" r="39" fill="url(#sealGradient)"/>
    <circle cx="${sealCx}" cy="${sealCy}" r="39" fill="none" stroke="rgba(255,255,255,0.25)" stroke-width="2"/>
    <text x="${sealCx}" y="${sealCy + 3}" text-anchor="middle" font-family="Georgia, serif" font-weight="700"
      font-size="22" fill="${COLORS.parchment}">${profile.rank}</text>
    <text x="${sealCx}" y="${sealCy + 17}" text-anchor="middle" font-family="Consolas, Menlo, monospace"
      font-size="8" letter-spacing="1" fill="rgba(236,224,194,0.85)">RANK</text>`);

  y += AVATAR + 26;

  // --- flavor text ---
  const flavorX = PAD + 14;
  parts.push(`<rect x="${PAD}" y="${y - 13}" width="2" height="${flavorLines.length * flavorLineHeight + 6}" fill="${COLORS.gold}"/>`);
  flavorLines.forEach((line, i) => {
    parts.push(`
      <text x="${flavorX}" y="${y + i * flavorLineHeight}" font-family="Georgia, serif" font-size="13"
        fill="${COLORS.inkSoft}">${esc(line)}</text>`);
  });
  y += flavorLines.length * flavorLineHeight + 22;

  // --- stat bars (2 columns) ---
  const colGap = 24;
  const colW = (contentW - colGap) / 2;
  const statList = [
    ['STR', profile.stats.STR],
    ['INT', profile.stats.INT],
    ['VIT', profile.stats.VIT],
    ['LUK', profile.stats.LUK],
    ['CON', profile.stats.CON],
  ];
  const rowH = 32;
  const maxStatValue = 150;
  statList.forEach(([label, value], i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    const x = PAD + col * (colW + colGap);
    const rowY = y + row * rowH;
    parts.push(statBar(x, rowY, colW, label, value, maxStatValue));
  });
  const statRows = Math.ceil(statList.length / 2);
  y += statRows * rowH + 14;

  // --- ledger ---
  parts.push(`<line x1="${PAD}" y1="${y}" x2="${W - PAD}" y2="${y}" stroke="rgba(42,32,19,0.2)" stroke-width="1"/>`);
  y += 26;
  const ledgerItems = [
    [user.public_repos ?? 0, 'QUESTS LOGGED'],
    [user.followers ?? 0, 'ALLIES'],
    [profile.totalStars, 'RENOWN'],
    [profile.totalContributions.toLocaleString(), 'CONTRIBUTIONS'],
  ];
  const ledgerColW = contentW / ledgerItems.length;
  ledgerItems.forEach(([num, label], i) => {
    const cx = PAD + ledgerColW * i + ledgerColW / 2;
    parts.push(`
      <text x="${cx}" y="${y}" text-anchor="middle" font-family="Consolas, Menlo, monospace" font-weight="700"
        font-size="16" fill="${COLORS.ink}">${num}</text>
      <text x="${cx}" y="${y + 14}" text-anchor="middle" font-family="Consolas, Menlo, monospace" font-size="8.5"
        letter-spacing="0.5" fill="${COLORS.inkSoft}">${label}</text>`);
  });
  y += 34;

  // --- footer ---
  parts.push(`
    <text x="${W / 2}" y="${y}" text-anchor="middle" font-family="Consolas, Menlo, monospace" font-size="10"
      fill="rgba(42,32,19,0.55)">${esc(user.html_url.replace('https://', ''))}</text>`);
  y += PAD - 6;

  const H = y;

  return `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
  width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
  <defs>
    <radialGradient id="bgGradient" cx="30%" cy="20%" r="90%">
      <stop offset="0%" stop-color="#f5ecd6"/>
      <stop offset="100%" stop-color="${COLORS.parchment}"/>
    </radialGradient>
    <linearGradient id="barGradient" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="${COLORS.teal}"/>
      <stop offset="100%" stop-color="${COLORS.gold}"/>
    </linearGradient>
    <radialGradient id="sealGradient" cx="35%" cy="30%" r="75%">
      <stop offset="0%" stop-color="${COLORS.bloodBright}"/>
      <stop offset="100%" stop-color="${COLORS.blood}"/>
    </radialGradient>
  </defs>

  <rect x="0" y="0" width="${W}" height="${H}" rx="10" fill="url(#bgGradient)"/>
  <rect x="8" y="8" width="${W - 16}" height="${H - 16}" rx="6" fill="none"
    stroke="rgba(42,32,19,0.25)" stroke-width="1"/>

  ${parts.join('\n')}
</svg>`;
}

// ---------- main ----------

async function main() {
  console.log(`Summoning guild card for @${USERNAME}...`);

  const user = await fetchUser(USERNAME);
  const [repos, totalContributions] = await Promise.all([
    fetchAllRepos(USERNAME),
    fetchTotalContributions(USERNAME),
  ]);
  const profile = buildProfile(user, repos, totalContributions);
  const avatarDataUri = await fetchAvatarDataUri(user.avatar_url);

  const svg = buildSvg({ user, profile }, avatarDataUri);
  fs.writeFileSync(OUTPUT_SVG, svg, 'utf8');
  console.log(`Wrote ${OUTPUT_SVG} (rank ${profile.rank}, class ${profile.className})`);

  }

main().catch((err) => {
  console.error('Guild card generation failed:', err.message);
  process.exit(1);
});
