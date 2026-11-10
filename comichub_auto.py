import os
import time
import requests
from flask import Flask, render_template_string, jsonify

app = Flask(__name__)

# --- CONFIGURATION ---
API_KEY = os.environ.get("API_FOOTBALL_KEY")
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
            print(f"❌ API ERROR: {data['errors']}")
            return [], data["errors"]
        
        fixtures = data.get("response", [])
        print(f"🌐 API Success: Found {len(fixtures)} live matches globally.")
        return fixtures, None
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
    stats = {"possession": "0% - 0%", "shots": "0 - 0", "dangerous": "0 - 0"}
    try:
        res = requests.get(url, headers=HEADERS).json().get("response", [])
        if len(res) == 2:
            home_stats = {s['type']: s['value'] for s in res[0]['statistics']}
            away_stats = {s['type']: s['value'] for s in res[1]['statistics']}
            stats['possession'] = f"{home_stats.get('Ball Possession', '0%')} - {away_stats.get('Ball Possession', '0%')}"
            stats['shots'] = f"{home_stats.get('Shots on Goal', 0)} - {away_stats.get('Shots on Goal', 0)}"
            stats['dangerous'] = f"{home_stats.get('Dangerous Attacks', 0)} - {away_stats.get('Dangerous Attacks', 0)}"
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
    <title>Comichub</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-body: #0b1120; --bg-container: linear-gradient(180deg, #1e293b 0%, #0f172a 20%);
            --bg-panel: rgba(15, 23, 42, 0.5); --bg-box: #26334d;
            --text-main: #f8fafc; --text-muted: #94a3b8;
            --accent-yellow: #facc15; --accent-green: #4ade80; --accent-red: #f87171;
            --border: #334155; --shadow: rgba(0,0,0,0.5); --tab-bg: rgba(15, 23, 42, 0.8);
            --safe-top: env(safe-area-inset-top, 44px); --safe-bottom: env(safe-area-inset-bottom, 34px);
        }
        [data-theme="light"] {
            --bg-body: #f1f5f9; --bg-container: #ffffff; --bg-panel: #f8fafc; --bg-box: #e2e8f0;
            --text-main: #0f172a; --text-muted: #64748b; --accent-yellow: #eab308;
            --accent-green: #10b981; --accent-red: #ef4444; --border: #cbd5e1;
            --shadow: rgba(0,0,0,0.1); --tab-bg: #f8fafc;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; transition: background 0.3s, color 0.3s; }
        body { font-family: 'Inter', sans-serif; background-color: var(--bg-body); color: var(--text-main); display: flex; justify-content: center; min-height: 100vh; overflow: hidden; }
        .app-container { width: 100%; max-width: 500px; background: var(--bg-container); height: 100vh; display: flex; flex-direction: column; box-shadow: 0 0 50px var(--shadow); position: relative; padding-top: var(--safe-top); padding-bottom: var(--safe-bottom); }

        .header { display: flex; justify-content: space-between; align-items: center; padding: 16px; background: var(--tab-bg); border-bottom: 1px solid var(--border); }
        .logo-area { display: flex; align-items: center; gap: 8px; }
        .logo-icon { width: 20px; height: 20px; background: var(--accent-yellow); border-radius: 4px; }
        .logo-text { font-size: 14px; font-weight: 800; letter-spacing: 1px; color: var(--text-main); }
        .real-badge { background: rgba(74, 222, 128, 0.15); color: var(--accent-green); border: 1px solid var(--accent-green); padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 700; }
        .controls { display: flex; gap: 15px; color: var(--text-muted); font-size: 18px; cursor: pointer; align-items: center; }
        .tabs { display: flex; border-bottom: 1px solid var(--border); background: var(--tab-bg); }
        .tab { flex: 1; text-align: center; padding: 16px; font-size: 14px; font-weight: 600; color: var(--text-muted); position: relative; cursor: pointer; }
        .tab.active { color: var(--accent-yellow); }
        .tab.active::after { content: ''; position: absolute; bottom: 0; left: 0; width: 100%; height: 3px; background: var(--accent-yellow); }

        .view { display: none; flex-direction: column; flex: 1; overflow-y: auto; -webkit-overflow-scrolling: touch; padding-bottom: 20px; }
        .view.active { display: flex; }

        .session-header { text-align: center; padding: 30px 20px 20px; }
        .session-title { font-size: 12px; color: var(--text-muted); letter-spacing: 2px; font-weight: 700; margin-bottom: 5px; text-transform: uppercase; }
        .session-wr { font-size: 48px; font-weight: 800; color: var(--accent-yellow); text-shadow: 0 0 20px rgba(250, 204, 21, 0.2); line-height: 1; margin-bottom: 10px; }
        .session-profit { font-size: 24px; font-weight: 700; color: var(--accent-green); margin-bottom: 5px; }
        .session-desc { font-size: 13px; color: var(--text-muted); font-weight: 500; }

        .stake-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 8px; padding: 0 16px; margin-bottom: 20px; }
        .stake-box { aspect-ratio: 1; border-radius: 8px; background: var(--bg-box); display: flex; justify-content: center; align-items: center; font-weight: 700; font-size: 16px; color: var(--text-muted); border: 2px solid transparent; transition: 0.3s; }
        .stake-box.win { background: rgba(74, 222, 128, 0.1); border-color: var(--accent-green); color: var(--accent-green); }
        .stake-box.loss { background: rgba(248, 113, 113, 0.1); border-color: var(--accent-red); color: var(--accent-red); }

        .match-container { margin: 0 16px 15px; background: var(--bg-box); border-radius: 12px; padding: 15px; border: 1px solid var(--border); }
        .match-container.under { border-color: var(--accent-green); }
        .match-container.over { border-color: var(--accent-red); }
        .mc-title { font-size: 11px; font-weight: 800; text-transform: uppercase; margin-bottom: 10px; text-align: center; letter-spacing: 1px; }
        .mc-title.under { color: var(--accent-green); }
        .mc-title.over { color: var(--accent-red); }
        .teams-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
        .team-name { font-size: 14px; font-weight: 600; width: 40%; text-align: center; }
        .score { font-size: 22px; font-weight: 800; background: var(--bg-panel); padding: 6px 14px; border-radius: 6px; }
        .league-name { text-align: center; font-size: 10px; color: var(--text-muted); font-weight: 600; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.5px; }
        .lm-stats { display: flex; justify-content: space-between; font-size: 10px; color: var(--text-muted); margin-bottom: 15px; border-top: 1px solid var(--border); padding-top: 10px; }
        .btn-bet { width: 100%; padding: 12px; border-radius: 8px; border: none; font-size: 14px; font-weight: 800; cursor: pointer; margin-top: 10px; }
        .btn-bet.under { background: var(--accent-green); color: #000; }
        .btn-bet.over { background: var(--accent-red); color: #fff; }

        .stats-panel { margin: 0 16px 20px; border: 1px solid var(--border); border-radius: 12px; display: grid; grid-template-columns: 1fr 1fr; background: var(--bg-panel); }
        .stat-cell { padding: 15px; border-bottom: 1px solid var(--border); }
        .stat-cell:nth-child(odd) { border-right: 1px solid var(--border); }
        .stat-cell:nth-child(3), .stat-cell:nth-child(4) { border-bottom: none; }
        .stat-lbl { font-size: 11px; color: var(--text-muted); text-transform: uppercase; font-weight: 700; margin-bottom: 5px; }
        .stat-val { font-size: 18px; font-weight: 700; color: var(--text-main); }
        .stat-val.green { color: var(--accent-green); }

        .actions { padding: 0 16px 20px; display: flex; flex-direction: column; gap: 10px; }
        .prob-display-box { border: 1px solid var(--accent-yellow); color: var(--accent-yellow); padding: 12px; border-radius: 8px; font-size: 14px; font-weight: 700; text-align: center; background: rgba(250, 204, 21, 0.05); }
        .btn-main { background: var(--accent-yellow); color: #000; border: none; padding: 16px; border-radius: 8px; font-size: 16px; font-weight: 700; cursor: pointer; }
        .btn-sec { background: transparent; color: var(--text-muted); border: 1px solid var(--border); padding: 14px; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; }

        .content-pad { padding: 20px 16px; display: flex; flex-direction: column; gap: 20px; }
        .setting-group { background: var(--bg-panel); border: 1px solid var(--border); border-radius: 12px; padding: 15px; }
        .setting-title { font-size: 14px; font-weight: 700; color: var(--accent-yellow); margin-bottom: 15px; border-bottom: 1px solid var(--border); padding-bottom: 10px; }
        .setting-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
        .setting-row:last-child { margin-bottom: 0; }
        .setting-label { font-size: 13px; font-weight: 600; color: var(--text-main); }
        .setting-input { background: var(--bg-box); border: 1px solid var(--border); color: var(--text-main); padding: 6px 10px; border-radius: 6px; width: 80px; text-align: right; font-weight: 700; }
        .btn-action { width: 100%; padding: 12px; background: var(--bg-box); color: var(--text-main); border: 1px solid var(--border); border-radius: 8px; font-weight: 700; cursor: pointer; margin-top: 10px; }

        .history-item { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px solid var(--border); font-size: 14px; }
        .history-item:last-child { border-bottom: none; }
        .h-win { color: var(--accent-green); font-weight: 800; }
        .h-loss { color: var(--accent-red); font-weight: 800; }
        .h-stake { color: var(--text-main); font-weight: 600; }
        .h-bal { color: var(--text-muted); font-weight: 600; }
        .spinner { display: inline-block; width: 16px; height: 16px; border: 2px solid rgba(255,255,255,0.3); border-radius: 50%; border-top-color: #fff; animation: spin 1s ease-in-out infinite; margin-right: 8px; vertical-align: middle; }
        @keyframes spin { to { transform: rotate(360deg); } }
    </style>
</head>
<body data-theme="dark">

    <div class="app-container">
        <div class="header">
            <div class="logo-area">
                <div class="logo-icon"></div>
                <div class="logo-text">COMICHUB</div>
                <div class="real-badge">REAL</div>
            </div>
            <div class="controls">
                <span class="theme-toggle" onclick="toggleTheme()" id="theme-icon">☀️</span>
                <span>⏸</span>
            </div>
        </div>

        <div class="tabs">
            <div class="tab active" onclick="switchTab('trade')" id="tab-trade">📈 Trade</div>
            <div class="tab" onclick="switchTab('settings')" id="tab-settings">⚙️ Settings</div>
            <div class="tab" onclick="switchTab('log')" id="tab-log">📝 Log</div>
        </div>

        <div class="view active" id="view-trade">
            <div class="session-header">
                <div class="session-title" id="session-title">SCANNING MARKET...</div>
                <div class="session-wr" id="session-wr">--%</div>
                <div class="session-profit" id="session-profit">+$0.00</div>
                <div class="session-desc" id="session-desc">Waiting for live opportunities</div>
            </div>

            <div class="stake-grid">
                <div class="stake-box" id="box-1">1</div>
                <div class="stake-box" id="box-2">2</div>
                <div class="stake-box" id="box-3">3</div>
                <div class="stake-box" id="box-4">4</div>
                <div class="stake-box" id="box-5">5</div>
                <div class="stake-box" id="box-6">6</div>
            </div>

            <div id="under-container"></div>
            <div id="over-container"></div>
            <div id="no-matches" style="text-align:center; padding:20px; color:var(--text-muted); font-size:13px; font-weight:600;">
                <div class="spinner"></div> Scanning live markets...
            </div>

            <div class="stats-panel">
                <div class="stat-cell">
                    <div class="stat-lbl">Balance</div>
                    <div class="stat-val" id="ui-balance">$100.00</div>
                </div>
                <div class="stat-cell">
                    <div class="stat-lbl">Next Stake</div>
                    <div class="stat-val" id="ui-next-stake">$10.00</div>
                </div>
                <div class="stat-cell">
                    <div class="stat-lbl">P/L</div>
                    <div class="stat-val green" id="ui-pl">+$0.00</div>
                </div>
                <div class="stat-cell">
                    <div class="stat-lbl">Wins / Left</div>
                    <div class="stat-val" id="ui-left">0 / 6</div>
                </div>
            </div>

            <div class="actions">
                <div class="prob-display-box" id="ui-prob">AWAITING MATCH DATA</div>
                <button class="btn-main" onclick="resetSession()">Repeat Session</button>
            </div>
        </div>

        <div class="view" id="view-settings">
            <div class="content-pad">
                <div class="setting-group">
                    <div class="setting-title">Market</div>
                    <div class="setting-row">
                        <div class="setting-label">Min Under Prob (%)</div>
                        <input type="number" class="setting-input" id="set-min-prob" value="65">
                    </div>
                    <div class="setting-row">
                        <div class="setting-label">Under Filter Max</div>
                        <input type="number" step="0.1" class="setting-input" id="set-under-filter" value="1.0">
                    </div>
                    <div class="setting-row">
                        <div class="setting-label">Over Filter Min</div>
                        <input type="number" step="0.1" class="setting-input" id="set-over-filter" value="1.8">
                    </div>
                </div>

                <div class="setting-group">
                    <div class="setting-title">Discipline</div>
                    <div class="setting-row">
                        <div class="setting-label">Max Stakes</div>
                        <input type="number" class="setting-input" id="set-max-stakes" value="6">
                    </div>
                    <div class="setting-row">
                        <div class="setting-label">Min Odds (Target)</div>
                        <input type="number" step="0.01" class="setting-input" id="set-min-odds" value="1.06">
                    </div>
                </div>

                <div class="setting-group">
                    <div class="setting-title">Data Management</div>
                    <button class="btn-action" onclick="backupData()">Backup Data</button>
                    <button class="btn-action" onclick="restoreData()">Restore Data</button>
                </div>
            </div>
        </div>

        <div class="view" id="view-log">
            <div class="content-pad">
                <div class="setting-group">
                    <div class="setting-title">Session History</div>
                    <div id="history-container">
                        <div style="color: var(--text-muted); font-size: 13px; text-align: center;">No bets placed today.</div>
                    </div>
                </div>
            </div>
        </div>
    </div>

<script>
    let currentTheme = localStorage.getItem('theme') || 'dark';
    let bankroll = parseFloat(localStorage.getItem('bankroll')) || 100.00;
    let startBalance = parseFloat(localStorage.getItem('startBalance')) || 100.00;
    let nextStake = parseFloat(localStorage.getItem('nextStake')) || 10.00;
    let history = JSON.parse(localStorage.getItem('history')) || [];
    
    let maxStakes = parseInt(localStorage.getItem('maxStakes')) || 6;
    let minOdds = parseFloat(localStorage.getItem('minOdds')) || 1.06;
    let minProb = parseFloat(localStorage.getItem('minProb')) || 65;
    let underFilter = parseFloat(localStorage.getItem('underFilter')) || 1.0;
    let overFilter = parseFloat(localStorage.getItem('overFilter')) || 1.8;

    let lastPlayedDate = localStorage.getItem('lastPlayedDate');
    let today = new Date().toDateString();
    let stakesUsed = 0;

    if (lastPlayedDate === today) {
        stakesUsed = parseInt(localStorage.getItem('stakesUsed')) || 0;
    } else {
        localStorage.setItem('lastPlayedDate', today);
        stakesUsed = 0;
        history = [];
        localStorage.setItem('history', JSON.stringify(history));
    }

    let activeMatches = { under: null, over: null };

    document.addEventListener("DOMContentLoaded", () => {
        setTheme(currentTheme);
        loadSettingsUI();
        updateUI();
        fetchMatches();
        setInterval(fetchMatches, 15000);
    });

    function toggleTheme() {
        currentTheme = currentTheme === 'dark' ? 'light' : 'dark';
        setTheme(currentTheme);
    }
    function setTheme(theme) {
        document.body.setAttribute('data-theme', theme);
        document.getElementById('theme-icon').innerText = theme === 'dark' ? '☀️' : '🌙';
        localStorage.setItem('theme', theme);
    }

    function switchTab(tabName) {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
        document.getElementById('tab-' + tabName).classList.add('active');
        document.getElementById('view-' + tabName).classList.add('active');
    }

    function loadSettingsUI() {
        document.getElementById('set-max-stakes').value = maxStakes;
        document.getElementById('set-min-odds').value = minOdds;
        document.getElementById('set-min-prob').value = minProb;
        document.getElementById('set-under-filter').value = underFilter;
        document.getElementById('set-over-filter').value = overFilter;
    }

    function saveSettings() {
        maxStakes = parseInt(document.getElementById('set-max-stakes').value) || 6;
        minOdds = parseFloat(document.getElementById('set-min-odds').value) || 1.06;
        minProb = parseFloat(document.getElementById('set-min-prob').value) || 65;
        underFilter = parseFloat(document.getElementById('set-under-filter').value) || 1.0;
        overFilter = parseFloat(document.getElementById('set-over-filter').value) || 1.8;

        localStorage.setItem('maxStakes', maxStakes);
        localStorage.setItem('minOdds', minOdds);
        localStorage.setItem('minProb', minProb);
        localStorage.setItem('underFilter', underFilter);
        localStorage.setItem('overFilter', overFilter);
        
        updateUI();
        fetchMatches(); 
    }

    function updateUI() {
        document.getElementById('ui-balance').innerText = `$${bankroll.toFixed(2)}`;
        document.getElementById('ui-next-stake').innerText = `$${nextStake.toFixed(2)}`;
        document.getElementById('ui-pl').innerText = `${bankroll >= startBalance ? '+' : ''}$${(bankroll - startBalance).toFixed(2)}`;
        document.getElementById('ui-left').innerText = `${history.filter(h => h.result === 'WIN').length} / ${maxStakes - stakesUsed}`;
        
        if (stakesUsed > 0) {
            document.getElementById('session-title').innerText = "Session Active";
            let winRate = Math.round((history.filter(h => h.result === 'WIN').length / stakesUsed) * 100);
            document.getElementById('session-wr').innerText = `${winRate}% W/R`;
            document.getElementById('session-desc').innerText = `${history.filter(h => h.result === 'WIN').length} of ${stakesUsed} sessions won`;
        }

        for(let i=1; i<=maxStakes; i++) {
            let box = document.getElementById('box-' + i);
            if(!box) continue;
            box.className = 'stake-box';
            if (i <= stakesUsed) {
                let h = history.find(item => item.id === i);
                if (h) box.classList.add(h.result === 'WIN' ? 'win' : 'loss');
            } else {
                box.innerText = i;
            }
        }

        let probEl = document.getElementById('ui-prob');
        if (activeMatches.under) {
            probEl.innerText = `UNDER 3.5 PROB: ${(activeMatches.under.prob * 100).toFixed(1)}%`;
            probEl.style.color = 'var(--accent-green)';
            probEl.style.borderColor = 'var(--accent-green)';
        } else if (activeMatches.over) {
            probEl.innerText = `OVER 3.5 PROB: ${(activeMatches.over.prob * 100).toFixed(1)}%`;
            probEl.style.color = 'var(--accent-red)';
            probEl.style.borderColor = 'var(--accent-red)';
        } else {
            probEl.innerText = "AWAITING MATCH DATA";
            probEl.style.color = 'var(--accent-yellow)';
            probEl.style.borderColor = 'var(--accent-yellow)';
        }

        renderHistory();
        localStorage.setItem('bankroll', bankroll);
        localStorage.setItem('startBalance', startBalance);
        localStorage.setItem('nextStake', nextStake);
        localStorage.setItem('stakesUsed', stakesUsed);
        localStorage.setItem('history', JSON.stringify(history));
    }

    function renderHistory() {
        let c = document.getElementById('history-container');
        if(history.length === 0) {
            c.innerHTML = '<div style="color: var(--text-muted); font-size: 13px; text-align: center;">No bets placed today.</div>';
            return;
        }
        c.innerHTML = history.slice().reverse().map(h => `
            <div class="history-item">
                <div class="${h.result === 'WIN' ? 'h-win' : 'h-loss'}">${h.result}</div>
                <div class="h-stake">$${h.stake.toFixed(2)}</div>
                <div class="h-bal">$${h.balance.toFixed(2)}</div>
            </div>
        `).join('');
    }

    function factorial(n) { if(n===0||n===1) return 1; let r=1; for(let i=2;i<=n;i++) r*=i; return r; }
    function poissonPMF(k, lambda) { if(lambda<0) return 0; return (Math.exp(-lambda)*Math.pow(lambda,k))/factorial(k); }
    function calcProb(lambdaHome, lambdaAway, currentHome, currentAway, minute) {
        let scale = Math.max(0, 90 - minute) / 90.0;
        let lamHRem = lambdaHome * scale, lamARem = lambdaAway * scale;
        let totalNow = currentHome + currentAway;
        let pUnder = 0, pOver = 0;
        for (let rh = 0; rh <= 10; rh++) {
            for (let ra = 0; ra <= 10; ra++) {
                let p = poissonPMF(rh, lamHRem) * poissonPMF(ra, lamARem);
                if (totalNow + rh + ra <= 3) pUnder += p; else pOver += p;
            }
        }
        return { under: pUnder, over: pOver };
    }

    async function fetchMatches() {
        if (stakesUsed >= maxStakes) {
            document.getElementById('no-matches').innerHTML = "Session Limit Reached.";
            document.getElementById('under-container').innerHTML = '';
            document.getElementById('over-container').innerHTML = '';
            return;
        }

        try {
            const res = await fetch('/api/live-matches');
            const data = await res.json();
            
            let underMatch = null;
            let overMatch = null;

            if (data.matches && data.matches.length > 0) {
                data.matches.forEach(m => {
                    let probs = calcProb(m.avg_home, m.avg_away, m.score_home, m.score_away, m.minute);
                    
                    if ((m.avg_home <= underFilter || m.avg_away <= underFilter) && (probs.under * 100) >= minProb) {
                        if(!underMatch) underMatch = { ...m, prob: probs.under };
                    }
                    if ((m.avg_home >= overFilter || m.avg_away >= overFilter) && (probs.over * 100) >= minProb) {
                        if(!overMatch) overMatch = { ...m, prob: probs.over };
                    }
                });
            }

            activeMatches.under = underMatch;
            activeMatches.over = overMatch;

            renderMatch('under-container', underMatch, 'under');
            renderMatch('over-container', overMatch, 'over');

            if (!underMatch && !overMatch) {
                document.getElementById('no-matches').innerHTML = '<div class="spinner"></div> Scanning live markets...';
            } else {
                document.getElementById('no-matches').innerHTML = '';
            }

            updateUI();
        } catch (e) { console.error(e); }
    }

    function renderMatch(containerId, match, type) {
        let container = document.getElementById(containerId);
        if (!match) {
            container.innerHTML = '';
            return;
        }

        container.innerHTML = `
            <div class="match-container ${type}">
                <div class="mc-title ${type}">${type.toUpperCase()} 3.5 OPPORTUNITY</div>
                <div class="teams-row">
                    <div class="team-name">${match.home_name}</div>
                    <div class="score">${match.score_home} - ${match.score_away}</div>
                    <div class="team-name">${match.away_name}</div>
                </div>
                <div class="league-name">${match.league_name} • ${match.minute}'</div>
                <div class="lm-stats">
                    <span>Poss: ${match.stats.possession}</span>
                    <span>Shots: ${match.stats.shots}</span>
                    <span>Danger: ${match.stats.dangerous}</span>
                </div>
                <button class="btn-bet ${type}" onclick="placeBet('${type}', ${match.fixture_id}, ${match.prob})">
                    BET $${nextStake.toFixed(2)} ON ${type.toUpperCase()}
                </button>
            </div>
        `;
    }

    function placeBet(type, fixtureId, prob) {
        if (stakesUsed >= maxStakes) return alert("DISCIPLINE: Stake limit reached.");
        if (bankroll < nextStake) return alert("Insufficient balance.");

        if (navigator.vibrate) navigator.vibrate(50);

        bankroll -= nextStake;
        
        let isWin = Math.random() < prob;
        let result = isWin ? "WIN" : "LOSS";
        let winAmount = isWin ? nextStake * minOdds : 0;
        
        bankroll += winAmount;
        if (isWin) nextStake = Math.round((nextStake * minOdds + Number.EPSILON) * 100) / 100;
        
        stakesUsed++;
        
        history.push({
            id: stakesUsed,
            result: result,
            stake: nextStake / (isWin ? minOdds : 1),
            balance: bankroll
        });

        if (isWin && navigator.vibrate) navigator.vibrate([100, 50, 100]);

        updateUI();
        activeMatches[type] = null;
        renderMatch(type + '-container', null, type);
        fetchMatches();
    }

    function resetSession() {
        if(confirm("Start a fresh session? This resets your bankroll to $100.")) {
            bankroll = 100.00; startBalance = 100.00; nextStake = 10.00; stakesUsed = 0; history = [];
            updateUI();
            fetchMatches();
        }
    }

    document.querySelectorAll('input').forEach(input => {
        input.addEventListener('change', saveSettings);
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
    if API_KEY == "YOUR_API_KEY_HERE": 
        print("⚠️ ERROR: You did not paste your API Key in the code!")
        return jsonify({"error": "Missing API key"}), 400

    fixtures, api_error = get_live_fixtures()
    
    if api_error: 
        return jsonify({"error": api_error}), 500

    results = []
    valid_matches_count = 0
    
    for fixture in fixtures:
        minute = fixture['fixture']['status']['elapsed']
        
        if not TEST_MODE:
            if minute is None or minute < 60: 
                continue
            
        home_id = fixture['teams']['home']['id']
        away_id = fixture['teams']['away']['id']
        
        avg_home = get_team_last5_avg(home_id)
        avg_away = get_team_last5_avg(away_id)

        if TEST_MODE or (avg_home <= 1.0 or avg_away <= 1.0) or (avg_home >= 1.8 or avg_away >= 1.8):
            valid_matches_count += 1
            print(f"✅ Match Found: {fixture['teams']['home']['name']} vs {fixture['teams']['away']['name']} ({minute}') - Fetching Stats...")
            
            stats = get_match_stats(fixture['fixture']['id'])
            
            results.append({
                "fixture_id": fixture['fixture']['id'],
                "league_name": fixture['league']['name'],
                "home_name": fixture['teams']['home']['name'],
                "away_name": fixture['teams']['away']['name'],
                "score_home": fixture['goals']['home'] or 0,
                "score_away": fixture['goals']['away'] or 0,
                "minute": minute,
                "avg_home": avg_home,
                "avg_away": avg_away,
                "stats": stats
            })

    print(f"📊 Scan Complete: {len(fixtures)} live matches -> {valid_matches_count} passed the filter.")
    return jsonify({"matches": results})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
