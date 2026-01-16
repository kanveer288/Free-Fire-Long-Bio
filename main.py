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

key = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
iv = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])

_sym_db = symbol_database.Default()
descriptor = descriptor_pool.Default().AddSerializedFile(
    b'\n\ndata.proto\"\xbb\x01\n\x04\x44\x61ta\x12\x0f\n\x07\x66ield_2\x18\x02 \x01(\x05'
    b'\x12\x1e\n\x07\x66ield_5\x18\x05 \x01(\x0b\x32\r.EmptyMessage\x12\x1e\n\x07\x66ield_6'
    b'\x18\x06 \x01(\x0b\x32\r.EmptyMessage\x12\x0f\n\x07\x66ield_8\x18\x08 \x01(\t\x12\x0f\n'
    b'\x07\x66ield_9\x18\t \x01(\x05\x12\x1f\n\x08\x66ield_11\x18\x0b \x01(\x0b\x32\r.'
    b'EmptyMessage\x12\x1f\n\x08\x66ield_12\x18\x0c \x01(\x0b\x32\r.EmptyMessage\"\x0e\n'
    b'\x0c\x45mptyMessageb\x06proto3'
)

globals_ = globals()
builder.BuildMessageAndEnumDescriptors(descriptor, globals_)
builder.BuildTopDescriptorsAndMessages(descriptor, 'data1_pb2', globals_)
Data = _sym_db.GetSymbol('Data')
EmptyMessage = _sym_db.GetSymbol('EmptyMessage')


def get_region_url(region):
    region = (region or "ind").lower()
    return {
        "ind": "https://client.ind.freefiremobile.com",
        "br": "https://client.us.freefiremobile.com",
        "us": "https://client.us.freefiremobile.com",
        "na": "https://client.us.freefiremobile.com",
        "sac": "https://client.us.freefiremobile.com"
    }.get(region, "https://clientbp.ggblueshark.com")


def contains_invalid_chars(text):
    try:
        return any(char in emoji.EMOJI_DATA for char in text)
    except Exception:
        emoji_pattern = re.compile(
            "[\U0001F600-\U0001F64F"
            "\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF"
            "]+",
            flags=re.UNICODE,
        )
        return bool(emoji_pattern.search(text))


@app.route('/update_bio', methods=['GET'])
def update_bio():
    access_token = request.args.get("access_token")
    bio = request.args.get("bio")

    if not access_token or not bio:
        return jsonify({"error": "Missing 'access_token' or 'bio' parameter."}), 400

    if contains_invalid_chars(bio):
        return jsonify({
            "status": "failed",
            "message": "Bio contains unsupported emojis."
        }), 400

    try:
        jwt_api_url = f"https://access.thug4ff.com/token?access={access_token}"
        logging.info(f"Requesting JWT: {jwt_api_url}")

        jwt_response = requests.get(jwt_api_url, timeout=10)

        if jwt_response.status_code != 200:
            return jsonify({
                "status": "error",
                "message": "Failed to retrieve JWT/token",
                "code": jwt_response.status_code,
                "body": jwt_response.text
            }), 502

        jwt_data = jwt_response.json()

        jwt_token = (
            jwt_data.get("token") or
            jwt_data.get("jwt") or
            jwt_data.get("access_token")
        )

        region = (jwt_data.get("region") or "ind").lower()

        if not jwt_token:
            return jsonify({"error": "JWT missing", "response": jwt_data}), 500

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "JWT fetch failed",
            "details": str(e)
        }), 500

    try:
        data = Data()
        data.field_2 = 17
        data.field_5.CopyFrom(EmptyMessage())
        data.field_6.CopyFrom(EmptyMessage())
        data.field_8 = bio
        data.field_9 = 1
        data.field_11.CopyFrom(EmptyMessage())
        data.field_12.CopyFrom(EmptyMessage())

        serialized = data.SerializeToString()
        padded = pad(serialized, AES.block_size)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        encrypted = cipher.encrypt(padded)

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "Encryption failed",
            "details": str(e),
            "trace": traceback.format_exc()
        }), 500

    try:
        post_url = f"{get_region_url(region)}/UpdateSocialBasicInfo"
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "X-Unity-Version": "2018.4.11f1",
            "X-GA": "v1 1",
            "ReleaseVersion": "OB52",
            "Content-Type": "application/octet-stream",
            "User-Agent": "Dalvik/2.1.0",
            "Connection": "Keep-Alive"
        }

        response = requests.post(post_url, headers=headers, data=encrypted, timeout=12)

        server_text = response.content.decode("utf-8", errors="replace")

        if response.status_code == 200:
            return jsonify({
                "status": "success",
                "region": region,
                "bio": bio,
                "uid": jwt_data.get("account_id"),
                "nickname": jwt_data.get("nickname"),
                "platform": jwt_data.get("platform"),
              #  "open_id": jwt_data.get("open_id"),
                "server_response": server_text
            })
        else:
            return jsonify({
                "status": "failed",
                "http_status": response.status_code,
                "server_response": server_text
            }), 400

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "Bio update failed",
            "details": str(e),
            "trace": traceback.format_exc()
        }), 500


if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5000)
