import os
import time
import requests
from flask import Flask, render_template_string, jsonify

app = Flask(__name__)

# --- CONFIGURATION ---
API_KEY = os.environ.get("API_FOOTBALL_KEY", "YOUR_API_KEY_HERE") 
API_HOST = "v3.football.api-sports.io"
HEADERS = {"x-rapidapi-key": API_KEY, "x-rapidapi-host": API_HOST}

TEST_MODE = False 

TEAM_AVG_CACHE = {}
MATCH_STATS_CACHE = {}

def get_live_fixtures():
    url = f"https://{API_HOST}/fixtures?live=all"
    try:
        response = requests.get(url, headers=HEADERS)
        data = response.json()
        if "errors" in data and data["errors"]: 
            return [], data["errors"]
        return data.get("response", []), None
    except Exception as e:
        return [], str(e)

def get_team_last5_avg(team_id):
    now = time.time()
    if team_id in TEAM_AVG_CACHE:
        cached_avg, timestamp = TEAM_AVG_CACHE[team_id]
        if now - timestamp < 3600: return cached_avg

    url = f"https://{API_HOST}/fixtures?team={team_id}&last=5"
    try:
        matches = requests.get(url, headers=HEADERS).json().get("response", [])
        if not matches: return 0.0
        total_goals = sum([(m['goals']['home'] or 0) if m['teams']['home']['id'] == team_id else (m['goals']['away'] or 0) for m in matches])
        avg = total_goals / len(matches)
        TEAM_AVG_CACHE[team_id] = (avg, now)
        return avg
    except: return 0.0

