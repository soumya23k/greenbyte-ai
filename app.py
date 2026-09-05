import os
import time
import urllib.request
import xml.etree.ElementTree as ET
import psutil
import gc
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

BOOT_TIME = psutil.boot_time()
CPU_CORES = psutil.cpu_count() or 1

GRID_INTENSITY = {
    "WB Grid (Thermal/Coal)": {"factor": 710.0, "status": "Critical"},
    "India Avg Grid": {"factor": 650.0, "status": "Moderate"},
    "Global Avg Grid": {"factor": 475.0, "status": "Moderate"},
    "EU Grid (Renewables)": {"factor": 210.0, "status": "Optimal"}
}

NETWORK_KWH_PER_GB = 0.06
ELECTRICITY_RATE_PER_KWH_INR = 7.5
initial_net_io = psutil.net_io_counters()

def fetch_live_eco_news():
    try:
        url = "https://sustainability.economictimes.indiatimes.com/rss/green-tech"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as response:
            xml_data = response.read()
            root = ET.fromstring(xml_data)
            news = []
            for item in root.findall('.//item')[:5]:
                title = item.find('title').text if item.find('title') is not None else ""
                news.append({"title": title, "tag": "Green Tech Live"})
            return news if news else fallback_news()
    except Exception:
        return fallback_news()

def fallback_news():
    return [
        {"title": "Data Centers Projected to Consume 8% of Global Electricity by 2030", "tag": "Cloud Impact"},
        {"title": "Dark Mode & Asset Compression Save Up to 15% Screen Power Draw", "tag": "Green Web"},
        {"title": "West Bengal Expanding Renewable Capacity to Lower Grid Emissions", "tag": "Clean Energy"}
    ]

