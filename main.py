import os
import json
import requests
import re
from flask import Flask, request
from geopy.distance import geodesic
from geopy.geocoders import Nominatim

app = Flask(__name__)

CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
KML_FILE = "mymap.kml"

geolocator = Nominatim(user_agent="line-bot")


# =========================
# TOP
# =========================
@app.route("/")
def home():
    return "LINE BOT OK", 200


# =========================
# CALLBACK
# =========================
@app.route("/callback", methods=["POST"])
def callback():

    print("STEP 1: CALLBACK HIT", flush=True)

    body = request.get_data(as_text=True)
    data = json.loads(body)

    events = data.get("events", [])

    for event in events:

        if event.get("type") != "message":
            continue

        message = event.get("message", {})
        msg_type = message.get("type")
        reply_token = event.get("replyToken")

        user_coords = resolve_location(message)

        if not user_coords:
            send_line_reply(reply_token, "住所やランドマークをもう少し詳しく送ってください")
            continue

        print("STEP 2: LOCATION RESOLVED", flush=True)

        reply_text = calculate_closest_places(user_coords)
        print("PINS COUNT:", len(pins), flush=True)
        print("TOTAL RESULTS:", len(results), flush=True)
        print("TOP LIST:", top5, flush=True)

        send_line_reply(reply_token, reply_text)

        print("STEP 3: REPLY DONE", flush=True)

    return "OK", 200


# =========================
# 入力 → 座標変換
# =========================
def resolve_location(message):

    msg_type = message.get("type")

    # ① 位置情報
    if msg_type == "location":
        return (
            float(message.get("latitude")),
            float(message.get("longitude"))
        )

    # ② テキスト（住所・ランドマーク）
    if msg_type == "text":

        text = message.get("text")

        try:
            location = geolocator.geocode(text)

            if location:
                return (location.latitude, location.longitude)

        except Exception as e:
            print("Geocode error:", e, flush=True)

    return None


# =========================
# KML読み込み
# =========================
def load_kml():

    with open(KML_FILE, "r", encoding="utf-8") as f:
        kml_data = f.read()

    placemarks = re.findall(r"<Placemark>.*?</Placemark>", kml_data, re.DOTALL)

    print(kml_data[:500], flush=True)

    pins = []

    for pm in placemarks:

        name_match = re.search(r"<name>(.*?)</name>", pm, re.DOTALL)
        name = name_match.group(1).strip() if name_match else "名称未設定"

        desc_match = re.search(r"<description>(.*?)</description>", pm, re.DOTALL)
        desc = desc_match.group(1).strip() if desc_match else ""

        coord_match = re.search(r"<coordinates>(.*?)</coordinates>", pm)

        if coord_match:
            parts = coord_match.group(1).split(",")

            if len(parts) >= 2:
                try:
                    lon = float(parts[0])
                    lat = float(parts[1])

                    pins.append({
                        "name": name,
                        "description": desc,
                        "coords": (lat, lon)
                    })

                except:
                    continue

    return pins


# =========================
# 距離計算
# =========================
def calculate_closest_places(user_coords):

    pins = load_kml()

    results = []

    for pin in pins:

        distance = geodesic(user_coords, pin["coords"]).km

        desc = pin["description"]

        tel_match = re.search(r"0\d{1,4}-\d{1,4}-\d{4}", desc)
        tel = tel_match.group(0) if tel_match else "なし"

        address = re.sub(r"<[^>]*>", "", desc).strip()
        address = address.replace(tel, "").strip()

        if not address:
            address = "住所不明"

        map_url = f"https://www.google.com/maps?q={pin['coords'][0]},{pin['coords'][1]}"

        results.append({
            "name": pin["name"],
            "distance": distance,
            "address": address,
            "tel": tel,
            "map": map_url
        })

    results.sort(key=lambda x: x["distance"])
    top5 = results[:5]

    text = "📍 近くの健診場所 TOP5\n\n"

    for i, r in enumerate(top5, 1):

        text += (
            f"{i}位 {r['name']}\n"
            f"📏 {r['distance']:.2f}km\n"
            f"🏠 {r['address']}\n"
            f"📞 {r['tel']}\n"
            f"🗺 {r['map']}\n"
            "-------------------\n"
        )

    return text


# =========================
# LINE送信
# =========================
def send_line_reply(reply_token, text):

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

    res = requests.post(url, headers=headers, json=payload, timeout=10)

    print("LINE STATUS:", res.status_code, flush=True)
    print("LINE RESPONSE:", res.text, flush=True)


# =========================
# START
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
