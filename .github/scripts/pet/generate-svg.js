// scripts/generate-svg.js
// Renders the pet state as a self-contained, animated PIXEL-ART SVG string.
// Each creature is a hand-authored bitmap (grid of tiny <rect> "pixels"),
// mirrored left-to-right, with an auto-generated dark outline. Faces and
// accessories (ears, spikes, wings, antenna, crown) are layered on top.
// Uses <style> (CSS animations) for a gentle bob + blink — these still
// play when the SVG is embedded via <img src="..."> in a README.

const DARK = "#3a2e2e";

const PALETTE = {
  egg: { body: "#e8e2d0", outline: "#b8ab84", highlight: "#f5f0e3", accent: "#d4c9a8" },
  baby: { body: "#ffd1dc", outline: "#e08aa0", highlight: "#ffeef2", accent: "#ff9eb5" },
  child: { body: "#bde0fe", outline: "#5a9bd8", highlight: "#e3f2ff", accent: "#7bb8f0" },
  teen: { body: "#caffbf", outline: "#5fae52", highlight: "#e8ffe0", accent: "#8fd97f" },
  adult: { body: "#ffd6a5", outline: "#e0913f", highlight: "#fff0da", accent: "#ffb570" },
  elder: { body: "#d0bfff", outline: "#8a6fd9", highlight: "#ece4ff", accent: "#a78bfa" },
};

// --- sprite authoring helpers -------------------------------------------
// Each sprite is authored as its LEFT HALF only (7 chars per row) and
// mirrored automatically, so every creature is symmetric by construction.
// Chars: '.' empty · 'B' body · 'H' highlight/blush · 'E' accent spot
function mirrorRows(halfRows) {
  return halfRows.map((row) => row + row.split("").reverse().join(""));
}

// Auto-outline: any filled 'B' pixel touching an empty neighbor becomes
// an outline pixel. This is what gives every creature a crisp sprite edge
// without hand-placing outline pixels.
function withOutline(grid) {
  const rows = grid.length;
  const cols = grid[0].length;
  const filled = (r, c) => r >= 0 && r < rows && c >= 0 && c < cols && grid[r][c] !== ".";
  const out = grid.map((row) => row.split(""));
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      if (grid[r][c] !== "B") continue;
      if (!filled(r - 1, c) || !filled(r + 1, c) || !filled(r, c - 1) || !filled(r, c + 1)) {
        out[r][c] = "O";
      }
    }
  }
  return out.map((r) => r.join(""));
}

function buildSprite(halfRows) {
  return withOutline(mirrorRows(halfRows));
}

function spriteSVG(grid, originX, originY, px, colors) {
  const colorFor = { O: colors.outline, B: colors.body, H: colors.highlight, E: colors.accent };
  let svg = "";
  for (let r = 0; r < grid.length; r++) {
    for (let c = 0; c < grid[r].length; c++) {
      const ch = grid[r][c];
      if (ch === ".") continue;
      svg += `<rect x="${originX + c * px}" y="${originY + r * px}" width="${px}" height="${px}" fill="${colorFor[ch]}"/>`;
    }
  }
  return svg;
}

