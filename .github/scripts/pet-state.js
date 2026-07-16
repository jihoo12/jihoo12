// scripts/pet-state.js
// Turns raw contribution days into a Tamagotchi state: hunger, happiness,
// health, evolution stage, and mood. Pure function, easy to unit test.

const STAGES = ["egg", "baby", "child", "teen", "adult", "elder"];

function clamp(n, min, max) {
  return Math.max(min, Math.min(max, n));
}

function computeStreaks(days) {
  // days is chronological ascending, each { date, count }
  let currentStreak = 0;
  let longestStreak = 0;
  let running = 0;

  for (const d of days) {
    if (d.count > 0) {
      running += 1;
      longestStreak = Math.max(longestStreak, running);
    } else {
      running = 0;
    }
  }

  // current streak = trailing run ending at the last day, walking backwards
  for (let i = days.length - 1; i >= 0; i--) {
    if (days[i].count > 0) currentStreak += 1;
    else break;
  }

  return { currentStreak, longestStreak };
}

function daysSinceLastContribution(days) {
  for (let i = days.length - 1; i >= 0; i--) {
    if (days[i].count > 0) {
      return days.length - 1 - i;
    }
  }
  return days.length; // never contributed in the window
}

function sumLastN(days, n) {
  return days.slice(-n).reduce((acc, d) => acc + d.count, 0);
}

function evolutionStage(totalContributions) {
  if (totalContributions < 10) return "egg";
  if (totalContributions < 50) return "baby";
  if (totalContributions < 150) return "child";
  if (totalContributions < 350) return "teen";
  if (totalContributions < 700) return "adult";
  return "elder";
}

function moodFrom(hunger, happiness, health) {
  if (hunger < 20) return "hungry";
  if (health < 30) return "sick";
  if (happiness > 70) return "happy";
  return "neutral";
}

/**
 * @param {{ totalContributions: number, days: {date:string,count:number}[] }} data
 */
function computePetState(data) {
  const { totalContributions, days } = data;
  const gap = daysSinceLastContribution(days);
  const { currentStreak, longestStreak } = computeStreaks(days);
  const last7 = sumLastN(days, 7);
  const last30 = sumLastN(days, 30);

  // Hunger: fed today = full, decays fast with each missed day.
  const hunger = clamp(100 - gap * 35, 0, 100);

  // Happiness: driven by an active streak, caps out around a 12-day streak.
  const happiness = clamp(currentStreak * 8, 0, 100);

  // Health: penalized by long neglect gaps, otherwise buoyed by recent volume.
  const neglectPenalty = Math.max(0, gap - 3) * 20;
  const health = clamp(50 + last30 * 1.5 - neglectPenalty, 0, 100);

  const stage = evolutionStage(totalContributions);
  const mood = moodFrom(hunger, happiness, health);

  return {
    stage,
    mood,
    hunger: Math.round(hunger),
    happiness: Math.round(happiness),
    health: Math.round(health),
    currentStreak,
    longestStreak,
    daysSinceLastContribution: gap,
    last7DaysTotal: last7,
    last30DaysTotal: last30,
    totalContributions,
  };
}

module.exports = { computePetState, STAGES };
