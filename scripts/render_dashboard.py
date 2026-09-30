import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = REPO_ROOT / "data" / "logs.jsonl"
OUT_HTML = REPO_ROOT / "dashboard.html"

def percentile(values, p):
    if not values:
        return 0.0
    sorted_v = sorted(values)
    k = (len(sorted_v) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(sorted_v[int(k)])
    d0 = sorted_v[int(f)] * (c - k)
    d1 = sorted_v[int(c)] * (k - f)
    return float(d0 + d1)

def parse_logs():
    records = []
    if not LOG_PATH.exists():
        return records
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                records.append(rec)
            except Exception:
                pass
    return records

def generate_dashboard():
    records = parse_logs()
    
    # Bucket by minute
    buckets = {} # "YYYY-MM-DD HH:MM": {latencies: [], ttfts: [], requests: 0, errors: 0, tool_success: 0, tool_total: 0, cost: 0.0, tokens_in: 0, tokens_out: 0, qualities: []}
    
    all_latencies = []
    all_ttfts = []
    total_requests = 0
    total_errors = 0
    total_cost = 0.0
    total_tokens_in = 0
    total_tokens_out = 0
    all_qualities = []
    tool_success_cnt = 0
    tool_total_cnt = 0

    for r in records:
        ts_str = r.get("ts", "")
        minute_key = "Recent"
        if ts_str:
            try:
                # ISO format
                dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                minute_key = dt.strftime("%H:%M")
            except Exception:
                pass
        
        if minute_key not in buckets:
            buckets[minute_key] = {
                "latencies": [],
                "ttfts": [],
                "requests": 0,
                "errors": 0,
                "tool_success": 0,
                "tool_total": 0,
                "cost": 0.0,
                "tokens_in": 0,
                "tokens_out": 0,
                "qualities": [],
            }
        
        b = buckets[minute_key]
        evt = r.get("event")
        
        if evt == "request_received":
            b["requests"] += 1
            total_requests += 1
        elif evt == "request_failed":
            b["errors"] += 1
            total_errors += 1
            if r.get("tool_name") == "retrieval":
                b["tool_total"] += 1
                tool_total_cnt += 1
                if r.get("tool_success") is True:
                    b["tool_success"] += 1
                    tool_success_cnt += 1
        elif evt == "response_sent":
            lat = r.get("latency_ms")
            ttft = r.get("ttft_ms")
            cost = r.get("cost_usd", 0.0)
            tin = r.get("tokens_in", 0)
            tout = r.get("tokens_out", 0)
            q = r.get("quality_score")
            
            if lat is not None:
                b["latencies"].append(lat)
                all_latencies.append(lat)
            if ttft is not None:
                b["ttfts"].append(ttft)
                all_ttfts.append(ttft)
            if cost is not None:
                b["cost"] += cost
                total_cost += cost
            if tin is not None:
                b["tokens_in"] += tin
                total_tokens_in += tin
            if tout is not None:
                b["tokens_out"] += tout
                total_tokens_out += tout
            if q is not None:
                b["qualities"].append(q)
                all_qualities.append(q)
            if r.get("tool_name") == "retrieval":
                b["tool_total"] += 1
                tool_total_cnt += 1
                if r.get("tool_success") is True:
                    b["tool_success"] += 1
                    tool_success_cnt += 1

    labels = list(buckets.keys())
    if not labels:
        labels = ["00:00", "00:05", "00:10"]

    # Compute series
    p50_series = [round(percentile(buckets[k]["latencies"], 50), 1) if buckets[k]["latencies"] else 0 for k in labels]
    p95_series = [round(percentile(buckets[k]["latencies"], 95), 1) if buckets[k]["latencies"] else 0 for k in labels]
    p99_series = [round(percentile(buckets[k]["latencies"], 99), 1) if buckets[k]["latencies"] else 0 for k in labels]
    ttft_p95_series = [round(percentile(buckets[k]["ttfts"], 95), 1) if buckets[k]["ttfts"] else 0 for k in labels]
    
    traffic_series = [buckets[k]["requests"] for k in labels]
    
    error_rate_series = [
        round((buckets[k]["errors"] / max(1, buckets[k]["requests"])) * 100, 2)
        for k in labels
    ]
    retrieval_success_series = [
        round((buckets[k]["tool_success"] / max(1, buckets[k]["tool_total"])) * 100, 1) if buckets[k]["tool_total"] > 0 else 100.0
        for k in labels
    ]
    
    cost_series = [round(buckets[k]["cost"], 5) for k in labels]
    # cumulative cost
    cum_cost = []
    curr = 0.0
    for k in labels:
        curr += buckets[k]["cost"]
        cum_cost.append(round(curr, 5))
        
    tokens_in_series = [buckets[k]["tokens_in"] for k in labels]
    tokens_out_series = [buckets[k]["tokens_out"] for k in labels]
    
    quality_series = [
        round(sum(buckets[k]["qualities"]) / len(buckets[k]["qualities"]), 2) if buckets[k]["qualities"] else 0.85
        for k in labels
    ]

    p95_overall = round(percentile(all_latencies, 95), 1)
    error_rate_overall = round((total_errors / max(1, total_requests)) * 100, 2)
    avg_quality_overall = round(sum(all_qualities) / max(1, len(all_qualities)), 2) if all_qualities else 0.85
    retrieval_success_overall = round((tool_success_cnt / max(1, tool_total_cnt)) * 100, 1) if tool_total_cnt > 0 else 100.0

    html_content = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>K4-L3B Day 13 Monitoring & LLMOps Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --bg-color: #0d1117;
            --card-bg: #161b22;
            --border-color: #30363d;
            --text-main: #c9d1d9;
            --text-muted: #8b949e;
            --accent-blue: #58a6ff;
            --accent-green: #3fb950;
            --accent-orange: #d29922;
            --accent-red: #f85149;
            --accent-purple: #bc8cff;
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }}
        body {{
            background-color: var(--bg-color);
            color: var(--text-main);
            padding: 24px;
        }}
        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 16px;
            margin-bottom: 20px;
        }}
        .header-title h1 {{
            font-size: 22px;
            font-weight: 600;
            color: #f0f6fc;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .badge-live {{
            background: rgba(63, 185, 80, 0.2);
            color: var(--accent-green);
            border: 1px solid var(--accent-green);
            font-size: 11px;
            padding: 2px 8px;
            border-radius: 12px;
            font-weight: bold;
            display: inline-flex;
            align-items: center;
            gap: 4px;
        }}
        .badge-live::before {{
            content: '';
            width: 6px;
            height: 6px;
            background: var(--accent-green);
            border-radius: 50%;
            display: inline-block;
        }}
        .header-meta {{
            display: flex;
            gap: 16px;
            font-size: 13px;
            color: var(--text-muted);
        }}
        .header-meta span {{
            background: var(--card-bg);
            padding: 6px 12px;
            border-radius: 6px;
            border: 1px solid var(--border-color);
        }}
        .kpi-row {{
            display: grid;
            grid-template-columns: repeat(6, 1fr);
            gap: 16px;
            margin-bottom: 24px;
        }}
        .kpi-card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 14px 16px;
        }}
        .kpi-label {{
            font-size: 12px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 6px;
        }}
        .kpi-value {{
            font-size: 22px;
            font-weight: 700;
            color: #f0f6fc;
        }}
        .kpi-sub {{
            font-size: 11px;
            color: var(--accent-green);
            margin-top: 4px;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
        }}
        .panel {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 18px 20px;
            display: flex;
            flex-direction: column;
        }}
        .panel-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }}
        .panel-title {{
            font-size: 15px;
            font-weight: 600;
            color: #f0f6fc;
        }}
        .panel-threshold {{
            font-size: 11px;
            color: var(--accent-orange);
            background: rgba(210, 153, 34, 0.15);
            padding: 2px 8px;
            border-radius: 4px;
            border: 1px solid rgba(210, 153, 34, 0.3);
        }}
        .chart-container {{
            position: relative;
            height: 230px;
            width: 100%;
        }}
    </style>
