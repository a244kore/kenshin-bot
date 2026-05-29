import os
import re
import json
from geopy.distance import geodesic
from fastkml import kml
from shapely.geometry import Point
from flask import Flask, request, jsonify

app = Flask(__name__)

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
            message = event.get('message', {})
            msg_type = message.get('type')
            
            print(f"Message Type: {msg_type}")
            
            # 位置情報メッセージだけを処理
            if msg_type == 'location':
                user_lat = message.get('latitude')
                user_lng = message.get('longitude')
                user_coords = (user_lat, user_lng)
                
                # 近い健診場所を計算
                reply_text = calculate_closest_places(user_coords)
                
                # 【最新のLINEルール】Webhookの返答としてその場で送り返す
                response_data = {
                    "replies": [
                        {
                            "type": "text",
                            "text": reply_text
                        }
                    ]
                }
                print("Success: Returning latest Webhook reply response with TEL links.")
                return jsonify(response_data)
                
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
        
        # fastkmlのバージョン差異を完全に吸収する安全な読み込み
        try:
            kml_obj.from_string(kml_data.encode('utf-8'))
        except Exception:
            kml_obj.from_string(kml_data.strip())
            
        pins = []
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
            tel = tel_match.group(0) if tel_match else "なし"
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
            # 【タップ発信対応】「TEL:」表記に変更してスマホの自動リンク機能を確実に発動させます
            reply_text += f"📞 TEL: {pin['tel']}\n"
            reply_text += "ーーーーーーーーーーー\n"
        reply_text += "※電話番号（TEL）をタップすると、そのまま直接電話をかけることができます。"
        return reply_text
        
    except Exception as e:
        print(f"KML Calculation Error: {e}")
        return f"計算中にエラーが発生しました。\n{str(e)}"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
