// scripts/fetch-contributions.js
// Fetches the past-year contribution calendar for a GitHub user via the GraphQL API.
// Requires a token with at least `read:user` scope. In the GitHub Action this is
// provided automatically-ish (you supply a PAT as a secret; see README).

const GITHUB_GRAPHQL_URL = "https://api.github.com/graphql";

const QUERY = `
query ($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
    }
  }
}
`;

async function fetchContributions(login, token) {
  if (!login) throw new Error("GITHUB_LOGIN is required");
  if (!token) throw new Error("GITHUB_TOKEN is required");

  const res = await fetch(GITHUB_GRAPHQL_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `bearer ${token}`,
    },
    body: JSON.stringify({ query: QUERY, variables: { login } }),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`GitHub API error ${res.status}: ${text}`);
  }

  const json = await res.json();
  if (json.errors) {
    throw new Error(`GraphQL error: ${JSON.stringify(json.errors)}`);
  }

  const calendar = json.data.user.contributionsCollection.contributionCalendar;

  // Flatten weeks -> a single chronological array of { date, count }
  const days = calendar.weeks
    .flatMap((w) => w.contributionDays)
    .map((d) => ({ date: d.date, count: d.contributionCount }))
    .sort((a, b) => (a.date < b.date ? -1 : 1));

  return {
    totalContributions: calendar.totalContributions,
    days,
  };
}

module.exports = { fetchContributions };
