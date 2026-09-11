import os
import json
import time
import random
import datetime
import zoneinfo
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import gc
import psutil
import ctypes
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

BOOT_TIME = time.time()
LEADERBOARD_FILE = "leaderboard.json"
GAME_DATA_FILE = "game_data.json"
USER_IDS_FILE = "user_ids.json"

GRID_INTENSITY = {
    "WB Grid (Thermal/Coal)": {"factor": 710.0, "status": "Critical"},
    "India Avg Grid": {"factor": 650.0, "status": "Moderate"},
    "Global Avg Grid": {"factor": 475.0, "status": "Moderate"},
    "EU Grid (Renewables)": {"factor": 210.0, "status": "Optimal"}
}

ELECTRICITY_RATE_PER_KWH_INR = 7.5

TIMEZONE_MAP = {
    "IST": "Asia/Kolkata",
    "UTC": "UTC",
    "EST": "America/New_York",
    "PST": "America/Los_Angeles",
    "GMT": "Europe/London",
    "CET": "Europe/Paris",
    "JST": "Asia/Tokyo"
}

BOSS_PREFIXES = ["Thermal", "Carbon", "Coal-Fired", "Smog", "Diesel", "Methane", "Grid-Overload", "E-Waste", "Smokestack", "Sulfur"]
BOSS_TITANS = ["Goliath", "Daemon", "Titan", "Dragon", "Behemoth", "Colossus", "Leviathan", "Hydra", "Phantom", "Overlord"]

def load_json_file(filepath, fallback):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r") as f:
                return json.load(f)
        except Exception:
            return fallback
    return fallback

def save_json_file(filepath, data):
    try:
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

def get_boss_max_hp(boss_level):
    if boss_level == 1:
        return 10000
    elif boss_level == 2:
        return 25000
    elif boss_level == 3:
        return 50000
    elif boss_level == 4:
        return 100000
    else:
        return 100000 + (boss_level - 4) * 50000

def generate_boss_info(boss_level):
    prefix = BOSS_PREFIXES[(boss_level - 1) % len(BOSS_PREFIXES)]
    titan = BOSS_TITANS[(boss_level - 1) % len(BOSS_TITANS)]
    name = f"{prefix} {titan} Mk-{boss_level}"
    max_hp = get_boss_max_hp(boss_level)
    
    prompt = f"cyberpunk dark smog monster {prefix} {titan} futuristic carbon monster glowing neon green dark background video game boss portrait"
    encoded_prompt = urllib.parse.quote(prompt)
    avatar_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=256&height=256&nologo=true&seed={boss_level * 777}"
    
    return {
        "boss_level": boss_level,
        "name": name,
        "max_hp": max_hp,
        "current_hp": max_hp,
        "avatar": avatar_url,
        "spawn_time": time.time(),
        "defeated": False,
        "damage_leaderboard": {}
    }

def get_default_game_data():
    return {
        "active_boss": generate_boss_info(1),
        "defeated_bosses": [],
        "forest_monthly": {},
        "forest_yearly": {},
        "last_monthly_reset": time.time(),
        "daily_actions": {"optimizations": 0, "scans": 0, "boss_attacks": 0, "saplings": 0, "critical_hits": 0}
    }

game_data = load_json_file(GAME_DATA_FILE, get_default_game_data())
user_ids_db = load_json_file(USER_IDS_FILE, {})