// --- per-stage sprite definitions (left halves, 7 chars wide) ----------
const SPRITES = {
  egg: [
    ".....BB",
    "....BBB",
    "...BBBB",
    "..BBBBB",
    "..BBBBB",
    ".BBBBBB",
    ".BEBBBB",
    ".BBBBBB",
    "..BBEBB",
    "..BBBBB",
    "...BBBB",
    ".....BB",
  ],
  baby: [
    "....BBB",
    "..BBBBB",
    ".BBBBBB",
    "BBBBBBB",
    "BBBBBBB",
    "BHBBBBB",
    "BBBBBBB",
    ".BBBBBB",
    "..BBBBB",
    "...BBBB",
    "....BBB",
    ".....BB",
  ],
  child: [
    "..B....",
    "..BB...",
    "...BBBB",
    ".BBBBBB",
    "BBBBBBB",
    "BBBBBBB",
    "BBBBBBB",
    "BHBBBBB",
    "BBBBBBB",
    ".BBBBBB",
    "..BBBBB",
    "...BBBB",
    "....BBB",
    ".....BB",
  ],
  teen: [
    "......B",
    "....BBB",
    "..BBBBB",
    ".BBBBBB",
    "BBBBBBB",
    "BBBBBBB",
    "BBBBBBB",
    "BHBBBBB",
    "BBBBBBB",
    "BBBBBBB",
    ".BBBBBB",
    "..BBBBB",
    "...BBBB",
    "....BBB",
    ".....BB",
  ],
  adult: [
    "......B",
    "....BBB",
    "..BBBBB",
    ".BBBBBB",
    "BBBBBBB",
    "BBBBBBB",
    "BHBBBBB",
    "BBBBBBB",
    "BBBBBBB",
    "BHHBBBB",
    "BHHBBBB",
    "BBBBBBB",
    ".BBBBBB",
    "..BBBBB",
    "...BBBB",
    ".....BB",
  ],
  elder: [
    "....BBB",
    "..BBBBB",
    ".BBBBBB",
    "BBBBBBB",
    "BBBBBBB",
    "BHBBBBB",
    "BBBBBBB",
    "BBBBBBB",
    "BBBBBBB",
    "BBBBBBB",
    "BBBBBBB",
    "BBBBBBB",
    "BBBBBBB",
    "BBBBBBB",
    "BBBBBBB",
    ".BBBBBB",
  ],
};

// Pixel size + face/anchor layout per stage. Rows come from SPRITES above.
const STAGE_LAYOUT = {
  egg: { px: 8, eyeRow: 6, eyeCol: 2.2, mouthRow: 8.2, mouthHalfW: 1 },
  baby: { px: 8, eyeRow: 5, eyeCol: 2.6, mouthRow: 8, mouthHalfW: 1.3 },
  child: { px: 8, eyeRow: 5, eyeCol: 3, mouthRow: 9, mouthHalfW: 1.5 },
  teen: { px: 8, eyeRow: 6, eyeCol: 3, mouthRow: 10, mouthHalfW: 1.6 },
  adult: { px: 8.5, eyeRow: 6, eyeCol: 3.2, mouthRow: 11, mouthHalfW: 1.7 },
  elder: { px: 8.5, eyeRow: 5, eyeCol: 3.2, mouthRow: 9, mouthHalfW: 1.7 },
};

const GRID_COLS = 14;
const GROUND_Y = 178; // every sprite's feet line up here regardless of height

// --- face (pixel eyes + mouth) ------------------------------------------
function eyesSVG(mood, origin, px, eyeRow, eyeCol) {
  const y = origin.y + eyeRow * px;
  const leftX = origin.x + (GRID_COLS / 2 - eyeCol) * px;
  const rightX = origin.x + (GRID_COLS / 2 + eyeCol - 1) * px;
  const s = px * 0.9;

  const dot = (x) => `<rect class="eye" x="${x}" y="${y}" width="${s}" height="${s}" fill="${DARK}"/>`;

  if (mood === "sick") {
    const xEye = (x) => `
      <rect x="${x}" y="${y - s * 0.15}" width="${s * 1.1}" height="${s * 0.34}" fill="${DARK}" transform="rotate(45 ${x + s * 0.5} ${y})"/>
      <rect x="${x}" y="${y - s * 0.15}" width="${s * 1.1}" height="${s * 0.34}" fill="${DARK}" transform="rotate(-45 ${x + s * 0.5} ${y})"/>
    `;
    return `${xEye(leftX)}${xEye(rightX)}`;
  }

  if (mood === "hungry") {
    // small droopy dot eyes
    return `${dot(leftX)}${dot(rightX)}`;
  }

  if (mood === "happy") {
    // upward ^ made of 3 small pixels per eye
    const caret = (x) => `
      <rect x="${x}" y="${y + s * 0.3}" width="${s * 0.5}" height="${s * 0.5}" fill="${DARK}"/>
      <rect x="${x + s * 0.35}" y="${y}" width="${s * 0.5}" height="${s * 0.5}" fill="${DARK}"/>
      <rect x="${x + s * 0.7}" y="${y + s * 0.3}" width="${s * 0.5}" height="${s * 0.5}" fill="${DARK}"/>
    `;
    return `${caret(leftX - s * 0.2)}${caret(rightX - s * 0.2)}`;
  }

  // neutral / default
  return `${dot(leftX)}${dot(rightX)}`;
}

