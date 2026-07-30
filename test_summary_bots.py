import requests

tokens = {
    "summary1": "8784019564:AAF1XBrGTb5QU_wmOcvYQQ49Vb7dpLWZnm4",
    "summary2": "8718236248:AAGIlK8xTWUvRB_WcYOGN2Qx1kEKZwRqihQ",
    "summary3": "8696806326:AAEDKqSNoHAaMEHD8oqjaLm4oSci_3KOUWA",
    # wait, summary4 has the same token as summary1 in my code??
    # Let me check if there's a 4th token in the env or if I used the wrong one.
}

for name, token in tokens.items():
    print(f"--- {name} ---")
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    try:
        resp = requests.get(url, timeout=5).json()
        if not resp.get('ok'):
            print("API Error:", resp)
            continue
        updates = resp.get('result', [])
        print(f"Got {len(updates)} updates.")
        found_id = None
        for res in reversed(updates):
            if 'message' in res:
                chat = res['message']['chat']
                print(f"  Found chat: {chat.get('title', 'Private')} (ID: {chat['id']}, Type: {chat['type']})")
                found_id = chat['id']
                break
            elif 'my_chat_member' in res:
                chat = res['my_chat_member']['chat']
                print(f"  Found chat member update: {chat.get('title', 'Group')} (ID: {chat['id']}, Type: {chat['type']})")
                found_id = chat['id']
                break
        if found_id:
            print(f"Best Chat ID for {name} -> {found_id}")
    except Exception as e:
        print("Error:", e)
    print()