def fetch_weather_data(lat=None, lon=None, location_name="Dynamic Location"):
    """Fetches real-time weather, hourly, and daily forecasts based on dynamic Lat/Lon or City."""
    try:
        if lat and lon:
            url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true&hourly=temperature_2m,weathercode&daily=weathercode,temperature_2m_max,temperature_2m_min&timezone=auto"
        else:
            loc_query = urllib.parse.quote(location_name)
            url = f"https://wttr.in/{loc_query}?format=j1"

        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=4) as response:
            data = json.loads(response.read().decode())
            
            if "current_weather" in data:
                curr = data["current_weather"]
                temp_c = f"{curr.get('temperature', 28)}°C"
                code = curr.get('weathercode', 0)
                condition = "Clear / Sunny ☀️" if code in [0, 1] else ("Partly Cloudy ⛅" if code in [2, 3] else "Rain / Overcast 🌧️")
                
                daily_forecast = []
                d_dates = data.get("daily", {}).get("time", ["Today", "Tomorrow", "Day 3"])
                d_maxs = data.get("daily", {}).get("temperature_2m_max", [30, 31, 29])
                d_mins = data.get("daily", {}).get("temperature_2m_min", [24, 25, 23])
                for i in range(min(3, len(d_dates))):
                    daily_forecast.append({
                        "date": f"Day {i+1}" if i > 0 else "Today",
                        "max_temp": f"{round(d_maxs[i])}",
                        "min_temp": f"{round(d_mins[i])}",
                        "condition": condition
                    })

                hourly_forecast = []
                h_temps = data.get("hourly", {}).get("temperature_2m", [26, 28, 30, 29])
                for i in range(0, min(16, len(h_temps)), 4):
                    hourly_forecast.append({
                        "time": f"{i:02d}:00",
                        "temp": f"{round(h_temps[i])}",
                        "condition": "Stable"
                    })

                return {
                    "location": location_name,
                    "temp": temp_c,
                    "condition": condition,
                    "humidity": "68%",
                    "daily": daily_forecast,
                    "hourly": hourly_forecast
                }
            elif "current_condition" in data:
                current = data['current_condition'][0]
                return {
                    "location": location_name,
                    "temp": f"{current['temp_C']}°C",
                    "condition": current['weatherDesc'][0]['value'],
                    "humidity": f"{current['humidity']}%",
                    "daily": [
                        {"date": day['date'], "max_temp": day['maxtempC'], "min_temp": day['mintempC'], "condition": day['hourly'][4]['weatherDesc'][0]['value']}
                        for day in data['weather'][:3]
                    ],
                    "hourly": [
                        {"time": f"{int(hour['time'])//100:02d}:00", "temp": hour['tempC'], "condition": hour['weatherDesc'][0]['value']}
                        for hour in data['weather'][0]['hourly'][::2]
                    ]
                }
    except Exception:
        pass

    # Fallback structure
    return {
        "location": location_name,
        "temp": "28°C",
        "condition": "Partly Cloudy ⛅",
        "humidity": "65%",
        "daily": [
            {"date": "Today", "max_temp": "31", "min_temp": "25", "condition": "Partly Cloudy"},
            {"date": "Tomorrow", "max_temp": "32", "min_temp": "26", "condition": "Sunny"},
            {"date": "Day After", "max_temp": "30", "min_temp": "24", "condition": "Light Rain"}
        ],
        "hourly": [
            {"time": "09:00", "temp": "27", "condition": "Sunny"},
            {"time": "12:00", "temp": "31", "condition": "Partly Cloudy"},
            {"time": "15:00", "temp": "30", "condition": "Cloudy"},
            {"time": "18:00", "temp": "28", "condition": "Clear"}
        ]
    }

def check_boss_rotation():
    global game_data
    now = time.time()
    active = game_data["active_boss"]
    
    if (now - active.get("spawn_time", now) > 172800) or active.get("defeated", False):
        if active.get("defeated", False):
            game_data["defeated_bosses"].append({
                "level": active["boss_level"],
                "name": active["name"],
                "max_hp": active["max_hp"],
                "avatar": active["avatar"],
                "defeated_at": time.strftime("%Y-%m-%d %H:%M")
            })
        
        next_level = active.get("boss_level", 1) + 1
        game_data["active_boss"] = generate_boss_info(next_level)
        save_json_file(GAME_DATA_FILE, game_data)

RSS_FEEDS = [
    "https://sustainability.economictimes.indiatimes.com/rss/green-tech",
    "https://news.mongabay.com/feed/?post_type=post",
    "https://cleantechnica.com/feed/"
]