function mouthSVG(mood, origin, px, mouthRow, mouthHalfW) {
  const cx = origin.x + (GRID_COLS / 2) * px;
  const y = origin.y + mouthRow * px;
  const w = mouthHalfW * px * 2;
  const h = px * 0.5;

  if (mood === "hungry") {
    // small open "o" mouth
    const size = px * 0.9;
    return `<rect x="${cx - size / 2}" y="${y}" width="${size}" height="${size}" fill="none" stroke="${DARK}" stroke-width="${px * 0.28}"/>`;
  }
  if (mood === "happy") {
    // wide smile: flat center bar + upturned corner pixels
    return `
      <rect x="${cx - w / 2}" y="${y}" width="${w}" height="${h}" fill="${DARK}"/>
      <rect x="${cx - w / 2 - h}" y="${y - h}" width="${h}" height="${h}" fill="${DARK}"/>
      <rect x="${cx + w / 2}" y="${y - h}" width="${h}" height="${h}" fill="${DARK}"/>
    `;
  }
  if (mood === "sick") {
    return `<rect x="${cx - w / 2.5}" y="${y}" width="${w / 1.25}" height="${h * 0.8}" fill="${DARK}"/>`;
  }
  // neutral
  return `<rect x="${cx - w / 2}" y="${y}" width="${w}" height="${h}" fill="${DARK}"/>`;
}

// --- accessories (ears/spikes are baked into sprites; these are the rest)
function accessories(stage, origin, px, colors) {
  const cx = origin.x + (GRID_COLS / 2) * px;

  if (stage === "teen") {
    // little arm nubs poking out mid-body
    const y = origin.y + 8 * px;
    return `
      <rect x="${origin.x - px * 0.8}" y="${y}" width="${px * 0.9}" height="${px * 1.6}" rx="${px * 0.3}" fill="${colors.outline}"/>
      <rect x="${origin.x + GRID_COLS * px - px * 0.1}" y="${y}" width="${px * 0.9}" height="${px * 1.6}" rx="${px * 0.3}" fill="${colors.outline}"/>
    `;
  }

  if (stage === "adult") {
    // antenna above head + small wing triangles at the sides
    const topY = origin.y - px * 1.6;
    const wingY = origin.y + 4 * px;
    return `
      <circle cx="${cx}" cy="${topY}" r="${px * 0.45}" fill="${colors.accent}"/>
      <line x1="${cx}" y1="${topY + px * 0.45}" x2="${cx}" y2="${origin.y + px}" stroke="${colors.accent}" stroke-width="${px * 0.25}"/>
      <path d="M ${origin.x - px * 1.4} ${wingY + px * 1.5} L ${origin.x} ${wingY} L ${origin.x} ${wingY + px * 2.5} Z" fill="${colors.accent}" opacity="0.9"/>
      <path d="M ${origin.x + GRID_COLS * px + px * 1.4} ${wingY + px * 1.5} L ${origin.x + GRID_COLS * px} ${wingY} L ${origin.x + GRID_COLS * px} ${wingY + px * 2.5} Z" fill="${colors.accent}" opacity="0.9"/>
    `;
  }

  if (stage === "elder") {
    // little crown above head + a soft beard patch below the mouth
    const topY = origin.y - px * 0.4;
    const beardY = origin.y + 10 * px;
    return `
      <path d="M ${cx - px * 2.2} ${topY} L ${cx - px * 1.3} ${topY - px * 1.8} L ${cx - px * 0.4} ${topY - px * 0.5} L ${cx} ${topY - px * 2} L ${cx + px * 0.4} ${topY - px * 0.5} L ${cx + px * 1.3} ${topY - px * 1.8} L ${cx + px * 2.2} ${topY} Z" fill="#ffd700" stroke="#c9a800" stroke-width="1.5"/>
      <rect x="${cx - px * 1.1}" y="${beardY}" width="${px * 2.2}" height="${px * 1.4}" rx="${px * 0.4}" fill="${colors.highlight}" opacity="0.85"/>
    `;
  }

  return "";
}

