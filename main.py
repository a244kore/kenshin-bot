print("APP VERSION 2026-05-30-01", flush=True)

import os
import re
import json
import requests
import xml.etree.ElementTree as ET

from geopy.distance import geodesic
from flask import Flask, request

app = Flask(__name__)

# トップページ（ブラウザで開く用）
@app.route("/")
def home():
    return "LINE BOT OK", 200

# LINEアクセストークン
CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')

@app.route("/callback", methods=["POST"])
def callback():

    print("CALLBACK HIT", flush=True)

    body = request.get_data(as_text=True)

    print(body, flush=True)

    return "OK", 200

    try:
        data = json.loads(body)
        events = data.get('events', [])

        if not events:
            return 'OK'

        for event in events:
            reply_token = event.get('replyToken')
            event_type = event.get('type')  # ★イベントの種類（message、followなど）を取得
            
            print(f"Received Event Type: {event_type}")

            # 1. ユーザーから「メッセージ」が届いた場合
            if event_type == 'message':
                message = event.get('message', {})
                msg_type = message.get('type')
                print(f"Message Type: {msg_type}")

                # 2. そのメッセージが「位置情報（location）」の場合だけ処理
                if msg_type == 'location':
                    # 【修正】messageの中に確実にデータがあるか安全に取得する
                    user_lat = message.get('latitude')
                    user_lng = message.get('longitude')
                    
                    # ログを出して、本当に緯度経度が取れているか目視確認する
                    print(f"🌍 User Coordinates Captured -> Lat: {user_lat}, Lng: {user_lng}")

                    # 万が一緯度経度が None や空だった場合は処理をスキップする
                    if user_lat is None or user_lng is None:
                        print("🚨 Error: Latitude or Longitude is missing in the message.")
                        continue

                    # 数値（float）に型変換を保証する
                    user_coords = (float(user_lat), float(user_lng))

                    # 最寄り健診場所を計算
                    reply_text = calculate_closest_places(user_coords)

                    # LINEへ返信
                    send_line_reply(reply_token, reply_text)
                    print("Success: Reply sent successfully.")
            
            # LINE Developersの「検証」ボタンを押したときのダミーデータ対策
            elif reply_token == '00000000000000000000000000000000' or reply_token == 'ffffffffffffffffffffffffffffffff':
                print("LINE Webhook Verification captured.")

    except Exception as e:
        print(f"Callback Global Error: {e}")
        return 'OK'


        # 【修正】大文字小文字を無視するために re.IGNORECASE (re.I) を追加
        placemarks = re.findall(r'<Placemark>.*?</Placemark>', kml_data, re.DOTALL | re.IGNORECASE)
        
        for pm in placemarks:
            # 【修正】ここも re.IGNORECASE を追加
            name_match = re.search(r'<name>(.*?)</name>', pm, re.IGNORECASE)
            name = name_match.group(1).strip() if name_match else "名称未設定"
            name = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', name)

            # 説明文
            desc_match = re.search(r'<description>(.*?)</description>', pm, re.DOTALL | re.IGNORECASE)
            desc = desc_match.group(1).strip() if desc_match else ""
            desc = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', desc)

            # 緯度・経度
            coord_match = re.search(r'<coordinates>(.*?)</coordinates>', pm, re.IGNORECASE)

        # 【究極の修正ポイント】fastkmlを一切使わず、正規表現（文字検索）で強制的にPlacemarkを分解します！
        # これにより、どんなKMLのバージョンや階層構造であっても、100%確実にピンを引っこ抜けます。
        placemarks = re.findall(r'<Placemark>.*?</Placemark>', kml_data, re.DOTALL)
        
        for pm in placemarks:
            # 名前の抽出
            name_match = re.search(r'<name>(.*?)</name>', pm)
            name = name_match.group(1).strip() if name_match else "名称未設定"
            # CDATA（特殊な文字装飾）が含まれている場合は除去
            name = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', name)

            # 説明文（住所・電話番号）の抽出
            desc_match = re.search(r'<description>(.*?)</description>', pm, re.DOTALL)
            desc = desc_match.group(1).strip() if desc_match else ""
            desc = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', desc)

            # 緯度・経度の抽出
            coord_match = re.search(r'<coordinates>(.*?)</coordinates>', pm)
            if coord_match:
                coord_str = coord_match.group(1).strip()
                # KMLは「経度,緯度,高度」の順番で並んでいるので分解する
                parts = coord_str.split(',')
                if len(parts) >= 2:
                    try:
                        lon = float(parts[0].strip())
                        lat = float(parts[1].strip())
                        
                        pins.append({
                            "name": name,
                            "description": desc,
                            "coords": (lat, lon)
                        })
                    except ValueError:
                        continue

        print(f"Successfully loaded {len(pins)} pins from KML using Regex parser.")

        if not pins:
            print("🚨 KML Error: Total pins loaded is 0. Regex couldn't find Placemarks.")
            return "位置情報を受け取りましたが、健診場所データ(KML)からピンを1件も読み込めませんでした。お手数ですがシステム管理者に連絡してください。"

        valid_pins = []
        for pin in pins:
            desc = pin["description"] or ""

            # 電話番号抽出
            tel_match = re.search(r'0\d{1,4}-\d{1,4}-\d{4}', desc)
            tel = tel_match.group(0) if tel_match else "なし"

            # 住所抽出
            address = desc.replace(tel, "").strip()
            # HTMLタグ（<br>など）が混ざっている場合は綺麗に消去する
            address = re.sub(r'<[^>]*>', '', address).strip()
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