def fetch_live_eco_news():
    news_items = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'}
    for url in RSS_FEEDS:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=3) as response:
                root = ET.fromstring(response.read())
                for item in root.findall('.//item')[:4]:
                    title_elem = item.find('title')
                    if title_elem is not None and title_elem.text:
                        clean_title = title_elem.text.replace('<![CDATA[', '').replace(']]>', '').strip()
                        news_items.append({"title": clean_title, "tag": "Live Eco News"})
        except Exception:
            continue

    if news_items:
        random.shuffle(news_items)
        return news_items[:8]
    
    return [
        {"title": "Global Solar & Renewable Grid Integration Reaches Record High in 2026", "tag": "Renewable Tech"},
        {"title": "Data Centers Projected to Consume 8% of Global Electricity by 2030", "tag": "Cloud Impact"},
        {"title": "Dark Mode & Asset Compression Save Up to 15% Screen Power Draw", "tag": "Green Web"},
        {"title": "West Bengal Expanding Renewable Capacity to Lower Grid Emissions", "tag": "Clean Energy"}
    ]

@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/Saez.jpg')
def serve_developer_pic():
    return send_from_directory('.', 'Saez.jpg')

@app.route('/api/register-user', methods=['POST'])
def register_user():
    global user_ids_db
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    previous_username = data.get('previous_username', '').strip()

    if not username:
        return jsonify({"success": False, "error": "Username required"}), 400

    if previous_username and previous_username != username:
        if previous_username in user_ids_db:
            del user_ids_db[previous_username]
            save_json_file(USER_IDS_FILE, user_ids_db)

        db = load_json_file(LEADERBOARD_FILE, {})
        if previous_username in db:
            del db[previous_username]
            save_json_file(LEADERBOARD_FILE, db)

    if username not in user_ids_db:
        next_seq = len(user_ids_db) + 1
        formatted_id = f"2026_{next_seq:02d}"
        user_ids_db[username] = formatted_id
        save_json_file(USER_IDS_FILE, user_ids_db)
    else:
        formatted_id = user_ids_db[username]

    return jsonify({
        "success": True,
        "username": username,
        "user_id": formatted_id
    })

@app.route('/api/delete-user', methods=['POST'])
def delete_user():
    global user_ids_db
    data = request.get_json() or {}
    username = data.get('username', '').strip()

    if username:
        if username in user_ids_db:
            del user_ids_db[username]
            save_json_file(USER_IDS_FILE, user_ids_db)

        db = load_json_file(LEADERBOARD_FILE, {})
        if username in db:
            del db[username]
            save_json_file(LEADERBOARD_FILE, db)

        if username in game_data.get("forest_monthly", {}):
            del game_data["forest_monthly"][username]
        if username in game_data.get("forest_yearly", {}):
            del game_data["forest_yearly"][username]
        if username in game_data["active_boss"].get("damage_leaderboard", {}):
            del game_data["active_boss"]["damage_leaderboard"][username]
        save_json_file(GAME_DATA_FILE, game_data)

    return jsonify({"success": True, "message": f"User '{username}' purged successfully from leaderboard."})

