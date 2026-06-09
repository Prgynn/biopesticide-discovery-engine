"""
day18_query_api.py
==================
Local Flask API + browser dashboard for the biopesticide discovery engine.

Endpoints:
  GET /                          — dashboard homepage
  GET /api/top?grade=A&limit=20  — top compound-pest pairs by grade
  GET /api/compound/<name>       — all data for a compound
  GET /api/pest/<name>           — all compounds active against a pest
  GET /api/search?q=neem         — search compounds + pests
  GET /api/stats                 — database summary stats
  GET /api/graph                 — graph data for visualization

Run:
  pip install flask
  python day18_query_api.py
  Open: http://localhost:5000
"""

import sqlite3, json, os
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)
DB_PATH = "biopesticide.db"

# ─────────────────────────────────────────────
# DB HELPER
# ─────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ─────────────────────────────────────────────
# HTML DASHBOARD
# ─────────────────────────────────────────────

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Biopesticide Discovery Engine</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', sans-serif; background: #0f1117; color: #e0e0e0; }

  .header {
    background: linear-gradient(135deg, #1a472a, #2d6a4f);
    padding: 24px 40px;
    border-bottom: 2px solid #40916c;
  }
  .header h1 { font-size: 1.8rem; color: #95d5b2; letter-spacing: 1px; }
  .header p  { color: #74c69d; margin-top: 4px; font-size: 0.9rem; }

  .stats-bar {
    display: flex; gap: 16px; padding: 16px 40px;
    background: #161b22; border-bottom: 1px solid #30363d;
    flex-wrap: wrap;
  }
  .stat-chip {
    background: #1f2937; border: 1px solid #374151;
    border-radius: 20px; padding: 6px 16px;
    font-size: 0.85rem; color: #9ca3af;
  }
  .stat-chip span { color: #6ee7b7; font-weight: 700; }

  .main { display: grid; grid-template-columns: 320px 1fr; gap: 0; min-height: calc(100vh - 120px); }

  .sidebar {
    background: #161b22; border-right: 1px solid #30363d;
    padding: 24px 20px;
  }
  .sidebar h3 { color: #6ee7b7; font-size: 0.8rem; text-transform: uppercase;
                letter-spacing: 1px; margin-bottom: 12px; }

  .search-box {
    width: 100%; padding: 10px 14px; background: #0d1117;
    border: 1px solid #30363d; border-radius: 8px;
    color: #e0e0e0; font-size: 0.9rem; margin-bottom: 20px;
    outline: none;
  }
  .search-box:focus { border-color: #40916c; }

  .grade-filter { display: flex; gap: 8px; margin-bottom: 20px; flex-wrap: wrap; }
  .grade-btn {
    padding: 5px 14px; border-radius: 6px; border: 1px solid #374151;
    background: #1f2937; color: #9ca3af; cursor: pointer; font-size: 0.8rem;
    transition: all 0.2s;
  }
  .grade-btn:hover, .grade-btn.active { border-color: #40916c; color: #6ee7b7; background: #1a3a2a; }
  .grade-btn.A { border-color: #166534; color: #4ade80; }
  .grade-btn.B { border-color: #1d4ed8; color: #60a5fa; }
  .grade-btn.C { border-color: #92400e; color: #fbbf24; }

  .compound-list { max-height: 400px; overflow-y: auto; }
  .compound-item {
    padding: 8px 12px; border-radius: 6px; cursor: pointer;
    margin-bottom: 4px; border: 1px solid transparent;
    transition: all 0.15s; font-size: 0.88rem;
  }
  .compound-item:hover { background: #1f2937; border-color: #374151; }
  .compound-item.selected { background: #1a3a2a; border-color: #40916c; color: #6ee7b7; }
  .compound-item .badge {
    float: right; font-size: 0.75rem; padding: 1px 7px;
    border-radius: 10px; background: #374151; color: #9ca3af;
  }

  .content { padding: 24px 32px; }

  .results-header {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 20px;
  }
  .results-header h2 { color: #6ee7b7; font-size: 1.1rem; }

  .card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; }

  .card {
    background: #161b22; border: 1px solid #30363d; border-radius: 10px;
    padding: 18px; transition: border-color 0.2s;
  }
  .card:hover { border-color: #40916c; }
  .card-top { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px; }
  .card-compound { font-weight: 600; color: #e0e0e0; font-size: 0.95rem; }
  .card-pest { color: #9ca3af; font-size: 0.82rem; margin-top: 3px; }
  .card-crop { color: #6b7280; font-size: 0.78rem; }

  .grade-badge {
    padding: 3px 10px; border-radius: 12px; font-size: 0.8rem; font-weight: 700;
    flex-shrink: 0;
  }
  .grade-A { background: #14532d; color: #4ade80; }
  .grade-B { background: #1e3a5f; color: #60a5fa; }
  .grade-C { background: #451a03; color: #fbbf24; }
  .grade-D { background: #1f2937; color: #6b7280; }

  .card-stats { display: flex; gap: 12px; margin-top: 10px; flex-wrap: wrap; }
  .card-stat { font-size: 0.78rem; color: #6b7280; }
  .card-stat span { color: #9ca3af; }

  .lc50-bar { margin-top: 10px; }
  .lc50-label { font-size: 0.75rem; color: #6b7280; margin-bottom: 4px; }
  .bar-track { background: #1f2937; border-radius: 4px; height: 6px; overflow: hidden; }
  .bar-fill { background: linear-gradient(90deg, #40916c, #6ee7b7); height: 100%; border-radius: 4px; }

  .empty-state {
    text-align: center; padding: 60px 20px; color: #4b5563;
  }
  .empty-state h3 { font-size: 1.1rem; margin-bottom: 8px; }

  .tab-bar { display: flex; gap: 4px; margin-bottom: 24px; }
  .tab {
    padding: 8px 20px; border-radius: 8px 8px 0 0; cursor: pointer;
    font-size: 0.85rem; border: 1px solid #30363d; border-bottom: none;
    background: #0d1117; color: #6b7280; transition: all 0.2s;
  }
  .tab.active { background: #161b22; color: #6ee7b7; border-color: #40916c; }

  .table-view { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
  .table-view th {
    text-align: left; padding: 10px 14px; background: #1f2937;
    color: #6b7280; font-weight: 600; font-size: 0.75rem;
    text-transform: uppercase; letter-spacing: 0.5px;
    border-bottom: 1px solid #374151;
  }
  .table-view td { padding: 10px 14px; border-bottom: 1px solid #1f2937; color: #d1d5db; }
  .table-view tr:hover td { background: #161b22; }

  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-track { background: #0d1117; }
  ::-webkit-scrollbar-thumb { background: #374151; border-radius: 3px; }
</style>
</head>
<body>

<div class="header">
  <h1>🌿 Biopesticide Discovery Engine</h1>
  <p>AI-powered compound-pest evidence database</p>
</div>

<div class="stats-bar" id="statsBar">
  <div class="stat-chip">Loading...</div>
</div>

<div class="main">
  <div class="sidebar">
    <h3>Search</h3>
    <input class="search-box" id="searchInput" placeholder="compound or pest name..." oninput="onSearch()">

    <h3>Filter by Grade</h3>
    <div class="grade-filter">
      <button class="grade-btn active" onclick="filterGrade('all', this)">All</button>
      <button class="grade-btn A" onclick="filterGrade('A', this)">Grade A</button>
      <button class="grade-btn B" onclick="filterGrade('B', this)">Grade B</button>
      <button class="grade-btn C" onclick="filterGrade('C', this)">Grade C</button>
      <button class="grade-btn" onclick="filterGrade('D', this)">Grade D</button>
    </div>

    <h3>Top Compounds</h3>
    <div class="compound-list" id="compoundList"></div>
  </div>

  <div class="content">
    <div class="tab-bar">
      <div class="tab active" onclick="switchTab('cards', this)">Card View</div>
      <div class="tab" onclick="switchTab('table', this)">Table View</div>
      <div class="tab" onclick="switchTab('broad', this)">Broad Spectrum</div>
    </div>

    <div id="tab-cards">
      <div class="results-header">
        <h2 id="resultsTitle">Top Grade A Pairs</h2>
        <span id="resultsCount" style="color:#6b7280;font-size:0.85rem;"></span>
      </div>
      <div class="card-grid" id="cardGrid"></div>
    </div>

    <div id="tab-table" style="display:none">
      <table class="table-view">
        <thead>
          <tr>
            <th>Compound</th><th>Pest</th><th>Crop</th>
            <th>Grade</th><th>Papers</th><th>Avg LC50</th><th>Avg Mortality</th>
          </tr>
        </thead>
        <tbody id="tableBody"></tbody>
      </table>
    </div>

    <div id="tab-broad" style="display:none">
      <div class="results-header"><h2>Broad-Spectrum Candidates</h2></div>
      <div id="broadContent"></div>
    </div>
  </div>
</div>

<script>
let allData = [];
let currentGrade = 'all';
let currentCompound = null;
let currentTab = 'cards';

async function init() {
  const [stats, top, compounds] = await Promise.all([
    fetch('/api/stats').then(r=>r.json()),
    fetch('/api/top?limit=200').then(r=>r.json()),
    fetch('/api/compounds').then(r=>r.json()),
  ]);

  // Stats bar
  document.getElementById('statsBar').innerHTML = [
    `<div class="stat-chip">Papers <span>${stats.papers}</span></div>`,
    `<div class="stat-chip">Compounds <span>${stats.compounds}</span></div>`,
    `<div class="stat-chip">Bioactivity records <span>${stats.bioactivity}</span></div>`,
    `<div class="stat-chip">Grade A pairs <span>${stats.grade_A}</span></div>`,
    `<div class="stat-chip">Grade B pairs <span>${stats.grade_B}</span></div>`,
    `<div class="stat-chip">Pests covered <span>${stats.pests}</span></div>`,
  ].join('');

  allData = top.results || [];
  renderCompoundList(compounds.compounds || []);
  renderResults(allData);
}

function renderCompoundList(compounds) {
  const el = document.getElementById('compoundList');
  el.innerHTML = compounds.slice(0,30).map(c => `
    <div class="compound-item" onclick="selectCompound('${c.name}', this)">
      ${c.name}
      <span class="badge">${c.score}</span>
    </div>
  `).join('');
}

function renderResults(data) {
  document.getElementById('resultsCount').textContent = `${data.length} results`;
  if (currentTab === 'cards') renderCards(data);
  else if (currentTab === 'table') renderTable(data);
}

function renderCards(data) {
  const grid = document.getElementById('cardGrid');
  if (!data.length) {
    grid.innerHTML = '<div class="empty-state"><h3>No results found</h3><p>Try a different filter or search</p></div>';
    return;
  }
  grid.innerHTML = data.slice(0,60).map(r => {
    const lc50 = r.avg_lc50 ? `<div class="lc50-bar"><div class="lc50-label">Avg LC50: ${r.avg_lc50} ppm</div><div class="bar-track"><div class="bar-fill" style="width:${Math.min(100,r.avg_lc50/10)}%"></div></div></div>` : '';
    const mort = r.avg_mortality ? `<div class="card-stat">Avg mortality: <span>${r.avg_mortality}%</span></div>` : '';
    return `
    <div class="card">
      <div class="card-top">
        <div>
          <div class="card-compound">${r.compound}</div>
          <div class="card-pest">→ ${r.pest}</div>
          <div class="card-crop">${r.crop || ''}</div>
        </div>
        <div class="grade-badge grade-${r.grade}">${r.grade}</div>
      </div>
      <div class="card-stats">
        <div class="card-stat">Papers: <span>${r.n_papers}</span></div>
        ${mort}
      </div>
      ${lc50}
    </div>`;
  }).join('');
}

function renderTable(data) {
  document.getElementById('tableBody').innerHTML = data.slice(0,100).map(r => `
    <tr>
      <td>${r.compound}</td>
      <td>${r.pest}</td>
      <td>${r.crop||'-'}</td>
      <td><span class="grade-badge grade-${r.grade}">${r.grade}</span></td>
      <td>${r.n_papers}</td>
      <td>${r.avg_lc50||'-'}</td>
      <td>${r.avg_mortality ? r.avg_mortality+'%' : '-'}</td>
    </tr>
  `).join('');
}

async function filterGrade(grade, btn) {
  document.querySelectorAll('.grade-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  currentGrade = grade;
  currentCompound = null;
  document.querySelectorAll('.compound-item').forEach(i => i.classList.remove('selected'));

  const url = grade === 'all' ? '/api/top?limit=200' : `/api/top?grade=${grade}&limit=200`;
  const data = await fetch(url).then(r=>r.json());
  allData = data.results || [];
  document.getElementById('resultsTitle').textContent =
    grade === 'all' ? 'All Pairs' : `Grade ${grade} Pairs`;
  renderResults(allData);
}

async function selectCompound(name, el) {
  document.querySelectorAll('.compound-item').forEach(i => i.classList.remove('selected'));
  el.classList.add('selected');
  currentCompound = name;
  document.getElementById('resultsTitle').textContent = name;

  const data = await fetch(`/api/compound/${encodeURIComponent(name)}`).then(r=>r.json());
  allData = data.pairs || [];
  renderResults(allData);
}

async function onSearch() {
  const q = document.getElementById('searchInput').value.trim();
  if (q.length < 2) { init(); return; }
  const data = await fetch(`/api/search?q=${encodeURIComponent(q)}`).then(r=>r.json());
  allData = data.results || [];
  document.getElementById('resultsTitle').textContent = `Results for "${q}"`;
  renderResults(allData);
}

async function switchTab(tab, el) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
  currentTab = tab;
  document.getElementById('tab-cards').style.display = tab==='cards' ? '' : 'none';
  document.getElementById('tab-table').style.display = tab==='table' ? '' : 'none';
  document.getElementById('tab-broad').style.display = tab==='broad' ? '' : 'none';

  if (tab === 'broad') {
    const data = await fetch('/api/broad').then(r=>r.json());
    const el2 = document.getElementById('broadContent');
    el2.innerHTML = '<div class="card-grid">' + (data.compounds||[]).map(c => `
      <div class="card">
        <div class="card-compound">${c.compound}</div>
        <div class="card-stats" style="margin-top:10px">
          <div class="card-stat">Pest targets: <span>${c.n_pests}</span></div>
          <div class="card-stat">Total papers: <span>${c.total_papers}</span></div>
          <div class="card-stat">Score: <span>${c.score}</span></div>
        </div>
        <div style="margin-top:10px;font-size:0.8rem;color:#6b7280">
          ${c.pests.slice(0,5).join(' • ')}
        </div>
      </div>
    `).join('') + '</div>';
  } else {
    renderResults(allData);
  }
}

init();
</script>
</body>
</html>
"""

# ─────────────────────────────────────────────
# API ROUTES
# ─────────────────────────────────────────────

@app.route("/")
def dashboard():
    return render_template_string(DASHBOARD_HTML)


@app.route("/api/stats")
def api_stats():
    conn = get_db()
    stats = {
        "papers":     conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0],
        "compounds":  conn.execute("SELECT COUNT(*) FROM compounds").fetchone()[0],
        "bioactivity":conn.execute("SELECT COUNT(*) FROM bioactivity").fetchone()[0],
        "grade_A":    conn.execute("SELECT COUNT(DISTINCT compound_id||pest) FROM bioactivity WHERE evidence_grade='A'").fetchone()[0],
        "grade_B":    conn.execute("SELECT COUNT(DISTINCT compound_id||pest) FROM bioactivity WHERE evidence_grade='B'").fetchone()[0],
        "pests":      conn.execute("SELECT COUNT(DISTINCT pest) FROM bioactivity WHERE pest!=''").fetchone()[0],
    }
    conn.close()
    return jsonify(stats)


@app.route("/api/top")
def api_top():
    grade = request.args.get("grade", "")
    limit = min(int(request.args.get("limit", 50)), 500)
    conn  = get_db()
    where = f"AND b.evidence_grade='{grade}'" if grade else ""
    rows  = conn.execute(f"""
        SELECT c.name, b.pest, b.crop, b.evidence_grade,
               COUNT(DISTINCT b.paper_id) as n_papers,
               AVG(b.lc50) as avg_lc50,
               AVG(b.efficacy_pct) as avg_mort
        FROM bioactivity b
        JOIN compounds c ON c.id = b.compound_id
        WHERE b.pest != '' {where}
        GROUP BY b.compound_id, b.pest
        ORDER BY
          CASE b.evidence_grade WHEN 'A' THEN 4 WHEN 'B' THEN 3 WHEN 'C' THEN 2 ELSE 1 END DESC,
          n_papers DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    results = [{"compound": r[0], "pest": r[1], "crop": r[2] or "",
                "grade": r[3], "n_papers": r[4],
                "avg_lc50": round(r[5],2) if r[5] else None,
                "avg_mortality": round(r[6],1) if r[6] else None}
               for r in rows]
    return jsonify({"results": results, "count": len(results)})


@app.route("/api/compound/<name>")
def api_compound(name):
    conn = get_db()
    rows = conn.execute("""
        SELECT c.name, b.pest, b.crop, b.evidence_grade,
               COUNT(DISTINCT b.paper_id) as n_papers,
               AVG(b.lc50) as avg_lc50, AVG(b.efficacy_pct) as avg_mort
        FROM bioactivity b
        JOIN compounds c ON c.id = b.compound_id
        WHERE LOWER(c.name) LIKE LOWER(?)
        GROUP BY b.compound_id, b.pest
        ORDER BY n_papers DESC
    """, (f"%{name}%",)).fetchall()
    conn.close()
    pairs = [{"compound": r[0], "pest": r[1], "crop": r[2] or "",
              "grade": r[3], "n_papers": r[4],
              "avg_lc50": round(r[5],2) if r[5] else None,
              "avg_mortality": round(r[6],1) if r[6] else None}
             for r in rows]
    return jsonify({"compound": name, "pairs": pairs})


@app.route("/api/pest/<name>")
def api_pest(name):
    conn = get_db()
    rows = conn.execute("""
        SELECT c.name, b.pest, b.crop, b.evidence_grade,
               COUNT(DISTINCT b.paper_id) as n_papers,
               AVG(b.lc50) as avg_lc50, AVG(b.efficacy_pct) as avg_mort
        FROM bioactivity b
        JOIN compounds c ON c.id = b.compound_id
        WHERE LOWER(b.pest) LIKE LOWER(?)
        GROUP BY b.compound_id, b.pest
        ORDER BY n_papers DESC
    """, (f"%{name}%",)).fetchall()
    conn.close()
    results = [{"compound": r[0], "pest": r[1], "crop": r[2] or "",
                "grade": r[3], "n_papers": r[4],
                "avg_lc50": round(r[5],2) if r[5] else None,
                "avg_mortality": round(r[6],1) if r[6] else None}
               for r in rows]
    return jsonify({"pest": name, "results": results})


@app.route("/api/search")
def api_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"results": []})
    conn = get_db()
    rows = conn.execute("""
        SELECT c.name, b.pest, b.crop, b.evidence_grade,
               COUNT(DISTINCT b.paper_id) as n_papers,
               AVG(b.lc50) as avg_lc50, AVG(b.efficacy_pct) as avg_mort
        FROM bioactivity b
        JOIN compounds c ON c.id = b.compound_id
        WHERE LOWER(c.name) LIKE LOWER(?) OR LOWER(b.pest) LIKE LOWER(?)
        GROUP BY b.compound_id, b.pest
        ORDER BY n_papers DESC
        LIMIT 100
    """, (f"%{q}%", f"%{q}%")).fetchall()
    conn.close()
    results = [{"compound": r[0], "pest": r[1], "crop": r[2] or "",
                "grade": r[3], "n_papers": r[4],
                "avg_lc50": round(r[5],2) if r[5] else None,
                "avg_mortality": round(r[6],1) if r[6] else None}
               for r in rows]
    return jsonify({"query": q, "results": results})


@app.route("/api/compounds")
def api_compounds():
    conn = get_db()
    rows = conn.execute("""
        SELECT c.name,
               COUNT(DISTINCT b.pest) as n_pests,
               COUNT(DISTINCT b.paper_id) as n_papers,
               SUM(CASE b.evidence_grade WHEN 'A' THEN 4 WHEN 'B' THEN 3
                   WHEN 'C' THEN 2 ELSE 1 END) as score
        FROM compounds c
        LEFT JOIN bioactivity b ON b.compound_id = c.id
        GROUP BY c.id
        HAVING n_papers > 0
        ORDER BY score DESC
        LIMIT 50
    """).fetchall()
    conn.close()
    compounds = [{"name": r[0], "n_pests": r[1],
                  "n_papers": r[2], "score": r[3]} for r in rows]
    return jsonify({"compounds": compounds})


@app.route("/api/broad")
def api_broad():
    con
    
if __name__ == '__main__':
    import os
    if not os.path.exists('biopesticide.db'):
        print('ERROR: biopesticide.db not found.')
    else:
        print()
        print('=' * 55)
        print('  BIOPESTICIDE DISCOVERY ENGINE')
        print('=' * 55)
        print('  Open in your browser:')
        print('  http://localhost:5000')
        print()
        print('  Press Ctrl+C to stop')
        print('=' * 55)
        print()
        app.run(debug=False, port=5000)
