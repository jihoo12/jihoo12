// scripts/index.js
// Entry point: fetch contributions -> compute state -> render SVG -> write file.
// Run with: GITHUB_LOGIN=yourname GITHUB_TOKEN=xxx node scripts/index.js

const fs = require("fs");
const path = require("path");
const { fetchContributions } = require("./fetch-contributions");
const { computePetState } = require("./pet-state");
const { renderSVG } = require("./generate-svg");

async function main() {
  const login = process.env.GITHUB_LOGIN;
  const token = process.env.GITHUB_TOKEN;
  const outputPath = process.env.PET_OUTPUT_PATH || "pet.svg";

  const data = await fetchContributions(login, token);
  const state = computePetState(data);
  const svg = renderSVG(state);

  fs.writeFileSync(path.resolve(outputPath), svg, "utf8");

  console.log("Pet state:", state);
  console.log(`SVG written to ${outputPath}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
