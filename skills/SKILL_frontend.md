# SKILL: React Frontend

## Purpose
Public-facing website displaying fighter profiles, fight predictions, model performance metrics, bet tracker, and blog posts.

## Files It Owns
```
frontend/
├── index.html
├── vite.config.js
├── tailwind.config.js
├── src/
│   ├── main.jsx
│   ├── App.jsx
│   ├── lib/
│   │   ├── api.js           # All API calls go here — nowhere else
│   │   └── utils.js         # Odds conversion, formatters
│   ├── components/
│   │   ├── EloChart.jsx
│   │   ├── PredictionCard.jsx
│   │   ├── BetTable.jsx
│   │   ├── ModelMetricsPanel.jsx
│   │   └── MarkdownRenderer.jsx
│   └── pages/
│       ├── Home.jsx
│       ├── Fighters.jsx
│       ├── FighterProfile.jsx
│       ├── Predictions.jsx
│       ├── ModelPerformance.jsx
│       ├── BetTracker.jsx
│       ├── Blog.jsx
│       └── BlogPost.jsx
```

## Key Libraries
- `react` + `react-dom` — UI framework
- `react-router-dom` — client-side routing
- `@tanstack/react-query` — all data fetching and caching
- `recharts` — all charts (Elo history, ROI, calibration curve)
- `react-markdown` — render blog post markdown content
- `tailwindcss` — styling

## Patterns

### API Client (lib/api.js)
```javascript
// All fetch calls go through this file. Never import fetch in a component.
const BASE_URL = import.meta.env.VITE_API_URL;

async function get(path) {
  const res = await fetch(`${BASE_URL}${path}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

async function post(path, body) {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export const api = {
  getFighters: (skip = 0, limit = 50) => get(`/fighters?skip=${skip}&limit=${limit}`),
  getFighter: (id) => get(`/fighters/${id}`),
  getFighterElo: (id) => get(`/fighters/${id}/elo`),
  getPredictions: () => get("/predictions"),
  getBets: () => get("/bets"),
  getBlogPosts: () => get("/blog"),
  getBlogPost: (slug) => get(`/blog/${slug}`),
};
```

### TanStack Query Usage
```javascript
// In a component — correct pattern
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";

function FighterProfile({ fighterId }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["fighter", fighterId],
    queryFn: () => api.getFighter(fighterId),
  });

  if (isLoading) return <div className="text-gray-400">Loading...</div>;
  if (error) return <div className="text-red-500">Failed to load fighter.</div>;

  return <div>{data.name}</div>;
}
```

### Elo History Chart
```javascript
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

function EloChart({ data }) {
  // data: [{ fight_date, elo_standard, elo_modified, opponent_name }, ...]
  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data}>
        <XAxis dataKey="fight_date" />
        <YAxis domain={["auto", "auto"]} />
        <Tooltip />
        <Line type="monotone" dataKey="elo_standard" stroke="#1a73e8" dot={false} name="Standard Elo" />
        <Line type="monotone" dataKey="elo_modified" stroke="#e8711a" dot={false} name="Modified Elo" />
      </LineChart>
    </ResponsiveContainer>
  );
}
```

### Odds Utility (lib/utils.js)
```javascript
export function americanToDecimal(oddsStr) {
  const odds = parseInt(oddsStr);
  return odds > 0 ? odds / 100 + 1 : 100 / Math.abs(odds) + 1;
}

export function formatOdds(oddsStr) {
  const n = parseInt(oddsStr);
  return n > 0 ? `+${n}` : `${n}`;
}

export function calculateROI(bets) {
  const totalStaked = bets.reduce((s, b) => s + b.stake_usd, 0);
  const totalProfit = bets.reduce((s, b) => s + (b.profit_usd ?? 0), 0);
  return totalStaked === 0 ? 0 : (totalProfit / totalStaked) * 100;
}
```

### Markdown Renderer
```javascript
import ReactMarkdown from "react-markdown";

function MarkdownRenderer({ content }) {
  return (
    <div className="prose prose-invert max-w-none">
      <ReactMarkdown>{content}</ReactMarkdown>
    </div>
  );
}
```

## Gotchas
- Vite uses `import.meta.env.VITE_*` for env vars. `process.env` does not work in Vite.
- TanStack Query v5 uses `{ queryKey, queryFn }` object syntax — not the old positional argument style.
- `react-markdown` renders raw HTML by default only if you pass `rehype-raw`. Keep it off unless needed.
- Tailwind's `prose` class requires the `@tailwindcss/typography` plugin for blog post formatting.
- React Router v6 uses `<Routes>` and `<Route element={}>` — not `<Switch>` and `component={}`.

## LLM Instructions
- See spec Section 10 for the full page map and component list.
- All API calls go through `lib/api.js`. Never call `fetch()` directly in a component file.
- Use `import.meta.env.VITE_API_URL` for the API base URL — never hard-code it.
- All charts use `recharts`. Do not introduce Chart.js or any other charting library.
- Do not install MUI, Ant Design, or any other UI component library. Use Tailwind only.
- Bootstrap the project with: `npm create vite@latest frontend -- --template react`
- **Focus on mobile-first design.** Use responsive Tailwind classes (e.g., `flex-col md:flex-row`, `p-4 md:p-8`) to ensure all views look optimal on small screens before scaling up.

## Status
NOT STARTED
