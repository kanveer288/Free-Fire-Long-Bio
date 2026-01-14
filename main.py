from flask import Flask, request, jsonify
import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from google.protobuf import descriptor_pool, symbol_database
from google.protobuf.internal import builder
import traceback
import emoji
import re
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# ---------------- AES CONFIG ----------------
KEY = bytes([89,103,38,116,99,37,68,69,117,104,54,37,90,99,94,56])
IV  = bytes([54,111,121,90,68,114,50,50,69,51,121,99,104,106,77,37])

# ---------------- PROTOBUF SETUP ----------------
_sym_db = symbol_database.Default()
descriptor = descriptor_pool.Default().AddSerializedFile(
    b'\n\ndata.proto"\xbb\x01\n\x04Data\x12\x0f\n\x07field_2\x18\x02 \x01(\x05'
    b'\x12\x1e\n\x07field_5\x18\x05 \x01(\x0b\x32\r.EmptyMessage'
    b'\x12\x1e\n\x07field_6\x18\x06 \x01(\x0b\x32\r.EmptyMessage'
    b'\x12\x0f\n\x07field_8\x18\x08 \x01(\t'
    b'\x12\x0f\n\x07field_9\x18\t \x01(\x05'
    b'\x12\x1f\n\x08field_11\x18\x0b \x01(\x0b\x32\r.EmptyMessage'
    b'\x12\x1f\n\x08field_12\x18\x0c \x01(\x0b\x32\r.EmptyMessage'
    b'"\x0e\n\x0cEmptyMessageb\x06proto3'
)

globals_ = globals()
builder.BuildMessageAndEnumDescriptors(descriptor, globals_)
builder.BuildTopDescriptorsAndMessages(descriptor, 'data_pb2', globals_)
Data = _sym_db.GetSymbol('Data')
EmptyMessage = _sym_db.GetSymbol('EmptyMessage')

# ---------------- UTILS ----------------
def get_region_url(region):
    return {
        "ind": "https://client.ind.freefiremobile.com",
        "br":  "https://client.us.freefiremobile.com",
        "us":  "https://client.us.freefiremobile.com",
        "na":  "https://client.us.freefiremobile.com",
        "sac": "https://client.us.freefiremobile.com"
    }.get(region.lower(), "https://clientbp.ggblueshark.com")

def contains_invalid_chars(text):
    try:
        return any(c in emoji.EMOJI_DATA for c in text)
    except:
        return bool(re.search(
            "[\U0001F600-\U0001F64F"
            "\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF]+", text))

# ---------------- MAIN API ----------------
@app.route("/update_bio", methods=["GET"])
def update_bio():
    access_token = request.args.get("access_token")
    bio = request.args.get("bio")
    use_sample = request.args.get("use_sample", "0") in ("1", "true")

    if not access_token or not bio:
        return jsonify({"error": "Missing access_token or bio"}), 400

    if contains_invalid_chars(bio):
        return jsonify({"status": "failed", "message": "Emoji not allowed in bio"}), 400

    # ---------- FETCH JWT ----------
    try:
        if use_sample:
            jwt_data = SAMPLE_JWT_RESPONSE.copy()
        else:
            url = f"https://access.thug4ff.com/token?access={access_token}"
            r = requests.get(url, timeout=10)

            if r.status_code != 200:
                return jsonify({
                    "status": "error",
                    "message": "JWT helper API failed",
                    "http_status": r.status_code
                }), 502

            jwt_data = r.json()

        jwt_token = jwt_data.get("token") or jwt_data.get("access_token")
        region = (jwt_data.get("region") or "ind").lower()

        if not jwt_token:
            return jsonify({"error": "JWT token missing"}), 500

    except Exception as e:
        return jsonify({"error": "JWT fetch failed", "details": str(e)}), 500

    # ---------- BUILD + ENCRYPT ----------
    try:
        d = Data()
        d.field_2 = 17
        d.field_5.CopyFrom(EmptyMessage())
        d.field_6.CopyFrom(EmptyMessage())
        d.field_8 = bio
        d.field_9 = 1
        d.field_11.CopyFrom(EmptyMessage())
        d.field_12.CopyFrom(EmptyMessage())

        encrypted = AES.new(KEY, AES.MODE_CBC, IV).encrypt(
            pad(d.SerializeToString(), AES.block_size)
        )

    except Exception as e:
        return jsonify({"error": "Encryption failed", "details": str(e)}), 500

    # ---------- SEND TO FREE FIRE ----------
    try:
        post_url = f"{get_region_url(region)}/UpdateSocialBasicInfo"
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/octet-stream",
            "User-Agent": "Dalvik/2.1.0",
            "X-Unity-Version": "2018.4.11f1",
            "ReleaseVersion": "OB51"
        }

        resp = requests.post(post_url, headers=headers, data=encrypted, timeout=12)
        text = resp.content.decode("utf-8", errors="replace")

        if resp.status_code == 200:
            return jsonify({
                "status": "success",
                "uid": jwt_data.get("account_id"),
                "nickname": jwt_data.get("nickname"),
                "platform": jwt_data.get("platform"),
                "platformID": jwt_data.get("platformID"),
                "region": region,
                "bio": bio,
                "expiry": jwt_data.get("expiryToken"),
                "server_response": text
            })

        return jsonify({
            "status": "failed",
            "http_status": resp.status_code,
            "server_response": text
        }), 400

    except Exception as e:
        return jsonify({
            "error": "Final request failed",
            "details": str(e),
            "trace": traceback.format_exc()
        }), 500


# ---------------- RUN SERVER ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

