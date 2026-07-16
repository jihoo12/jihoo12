// scripts/generate-svg.js
// Renders the pet state into a self-contained, animated SVG string.
// Uses <style> (CSS animations) for a gentle bob + blink — these still
// play when the SVG is embedded via <img src="..."> in a README, since
// browsers apply CSS/SMIL animation to image-loaded SVGs (just not <script>).

const PALETTE = {
  egg: { body: "#e8e2d0", accent: "#d4c9a8" },
  baby: { body: "#ffd1dc", accent: "#ff9eb5" },
  child: { body: "#bde0fe", accent: "#7bb8f0" },
  teen: { body: "#caffbf", accent: "#8fd97f" },
  adult: { body: "#ffd6a5", accent: "#ffb570" },
  elder: { body: "#d0bfff", accent: "#a78bfa" },
};

const STAGE_SIZE = {
  egg: 60,
  baby: 70,
  child: 80,
  teen: 90,
  adult: 100,
  elder: 100,
};

function face(mood, cx, cy) {
  // Returns SVG snippet for eyes + mouth, centered around (cx, cy)
  switch (mood) {
    case "hungry":
      return `
        <circle class="eye" cx="${cx - 15}" cy="${cy - 5}" r="5" fill="#3a2e2e"/>
        <circle class="eye" cx="${cx + 15}" cy="${cy - 5}" r="5" fill="#3a2e2e"/>
        <path d="M ${cx - 12} ${cy + 18} Q ${cx} ${cy + 8} ${cx + 12} ${cy + 18}" stroke="#3a2e2e" stroke-width="3" fill="none" stroke-linecap="round"/>
      `;
    case "sick":
      return `
        <path d="M ${cx - 19} ${cy - 9} L ${cx - 9} ${cy - 1} M ${cx - 19} ${cy - 1} L ${cx - 9} ${cy - 9}" stroke="#3a2e2e" stroke-width="3" stroke-linecap="round"/>
        <path d="M ${cx + 9} ${cy - 9} L ${cx + 19} ${cy - 1} M ${cx + 9} ${cy - 1} L ${cx + 19} ${cy - 9}" stroke="#3a2e2e" stroke-width="3" stroke-linecap="round"/>
        <path d="M ${cx - 10} ${cy + 16} Q ${cx} ${cy + 10} ${cx + 10} ${cy + 16}" stroke="#3a2e2e" stroke-width="3" fill="none" stroke-linecap="round"/>
      `;
    case "happy":
      return `
        <path class="eye" d="M ${cx - 20} ${cy - 5} Q ${cx - 15} ${cy - 12} ${cx - 10} ${cy - 5}" stroke="#3a2e2e" stroke-width="3" fill="none" stroke-linecap="round"/>
        <path class="eye" d="M ${cx + 10} ${cy - 5} Q ${cx + 15} ${cy - 12} ${cx + 20} ${cy - 5}" stroke="#3a2e2e" stroke-width="3" fill="none" stroke-linecap="round"/>
        <path d="M ${cx - 14} ${cy + 8} Q ${cx} ${cy + 24} ${cx + 14} ${cy + 8}" stroke="#3a2e2e" stroke-width="3" fill="none" stroke-linecap="round"/>
      `;
    default:
      return `
        <circle class="eye" cx="${cx - 15}" cy="${cy - 5}" r="5" fill="#3a2e2e"/>
        <circle class="eye" cx="${cx + 15}" cy="${cy - 5}" r="5" fill="#3a2e2e"/>
        <path d="M ${cx - 10} ${cy + 14} Q ${cx} ${cy + 20} ${cx + 10} ${cy + 14}" stroke="#3a2e2e" stroke-width="3" fill="none" stroke-linecap="round"/>
      `;
  }
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

function accessory(stage, cx, cy) {
  if (stage === "elder") {
    // simple crown
    return `<path d="M ${cx - 20} ${cy} L ${cx - 12} ${cy - 16} L ${cx - 4} ${cy - 4} L ${cx} ${cy - 18} L ${cx + 4} ${cy - 4} L ${cx + 12} ${cy - 16} L ${cx + 20} ${cy} Z" fill="#ffd700" stroke="#c9a800" stroke-width="1.5"/>`;
  }
  if (stage === "adult") {
    // little antenna/bow
    return `<circle cx="${cx}" cy="${cy - 30}" r="4" fill="#ff6b6b"/><line x1="${cx}" y1="${cy - 26}" x2="${cx}" y2="${cy - 14}" stroke="#ff6b6b" stroke-width="2"/>`;
  }
  return "";
}

function bodyShape(stage, cx, cy, colors) {
  const size = STAGE_SIZE[stage];
  if (stage === "egg") {
    return `<ellipse class="bob" cx="${cx}" cy="${cy}" rx="${size * 0.55}" ry="${size * 0.7}" fill="${colors.body}" stroke="${colors.accent}" stroke-width="3"/>`;
  }
  return `<circle class="bob" cx="${cx}" cy="${cy}" r="${size * 0.55}" fill="${colors.body}" stroke="${colors.accent}" stroke-width="3"/>`;
}

function renderSVG(state) {
  const {
    stage,
    mood,
    hunger,
    happiness,
    health,
    currentStreak,
    daysSinceLastContribution,
  } = state;

  const colors = PALETTE[stage] || PALETTE.egg;
  const width = 320;
  const height = 260;
  const cx = width / 2;
  const cy = 100;

  const blinkEyes = mood !== "sick"; // sick uses X eyes, no blink needed

  return `<svg viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg" font-family="Verdana, sans-serif">
  <style>
    .bob { transform-origin: ${cx}px ${cy}px; animation: bob 2.4s ease-in-out infinite; }
    @keyframes bob {
      0%, 100% { transform: translateY(0px); }
      50% { transform: translateY(-6px); }
    }
    ${
      blinkEyes
        ? `.eye { animation: blink 4s infinite; transform-origin: center; }
    @keyframes blink {
      0%, 92%, 100% { transform: scaleY(1); }
      95% { transform: scaleY(0.1); }
    }`
        : ""
    }
  </style>

  <rect width="${width}" height="${height}" rx="16" fill="#fafafa"/>

  ${accessory(stage, cx, cy - 45)}
  ${bodyShape(stage, cx, cy, colors)}
  ${face(mood, cx, cy)}

  <text x="${width / 2}" y="182" text-anchor="middle" font-size="13" fill="#333" font-weight="bold">
    ${stage.toUpperCase()} · ${mood}
  </text>

  ${statBar("Hunger", hunger, 205, "#ff9e6d")}
  ${statBar("Happiness", happiness, 227, "#ffd166")}
  ${statBar("Health", health, 249, "#6dbf6d")}

  <text x="${width - 12}" y="18" text-anchor="end" font-size="10" fill="#999">
    streak: ${currentStreak}d · last commit: ${daysSinceLastContribution === 0 ? "today" : daysSinceLastContribution + "d ago"}
  </text>
</svg>`;
}

module.exports = { renderSVG };