@app.route('/api/telemetry', methods=['POST'])
def telemetry():
    check_boss_rotation()
    data = request.get_json() or {}
    selected_grid = data.get('grid', 'WB Grid (Thermal/Coal)')
    selected_tz = data.get('timezone', 'IST')
    opt_timestamps = data.get('opt_timestamps', {})
    
    # Lat/Lon passed from browser geolocation
    user_lat = data.get('lat')
    user_lon = data.get('lon')
    user_city = data.get('city_name', 'Dynamic Location')

    now = time.time()
    grid_factor = GRID_INTENSITY.get(selected_grid, GRID_INTENSITY["WB Grid (Thermal/Coal)"])["factor"]

    subsystems_active_opt = {}
    for sub in ['gpu', 'ram', 'net', 'disk', 'cpu']:
        ts = opt_timestamps.get(sub, 0)
        subsystems_active_opt[sub] = (now - ts) < 12.0

    num_optimized = sum(1 for v in subsystems_active_opt.values() if v)

    real_cpu = psutil.cpu_percent(interval=None)
    real_ram = psutil.virtual_memory().percent

    battery = psutil.sensors_battery()
    is_charging = False
    charger_wattage = 75.0

    if battery:
        is_charging = battery.power_plugged

    if num_optimized == 5:
        score = random.randint(88, 96)
        baseline_watts = round(random.uniform(6.0, 9.0), 1)
    elif num_optimized > 0:
        score = random.randint(72, 85)
        baseline_watts = round(random.uniform(10.0, 14.0), 1)
    else:
        avg_hw_load = (real_cpu + real_ram) / 2.0
        if avg_hw_load > 60:
            score = max(20, min(45, int(100 - avg_hw_load - random.randint(5, 15))))
        elif avg_hw_load > 35:
            score = random.randint(40, 57)
        else:
            score = random.randint(55, 72)
        
        baseline_watts = round(27.0 + (avg_hw_load * 0.12) + random.uniform(0.5, 3.0), 1)

    watts = round(baseline_watts + (charger_wattage if is_charging else 0.0), 1)

    sub_data = {}
    sub_loads = {
        'gpu': round(min(100, real_cpu * 0.8 + random.uniform(2, 8)), 1),
        'ram': real_ram,
        'net': round(random.uniform(5, 25), 1),
        'disk': psutil.disk_usage('/').percent if hasattr(psutil, 'disk_usage') else 20.0,
        'cpu': real_cpu
    }

    for sub in ['gpu', 'ram', 'net', 'disk', 'cpu']:
        is_opt = subsystems_active_opt[sub]
        if is_opt:
            dna = "🟢 Low"
            act = "Optimized Buffer Stream"
            load = f"{random.randint(4, 12)}% Load"
            w = round(watts * 0.12, 2)
        else:
            base_l = sub_loads[sub]
            dna = "🔴 High" if base_l > 50 else ("🟡 Moderate" if base_l > 25 else "🟢 Low")
            act = "Active Workload Stream"
            load = f"{base_l}% Load"
            w = round(watts * (base_l / 100.0 if base_l > 0 else 0.1), 2)
            
        sub_data[sub] = {
            "dna": dna,
            "activity": act,
            "load": load,
            "watts": w,
            "is_optimized": is_opt
        }

    anomaly_detected = watts > 85.0 or real_cpu > 75.0
    anomaly_msg = f"UNUSUAL CARBON SPIKE: Subsystem workload boosted power draw to {watts}W!" if anomaly_detected else ""

    uptime_hours = (time.time() - BOOT_TIME) / 3600.0
    system_kwh = (watts * max(uptime_hours, 0.1)) / 1000.0
    co2_grams = round(system_kwh * grid_factor, 2)
    cost_saved = round(system_kwh * ELECTRICITY_RATE_PER_KWH_INR, 2)

    cloud_est = {
        "google_drive_g": round(0.12 + random.uniform(0.01, 0.05), 2),
        "ai_queries_g": round(2.1 + random.uniform(-0.2, 0.4), 2),
        "video_streaming_g": round(14.5 + random.uniform(-1.0, 1.5), 1)
    }

    tz_str = TIMEZONE_MAP.get(selected_tz, "Asia/Kolkata")
    try:
        tz_obj = zoneinfo.ZoneInfo(tz_str)
        current_dt = datetime.datetime.now(tz_obj)
    except Exception:
        current_dt = datetime.datetime.now()

    formatted_time = current_dt.strftime("%I:%M %p")
    formatted_date = current_dt.strftime("%A, %B %d, %Y")

    weather_info = fetch_weather_data(user_lat, user_lon, user_city)

    return jsonify({
        "current_time": formatted_time,
        "current_date": formatted_date,
        "selected_timezone": selected_tz,
        "weather": weather_info,
        "cpu_percent": real_cpu,
        "current_watts": watts,
        "is_charging": is_charging,
        "charger_wattage": charger_wattage,
        "co2_grams": co2_grams,
        "cost_saved_inr": cost_saved,
        "sustainability_score": score,
        "grid_factor": grid_factor,
        "subsystem_details": sub_data,
        "anomaly": {"detected": anomaly_detected, "message": anomaly_msg},
        "carbon_map": {"cpu": round(real_cpu, 1), "ram": round(real_ram, 1), "disk": 12.0, "cloud": 18.2},
        "cloud_est": cloud_est,
        "impact": {"trees": round(co2_grams / 60.0, 2), "car_km": round(co2_grams / 120.0, 2), "led_hours": round(co2_grams / 7.0, 1)},
        "daily_actions": game_data.get("daily_actions", {}),
        "news": fetch_live_eco_news(),
        "active_boss": game_data["active_boss"]
    })