</head>
<body>
    <header>
        <div class="header-title">
            <h1>K4-L3B Day 13 Monitoring & LLMOps Dashboard <span class="badge-live">LIVE</span></h1>
        </div>
        <div class="header-meta">
            <span>👤 Học viên: <strong>Lục Tiến Đạt (2A202602969)</strong></span>
            <span>⏱️ Time Range: <strong>60 Minutes</strong></span>
            <span>🔄 Refresh: <strong>30s</strong></span>
        </div>
    </header>

    <div class="kpi-row">
        <div class="kpi-card">
            <div class="kpi-label">Total Requests</div>
            <div class="kpi-value">{total_requests}</div>
            <div class="kpi-sub">Events: request_received</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Latency P95</div>
            <div class="kpi-value">{p95_overall} ms</div>
            <div class="kpi-sub">SLO target: &le; 3000ms</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Error Rate</div>
            <div class="kpi-value">{error_rate_overall}%</div>
            <div class="kpi-sub">Threshold: &le; 2.0%</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Retrieval Success</div>
            <div class="kpi-value">{retrieval_success_overall}%</div>
            <div class="kpi-sub">Threshold: &ge; 90.0%</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Total Cost</div>
            <div class="kpi-value">${round(total_cost, 4)}</div>
            <div class="kpi-sub">Budget: &le; $2.50</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Avg Quality</div>
            <div class="kpi-value">{avg_quality_overall}</div>
            <div class="kpi-sub">Threshold: &ge; 0.75</div>
        </div>
    </div>

    <div class="grid">
        <!-- 1. Latency Panel -->
        <div class="panel">
            <div class="panel-header">
                <span class="panel-title">1. Latency percentiles & TTFT (ms)</span>
                <span class="panel-threshold">Threshold: P95 &le; 3000 ms</span>
            </div>
            <div class="chart-container">
                <canvas id="chartLatency"></canvas>
            </div>
        </div>

        <!-- 2. Traffic Panel -->
        <div class="panel">
            <div class="panel-header">
                <span class="panel-title">2. Request Traffic (requests/min)</span>
                <span class="panel-threshold">Threshold: Rate &ge; 1 req/min</span>
            </div>
            <div class="chart-container">
                <canvas id="chartTraffic"></canvas>
            </div>
        </div>

        <!-- 3. Errors Panel -->
        <div class="panel">
            <div class="panel-header">
                <span class="panel-title">3. Error Rate & Retrieval Success (%)</span>
                <span class="panel-threshold">Threshold: Error &le; 2% | Retrieval &ge; 90%</span>
            </div>
            <div class="chart-container">
                <canvas id="chartErrors"></canvas>
            </div>
        </div>

        <!-- 4. Cost Panel -->
        <div class="panel">
            <div class="panel-header">
                <span class="panel-title">4. Cost over time (USD)</span>
                <span class="panel-threshold">Threshold: Total &le; $2.50</span>
            </div>
            <div class="chart-container">
                <canvas id="chartCost"></canvas>
            </div>
        </div>

        <!-- 5. Tokens Panel -->
        <div class="panel">
            <div class="panel-header">
                <span class="panel-title">5. Input & Output Tokens (sum)</span>
                <span class="panel-threshold">Threshold: Total &le; 50,000 tokens</span>
            </div>
            <div class="chart-container">
                <canvas id="chartTokens"></canvas>
            </div>
        </div>

        <!-- 6. Quality Panel -->
        <div class="panel">
            <div class="panel-header">
                <span class="panel-title">6. Quality Proxy (score 0.0 - 1.0)</span>
                <span class="panel-threshold">Threshold: Mean &ge; 0.75</span>
            </div>
            <div class="chart-container">
                <canvas id="chartQuality"></canvas>
            </div>
        </div>
    </div>

    <script>
        const labels = {json.dumps(labels)};
        const chartOptions = (unit, thresholdVal, thresholdText, isGte = false) => ({{
            responsive: true,
            maintainAspectRatio: false,
            interaction: {{ mode: 'index', intersect: false }},
            plugins: {{
                legend: {{ position: 'top', labels: {{ color: '#c9d1d9', font: {{ size: 11 }} }} }},
                tooltip: {{ backgroundColor: '#21262d', titleColor: '#f0f6fc', bodyColor: '#c9d1d9', borderColor: '#30363d', borderWidth: 1 }}
            }},
            scales: {{
                x: {{ grid: {{ color: 'rgba(255,255,255,0.06)' }}, ticks: {{ color: '#8b949e', font: {{ size: 10 }} }} }},
                y: {{ grid: {{ color: 'rgba(255,255,255,0.06)' }}, ticks: {{ color: '#8b949e', font: {{ size: 10 }} }}, title: {{ display: true, text: unit, color: '#8b949e', font: {{ size: 10 }} }} }}
            }}
        }});

        // 1. Latency Chart
        new Chart(document.getElementById('chartLatency'), {{
            type: 'line',
            data: {{
                labels: labels,
                datasets: [
                    {{ label: 'P95 Latency', data: {json.dumps(p95_series)}, borderColor: '#f85149', backgroundColor: 'rgba(248,81,73,0.1)', tension: 0.2 }},
                    {{ label: 'P50 Latency', data: {json.dumps(p50_series)}, borderColor: '#58a6ff', backgroundColor: 'rgba(88,166,255,0.1)', tension: 0.2 }},
                    {{ label: 'P99 Latency', data: {json.dumps(p99_series)}, borderColor: '#bc8cff', borderDash: [4, 4], tension: 0.2 }},
                    {{ label: 'TTFT P95', data: {json.dumps(ttft_p95_series)}, borderColor: '#d29922', tension: 0.2 }},
                    {{ label: 'Threshold (3000ms)', data: labels.map(() => 3000), borderColor: '#f85149', borderDash: [6, 6], pointRadius: 0, fill: false }}
                ]
            }},
            options: chartOptions('Milliseconds (ms)', 3000, 'Threshold 3000ms')
        }});

        // 2. Traffic Chart
        new Chart(document.getElementById('chartTraffic'), {{
            type: 'bar',
            data: {{
                labels: labels,
                datasets: [
                    {{ label: 'Requests / min', data: {json.dumps(traffic_series)}, backgroundColor: '#58a6ff', borderRadius: 4 }},
                    {{ type: 'line', label: 'Threshold (1 req/min)', data: labels.map(() => 1), borderColor: '#d29922', borderDash: [6, 6], pointRadius: 0 }}
                ]
            }},
            options: chartOptions('Requests/min', 1, 'Min 1 req/min')
        }});

        // 3. Errors & Retrieval Chart
        new Chart(document.getElementById('chartErrors'), {{
            type: 'line',
            data: {{
                labels: labels,
                datasets: [
                    {{ label: 'Retrieval Success %', data: {json.dumps(retrieval_success_series)}, borderColor: '#3fb950', backgroundColor: 'rgba(63,185,80,0.1)', tension: 0.2 }},
                    {{ label: 'Error Rate %', data: {json.dumps(error_rate_series)}, borderColor: '#f85149', backgroundColor: 'rgba(248,81,73,0.1)', tension: 0.2 }},
                    {{ label: 'Error Threshold (2%)', data: labels.map(() => 2), borderColor: '#f85149', borderDash: [6, 6], pointRadius: 0 }}
                ]
            }},
            options: chartOptions('Percentage (%)', 2, 'Threshold 2%')
        }});

        // 4. Cost Chart
        new Chart(document.getElementById('chartCost'), {{
            type: 'line',
            data: {{
                labels: labels,
                datasets: [
                    {{ label: 'Cumulative Cost ($)', data: {json.dumps(cum_cost)}, borderColor: '#3fb950', backgroundColor: 'rgba(63,185,80,0.15)', fill: true, tension: 0.2 }},
                    {{ label: 'Cost / min ($)', data: {json.dumps(cost_series)}, borderColor: '#58a6ff', borderDash: [3, 3], tension: 0.2 }},
                    {{ label: 'Threshold ($2.50)', data: labels.map(() => 2.50), borderColor: '#d29922', borderDash: [6, 6], pointRadius: 0 }}
                ]
            }},
            options: chartOptions('USD ($)', 2.5, 'Threshold $2.50')
        }});

        // 5. Tokens Chart
        new Chart(document.getElementById('chartTokens'), {{
            type: 'bar',
            data: {{
                labels: labels,
                datasets: [
                    {{ label: 'Tokens In', data: {json.dumps(tokens_in_series)}, backgroundColor: '#58a6ff', stack: 'tokens' }},
                    {{ label: 'Tokens Out', data: {json.dumps(tokens_out_series)}, backgroundColor: '#bc8cff', stack: 'tokens' }},
                    {{ type: 'line', label: 'Threshold (50k)', data: labels.map(() => 50000), borderColor: '#f85149', borderDash: [6, 6], pointRadius: 0 }}
                ]
            }},
            options: chartOptions('Tokens', 50000, 'Threshold 50,000')
        }});

        // 6. Quality Chart
        new Chart(document.getElementById('chartQuality'), {{
            type: 'line',
            data: {{
                labels: labels,
                datasets: [
                    {{ label: 'Quality Proxy', data: {json.dumps(quality_series)}, borderColor: '#3fb950', backgroundColor: 'rgba(63,185,80,0.1)', tension: 0.2 }},
                    {{ label: 'Threshold (0.75)', data: labels.map(() => 0.75), borderColor: '#d29922', borderDash: [6, 6], pointRadius: 0 }}
                ]
            }},
            options: chartOptions('Score (0.0 - 1.0)', 0.75, 'Min 0.75')
        }});

        // Auto refresh every 30s
        setTimeout(() => {{ window.location.reload(); }}, 30000);
    </script>
</body>
</html>
"""

    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"Dashboard HTML successfully generated at: {OUT_HTML}")

if __name__ == "__main__":
    generate_dashboard()
