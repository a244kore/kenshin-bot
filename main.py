import os
import re
import json
import requests

from geopy.distance import geodesic
from fastkml import kml
from shapely.geometry import Point
from flask import Flask, request

app = Flask(__name__)

# LINEアクセストークン
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

            # 位置情報メッセージだけ処理
            if msg_type == 'location':
                user_lat = message.get('latitude')
                user_lng = message.get('longitude')
                user_coords = (user_lat, user_lng)

                # 最寄り健診場所を計算
                reply_text = calculate_closest_places(user_coords)

                # LINEへ返信
                send_line_reply(reply_token, reply_text)
                print("Success: Reply sent successfully.")

        return 'OK'

    except Exception as e:
        print(f"Callback Global Error: {e}")
        return 'OK'


def extract_pins_from_features(features_source, pins_list):
    """KMLの全特徴を探索し、位置情報(数字)が入っているピンを1件残らず強制回収する関数"""
    if not features_source:
        return

    try:
        current_features = list(features_source() if callable(features_source) else features_source)
    except Exception:
        return

    for feature in current_features:
        # 子フォルダや子レイヤーがあれば、さらに深く潜る
        if hasattr(feature, 'features') and feature.features:
            extract_pins_from_features(feature.features, pins_list)
        
        # 【超強化ポイント】Point判定が厳密すぎて弾かれるのを防ぐため、
        # 緯度・経度の数字（x, y または coordinates）が裏側に存在すれば、無条件でピンとして強制回収します！
        if hasattr(feature, 'geometry') and feature.geometry:
            g = feature.geometry
            lon, lat = None, None
            
            # 書き方の違い（Pointオブジェクト、または直接座標を持っている場合など）をすべてカバー
            if isinstance(g, Point):
                lon, lat = g.x, g.y
            elif hasattr(g, 'x') and hasattr(g, 'y'):
                lon, lat = g.x, g.y
            elif hasattr(g, 'coordinates') and g.coordinates:
                # 座標リストが入っている場合
                coords = list(g.coordinates)
                if coords:
                    lon, lat = coords[0][0], coords[0][1]

            if lat is not None and lon is not None:
                pins_list.append({
                    "name": getattr(feature, 'name', '名称未設定'),
                    "description": getattr(feature, 'description', ''),
                    "coords": (lat, lon)
                })


def calculate_closest_places(user_coords):
    try:
        # KMLファイル読み込み
        kml_path = os.path.join(os.path.dirname(__file__), 'mymap.kml')

        with open(kml_path, 'rt', encoding='utf-8') as f:
            kml_data = f.read()

        kml_obj = kml.KML()

        # fastkmlバージョン差異対応
        try:
            kml_obj.from_string(kml_data.encode('utf-8'))
        except Exception:
            kml_obj.from_string(kml_data.strip())

        pins = []
        
        # どんなに深いフォルダ構造でも、1つ残らずピンを回収
        if hasattr(kml_obj, 'features') and kml_obj.features:
            extract_pins_from_features(kml_obj.features, pins)

        print(f"Successfully loaded {len(pins)} pins from KML.")

        if not pins:
            print("🚨 KML Error: Total pins loaded is 0.")
            return "位置情報を受け取りましたが、健診場所データ(KML)からピン（場所情報）を1件も読み込めませんでした。マイマップの保存形式を確認してください。"

        valid_pins = []
        for pin in pins:
            desc = pin["description"] or ""

            # 電話番号抽出
            tel_match = re.search(r'0\d{1,4}-\d{1,4}-\d{4}', desc)
            tel = tel_match.group(0) if tel_match else "なし"

            # 住所抽出
            address = desc.replace(tel, "").strip()
            if not address:
                address = "住所情報なし"

            # 距離計算
            distance = geodesic(user_coords, pin["coords"]).km

            valid_pins.append({
                "name": pin["name"],
                "address": address,
                "tel": tel,
                "distance": distance
            })

        # 近い順Top5
        closest_pins = sorted(valid_pins, key=lambda x: x["distance"])[:5]

        # 返信文作成
        reply_text = "📍 近くの健診場所 Top 5\n"
        reply_text += "ーーーーーーーーーーー\n"

        for i, pin in enumerate(closest_pins, 1):
            reply_text += f"{i}位: {pin['name']}\n"
            reply_text += f"📏 距離: 約{pin['distance']:.2f}km\n"
            reply_text += f"🏠 住所: {pin['address']}\n"
            reply_text += f"📞 TEL: {pin['tel']}\n"
            reply_text += "ーーーーーーーーーーー\n"

        reply_text += "※TELをタップすると電話できます。"
        return reply_text

    except Exception as e:
        print(f"KML Calculation Error: {e}")
        return f"計算中にエラーが発生しました。\n{str(e)}"


def send_line_reply(reply_token, reply_text):
    # 【固定】詳しい人のアドバイス通りのAPI正式URLです
    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}"
    }

    reply_text = reply_text[:4500]
    payload = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": reply_text}]
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        print(f"LINE Reply HTTP Status: {res.status_code}")
        print(f"LINE Reply Response: {res.text}")
    except Exception as e:
        print(f"LINE Reply Error: {e}")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