def get_match_stats(fixture_id):
    now = time.time()
    if fixture_id in MATCH_STATS_CACHE:
        cached_stats, timestamp = MATCH_STATS_CACHE[fixture_id]
        if now - timestamp < 120: return cached_stats
        
    url = f"https://{API_HOST}/fixtures/statistics?fixture={fixture_id}"
    
    # Defaults if API fails
    stats = {
        "possession": {"home": 50, "away": 50},
        "shots": {"home": 0, "away": 0},
        "shots_on_target": {"home": 0, "away": 0},
        "corners": {"home": 0, "away": 0},
        "xg": {"home": 0.0, "away": 0.0},
        "xg_total": 0.0,
        "dangerous": {"home": 0, "away": 0},
        "momentum": {"home": 50, "away": 50}
    }
    
    try:
        res = requests.get(url, headers=HEADERS).json().get("response", [])
        if len(res) == 2:
            h_stats = {s['type']: s['value'] for s in res[0]['statistics']}
            a_stats = {s['type']: s['value'] for s in res[1]['statistics']}
            
            # Parse Possession (e.g., "55%" -> 55)
            try:
                stats["possession"]["home"] = int(str(h_stats.get('Ball Possession', '50%')).replace('%',''))
                stats["possession"]["away"] = 100 - stats["possession"]["home"]
            except: pass
            
            stats["shots"]["home"] = int(h_stats.get('Total Shots') or 0)
            stats["shots"]["away"] = int(a_stats.get('Total Shots') or 0)
            
            stats["shots_on_target"]["home"] = int(h_stats.get('Shots on Goal') or 0)
            stats["shots_on_target"]["away"] = int(a_stats.get('Shots on Goal') or 0)
            
            stats["corners"]["home"] = int(h_stats.get('Corner Kicks') or 0)
            stats["corners"]["away"] = int(a_stats.get('Corner Kicks') or 0)
            
            stats["dangerous"]["home"] = int(h_stats.get('Dangerous Attacks') or 0)
            stats["dangerous"]["away"] = int(a_stats.get('Dangerous Attacks') or 0)

            try: stats["xg"]["home"] = float(h_stats.get('expected_goals') or 0.0)
            except: pass
            try: stats["xg"]["away"] = float(a_stats.get('expected_goals') or 0.0)
            except: pass
            stats["xg_total"] = stats["xg"]["home"] + stats["xg"]["away"]

            # Calculate Momentum (using dangerous attacks ratio)
            tot_danger = stats["dangerous"]["home"] + stats["dangerous"]["away"]
            if tot_danger > 0:
                stats["momentum"]["home"] = int((stats["dangerous"]["home"] / tot_danger) * 100)
                stats["momentum"]["away"] = 100 - stats["momentum"]["home"]

            MATCH_STATS_CACHE[fixture_id] = (stats, now)
        return stats
    except: return stats

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <title>Comichub Pro</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-body: #0b111e; 
            --bg-card: #151f32;
            --bg-card-hover: #1c2940;
            --text-main: #f8fafc; 
            --text-muted: #8b9eb7;
            --accent-green: #00e676; 
            --accent-red: #ff5252; 
            --accent-blue: #38bdf8;
            --accent-yellow: #facc15;
            --border: #22314a;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }
        body { font-family: 'Inter', sans-serif; background-color: var(--bg-body); color: var(--text-main); display: flex; justify-content: center; min-height: 100vh; overflow: hidden; }
        
        .app-container { width: 100%; max-width: 500px; height: 100vh; display: flex; flex-direction: column; position: relative; padding-top: env(safe-area-inset-top, 20px); padding-bottom: env(safe-area-inset-bottom, 20px); overflow: hidden; }

        /* --- VIEWS --- */
        .view { display: none; flex-direction: column; flex: 1; overflow-y: auto; padding-bottom: 80px; }
        .view.active { display: flex; }
        
        /* --- TOP NAVIGATION --- */
        .top-nav { display: flex; justify-content: space-between; align-items: center; padding: 15px 20px; background: var(--bg-body); position: sticky; top: 0; z-index: 10; }
        .nav-btn { background: transparent; border: none; color: var(--text-main); font-size: 20px; cursor: pointer; display: flex; align-items: center; gap: 10px; font-weight: 600; }
        .settings-icon { font-size: 20px; color: var(--text-muted); cursor: pointer; }

        /* --- SCANNER LIST --- */
        .opp-card { background: var(--bg-card); margin: 0 15px 15px; border-radius: 16px; padding: 15px; border-left: 4px solid; }
        .opp-card.under { border-color: var(--accent-green); }
        .opp-card.over { border-color: var(--accent-red); }
        .opp-teams { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; font-size: 16px; font-weight: 700; }
        .opp-score { background: var(--bg-body); padding: 5px 12px; border-radius: 8px; font-size: 18px; }
        .opp-meta { display: flex; justify-content: space-between; font-size: 12px; color: var(--text-muted); margin-bottom: 15px; }
        .opp-market { background: rgba(255,255,255,0.05); padding: 10px; border-radius: 8px; text-align: center; font-weight: 800; font-size: 15px; margin-bottom: 10px; }
        .opp-market.under { color: var(--accent-green); }
        .opp-market.over { color: var(--accent-red); }

        /* --- MATCH DETAIL (The New Design) --- */
        .match-header { display: flex; justify-content: space-between; align-items: flex-start; padding: 20px; }
        .team-col { display: flex; flex-direction: column; align-items: center; width: 30%; text-align: center; }
        .team-logo { width: 60px; height: 60px; object-fit: contain; margin-bottom: 10px; }
        .team-name { font-size: 14px; font-weight: 600; line-height: 1.2; }
        .score-col { display: flex; flex-direction: column; align-items: center; width: 40%; }
        .live-badge { background: rgba(0, 230, 118, 0.15); color: var(--accent-green); padding: 4px 10px; border-radius: 20px; font-size: 11px; font-weight: 800; text-transform: uppercase; margin-bottom: 5px; letter-spacing: 1px; }
        .score-text { font-size: 36px; font-weight: 800; margin: 5px 0; }
        .match-time { font-size: 13px; color: var(--accent-green); font-weight: 600; }

        /* Prediction Box */
        .prediction-box { margin: 0 20px 20px; background: linear-gradient(135deg, #1e293b, #0f172a); border: 1px solid var(--accent-yellow); border-radius: 16px; padding: 15px; text-align: center; }
        .prediction-title { font-size: 11px; color: var(--accent-yellow); text-transform: uppercase; font-weight: 800; letter-spacing: 1px; margin-bottom: 5px; }
        .prediction-market { font-size: 22px; font-weight: 800; color: #fff; }
        .prediction-prob { font-size: 14px; color: var(--accent-green); font-weight: 600; margin-bottom: 10px; }
        .btn-bet-main { background: var(--accent-yellow); color: #000; border: none; width: 100%; padding: 12px; border-radius: 8px; font-weight: 800; font-size: 15px; cursor: pointer; }

        /* Stat Sections */
        .stat-section { margin: 0 15px 15px; background: var(--bg-card); border-radius: 16px; padding: 15px; }
        .section-title { font-size: 13px; font-weight: 700; color: var(--text-muted); margin-bottom: 15px; }
        
        /* Dual Progress Bars */
        .stat-row { display: flex; justify-content: space-between; font-size: 13px; font-weight: 700; margin-bottom: 5px; }
        .stat-lbl { font-size: 12px; color: var(--text-muted); font-weight: 500; text-align: center; margin-bottom: 5px; }
        .bar-container { display: flex; height: 6px; border-radius: 3px; overflow: hidden; background: #000; margin-bottom: 15px; }
        .bar-home { background: var(--accent-green); transition: width 0.5s; }
        .bar-away { background: var(--accent-red); transition: width 0.5s; }
        
        /* xG Section */
        .xg-val-home { color: var(--accent-green); }
        .xg-val-away { color: var(--accent-red); }

        /* Bottom Nav */
        .bottom-nav { position: absolute; bottom: 0; width: 100%; display: flex; justify-content: space-around; padding: 15px 0; background: var(--bg-card); border-top: 1px solid var(--border); padding-bottom: env(safe-area-inset-bottom, 15px); }
        .nav-item { display: flex; flex-direction: column; align-items: center; color: var(--text-muted); font-size: 10px; font-weight: 600; cursor: pointer; gap: 4px; }
        .nav-item.active { color: var(--accent-green); }
        .nav-item svg { width: 20px; height: 20px; fill: currentColor; }
        
        .empty-state { text-align: center; padding: 40px 20px; color: var(--text-muted); font-size: 14px; font-weight: 500; }
    </style>
</head>
<body>

    <div class="app-container">
        
        <!-- ========================================== -->
        <!-- VIEW 1: SCANNER LIST                       -->
        <!-- ========================================== -->
        <div class="view active" id="view-scanner">
            <div class="top-nav">
                <div style="font-size: 18px; font-weight: 800; letter-spacing: 1px;">COMICHUB <span style="color:var(--accent-yellow)">PRO</span></div>
                <div class="settings-icon" onclick="switchView('settings')">⚙️</div>
            </div>
            
            <div id="scanner-container">
                <div class="empty-state">Scanning live markets for high probability setups...</div>
            </div>
        </div>

        <!-- ========================================== -->
        <!-- VIEW 2: MATCH DETAIL (Sofascore Style)     -->
        <!-- ========================================== -->
        <div class="view" id="view-detail">
            <!-- Top Nav with Back Button -->
            <div class="top-nav">
                <button class="nav-btn" onclick="switchView('scanner')">← Back</button>
                <div class="settings-icon">🔔</div>
            </div>

            <!-- Match Header -->
            <div class="match-header">
                <div class="team-col">
                    <img id="d-home-logo" class="team-logo" src="" alt="Home">
                    <div id="d-home-name" class="team-name">Home Team</div>
                </div>
                <div class="score-col">
                    <div class="live-badge">LIVE</div>
                    <div id="d-score" class="score-text">0 - 0</div>
                    <div id="d-minute" class="match-time">0'</div>
                </div>
                <div class="team-col">
                    <img id="d-away-logo" class="team-logo" src="" alt="Away">
                    <div id="d-away-name" class="team-name">Away Team</div>
                </div>
            </div>

            <!-- The Prediction Box -->
            <div class="prediction-box">
                <div class="prediction-title">Comichub Prediction</div>
                <div id="d-market" class="prediction-market">UNDER 3.5</div>
                <div id="d-prob" class="prediction-prob">85.0% Probability</div>
                <button class="btn-bet-main" onclick="placeBetUI()">BET $10.00</button>
            </div>

            <!-- Match Stats (Like the Image) -->
            <div class="stat-section">
                <div class="section-title">Match Stats</div>
                
                <!-- Possession -->
                <div class="stat-row"><span id="d-poss-home">50%</span><span style="color:var(--text-muted); font-weight:500;">Possession</span><span id="d-poss-away">50%</span></div>
                <div class="bar-container">
                    <div id="bar-poss-home" class="bar-home" style="width: 50%"></div>
                    <div id="bar-poss-away" class="bar-away" style="width: 50%"></div>
                </div>

                <!-- Shots on Target -->
                <div class="stat-row"><span id="d-shots-home">0</span><span style="color:var(--text-muted); font-weight:500;">Shots on Target</span><span id="d-shots-away">0</span></div>
                <div class="bar-container">
                    <div id="bar-shots-home" class="bar-home" style="width: 50%"></div>
                    <div id="bar-shots-away" class="bar-away" style="width: 50%"></div>
                </div>

                <!-- Corners -->
                <div class="stat-row"><span id="d-corners-home">0</span><span style="color:var(--text-muted); font-weight:500;">Corners</span><span id="d-corners-away">0</span></div>
                <div class="bar-container">
                    <div id="bar-corners-home" class="bar-home" style="width: 50%"></div>
                    <div id="bar-corners-away" class="bar-away" style="width: 50%"></div>
                </div>
            </div>

            <!-- Advanced Stats (xG & Momentum) -->
            <div class="stat-section">
                <div class="section-title">xG (Expected Goals)</div>
                <div class="stat-row">
                    <span id="d-xg-home" class="xg-val-home">0.00</span>
                    <span style="font-size: 11px; color: var(--text-muted);">Total: <span id="d-xg-total">0.00</span></span>
                    <span id="d-xg-away" class="xg-val-away">0.00</span>
                </div>
                <div class="bar-container">
                    <div id="bar-xg-home" class="bar-home" style="width: 50%"></div>
                    <div id="bar-xg-away" class="bar-away" style="width: 50%"></div>
                </div>

                <div class="section-title" style="margin-top: 15px;">Momentum (Attacks)</div>
                <div class="bar-container" style="height: 10px;">
                    <div id="bar-mom-home" class="bar-home" style="width: 50%"></div>
                    <div id="bar-mom-away" class="bar-away" style="width: 50%"></div>
                </div>
            </div>
        </div>

        <!-- ========================================== -->
        <!-- VIEW 3: SETTINGS                           -->
        <!-- ========================================== -->
        <div class="view" id="view-settings">
            <div class="top-nav">
                <button class="nav-btn" onclick="switchView('scanner')">← Back</button>
                <div style="font-size: 16px; font-weight: 700;">Settings</div>
                <div style="width: 20px;"></div>
            </div>
            <div class="stat-section" style="margin-top: 15px;">
                <div class="section-title">Scanner Thresholds</div>
                <div style="display:flex; justify-content:space-between; margin-bottom: 10px;">
                    <span>Min Probability (%)</span>
                    <input type="number" id="set-min-prob" value="65" style="width: 60px; background: #000; color: #fff; border: 1px solid #333; text-align: right;">
                </div>
                <div style="display:flex; justify-content:space-between; margin-bottom: 10px;">
                    <span>Under Team Avg (Max)</span>
                    <input type="number" id="set-under-filter" value="1.0" step="0.1" style="width: 60px; background: #000; color: #fff; border: 1px solid #333; text-align: right;">
                </div>
                <div style="display:flex; justify-content:space-between;">
                    <span>Over Team Avg (Min)</span>
                    <input type="number" id="set-over-filter" value="1.8" step="0.1" style="width: 60px; background: #000; color: #fff; border: 1px solid #333; text-align: right;">
                </div>
            </div>
            <button onclick="saveSettings()" style="margin: 20px 15px; padding: 15px; background: var(--accent-yellow); color: #000; border: none; border-radius: 10px; font-weight: 800; font-size: 16px;">Save Settings</button>
        </div>

        <!-- BOTTOM NAVIGATION -->
        <div class="bottom-nav">
            <div class="nav-item active" onclick="switchView('scanner')">
                <svg viewBox="0 0 24 24"><path d="M21 6h-2v9H6v2c0 .55.45 1 1 1h11l4 4V7c0-.55-.45-1-1-1zm-4 6V3c0-.55-.45-1-1-1H3c-.55 0-1 .45-1 1v14l4-4h10c.55 0 1-.45 1-1z"/></svg>
                Matches
            </div>
            <div class="nav-item" onclick="switchView('settings')">
                <svg viewBox="0 0 24 24"><path d="M19.14,12.94c0.04-0.3,0.06-0.61,0.06-0.94c0-0.32-0.02-0.64-0.06-0.94l2.03-1.58c0.18-0.14,0.23-0.41,0.12-0.61 l-1.92-3.32c-0.12-0.22-0.37-0.29-0.59-0.22l-2.39,0.96c-0.5-0.38-1.03-0.7-1.62-0.94L14.4,2.81c-0.04-0.24-0.24-0.41-0.48-0.41 h-3.84c-0.24,0-0.43,0.17-0.47,0.41L9.25,5.35C8.66,5.59,8.12,5.92,7.63,6.29L5.24,5.33c-0.22-0.08-0.47,0-0.59,0.22L2.73,8.87 C2.62,9.08,2.66,9.34,2.86,9.48l2.03,1.58C4.84,11.36,4.8,11.69,4.8,12s0.02,0.64,0.06,0.94l-2.03,1.58 c-0.18,0.14-0.23,0.41-0.12,0.61l1.92,3.32c0.12,0.22,0.37,0.29,0.59,0.22l2.39-0.96c0.5,0.38,1.03,0.7,1.62,0.94l0.36,2.54 c0.05,0.24,0.24,0.41,0.48,0.41h3.84c0.24,0,0.43-0.17,0.47-0.41l0.36-2.54c0.59-0.24,1.13-0.56,1.62-0.94l2.39,0.96 c0.22,0.08,0.47,0,0.59-0.22l1.92-3.32c0.12-0.22,0.07-0.49-0.12-0.61L19.14,12.94z M12,15.6c-1.98,0-3.6-1.62-3.6-3.6 s1.62-3.6,3.6-3.6s3.6,1.62,3.6,3.6S13.98,15.6,12,15.6z"/></svg>
                Settings
            </div>
        </div>

    </div>

<script>
    // --- STATE ---
    let opportunities = [];
    let selectedMatch = null;
    let selectedMarket = null;
    
    let minProb = parseFloat(localStorage.getItem('minProb')) || 65;
    let underFilter = parseFloat(localStorage.getItem('underFilter')) || 1.0;
    let overFilter = parseFloat(localStorage.getItem('overFilter')) || 1.8;

    // --- UI ROUTING ---
    function switchView(viewId) {
        document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
        document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
        
        document.getElementById('view-' + viewId).classList.add('active');
        
        if(viewId === 'scanner') document.querySelectorAll('.nav-item')[0].classList.add('active');
        if(viewId === 'settings') {
            document.querySelectorAll('.nav-item')[1].classList.add('active');
            document.getElementById('set-min-prob').value = minProb;
            document.getElementById('set-under-filter').value = underFilter;
            document.getElementById('set-over-filter').value = overFilter;
        }
    }

    function saveSettings() {
        minProb = parseFloat(document.getElementById('set-min-prob').value);
        underFilter = parseFloat(document.getElementById('set-under-filter').value);
        overFilter = parseFloat(document.getElementById('set-over-filter').value);
        
        localStorage.setItem('minProb', minProb);
        localStorage.setItem('underFilter', underFilter);
        localStorage.setItem('overFilter', overFilter);
        
        switchView('scanner');
        fetchMatches(); // Re-scan immediately
    }

    // --- FETCH & RENDER LIST ---
    async function fetchMatches() {
        try {
            const res = await fetch('/api/live-matches');
            const data = await res.json();
            
            opportunities = [];
            if (data.matches && data.matches.length > 0) {
                data.matches.forEach(m => {
                    let bestMarkets = calculateAllLines(m.avg_home, m.avg_away, m.score_home, m.score_away, m.minute, m.stats);
                    if (bestMarkets.length > 0) {
                        opportunities.push({ match: m, market: bestMarkets[0] });
                    }
                });
            }
            renderList();
        } catch (e) { 
            document.getElementById('scanner-container').innerHTML = `<div class="empty-state">Error connecting to server.</div>`;
        }
    }

    function renderList() {
        let container = document.getElementById('scanner-container');
        if(opportunities.length === 0) {
            container.innerHTML = `<div class="empty-state">Scanning live markets...<br>No opportunities match your strict criteria right now.</div>`;
            return;
        }

        container.innerHTML = opportunities.map((op, index) => {
            let m = op.match;
            let mk = op.market;
            let typeClass = mk.type === 'under' ? 'under' : 'over';
            let displayLine = `${mk.type.toUpperCase()} ${mk.line}`;

            return `
                <div class="opp-card ${typeClass}" onclick="openMatch(${index})">
                    <div class="opp-teams">
                        <span>${m.home_name}</span>
                        <div class="opp-score">${m.score_home} - ${m.score_away}</div>
                        <span>${m.away_name}</span>
                    </div>
                    <div class="opp-meta">
                        <span>${m.league_name}</span>
                        <span style="color:var(--accent-green); font-weight:700;">${m.minute}'</span>
                    </div>
                    <div class="opp-market ${typeClass}">
                        ${displayLine} • ${(mk.prob * 100).toFixed(1)}%
                    </div>
                    <div style="text-align:center; font-size:11px; color:var(--text-muted);">Tap to view live stats & bet</div>
                </div>
            `;
        }).join('');
    }

    // --- OPEN MATCH DETAIL ---
    function openMatch(index) {
        selectedMatch = opportunities[index].match;
        selectedMarket = opportunities[index].market;
        
        let m = selectedMatch;
        let mk = selectedMarket;
        let s = m.stats;

        // Populate Team Info
        document.getElementById('d-home-name').innerText = m.home_name;
        document.getElementById('d-away-name').innerText = m.away_name;
        document.getElementById('d-score').innerText = `${m.score_home} - ${m.score_away}`;
        document.getElementById('d-minute').innerText = `${m.minute}'`;
        
        // Logos (Using placeholder URLs if API doesn't return them)
        document.getElementById('d-home-logo').src = m.home_logo || `https://ui-avatars.com/api/?name=${m.home_name}&background=random&color=fff&rounded=true`;
        document.getElementById('d-away-logo').src = m.away_logo || `https://ui-avatars.com/api/?name=${m.away_name}&background=random&color=fff&rounded=true`;

        // Prediction Box
        document.getElementById('d-market').innerText = `${mk.type.toUpperCase()} ${mk.line}`;
        document.getElementById('d-prob').innerText = `${(mk.prob * 100).toFixed(1)}% Probability`;
        document.getElementById('d-market').style.color = mk.type === 'under' ? 'var(--accent-green)' : 'var(--accent-red)';

        // Stats: Possession
        document.getElementById('d-poss-home').innerText = `${s.possession.home}%`;
        document.getElementById('d-poss-away').innerText = `${s.possession.away}%`;
        document.getElementById('bar-poss-home').style.width = `${s.possession.home}%`;
        document.getElementById('bar-poss-away').style.width = `${s.possession.away}%`;

        // Stats: Shots
        document.getElementById('d-shots-home').innerText = s.shots_on_target.home;
        document.getElementById('d-shots-away').innerText = s.shots_on_target.away;
        let totShots = s.shots_on_target.home + s.shots_on_target.away || 1;
        document.getElementById('bar-shots-home').style.width = `${(s.shots_on_target.home/totShots)*100}%`;
        document.getElementById('bar-shots-away').style.width = `${(s.shots_on_target.away/totShots)*100}%`;

        // Stats: Corners
        document.getElementById('d-corners-home').innerText = s.corners.home;
        document.getElementById('d-corners-away').innerText = s.corners.away;
        let totCorners = s.corners.home + s.corners.away || 1;
        document.getElementById('bar-corners-home').style.width = `${(s.corners.home/totCorners)*100}%`;
        document.getElementById('bar-corners-away').style.width = `${(s.corners.away/totCorners)*100}%`;

        // Stats: xG
        document.getElementById('d-xg-home').innerText = s.xg.home.toFixed(2);
        document.getElementById('d-xg-away').innerText = s.xg.away.toFixed(2);
        document.getElementById('d-xg-total').innerText = s.xg_total.toFixed(2);
        let totXg = s.xg_total || 1;
        document.getElementById('bar-xg-home').style.width = `${(s.xg.home/totXg)*100}%`;
        document.getElementById('bar-xg-away').style.width = `${(s.xg.away/totXg)*100}%`;

        // Stats: Momentum
        document.getElementById('bar-mom-home').style.width = `${s.momentum.home}%`;
        document.getElementById('bar-mom-away').style.width = `${s.momentum.away}%`;

        switchView('detail');
    }

    function placeBetUI() {
        alert(`Bet placed on ${selectedMarket.type.toUpperCase()} ${selectedMarket.line}!\n(Simulated Win)`);
        switchView('scanner');
    }

    // --- MATH ENGINE ---
    function factorial(n) { if(n===0||n===1) return 1; let r=1; for(let i=2;i<=n;i++) r*=i; return r; }
    function poissonPMF(k, lambda) { if(lambda<0) return 0; return (Math.exp(-lambda)*Math.pow(lambda,k))/factorial(k); }
    
    function calculateAllLines(lambdaHome, lambdaAway, currentHome, currentAway, minute, liveStats) {
        let scale = Math.max(0, 90 - minute) / 90.0;
        let lamHRem = lambdaHome * scale, lamARem = lambdaAway * scale;
        let totalNow = currentHome + currentAway;
        
        let lines = [0.5, 1.5, 2.5, 3.5, 4.5];
        let results = [];

        let xgTotal = liveStats.xg_total || 0;
        let isHighMomentum = (xgTotal >= 1.5);
        let isLowMomentum = (xgTotal < 0.8);

        lines.forEach(line => {
            let maxUnder = Math.floor(line);
            let pUnder = 0, pOver = 0;

            for (let rh = 0; rh <= 10; rh++) {
                for (let ra = 0; ra <= 10; ra++) {
                    let p = poissonPMF(rh, lamHRem) * poissonPMF(ra, lamARem);
                    if (totalNow + rh + ra <= maxUnder) pUnder += p; else pOver += p;
                }
            }

            if (isLowMomentum) pUnder += 0.05;
            if (isHighMomentum) pOver += 0.05;

            let totalProb = pUnder + pOver;
            pUnder = pUnder / totalProb;
            pOver = pOver / totalProb;

            results.push({ line, type: 'under', prob: pUnder });
            results.push({ line, type: 'over', prob: pOver });
        });

        return results.filter(r => (r.prob * 100) >= minProb).sort((a, b) => b.prob - a.prob);
    }

    // Init
    document.addEventListener("DOMContentLoaded", () => {
        fetchMatches();
        setInterval(fetchMatches, 15000);
    });
</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/live-matches')
def live_matches():
    if API_KEY == "YOUR_API_KEY_HERE" or not API_KEY: 
        return jsonify({"error": "Missing API key"}), 400

    fixtures, api_error = get_live_fixtures()
    if api_error: return jsonify({"error": api_error}), 500

    results = []
    
    for fixture in fixtures:
        minute = fixture['fixture']['status']['elapsed']
        if not TEST_MODE and (minute is None or minute < 60): continue
            
        home_id = fixture['teams']['home']['id']
        away_id = fixture['teams']['away']['id']
        
        avg_home = get_team_last5_avg(home_id)
        avg_away = get_team_last5_avg(away_id)

        if (avg_home <= 1.5 or avg_away <= 1.5) or (avg_home >= 1.5 or avg_away >= 1.5):
            stats = get_match_stats(fixture['fixture']['id'])
            
            results.append({
                "fixture_id": fixture['fixture']['id'],
                "league_name": fixture['league']['name'],
                "home_name": fixture['teams']['home']['name'],
                "away_name": fixture['teams']['away']['name'],
                "home_logo": fixture['teams']['home']['logo'], # Added logo
                "away_logo": fixture['teams']['away']['logo'], # Added logo
                "score_home": fixture['goals']['home'] or 0,
                "score_away": fixture['goals']['away'] or 0,
                "minute": minute,
                "avg_home": avg_home,
                "avg_away": avg_away,
                "stats": stats
            })

    return jsonify({"matches": results})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
