#!/usr/bin/env python3
"""Write site/index.html, a static dashboard of the release registry.

The page embeds the registry and Gaussian catalog as of the build, then in the
browser loads the live copies from the default branch plus the GitHub Releases
API, and compares them: registered vs latest version, publish date, size,
downloads and SHA-256 digest. It falls back to the embedded snapshot offline.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "soraxas/inlier-data"
BRANCH = "main"
SOURCES = {
    "registry": "inlier_data/release_artifacts.json",
    "gaussian": "inlier_data/gaussian_splats.json",
}

TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Inlier Data Releases</title>
<style>
:root {
  --bg: #f7f7f5; --surface: #ffffff; --text: #1c1c1a; --muted: #6b6b66;
  --border: #e3e3de; --accent: #2f5bd3;
  --ok-bg: #e6f4ea; --ok: #1e6b34; --warn-bg: #fdf1d8; --warn: #8a5a00;
  --bad-bg: #fbe4e2; --bad: #a3261c; --info-bg: #e8eefc; --info: #2747a8;
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #141413; --surface: #1d1d1b; --text: #ecebe6; --muted: #a09f98;
    --border: #2e2e2b; --accent: #8aa8ff;
    --ok-bg: #173322; --ok: #8fd6a4; --warn-bg: #3a2d10; --warn: #f0c46a;
    --bad-bg: #3d1b18; --bad: #f4a29a; --info-bg: #1b2547; --info: #a9bdff;
    color-scheme: dark;
  }
}
:root[data-theme="dark"] {
  --bg: #141413; --surface: #1d1d1b; --text: #ecebe6; --muted: #a09f98;
  --border: #2e2e2b; --accent: #8aa8ff;
  --ok-bg: #173322; --ok: #8fd6a4; --warn-bg: #3a2d10; --warn: #f0c46a;
  --bad-bg: #3d1b18; --bad: #f4a29a; --info-bg: #1b2547; --info: #a9bdff;
  color-scheme: dark;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--text);
  font: 14px/1.5 ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
}
main { max-width: 1180px; margin: 0 auto; padding: 32px 16px 48px; }
header { display: flex; flex-wrap: wrap; gap: 12px; align-items: baseline;
  justify-content: space-between; margin-bottom: 20px; }
h1 { font-size: 22px; margin: 0; letter-spacing: -0.01em; }
h2 { font-size: 15px; margin: 28px 0 4px; }
h2 + .meta { margin: 0 0 10px; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
.meta { color: var(--muted); font-size: 13px; }
.source { display: inline-block; padding: 1px 8px; border-radius: 999px;
  font-size: 12px; margin-left: 6px; }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 10px; margin-bottom: 18px; }
.tile { background: var(--surface); border: 1px solid var(--border);
  border-radius: 10px; padding: 12px 14px; }
.tile .value { font-size: 24px; font-weight: 600; font-variant-numeric: tabular-nums; }
.tile .label { color: var(--muted); font-size: 12px; }
.tile.alert { border-color: var(--warn); }
.tile.alert .value { color: var(--warn); }
td.tag { white-space: nowrap; }
.toolbar { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
input[type=search], select, button {
  font: inherit; color: var(--text); background: var(--surface);
  border: 1px solid var(--border); border-radius: 8px; padding: 6px 10px; }
input[type=search] { flex: 1 1 220px; min-width: 0; }
button { cursor: pointer; }
.table-wrap { overflow-x: auto; background: var(--surface);
  border: 1px solid var(--border); border-radius: 10px; }
table { width: 100%; border-collapse: collapse; min-width: 860px; }
th, td { text-align: left; padding: 9px 12px; border-bottom: 1px solid var(--border);
  vertical-align: top; }
th { font-size: 12px; color: var(--muted); font-weight: 500; white-space: nowrap; }
tr:last-child td { border-bottom: 0; }
td.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
th.num { text-align: right; }
.name { font-weight: 600; }
.sub { color: var(--muted); font-size: 12px; }
code { font: 12px ui-monospace, SFMono-Regular, Menlo, monospace; }
.pill { display: inline-block; padding: 1px 8px; border-radius: 999px; font-size: 12px;
  font-weight: 500; white-space: nowrap; }
.ok { background: var(--ok-bg); color: var(--ok); }
.warn { background: var(--warn-bg); color: var(--warn); }
.bad { background: var(--bad-bg); color: var(--bad); }
.info { background: var(--info-bg); color: var(--info); }
.empty { padding: 18px; color: var(--muted); }
</style>
</head>
<body>
<main>
  <header>
    <div>
      <h1>Inlier Data Releases</h1>
      <div class="meta">
        <a id="repo-link"></a> · <span id="checked"></span><span id="source" class="source"></span>
      </div>
    </div>
    <button id="refresh" type="button">Refresh</button>
  </header>

  <section class="tiles" id="tiles"></section>

  <div class="toolbar">
    <input id="filter" type="search" placeholder="Filter datasets, tags, licenses" aria-label="Filter">
    <select id="status" aria-label="Status">
      <option value="">All statuses</option>
      <option value="ok">Up to date</option>
      <option value="problem">Needs attention</option>
    </select>
  </div>
  <div class="table-wrap">
    <table>
      <thead><tr>
        <th>Dataset</th><th>Status</th><th>Registered</th><th>Latest release</th>
        <th>Published</th><th class="num">Size</th><th class="num">Downloads</th>
        <th>SHA-256</th><th>License</th>
      </tr></thead>
      <tbody id="rows"></tbody>
    </table>
  </div>

  <h2>Published but not registered</h2>
  <p class="meta">Uploaded to a GitHub release, but missing from <code>release_artifacts.json</code> on the default branch, so <code>inlier_data</code> cannot fetch them. Register them by committing the publisher's registry update.</p>
  <div class="table-wrap">
    <table>
      <thead><tr><th>Asset</th><th>Release</th><th>Published</th><th class="num">Size</th></tr></thead>
      <tbody id="orphans"></tbody>
    </table>
  </div>
</main>
<script>
const CONFIG = __CONFIG__;
const SNAPSHOT = __SNAPSHOT__;

const $ = (id) => document.getElementById(id);
const el = (tag, props = {}, ...children) => {
  const node = Object.assign(document.createElement(tag), props);
  for (const child of children) node.append(child ?? "");
  return node;
};
const link = (href, text) => el("a", { href, textContent: text, target: "_blank", rel: "noopener" });
const pill = (cls, text, title = "") => el("span", { className: `pill ${cls}`, textContent: text, title });

function bytes(n) {
  if (n == null) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let i = 0;
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(i ? 1 : 0)} ${units[i]}`;
}
const date = (iso) => iso ? new Date(iso).toLocaleDateString(undefined,
  { year: "numeric", month: "short", day: "numeric" }) : "—";
// "phototourism-ransac-val-v1" -> { family: "phototourism-ransac-val", version: 1 }
function parseVersion(tag) {
  const match = /^(.*)-v(\d+)$/.exec(tag);
  return match ? { family: match[1], version: Number(match[2]) } : { family: tag, version: 0 };
}

async function getJSON(url) {
  const response = await fetch(url, { headers: { Accept: "application/vnd.github+json" } });
  if (!response.ok) throw new Error(`${response.status} ${url}`);
  return response.json();
}

async function loadLive() {
  const raw = (path) => `https://raw.githubusercontent.com/${CONFIG.repository}/${CONFIG.branch}/${path}`;
  const releases = [];
  for (let page = 1; ; page++) {
    const batch = await getJSON(`https://api.github.com/repos/${CONFIG.repository}/releases?per_page=100&page=${page}`);
    releases.push(...batch);
    if (batch.length < 100) break;
  }
  const [registry, gaussian] = await Promise.all([raw(CONFIG.sources.registry), raw(CONFIG.sources.gaussian)].map(getJSON));
  return { registry, gaussian, releases, live: true };
}

function analyse({ registry, gaussian, releases }) {
  const assets = new Map();
  const latest = new Map();
  for (const release of releases ?? []) {
    const { family, version } = parseVersion(release.tag_name);
    const current = latest.get(family);
    if (!current || version > current.version) latest.set(family, { version, release });
    for (const asset of release.assets) assets.set(asset.browser_download_url, { asset, release });
  }
  const licenses = new Map();
  for (const [id, dataset] of Object.entries(gaussian?.datasets ?? {})) {
    if (dataset.release_artifact) licenses.set(dataset.release_artifact, { id, ...dataset });
  }

  const rows = Object.entries(registry).sort(([a], [b]) => a.localeCompare(b)).map(([name, entry]) => {
    const found = assets.get(entry.url);
    assets.delete(entry.url);
    const { family, version } = parseVersion(entry.release);
    const newest = latest.get(family);
    const problems = [];
    if (releases) {
      if (!found) problems.push(["bad", "Missing asset", "No release asset at the registered URL"]);
      else if (found.asset.digest && found.asset.digest !== `sha256:${entry.sha256}`)
        problems.push(["bad", "Digest mismatch", `GitHub reports ${found.asset.digest}`]);
      else if (!found.asset.digest) problems.push(["warn", "No digest", "GitHub has no digest for this asset"]);
      if (newest && newest.version > version)
        problems.push(["warn", `v${newest.version} unregistered`, `${newest.release.tag_name} exists but is not in the registry`]);
    }
    return { name, entry, family, found, newest, problems, license: licenses.get(name) };
  });
  const orphans = [...assets.values()];
  return { rows, orphans };
}

function render(data, checkedAt) {
  const { rows, orphans } = analyse(data);
  $("source").textContent = data.live ? "live" : "snapshot";
  $("source").className = `source ${data.live ? "ok" : "warn"}`;
  $("source").title = data.live ? "" : `GitHub unavailable (${data.error}); showing data from ${CONFIG.builtAt}`;
  $("checked").textContent = `checked ${checkedAt.toLocaleString()}`;

  const problems = rows.filter((row) => row.problems.length).length + orphans.length;
  const downloads = rows.reduce((sum, row) => sum + (row.found?.asset.download_count ?? 0), 0);
  const total = rows.reduce((sum, row) => sum + (row.found?.asset.size ?? 0), 0);
  const newest = rows.map((row) => row.found?.release.published_at).filter(Boolean).sort().at(-1);
  $("tiles").replaceChildren(...[
    [rows.length, "registered artifacts"],
    [data.releases ? problems : "—", "need attention"],
    [bytes(total), "total size"],
    [downloads.toLocaleString(), "downloads"],
    [date(newest), "latest publish"],
  ].map(([value, label]) => el("div", { className: `tile${label === "need attention" && problems ? " alert" : ""}` },
    el("div", { className: "value", textContent: value }), el("div", { className: "label", textContent: label }))));

  const query = $("filter").value.trim().toLowerCase();
  const wanted = $("status").value;
  const visible = rows.filter((row) => {
    const text = [row.name, row.entry.release, row.license?.title, row.license?.license?.status].join(" ").toLowerCase();
    if (query && !text.includes(query)) return false;
    if (wanted === "ok") return !row.problems.length;
    if (wanted === "problem") return row.problems.length > 0;
    return true;
  });

  $("rows").replaceChildren(...visible.map((row) => {
    const { entry, found, newest, license } = row;
    const status = !data.releases ? pill("info", "Unchecked")
      : row.problems.length ? el("div", {}, ...row.problems.map(([cls, text, title]) => pill(cls, text, title)))
      : pill("ok", "Up to date");
    const releaseUrl = `https://github.com/${CONFIG.repository}/releases/tag/${entry.release}`;
    const licenseCell = license
      ? el("div", {}, el("div", { textContent: license.license.status }),
          el("div", { className: "sub" }, ...license.license.evidence.flatMap((item, i) =>
            [i ? " · " : "", link(item.url, item.declaration)])))
      : el("span", { className: "sub", textContent: "—" });
    return el("tr", {},
      el("td", {}, el("div", { className: "name", textContent: license?.title ?? row.family }),
        el("div", { className: "sub" }, link(entry.url, row.name))),
      el("td", {}, status),
      el("td", { className: "tag" }, link(releaseUrl, entry.release)),
      el("td", { className: "tag" }, !newest ? "—"
        : newest.release.tag_name === entry.release ? el("span", { className: "sub", textContent: "same" })
        : link(newest.release.html_url, newest.release.tag_name)),
      el("td", { textContent: date(found?.release.published_at) }),
      el("td", { className: "num", textContent: bytes(found?.asset.size) }),
      el("td", { className: "num", textContent: found ? found.asset.download_count.toLocaleString() : "—" }),
      el("td", {}, el("code", { textContent: entry.sha256.slice(0, 12), title: entry.sha256 })),
      el("td", {}, licenseCell));
  }));
  if (!visible.length) $("rows").replaceChildren(el("tr", {}, el("td", { colSpan: 9, className: "empty", textContent: "No matching artifacts." })));

  $("orphans").replaceChildren(...(orphans.length ? orphans.map(({ asset, release }) => el("tr", {},
      el("td", {}, link(asset.browser_download_url, asset.name)),
      el("td", {}, link(release.html_url, release.tag_name)),
      el("td", { textContent: date(release.published_at) }),
      el("td", { className: "num", textContent: bytes(asset.size) })))
    : [el("tr", {}, el("td", { colSpan: 4, className: "empty",
        textContent: data.releases ? "Every release asset is registered." : "Not checked: GitHub unavailable." }))]));
}

let current = null;
async function refresh() {
  $("refresh").disabled = true;
  try {
    current = await loadLive();
  } catch (error) {
    current = { ...SNAPSHOT, releases: null, live: false, error: error.message };
  }
  $("refresh").disabled = false;
  render(current, new Date());
}

$("repo-link").href = `https://github.com/${CONFIG.repository}`;
$("repo-link").textContent = CONFIG.repository;
$("filter").addEventListener("input", () => current && render(current, new Date()));
$("status").addEventListener("change", () => current && render(current, new Date()));
$("refresh").addEventListener("click", refresh);
refresh();
</script>
</body>
</html>
"""


def _script_json(value: object) -> str:
    # Safe to inline inside <script>: no "</script>" or HTML comment openers.
    return json.dumps(value, sort_keys=True).replace("<", "\\u003c")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "site" / "index.html")
    args = parser.parse_args()

    snapshot = {
        key: json.loads((ROOT / path).read_text()) for key, path in SOURCES.items()
    }
    config = {
        "repository": REPOSITORY,
        "branch": BRANCH,
        "sources": SOURCES,
        "builtAt": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }
    html = TEMPLATE.replace("__CONFIG__", _script_json(config)).replace(
        "__SNAPSHOT__", _script_json(snapshot)
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html)
    print(args.output)


if __name__ == "__main__":
    main()