function statBar(label, value, y, color) {
  const width = 160;
  const filled = Math.round((value / 100) * width);
  return `
    <text x="20" y="${y - 6}" font-size="11" fill="#555" font-family="Verdana, sans-serif">${label}</text>
    <rect x="20" y="${y}" width="${width}" height="10" rx="5" fill="#eee"/>
    <rect x="20" y="${y}" width="${filled}" height="10" rx="5" fill="${color}"/>
    <text x="${20 + width + 8}" y="${y + 9}" font-size="10" fill="#555" font-family="Verdana, sans-serif">${value}</text>
  `;
}

function renderSVG(state) {
  const { stage, mood, hunger, happiness, health, currentStreak, daysSinceLastContribution } = state;

  const safeStage = SPRITES[stage] ? stage : "egg";
  const colors = PALETTE[safeStage];
  const layout = STAGE_LAYOUT[safeStage];
  const grid = buildSprite(SPRITES[safeStage]);

  const width = 320;
  const height = 296;
  const cx = width / 2;

  const originX = cx - (GRID_COLS * layout.px) / 2;
  const originY = GROUND_Y - grid.length * layout.px;
  const origin = { x: originX, y: originY };

  const blinkEyes = mood !== "sick";

  return `<svg viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg" font-family="Verdana, sans-serif" shape-rendering="crispEdges">
  <style>
    .critter { transform-origin: ${cx}px ${originY + (grid.length * layout.px) / 2}px; animation: bob 2.4s ease-in-out infinite; }
    @keyframes bob {
      0%, 100% { transform: translateY(0px); }
      50% { transform: translateY(-4px); }
    }
    ${
      blinkEyes
        ? `.eye { animation: blink 4s infinite; transform-origin: center; }
    @keyframes blink {
      0%, 92%, 100% { transform: scaleY(1); }
      95% { transform: scaleY(0.15); }
    }`
        : ""
    }
  </style>

  <rect width="${width}" height="${height}" rx="16" fill="#fafafa"/>

  <ellipse cx="${cx}" cy="${GROUND_Y + 6}" rx="${GRID_COLS * layout.px * 0.42}" ry="6" fill="#000" opacity="0.06"/>

  <g class="critter">
    ${spriteSVG(grid, originX, originY, layout.px, colors)}
    ${accessories(safeStage, origin, layout.px, colors)}
    ${eyesSVG(mood, origin, layout.px, layout.eyeRow, layout.eyeCol)}
    ${mouthSVG(mood, origin, layout.px, layout.mouthRow, layout.mouthHalfW)}
  </g>

  <text x="${width / 2}" y="200" text-anchor="middle" font-size="13" fill="#333" font-weight="bold">
    ${safeStage.toUpperCase()} · ${mood}
  </text>

  ${statBar("Hunger", hunger, 214, "#ff9e6d")}
  ${statBar("Happiness", happiness, 240, "#ffd166")}
  ${statBar("Health", health, 266, "#6dbf6d")}

  <text x="${width - 12}" y="18" text-anchor="end" font-size="10" fill="#999">
    streak: ${currentStreak}d · last commit: ${daysSinceLastContribution === 0 ? "today" : daysSinceLastContribution + "d ago"}
  </text>
</svg>`;
}

module.exports = { renderSVG };
