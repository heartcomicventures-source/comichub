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
    stats = {"possession": "0% - 0%", "shots": "0 - 0", "dangerous": "0 - 0", "xg": "0.0 - 0.0", "xg_float": 0.0}
    try:
        res = requests.get(url, headers=HEADERS).json().get("response", [])
        if len(res) == 2:
            home_stats = {s['type']: s['value'] for s in res[0]['statistics']}
            away_stats = {s['type']: s['value'] for s in res[1]['statistics']}
            
            stats['possession'] = f"{home_stats.get('Ball Possession', '0%')} - {away_stats.get('Ball Possession', '0%')}"
            stats['shots'] = f"{home_stats.get('Shots on Goal', 0)} - {away_stats.get('Shots on Goal', 0)}"
            stats['dangerous'] = f"{home_stats.get('Dangerous Attacks', 0)} - {away_stats.get('Dangerous Attacks', 0)}"
            
            xg_home = float(home_stats.get('expected_goals') or 0)
            xg_away = float(away_stats.get('expected_goals') or 0)
            stats['xg'] = f"{xg_home:.2f} - {xg_away:.2f}"
            stats['xg_float'] = xg_home + xg_away
            
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
            --bg-body: #0b1120; --bg-container: linear-gradient(180deg, #1e293b 0%, #0f172a 20%);
            --bg-panel: rgba(15, 23, 42, 0.5); --bg-box: #26334d;
            --text-main: #f8fafc; --text-muted: #94a3b8;
            --accent-yellow: #facc15; --accent-green: #4ade80; --accent-red: #f87171; --accent-blue: #38bdf8;
            --border: #334155; --shadow: rgba(0,0,0,0.5); --tab-bg: rgba(15, 23, 42, 0.8);
            --safe-top: env(safe-area-inset-top, 44px); --safe-bottom: env(safe-area-inset-bottom, 34px);
        }
        [data-theme="light"] {
            --bg-body: #f1f5f9; --bg-container: #ffffff; --bg-panel: #f8fafc; --bg-box: #e2e8f0;
            --text-main: #0f172a; --text-muted: #64748b; --accent-yellow: #eab308;
            --accent-green: #10b981; --accent-red: #ef4444; --accent-blue: #0284c7; --border: #cbd5e1;
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
        .alert-btn { background: transparent; border: 1px solid var(--border); color: var(--text-main); padding: 4px 8px; border-radius: 6px; font-size: 12px; font-weight: 700; cursor: pointer; }

        .tabs { display: flex; border-bottom: 1px solid var(--border); background: var(--tab-bg); }
        .tab { flex: 1; text-align: center; padding: 16px; font-size: 14px; font-weight: 600; color: var(--text-muted); position: relative; cursor: pointer; }
        .tab.active { color: var(--accent-yellow); }
        .tab.active::after { content: ''; position: absolute; bottom: 0; left: 0; width: 100%; height: 3px; background: var(--accent-yellow); }

        .view { display: none; flex-direction: column; flex: 1; overflow-y: auto; -webkit-overflow-scrolling: touch; padding-bottom: 20px; }
        .view.active { display: flex; }

        .session-header { text-align: center; padding: 20px 20px 10px; }
        .session-title { font-size: 12px; color: var(--text-muted); letter-spacing: 2px; font-weight: 700; margin-bottom: 5px; text-transform: uppercase; }
        .session-wr { font-size: 48px; font-weight: 800; color: var(--accent-yellow); text-shadow: 0 0 20px rgba(250, 204, 21, 0.2); line-height: 1; margin-bottom: 10px; }
        .session-profit { font-size: 24px; font-weight: 700; color: var(--accent-green); margin-bottom: 5px; }
        .session-desc { font-size: 13px; color: var(--text-muted); font-weight: 500; }

        .stake-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 8px; padding: 0 16px; margin-bottom: 20px; }
        .stake-box { aspect-ratio: 1; border-radius: 8px; background: var(--bg-box); display: flex; justify-content: center; align-items: center; font-weight: 700; font-size: 16px; color: var(--text-muted); border: 2px solid transparent; }
        .stake-box.win { background: rgba(74, 222, 128, 0.1); border-color: var(--accent-green); color: var(--accent-green); }
        .stake-box.loss { background: rgba(248, 113, 113, 0.1); border-color: var(--accent-red); color: var(--accent-red); }

        .match-container { margin: 0 16px 15px; background: var(--bg-box); border-radius: 12px; padding: 15px; border: 1px solid var(--border); position: relative; overflow: hidden; }
        .match-container.under { border-color: var(--accent-green); }
        .match-container.over { border-color: var(--accent-red); }
        
        .mc-title { font-size: 12px; font-weight: 800; text-transform: uppercase; margin-bottom: 10px; text-align: center; letter-spacing: 1px; }
        .mc-title.under { color: var(--accent-green); }
        .mc-title.over { color: var(--accent-red); }
        
        .teams-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
        .team-name { font-size: 14px; font-weight: 600; width: 40%; text-align: center; }
        .score { font-size: 22px; font-weight: 800; background: var(--bg-panel); padding: 6px 14px; border-radius: 6px; }
        
        .league-name { text-align: center; font-size: 10px; color: var(--text-muted); font-weight: 600; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.5px; }
        
        .lm-stats { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 15px; border-top: 1px solid var(--border); padding-top: 10px; }
        .lm-stat-item { background: var(--bg-panel); padding: 8px; border-radius: 6px; text-align: center; }
        .lm-stat-label { font-size: 9px; color: var(--text-muted); text-transform: uppercase; font-weight: 700; }
        .lm-stat-val { font-size: 12px; font-weight: 600; color: var(--text-main); margin-top: 2px; }

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
        .btn-main { background: var(--accent-yellow); color: #000; border: none; padding: 16px; border-radius: 8px; font-size: 16px; font-weight: 700; cursor: pointer; }

        .content-pad { padding: 20px 16px; display: flex; flex-direction: column; gap: 20px; }
        .setting-group { background: var(--bg-panel); border: 1px solid var(--border); border-radius: 12px; padding: 15px; }
        .setting-title { font-size: 14px; font-weight: 700; color: var(--accent-yellow); margin-bottom: 15px; border-bottom: 1px solid var(--border); padding-bottom: 10px; }
        .setting-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
        .setting-row:last-child { margin-bottom: 0; }
        .setting-label { font-size: 13px; font-weight: 600; color: var(--text-main); }
        .setting-input { background: var(--bg-box); border: 1px solid var(--border); color: var(--text-main); padding: 6px 10px; border-radius: 6px; width: 80px; text-align: right; font-weight: 700; }

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
                <div class="real-badge">PRO</div>
            </div>
            <div class="controls">
                <button class="alert-btn" onclick="enableAlerts()" id="alert-status">Enable Alerts</button>
                <span class="theme-toggle" onclick="toggleTheme()" id="theme-icon">☀️</span>
            </div>
        </div>

        <div class="tabs">
            <div class="tab active" onclick="switchTab('trade')" id="tab-trade">📈 Scanner</div>
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

            <!-- Dynamically rendered opportunities -->
            <div id="opportunities-container"></div>
            
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
                <button class="btn-main" onclick="resetSession()">Repeat Session</button>
            </div>
        </div>

        <div class="view" id="view-settings">
            <div class="content-pad">
                <!-- MARKET THRESHOLDS -->
                <div class="setting-group">
                    <div class="setting-title">Scanner Thresholds</div>
                    <div class="setting-row">
                        <div class="setting-label">Min Probability (%)</div>
                        <input type="number" class="setting-input" id="set-min-prob" value="65">
                    </div>
                    <div class="setting-row">
                        <div class="setting-label">Under Team Avg (Max)</div>
                        <input type="number" step="0.1" class="setting-input" id="set-under-filter" value="1.0">
                    </div>
                    <div class="setting-row">
                        <div class="setting-label">Over Team Avg (Min)</div>
                        <input type="number" step="0.1" class="setting-input" id="set-over-filter" value="1.8">
                    </div>
                </div>

                <!-- LIVE DECISION FACTORS -->
                <div class="setting-group">
                    <div class="setting-title">Live Validation</div>
                    <div class="setting-row">
                        <div class="setting-label">xG Trigger (Over)</div>
                        <input type="number" step="0.1" class="setting-input" id="set-xg-over" value="1.5">
                    </div>
                    <div class="setting-row">
                        <div class="setting-label">Shots Trigger (Over)</div>
                        <input type="number" step="1" class="setting-input" id="set-shots-over" value="8">
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
    let xgOverTrigger = parseFloat(localStorage.getItem('xgOverTrigger')) || 1.5;
    let shotsOverTrigger = parseFloat(localStorage.getItem('shotsOverTrigger')) || 8;

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

    let alertedMatches = new Set(); // Prevents spamming the same alert
    let activeOpportunities = [];

    document.addEventListener("DOMContentLoaded", () => {
        setTheme(currentTheme);
        loadSettingsUI();
        updateUI();
        checkAlertPermission();
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
        document.getElementById('set-xg-over').value = xgOverTrigger;
        document.getElementById('set-shots-over').value = shotsOverTrigger;
    }

    function saveSettings() {
        maxStakes = parseInt(document.getElementById('set-max-stakes').value) || 6;
        minOdds = parseFloat(document.getElementById('set-min-odds').value) || 1.06;
        minProb = parseFloat(document.getElementById('set-min-prob').value) || 65;
        underFilter = parseFloat(document.getElementById('set-under-filter').value) || 1.0;
        overFilter = parseFloat(document.getElementById('set-over-filter').value) || 1.8;
        xgOverTrigger = parseFloat(document.getElementById('set-xg-over').value) || 1.5;
        shotsOverTrigger = parseFloat(document.getElementById('set-shots-over').value) || 8;

        localStorage.setItem('maxStakes', maxStakes);
        localStorage.setItem('minOdds', minOdds);
        localStorage.setItem('minProb', minProb);
        localStorage.setItem('underFilter', underFilter);
        localStorage.setItem('overFilter', overFilter);
        localStorage.setItem('xgOverTrigger', xgOverTrigger);
        localStorage.setItem('shotsOverTrigger', shotsOverTrigger);
        
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

    // --- NOTIFICATIONS & SOUND ---
    function checkAlertPermission() {
        if (!("Notification" in window)) return;
        if (Notification.permission === "granted") {
            document.getElementById('alert-status').innerText = "🔔 Alerts ON";
            document.getElementById('alert-status').style.color = "var(--accent-green)";
            document.getElementById('alert-status').style.borderColor = "var(--accent-green)";
        }
    }

    function enableAlerts() {
        if (!("Notification" in window)) return alert("This device does not support notifications.");
        
        Notification.requestPermission().then(permission => {
            if (permission === "granted") {
                checkAlertPermission();
                playSound(); // Play a test sound
                new Notification("Comichub Alerts Enabled!", { body: "You will now be notified of live opportunities." });
            }
        });
    }

    function playSound() {
        try {
            const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            const oscillator = audioCtx.createOscillator();
            const gainNode = audioCtx.createGain();
            oscillator.type = 'sine';
            oscillator.frequency.setValueAtTime(800, audioCtx.currentTime);
            oscillator.frequency.exponentialRampToValueAtTime(1200, audioCtx.currentTime + 0.1);
            gainNode.gain.setValueAtTime(0.5, audioCtx.currentTime);
            gainNode.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.3);
            oscillator.connect(gainNode);
            gainNode.connect(audioCtx.destination);
            oscillator.start();
            oscillator.stop(audioCtx.currentTime + 0.3);
        } catch (e) { console.log("Audio not supported", e); }
    }

    function triggerAlert(match, marketType, line, prob) {
        let alertId = `${match.fixture_id}-${marketType}-${line}`;
        if (alertedMatches.has(alertId)) return; // Don't spam
        alertedMatches.add(alertId);

        if (navigator.vibrate) navigator.vibrate([200, 100, 200]);
        playSound();

        if (Notification.permission === "granted") {
            new Notification(`🔥 ${marketType.toUpperCase()} ${line} Opportunity!`, {
                body: `${match.home_name} vs ${match.away_name} (${match.minute}')\nProb: ${(prob*100).toFixed(1)}%`,
                icon: "https://cdn-icons-png.flaticon.com/512/53/53283.png"
            });
        }
    }

    // --- MATH ENGINE (Multi-Line) ---
    function factorial(n) { if(n===0||n===1) return 1; let r=1; for(let i=2;i<=n;i++) r*=i; return r; }
    function poissonPMF(k, lambda) { if(lambda<0) return 0; return (Math.exp(-lambda)*Math.pow(lambda,k))/factorial(k); }
    
    function calculateAllLines(lambdaHome, lambdaAway, currentHome, currentAway, minute, liveStats) {
        let scale = Math.max(0, 90 - minute) / 90.0;
        let lamHRem = lambdaHome * scale, lamARem = lambdaAway * scale;
        let totalNow = currentHome + currentAway;
        
        let lines = [0.5, 1.5, 2.5, 3.5, 4.5];
        let results = [];

        // Calculate xG/Momentum modifiers
        let xgTotal = liveStats.xg_float || 0;
        let shotsStr = liveStats.shots.split(' - ');
        let shotsTotal = (parseInt(shotsStr[0]) || 0) + (parseInt(shotsStr[1]) || 0);
        
        let isHighMomentum = (xgTotal >= xgOverTrigger) || (shotsTotal >= shotsOverTrigger);
        let isLowMomentum = (xgTotal < 0.8 && shotsTotal < 5);

        lines.forEach(line => {
            let maxUnder = Math.floor(line); // e.g., 2.5 -> 2
            let pUnder = 0, pOver = 0;

            for (let rh = 0; rh <= 10; rh++) {
                for (let ra = 0; ra <= 10; ra++) {
                    let p = poissonPMF(rh, lamHRem) * poissonPMF(ra, lamARem);
                    if (totalNow + rh + ra <= maxUnder) pUnder += p; else pOver += p;
                }
            }

            // Apply Modifiers
            if (isLowMomentum) pUnder += 0.05; // Small boost to under
            if (isHighMomentum) pOver += 0.05;  // Small boost to over

            // Normalize
            let totalProb = pUnder + pOver;
            pUnder = pUnder / totalProb;
            pOver = pOver / totalProb;

            results.push({ line, type: 'under', prob: pUnder });
            results.push({ line, type: 'over', prob: pOver });
        });

        // Filter by minimum probability and sort by best probability
        return results.filter(r => (r.prob * 100) >= minProb).sort((a, b) => b.prob - a.prob);
    }

    async function fetchMatches() {
        if (stakesUsed >= maxStakes) {
            document.getElementById('no-matches').innerHTML = "Session Limit Reached.";
            document.getElementById('opportunities-container').innerHTML = '';
            return;
        }

        try {
            const res = await fetch('/api/live-matches');
            const data = await res.json();
            
            activeOpportunities = [];

            if (data.matches && data.matches.length > 0) {
                data.matches.forEach(m => {
                    let bestMarkets = calculateAllLines(m.avg_home, m.avg_away, m.score_home, m.score_away, m.minute, m.stats);
                    
                    if (bestMarkets.length > 0) {
                        // Attach the top market to the match object
                        activeOpportunities.push({
                            match: m,
                            market: bestMarkets[0] // The highest probability market
                        });

                        // Trigger Alert
                        triggerAlert(m, bestMarkets[0].type, bestMarkets[0].line, bestMarkets[0].prob);
                    }
                });
            }

            renderMatches();

            if (activeOpportunities.length === 0) {
                document.getElementById('no-matches').innerHTML = '<div class="spinner"></div> Scanning live markets...';
            } else {
                document.getElementById('no-matches').innerHTML = '';
            }

            updateUI();
        } catch (e) { console.error(e); }
    }

    function renderMatches() {
        let container = document.getElementById('opportunities-container');
        
        if (activeOpportunities.length === 0) {
            container.innerHTML = '';
            return;
        }

        // Only show the top 3 opportunities to avoid clutter
        container.innerHTML = activeOpportunities.slice(0, 3).map(op => {
            let m = op.match;
            let mk = op.market;
            
            let colorClass = mk.type === 'under' ? 'under' : 'over';
            let displayLine = mk.type === 'under' ? `UNDER ${mk.line}` : `OVER ${mk.line}`;

            return `
                <div class="match-container ${colorClass}">
                    <div class="mc-title ${colorClass}">${displayLine} OPPORTUNITY</div>
                    <div class="teams-row">
                        <div class="team-name">${m.home_name}</div>
                        <div class="score">${m.score_home} - ${m.score_away}</div>
                        <div class="team-name">${m.away_name}</div>
                    </div>
                    <div class="league-name">${m.league_name} • ${m.minute}'</div>
                    
                    <div class="lm-stats">
                        <div class="lm-stat-item"><div class="lm-stat-label">xG</div><div class="lm-stat-val">${m.stats.xg}</div></div>
                        <div class="lm-stat-item"><div class="lm-stat-label">Shots</div><div class="lm-stat-val">${m.stats.shots}</div></div>
                        <div class="lm-stat-item"><div class="lm-stat-label">Attacks</div><div class="lm-stat-val">${m.stats.dangerous}</div></div>
                        <div class="lm-stat-item"><div class="lm-stat-label">Prob</div><div class="lm-stat-val" style="color:var(--accent-green)">${(mk.prob * 100).toFixed(1)}%</div></div>
                    </div>

                    <button class="btn-bet ${colorClass}" onclick="placeBet('${mk.type}', ${m.fixture_id}, ${mk.prob})">
                        BET $${nextStake.toFixed(2)} ON ${displayLine}
                    </button>
                </div>
            `;
        }).join('');
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
        fetchMatches();
    }

    function resetSession() {
        if(confirm("Start a fresh session? This resets your bankroll to $100.")) {
            bankroll = 100.00; startBalance = 100.00; nextStake = 10.00; stakesUsed = 0; history = [];
            alertedMatches.clear();
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
    if API_KEY == "YOUR_API_KEY_HERE" or not API_KEY: 
        return jsonify({"error": "Missing API key"}), 400

    fixtures, api_error = get_live_fixtures()
    
    if api_error: 
        return jsonify({"error": api_error}), 500

    results = []
    
    for fixture in fixtures:
        minute = fixture['fixture']['status']['elapsed']
        
        if not TEST_MODE:
            if minute is None or minute < 60: 
                continue
            
        home_id = fixture['teams']['home']['id']
        away_id = fixture['teams']['away']['id']
        
        avg_home = get_team_last5_avg(home_id)
        avg_away = get_team_last5_avg(away_id)

        # We fetch all matches past 60' that are either low scoring or high scoring
        if (avg_home <= 1.5 or avg_away <= 1.5) or (avg_home >= 1.5 or avg_away >= 1.5):
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

    return jsonify({"matches": results})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
