import os
import json
import re
import requests
from flask import Flask, request
from geopy.distance import geodesic
from geopy.geocoders import Nominatim

app = Flask(__name__)

CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
KML_FILE = "mymap.kml"

geolocator = Nominatim(user_agent="line-bot", timeout=10)

# =========================
# キャッシュ（超重要）
# =========================
geo_cache = {}

# =========================
# KMLは起動時に読み込み
# =========================
PINS = []


# =========================
# TOP
# =========================
@app.route("/")
def home():
    return "LINE BOT OK", 200


# =========================
# LINE webhook
# =========================
@app.route("/callback", methods=["POST"])
def callback():

    print("STEP 1: CALLBACK HIT", flush=True)

    body = request.get_data(as_text=True)
    data = json.loads(body)

    for event in data.get("events", []):

        if event.get("type") != "message":
            continue

        message = event.get("message", {})
        reply_token = event.get("replyToken")

        user_coords = resolve_location(message)

        if not user_coords:
            send_reply(reply_token, "住所かランドマークを送ってください")
            continue

        print("STEP 2: LOCATION OK", flush=True)

        reply_text = calculate_top5(user_coords)

        send_reply(reply_token, reply_text)

        print("STEP 3: DONE", flush=True)

    return "OK", 200


# =========================
# 入力解析（位置・住所・ランドマーク）
# =========================
def resolve_location(message):

    msg_type = message.get("type")

    # 位置情報
    if msg_type == "location":
        return (
            float(message.get("latitude")),
            float(message.get("longitude"))
        )

    # テキスト（住所・ランドマーク）
    if msg_type == "text":

        text = message.get("text")

        location = safe_geocode(text)

        if location:
            return (location.latitude, location.longitude)

    return None


# =========================
# ジオコーディング（安全版）
# =========================
def safe_geocode(text):

    if text in geo_cache:
        return geo_cache[text]

    try:
        loc = geolocator.geocode(text, timeout=10)

        if loc:
            geo_cache[text] = loc
            return loc

    except Exception as e:
        print("geocode error:", e, flush=True)

    return None


# =========================
# KMLロード（1回だけ）
# =========================
def load_kml():

    with open(KML_FILE, "r", encoding="utf-8") as f:
        kml = f.read()

    placemarks = re.findall(r"<Placemark.*?</Placemark>", kml, re.DOTALL)

    pins = []

    for pm in placemarks:

        name = re.search(r"<name>(.*?)</name>", pm)
        name = name.group(1) if name else "名称不明"

        coord = re.search(r"<coordinates>(.*?)</coordinates>", pm)

        if not coord:
            continue

        parts = coord.group(1).split(",")

        if len(parts) < 2:
            continue

        try:
            lon = float(parts[0])
            lat = float(parts[1])

            pins.append({
                "name": name,
                "coords": (lat, lon)
            })

        except:
            continue

    print("PINS LOADED:", len(pins), flush=True)

    return pins


# =========================
# TOP5計算
# =========================
def calculate_top5(user_coords):

    results = []

    for pin in PINS:

        dist = geodesic(user_coords, pin["coords"]).km

        results.append({
            "name": pin["name"],
            "distance": dist
        })

    results.sort(key=lambda x: x["distance"])

    top5 = results[:5]

    if not top5:
        return "近くの施設が見つかりませんでした"

    text = "📍 近い順TOP5\n\n"

    for i, r in enumerate(top5, 1):
        text += f"{i}. {r['name']}\n📏 {r['distance']:.2f}km\n\n"

    return text


# =========================
# LINE送信
# =========================
def send_reply(reply_token, text):

    url = "https://api.line.me/v2/bot/message/reply"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}"
    }

    payload = {
        "replyToken": reply_token,
        "messages": [
            {"type": "text", "text": text[:4500]}
        ]
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        print("LINE STATUS:", res.status_code, flush=True)
    except Exception as e:
        print("LINE ERROR:", e, flush=True)


# =========================
# 起動時にKMLロード
# =========================
if __name__ == "__main__":
    PINS = load_kml()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
