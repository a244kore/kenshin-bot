import os
import json
import requests
import re
from flask import Flask, request
from geopy.distance import geodesic

app = Flask(__name__)

CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")

KML_FILE = "kenshin.kml"  # ←あなたのKMLファイル名に合わせる


# =========================
# TOP PAGE
# =========================
@app.route("/")
def home():
    return "LINE BOT OK", 200


# =========================
# LINE WEBHOOK
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

        # -------------------------
        # 位置情報のときだけ処理
        # -------------------------
        if msg_type == "location":

            print("STEP 2: LOCATION RECEIVED", flush=True)

            user_coords = (
                float(message.get("latitude")),
                float(message.get("longitude"))
            )

            reply_text = calculate_closest_places(user_coords)

            send_line_reply(reply_token, reply_text)

            print("STEP 3: REPLY DONE", flush=True)

        else:
            send_line_reply(reply_token, "位置情報を送ってください")


    return "OK", 200


# =========================
# KML読み込み＆解析
# =========================
def load_kml():

    with open(KML_FILE, "r", encoding="utf-8") as f:
        kml_data = f.read()

    placemarks = re.findall(
        r"<Placemark>.*?</Placemark>",
        kml_data,
        re.DOTALL
    )

    pins = []

    for pm in placemarks:

        name_match = re.search(r"<name>(.*?)</name>", pm, re.DOTALL)
        name = name_match.group(1).strip() if name_match else "名称未設定"
        name = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", name)

        desc_match = re.search(r"<description>(.*?)</description>", pm, re.DOTALL)
        desc = desc_match.group(1).strip() if desc_match else ""
        desc = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", desc)

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
# 距離計算メイン
# =========================
def calculate_closest_places(user_coords):

    pins = load_kml()

    results = []

    for pin in pins:

        distance = geodesic(user_coords, pin["coords"]).km

        desc = pin["description"]

        # 電話番号抽出
        tel_match = re.search(r"0\d{1,4}-\d{1,4}-\d{4}", desc)
        tel = tel_match.group(0) if tel_match else "なし"

        # 住所整理
        address = re.sub(r"<[^>]*>", "", desc).strip()
        address = address.replace(tel, "").strip()

        if not address:
            address = "住所不明"

        results.append({
            "name": pin["name"],
            "distance": distance,
            "address": address,
            "tel": tel
        })

    results.sort(key=lambda x: x["distance"])
    top5 = results[:5]

    text = "📍 近くの健診場所 Top 5\n\n"

    for i, r in enumerate(top5, 1):
        text += (
            f"{i}位: {r['name']}\n"
            f"📏 約{r['distance']:.2f}km\n"
            f"🏠 {r['address']}\n"
            f"📞 {r['tel']}\n"
            "------------------\n"
        )

    return text


# =========================
# LINE返信
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
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