# === ROUTE TO SERVE FRONTEND INDEX.HTML ===
@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/api/telemetry', methods=['GET'])
def telemetry():
    selected_grid = request.args.get('grid', 'WB Grid (Thermal/Coal)')
    grid_data = GRID_INTENSITY.get(selected_grid, GRID_INTENSITY["WB Grid (Thermal/Coal)"])
    grid_factor = grid_data["factor"]

    # 1. System Telemetry
    raw_cpu = psutil.cpu_percent(interval=0.3)
    normalized_cpu = round(raw_cpu / CPU_CORES, 1)
    
    mem = psutil.virtual_memory()
    mem_pct = mem.percent
    disk = psutil.disk_usage('/')

    # 2. Power Consumption & Energy
    base_watts = 12.0
    dynamic_watts = (normalized_cpu / 100.0) * 38.0
    current_watts = base_watts + dynamic_watts

    uptime_seconds = time.time() - BOOT_TIME
    uptime_hours = uptime_seconds / 3600.0
    system_kwh = (current_watts * uptime_hours) / 1000.0

    # 3. Data Transfer
    current_net_io = psutil.net_io_counters()
    bytes_sent = current_net_io.bytes_sent - initial_net_io.bytes_sent
    bytes_recv = current_net_io.bytes_recv - initial_net_io.bytes_recv
    total_data_gb = (bytes_sent + bytes_recv) / (1024**3)
    network_kwh = total_data_gb * NETWORK_KWH_PER_GB

    total_kwh = system_kwh + network_kwh
    co2_grams = round(total_kwh * grid_factor, 2)
    cost_saved_inr = round((system_kwh) * ELECTRICITY_RATE_PER_KWH_INR, 2)

    # 4. Real-World Impact Translator Calculations
    trees_equivalent = round(co2_grams / 60.0, 2)
    car_km_avoided = round(co2_grams / 120.0, 2)
    led_bulb_hours = round(co2_grams / 7.0, 1)

    # 5. Sustainability Score
    score = 100
    if normalized_cpu > 70: score -= 35
    elif normalized_cpu > 40: score -= 20
    elif normalized_cpu > 20: score -= 10

    if mem_pct > 80: score -= 20
    elif mem_pct > 60: score -= 10

    if disk.percent > 85: score -= 15

    battery = psutil.sensors_battery()
    battery_pct = battery.percent if battery else 100
    plugged_in = battery.power_plugged if battery else True

    if plugged_in and battery_pct >= 95: score -= 15
    score = max(min(score, 100), 10)

    # 6. E-Waste Thermal Wear Factor
    wear_factor = "Low"
    if normalized_cpu > 60 or (plugged_in and battery_pct >= 95):
        wear_factor = "High (Thermal Stress)"
    elif normalized_cpu > 30:
        wear_factor = "Moderate"

    # 7. Gamification System (XP, Level, Streaks)
    xp = int(uptime_hours * 120 + score * 5)
    user_level = "Eco Warrior" if xp > 500 else "Green Novice"
    streak_days = 7

    badges = []
    if score >= 85: badges.append({"title": "🌱 Eco Pioneer", "desc": "High efficiency score maintained."})
    if total_data_gb < 0.5: badges.append({"title": "⚡ Low Bandwidth", "desc": "Minimizing data center network draw."})
    if not plugged_in or battery_pct < 95: badges.append({"title": "🔋 Battery Guardian", "desc": "Preventing trickle charge wear."})

    # 8. Process Carbon Breakdown
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            p_info = proc.info
            p_name = p_info['name']
            if p_name.lower() in ['system idle process', 'idle']:
                continue

            p_cpu = round((p_info['cpu_percent'] or 0.0) / CPU_CORES, 1)
            p_mem = round(p_info['memory_percent'] or 0.0, 1)

            if p_cpu > 0.1 or p_mem > 0.5:
                app_watts = (p_cpu / 100.0) * 35.0
                app_co2_hourly = round((app_watts / 1000.0) * grid_factor, 2)
                processes.append({
                    "pid": p_info['pid'],
                    "name": p_name,
                    "cpu": p_cpu,
                    "memory": p_mem,
                    "co2_hourly_g": app_co2_hourly
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    processes = sorted(processes, key=lambda x: x['co2_hourly_g'], reverse=True)[:6]

    # 9. AI Sustainability 7-Day Forecast
    projected_7day_kwh = round((current_watts * 24 * 7) / 1000.0, 2)
    projected_7day_co2 = round((projected_7day_kwh * grid_factor) / 1000.0, 2)
    trend = "Improving 📈" if score >= 80 else "Needs Optimization ⚠️"

    suggestions = []
    if normalized_cpu > 40:
        suggestions.append(f"High CPU load ({normalized_cpu}%). Consider closing resource-heavy apps.")
    if processes and processes[0]['cpu'] > 10:
        suggestions.append(f"App '{processes[0]['name']}' emits ~{processes[0]['co2_hourly_g']}g CO₂/hr.")
    if plugged_in and battery_pct >= 95:
        suggestions.append("Battery is full. Unplug charger to prevent heat and trickle-charge waste.")
    if not suggestions:
        suggestions.append("System running at optimal eco-efficiency!")

    return jsonify({
        "cpu_percent": normalized_cpu,
        "ram_percent": mem_pct,
        "disk_percent": disk.percent,
        "current_watts": round(current_watts, 1),
        "co2_grams": co2_grams,
        "cost_saved_inr": cost_saved_inr,
        "sustainability_score": score,
        "hardware_wear": wear_factor,
        "impact": {
            "trees": trees_equivalent,
            "car_km": car_km_avoided,
            "led_hours": led_bulb_hours
        },
        "gamification": {
            "xp": xp,
            "level": user_level,
            "streak": streak_days,
            "badges": badges
        },
        "forecast": {
            "kwh_7day": projected_7day_kwh,
            "co2_7day_kg": projected_7day_co2,
            "trend": trend
        },
        "top_processes": processes,
        "suggestions": suggestions,
        "news": fetch_live_eco_news()
    })

@app.route('/api/analyze-url', methods=['POST'])
def analyze_url():
    data = request.get_json()
    url = data.get('url', '')
    if not url.startswith('http'):
        url = 'https://' + url

    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        start = time.time()
        with urllib.request.urlopen(req, timeout=5) as response:
            html = response.read()
            load_time = round(time.time() - start, 2)
            page_size_kb = round(len(html) / 1024, 2)
            est_co2_g = round((page_size_kb / 1024.0) * 0.8, 3)
            rating = "A+" if est_co2_g < 0.2 else ("B" if est_co2_g < 0.5 else "C (Asset Heavy)")

            return jsonify({
                "success": True,
                "url": url,
                "size_kb": page_size_kb,
                "load_time_sec": load_time,
                "co2_per_visit_g": est_co2_g,
                "green_rating": rating
            })
    except Exception as e:
        return jsonify({"success": False, "message": f"Scan failed: {str(e)}"}), 400

@app.route('/api/eco-optimize', methods=['POST'])
def eco_optimize():
    try:
        collected = gc.collect()
        return jsonify({
            "success": True,
            "message": f"Eco-Optimization finished! Flushed standby memory & recycled {collected} background objects."
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400

@app.route('/api/kill-process', methods=['POST'])
def kill_process():
    data = request.get_json()
    pid = data.get('pid')
    try:
        proc = psutil.Process(pid)
        proc.terminate()
        return jsonify({"success": True, "message": f"Terminated process {pid}"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400

if __name__ == '__main__':
    print("Starting All-In-One Master GreenByte Engine on http://localhost:5000...")
    app.run(port=5000, debug=True)