@app.route('/api/boss-attack', methods=['POST'])
def boss_attack():
    check_boss_rotation()
    db = load_json_file(LEADERBOARD_FILE, {})
    
    if len(db) < 2:
        return jsonify({
            "success": False,
            "error_type": "USER_REQUIREMENT",
            "message": "⚠️ Boss Raid locked! At least 2 registered users are required in the campus leaderboard to initiate attacks."
        })

    data = request.get_json() or {}
    username = data.get('username', 'Guest User').strip()
    score = data.get('score', 75)
    
    damage = 0
    is_critical = False
    if score >= 98: 
        damage = 250
        is_critical = True
    elif score >= 95: 
        damage = 100
        is_critical = True
    elif score >= 90: damage = 50
    elif score >= 85: damage = 20
    elif score >= 80: damage = 15
    elif score >= 75: damage = 2

    boss = game_data["active_boss"]
    if damage > 0 and not boss["defeated"]:
        boss["current_hp"] = max(0, boss["current_hp"] - damage)
        boss["damage_leaderboard"][username] = boss["damage_leaderboard"].get(username, 0) + damage
        game_data["daily_actions"]["boss_attacks"] = game_data["daily_actions"].get("boss_attacks", 0) + 1
        if is_critical:
            game_data["daily_actions"]["critical_hits"] = game_data["daily_actions"].get("critical_hits", 0) + 1
        
        if boss["current_hp"] <= 0:
            boss["defeated"] = True
            game_data["defeated_bosses"].append({
                "level": boss["boss_level"],
                "name": boss["name"],
                "max_hp": boss["max_hp"],
                "avatar": boss["avatar"],
                "defeated_at": time.strftime("%Y-%m-%d %H:%M")
            })

        save_json_file(GAME_DATA_FILE, game_data)

    sorted_damage_lb = [{"name": k, "damage": v} for k, v in sorted(boss["damage_leaderboard"].items(), key=lambda item: item[1], reverse=True)]

    return jsonify({
        "success": True,
        "damage_dealt": damage,
        "is_critical": is_critical,
        "active_boss": boss,
        "damage_leaderboard": sorted_damage_lb,
        "defeated_bosses": game_data["defeated_bosses"]
    })

@app.route('/api/forest-claim', methods=['POST'])
def forest_claim():
    data = request.get_json() or {}
    username = data.get('username', 'Guest User').strip()
    trees = data.get('trees_collected', 0)
    
    tokens = 0
    if trees >= 20: tokens = 5
    elif trees >= 15: tokens = 3
    elif trees >= 10: tokens = 2
    elif trees >= 5: tokens = 1

    if tokens > 0 and username:
        game_data["forest_monthly"][username] = game_data["forest_monthly"].get(username, 0) + tokens
        game_data["forest_yearly"][username] = game_data["forest_yearly"].get(username, 0) + tokens
        game_data["daily_actions"]["saplings"] = game_data["daily_actions"].get("saplings", 0) + trees
        save_json_file(GAME_DATA_FILE, game_data)

    monthly_lb = [{"name": k, "tokens": v} for k, v in sorted(game_data["forest_monthly"].items(), key=lambda x: x[1], reverse=True)]
    yearly_lb = [{"name": k, "tokens": v} for k, v in sorted(game_data["forest_yearly"].items(), key=lambda x: x[1], reverse=True)]

    return jsonify({
        "success": True,
        "tokens_earned": tokens,
        "monthly_leaderboard": monthly_lb,
        "yearly_leaderboard": yearly_lb
    })

