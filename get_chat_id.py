"""
텔레그램 그룹 Chat ID 조회
- 그룹에서 봇에게 /start 또는 @봇이름 메시지 보낸 후 실행
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

def get_group_ids(bot_token: str, label: str):
    """봇의 getUpdates에서 그룹 Chat ID 추출"""
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        if not data.get("ok"):
            print(f"[{label}] API 오류: {data}")
            return []
        
        results = data.get("result", [])
        groups = []
        seen = set()
        
        for upd in results:
            chat = None
            if "message" in upd:
                chat = upd["message"].get("chat")
            elif "my_chat_member" in upd:
                chat = upd["my_chat_member"].get("chat")
            
            if chat and chat.get("type") in ["group", "supergroup"]:
                cid = chat.get("id")
                if cid not in seen:
                    seen.add(cid)
                    groups.append({
                        "id": cid,
                        "title": chat.get("title", "?"),
                        "type": chat.get("type")
                    })
        
        return groups
    except Exception as e:
        print(f"[{label}] 오류: {e}")
        return []

if __name__ == "__main__":
    print("=" * 50)
    print("텔레그램 그룹 Chat ID 조회")
    print("=" * 50)
    print("(그룹에서 봇에게 /start 보낸 후 실행하세요)\n")
    
    token1 = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    token2 = os.getenv("TELEGRAM_BOT_TOKEN_2", "").strip()
    
    all_groups = {}
    
    if token1:
        g1 = get_group_ids(token1, "봇1")
        for g in g1:
            all_groups[g["id"]] = g
            print(f"[봇1] {g['title']}")
            print(f"      Chat ID: {g['id']}")
            print()
    
    if token2:
        g2 = get_group_ids(token2, "봇2")
        for g in g2:
            if g["id"] not in all_groups:
                all_groups[g["id"]] = g
                print(f"[봇2] {g['title']}")
                print(f"      Chat ID: {g['id']}")
                print()
    
    if all_groups:
        print("=" * 50)
        print("발견된 그룹 목록:")
        for cid, g in all_groups.items():
            print(f"  {g['title']}: {cid}")
        print("\n.env에 설정할 값:")
        print(f"TELEGRAM_CHAT_ID={list(all_groups.values())[0]['id']}")
    else:
        print("그룹을 찾을 수 없습니다.")
        print("1. 그룹에 봇을 추가했는지 확인")
        print("2. 그룹에서 봇에게 /start 또는 @봇이름 전송")
        print("3. 다시 이 스크립트 실행")
