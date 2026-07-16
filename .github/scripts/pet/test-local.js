// scripts/test-local.js
// Quick local sanity check using mock data — no GitHub token needed.
// Run with: node scripts/test-local.js
const fs = require("fs");
const { computePetState } = require("./pet-state");
const { renderSVG } = require("./generate-svg");

function mockDays({ totalDays = 365, pattern }) {
  const days = [];
  const today = new Date();
  for (let i = totalDays - 1; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(d.getDate() - i);
    days.push({ date: d.toISOString().slice(0, 10), count: pattern(i) });
  }
  return days;
}

const scenarios = {
  // active streaker: commits every day for the last 10 days
  activeStreak: mockDays({
    pattern: (i) => (i < 10 ? Math.floor(Math.random() * 4) + 1 : Math.random() < 0.3 ? 1 : 0),
  }),
  // neglected: nothing for the last 6 days, sporadic before that
  neglected: mockDays({
    pattern: (i) => (i < 6 ? 0 : Math.random() < 0.4 ? 1 : 0),
  }),
  // brand new account: almost no history
  newAccount: mockDays({
    pattern: (i) => (i > 355 ? 1 : 0),
  }),
  // veteran: tons of history, active today
  veteran: mockDays({
    pattern: (i) => (i === 0 ? 3 : Math.random() < 0.7 ? Math.floor(Math.random() * 5) : 0),
  }),
};

for (const [name, days] of Object.entries(scenarios)) {
  const total = days.reduce((a, d) => a + d.count, 0);
  const state = computePetState({ totalContributions: total, days });
  const svg = renderSVG(state);
  fs.writeFileSync(`preview-${name}.svg`, svg, "utf8");
  console.log(`\n=== ${name} ===`);
  console.log(state);
}