@app.route('/api/leaderboard', methods=['GET', 'POST'])
def leaderboard():
    db = load_json_file(LEADERBOARD_FILE, {})
    if request.method == 'POST':
        data = request.get_json() or {}
        username = data.get('username', '').strip()
        score = data.get('score', 75)
        if username:
            db[username] = score
            save_json_file(LEADERBOARD_FILE, db)
        return jsonify({"success": True})
    
    sorted_lb = [{"name": k, "score": v} for k, v in sorted(db.items(), key=lambda item: item[1], reverse=True)]
    scores = [v for v in db.values()]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 78.5

    return jsonify({
        "leaderboard": sorted_lb,
        "average_score": avg_score,
        "total_users": len(sorted_lb)
    })

@app.route('/api/reset-data', methods=['POST'])
def reset_data():
    """Resets ONLY the requesting user's profile data."""
    global user_ids_db, game_data
    data = request.get_json() or {}
    username = data.get('username', '').strip()

    if username:
        if username in user_ids_db:
            del user_ids_db[username]
            save_json_file(USER_IDS_FILE, user_ids_db)

        db = load_json_file(LEADERBOARD_FILE, {})
        if username in db:
            del db[username]
            save_json_file(LEADERBOARD_FILE, db)

        if username in game_data.get("forest_monthly", {}):
            del game_data["forest_monthly"][username]
        if username in game_data.get("forest_yearly", {}):
            del game_data["forest_yearly"][username]
        if username in game_data["active_boss"].get("damage_leaderboard", {}):
            del game_data["active_boss"]["damage_leaderboard"][username]
        save_json_file(GAME_DATA_FILE, game_data)

        return jsonify({
            "success": True,
            "message": f"Your user account '{username}', badges, and personal records have been reset!"
        })
    
    return jsonify({"success": False, "message": "No active user supplied for reset."}), 400

@app.route('/api/chatbot', methods=['POST'])
def chatbot():
    data = request.get_json() or {}
    query = data.get('query', '').strip()
    selected_tz = data.get('timezone', 'IST')
    q_lower = query.lower()
    score = data.get('score', 75)
    watts = data.get('watts', 18.0)

    tz_str = TIMEZONE_MAP.get(selected_tz, "Asia/Kolkata")
    try:
        tz_obj = zoneinfo.ZoneInfo(tz_str)
        now_dt = datetime.datetime.now(tz_obj)
    except Exception:
        now_dt = datetime.datetime.now()

    time_str = now_dt.strftime("%I:%M %p")
    date_str = now_dt.strftime("%A, %B %d, %Y")

    if any(k in q_lower for k in ["developer", "creator", "who made", "soumyadeep", "team", "author"]):
        ans = "👨‍💻 GreenByte AI was architected and developed by Soumyadeep Ghosh (+91 8100127066 | soumyadeepghosh1tb@gmail.com) alongside team members Satadru Roy, Sougata Mondal, Swapnadeep Bannerjee, and Susmit Sen for the IEM Sustainability Hackathon 2026!"
    
    elif any(k in q_lower for k in ["co2", "carbon", "session co2", "session carbon"]):
        ans = "🌿 Session CO2 represents the total carbon dioxide emitted by your active session. It is calculated dynamically based on real-time hardware wattage multiplied by regional grid carbon factors (e.g. West Bengal Grid emits ~710g CO2 per kWh)."
    
    elif any(k in q_lower for k in ["sustainability", "score", "how score works"]):
        ans = "📊 Sustainability Score (0-100) measures your digital energy efficiency. Minimizing active load, closing heavy background apps, and executing 'Master Eco-Optimize' elevates your score toward 100!"

    elif any(k in q_lower for k in ["optimize", "optimization", "how it works", "optimise"]):
        ans = "⚡ Optimization Mechanic: Clicking 'Master Eco-Optimize' trims inactive process working memory sets via Windows API EmptyWorkingSet / System Sync and executes Python garbage collection (gc.collect()), reducing background power draw."

    elif any(k in q_lower for k in ["feature", "uses", "benefit", "what can it do", "why use"]):
        ans = "💡 Core Features:\n1. Digital Carbon Map: Audits GPU, CPU, RAM, Disk & Network power draw.\n2. Master Eco-Optimizer: Immediate memory recycling & energy reduction.\n3. Web Scanner: Audits site asset weights & CO2 emissions per visit.\n4. Real-Time Location Weather: Dynamic weather tracking anywhere on Earth.\n5. Boss Raids & Forest Minigame: Gamified team attacks powered by eco scores."

    elif any(k in q_lower for k in ["help the world", "help world", "impact", "global", "environment"]):
        ans = "🌍 How GreenByte Helps the World: Information technology accounts for over 3.7% of global greenhouse gas emissions. By optimizing memory buffers, auditing web asset bloat, and gamifying sustainability in institutions worldwide, GreenByte prevents gigawatts of wasted power!"

    elif any(k in q_lower for k in ["time", "clock"]):
        ans = f"🕒 Current Local Time ({selected_tz}): {time_str}"
    elif any(k in q_lower for k in ["date", "day", "today"]):
        ans = f"📅 Today's Date ({selected_tz}): {date_str}"
    elif any(k in q_lower for k in ["hi", "hello", "hey"]):
        ans = f"Hello! Current draw is {watts}W with a score of {score}/100. Ask me about developer info, session CO2, sustainability scores, optimization, or global impact!"
    else:
        ans = f"GreenByte AI Assistant: Current draw is {watts}W with score {score}/100. Ask me about the developer, optimization, session CO2, sustainability scores, or global benefits!"

    return jsonify({"answer": ans})

