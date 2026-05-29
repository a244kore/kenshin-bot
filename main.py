import os
import re
import json
from geopy.distance import geodesic
from fastkml import kml
from shapely.geometry import Point
from flask import Flask, request, abort
import requests

app = Flask(__name__)

CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')

@app.route("/callback", methods=['POST'])
def callback():
    body = request.get_data(as_text=True)
    try:
        data = json.loads(body)
        events = data.get('events', [])
        for event in events:
            reply_token = event.get('replyToken')
            message = event.get('message', {})
            
            # 位置情報メッセージだけを処理
            if message.get('type') == 'location':
                user_lat = message.get('latitude')
                user_lng = message.get('longitude')
                user_coords = (user_lat, user_lng)
                
                # 近い場所を計算して返信する
                reply_text = calculate_closest_places(user_coords)
                send_line_reply(reply_token, reply_text)
                
        return 'OK'
    except Exception as e:
        print(f"Callback Error: {e}")
        return 'OK'

def calculate_closest_places(user_coords):
    try:
        kml_path = os.path.join(os.path.dirname(__file__), 'mymap.kml')
        with open(kml_path, 'rt', encoding='utf-8') as f:
            kml_data = f.read()
            
        kml_obj = kml.KML()
        kml_obj.from_string(kml_data.strip())
        
        pins = []
        for f0 in kml_obj.features():
            if hasattr(f0, "features"):
                for f1 in f0.features():
                    if hasattr(f1, "features"):
                        for f2 in f1.features():
                            if f2.geometry and isinstance(f2.geometry, Point):
                                pins.append(parse_placemark(f2))
                    elif f1.geometry and isinstance(f1.geometry, Point):
                        pins.append(parse_placemark(f1))
                        
        valid_pins = [p for p in pins if p is not None]
        
        for pin in valid_pins:
            pin["distance"] = geodesic(user_coords, pin["coords"]).km
            
        closest_pins = sorted(valid_pins, key=lambda x: x["distance"])[:5]
        
        reply_text = "📍 近くの健診場所 Top 5\n"
        reply_text += "ーーーーーーーーーーー\n"
        for i, pin in enumerate(closest_pins, 1):
            reply_text += f"{i}位: {pin['name']}\n"
            reply_text += f"📏 距離: 約{pin['distance']:.2f}km\n"
            reply_text += f"🏠 住所: {pin['address']}\n"
            reply_text += f"📞 電話: {pin['tel']}\n"
            reply_text += "ーーーーーーーーーーー\n"
        reply_text += "※電話番号をタップすると直接発信できます。"
        return reply_text
    except Exception as e:
        return f"データの読み込み中にエラーが発生しました。\n{str(e)}"

def parse_placemark(placemark):
    desc = placemark.description if placemark.description else ""
    tel_match = re.search(r'0\d{1,4}-\d{1,4}-\d{4}', desc)
    tel = tel_match.group(0) if tel_match else "電話番号なし"
    address = desc.replace(tel, "").strip() if desc else "住所情報なし"
    
    return {
        "name": placemark.name,
        "address": address,
        "tel": tel,
        "coords": (placemark.geometry.y, placemark.geometry.x)
    }

def send_line_reply(reply_token, reply_text):
    url = "https://line.me"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}"
    }
    payload = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": reply_text}]
    }
    res = requests.post(url, headers=headers, json=payload)
    print(f"LINE Reply Response: {res.status_code} - {res.text}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
