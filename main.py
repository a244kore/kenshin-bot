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
    print(f"Received LINE Data: {body}")
    
    try:
        data = json.loads(body)
        events = data.get('events', [])
        
        if not events:
            return 'OK'
            
        for event in events:
            reply_token = event.get('replyToken')
            message = event.get('message', {})
            msg_type = message.get('type')
            
            print(f"Message Type: {msg_type}")
            
            if msg_type == 'location':
                user_lat = message.get('latitude')
                user_lng = message.get('longitude')
                user_coords = (user_lat, user_lng)
                
                # 計算処理を呼び出す
                reply_text = calculate_closest_places(user_coords)
                
                # LINEへ確実に返信する
                send_line_reply(reply_token, reply_text)
                print("Success: Reply execution finished.")
                
        return 'OK'
    except Exception as e:
        print(f"Callback Global Error: {e}")
        return 'OK'

def calculate_closest_places(user_coords):
    try:
        kml_path = os.path.join(os.path.dirname(__file__), 'mymap.kml')
        with open(kml_path, 'rt', encoding='utf-8') as f:
            kml_data = f.read()
            
        kml_obj = kml.KML()
        
        # 【最新のfastkml対応】バージョン差異による読み込みエラーを完全に回避する書き方
        try:
            # 最新のfastkml（v1.0以降）の読み込み方
            kml_obj.from_string(kml_data.encode('utf-8'))
        except Exception:
            # 古いfastkmlの読み込み方（予備ルート）
            kml_obj.from_string(kml_data.strip())
            
        pins = []
        
        # KMLの全特徴（ピン）を安全に一括で引っこ抜くループ構造
        features = list(kml_obj.features())
        while features:
            feature = features.pop(0)
            if hasattr(feature, 'features'):
                features.extend(list(feature.features()))
            if hasattr(feature, 'geometry') and feature.geometry and isinstance(feature.geometry, Point):
                pins.append({
                    "name": getattr(feature, 'name', '名称未設定'),
                    "description": getattr(feature, 'description', ''),
                    "coords": (feature.geometry.y, feature.geometry.x)
                })

        print(f"Successfully loaded {len(pins)} pins from KML.")
        
        if not pins:
            return "位置情報を受け取りましたが、健診場所データ(KML)が空っぽか、読み込めませんでした。"

        valid_pins = []
        for pin in pins:
            desc = pin["description"] if pin["description"] else ""
            tel_match = re.search(r'0\d{1,4}-\d{1,4}-\d{4}', desc)
            tel = tel_match.group(0) if tel_match else "電話番号なし"
            address = desc.replace(tel, "").strip() if desc else "住所情報なし"
            
            distance = geodesic(user_coords, pin["coords"]).km
            valid_pins.append({
                "name": pin["name"],
                "address": address,
                "tel": tel,
                "distance": distance
            })
            
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
        print(f"KML Calculation Error: {e}")
        return f"計算中にエラーが発生しました。\n{str(e)}"

def send_line_reply(reply_token, reply_text):
    # 【Reply API URLも完璧に最新・最速のものに固定】
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
    print(f"LINE Reply HTTP Status: {res.status_code} - Response: {res.text}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