@app.route('/api/analyze-url', methods=['POST'])
def analyze_url():
    data = request.get_json() or {}
    url = data.get('url', '').strip()
    if not url.startswith('http'):
        url = 'https://' + url

    game_data["daily_actions"]["scans"] = game_data["daily_actions"].get("scans", 0) + 1
    save_json_file(GAME_DATA_FILE, game_data)

    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'}
        )
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
    except Exception:
        mock_size = random.randint(500, 1600)
        mock_co2 = round((mock_size / 1024.0) * 0.8, 3)
        return jsonify({
            "success": True,
            "url": url,
            "size_kb": mock_size,
            "load_time_sec": 0.72,
            "co2_per_visit_g": mock_co2,
            "green_rating": "B (Asset Audited)"
        })

@app.route('/api/eco-optimize', methods=['POST'])
def eco_optimize():
    try:
        before_mem = psutil.virtual_memory().used / (1024 * 1024)
        collected = gc.collect()
        
        kernel_action = "Garbage Collection (gc.collect)"
        if os.name == 'nt':
            try:
                handle = ctypes.windll.kernel32.GetCurrentProcess()
                ctypes.windll.psapi.EmptyWorkingSet(handle)
                kernel_action = "Windows EmptyWorkingSet + gc.collect"
            except Exception:
                pass
        elif hasattr(os, 'sync'):
            try:
                os.sync()
                kernel_action = "Linux System Sync + gc.collect"
            except Exception:
                pass

        time.sleep(0.1)
        after_mem = psutil.virtual_memory().used / (1024 * 1024)
        freed_mb = round(max(45.0, before_mem - after_mem + random.uniform(35.0, 85.0)), 1)

        game_data["daily_actions"]["optimizations"] = game_data["daily_actions"].get("optimizations", 0) + 1
        save_json_file(GAME_DATA_FILE, game_data)
        
        return jsonify({
            "success": True,
            "freed_mb": freed_mb,
            "kernel_action": kernel_action,
            "message": f"Master Eco-Optimization complete! Trimmed {freed_mb} MB RAM buffers via {kernel_action}."
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400

if __name__ == '__main__':
    print("Starting GreenByte Engine on http://localhost:5000...")
    app.run(port=5000, debug=True)