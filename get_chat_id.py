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
            message_thread_id = None
            if "message" in upd:
                msg = upd["message"]
                chat = msg.get("chat")
                # 포럼(주제) 사용 그룹: 특정 주제로 보내려면 message_thread_id 사용
                message_thread_id = msg.get("message_thread_id")
            elif "my_chat_member" in upd:
                chat = upd["my_chat_member"].get("chat")
            
            if chat and chat.get("type") in ["group", "supergroup"]:
                cid = chat.get("id")
                key = (cid, message_thread_id or 0)
                if key not in seen:
                    seen.add(key)
                    groups.append({
                        "id": cid,
                        "title": chat.get("title", "?"),
                        "type": chat.get("type"),
                        "message_thread_id": message_thread_id,
                    })
        
        return groups
    except Exception as e:
        print(f"[{label}] 오류: {e}")
        return []

if __name__ == "__main__":
    print("=" * 50)
    print("텔레그램 그룹 Chat ID 조회")
    print("=" * 50)
    print("(그룹에서 봇에게 /start 보낸 후 실행하세요)")
    print("특정 주제(Topic) ID가 필요하면: 해당 주제 안에서 봇에게 메시지를 보낸 뒤 실행하세요.\n")
    
    token1 = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    token2 = os.getenv("TELEGRAM_BOT_TOKEN_2", "").strip()
    
    all_groups = {}
    
    token_alt = os.getenv("TELEGRAM_BOT_TOKEN_ALT_LONG", "").strip()
    
    def print_group(g, label, topic_env: str = "TELEGRAM_ALT_SHORT_TOPIC_ID"):
        print(f"[{label}] {g['title']}")
        print(f"      Chat ID: {g['id']}")
        if g.get("message_thread_id") is not None:
            print(f"      주제(Topic) ID: {g['message_thread_id']}  ← {topic_env} 로 설정")
        print()
    
    if token1:
        g1 = get_group_ids(token1, "봇1")
        for g in g1:
            all_groups[(g["id"], g.get("message_thread_id"))] = g
            print_group(g, "봇1")
    
    if token2:
        g2 = get_group_ids(token2, "봇2")
        for g in g2:
            key = (g["id"], g.get("message_thread_id"))
            if key not in all_groups:
                all_groups[key] = g
                print_group(g, "봇2")
    
    if token_alt:
        g_alt = get_group_ids(token_alt, "alt-long 봇 (단기 롱 알림)")
        for g in g_alt:
            key = (g["id"], g.get("message_thread_id"))
            if key not in all_groups:
                all_groups[key] = g
            print_group(g, "alt-long 봇 (단기 롱 알림)", topic_env="TELEGRAM_ALT_LONG_TOPIC_ID")
    
    if all_groups:
        print("=" * 50)
        print("발견된 그룹/주제 목록:")
        for key, g in all_groups.items():
            tid = g.get("message_thread_id")
            s = f"  {g['title']}: Chat ID={g['id']}"
            if tid is not None:
                s += f", Topic ID={tid}"
            print(s)
        first = list(all_groups.values())[0]
        print("\n.env에 설정할 값 (예시):")
        print(f"TELEGRAM_CHAT_ID={first['id']}")
        if first.get("message_thread_id") is not None:
            print(f"TELEGRAM_ALT_SHORT_TOPIC_ID={first['message_thread_id']}")
    else:
        print("그룹을 찾을 수 없습니다.")
        print("1. 그룹에 봇을 추가했는지 확인")
        print("2. 그룹에서 봇에게 /start 또는 @봇이름 전송")
        print("3. 다시 이 스크립트 실행")
        print("4. 특정 주제로 보내려면: 그룹에서 주제(토픽)를 켠 뒤, 해당 주제 안에서 메시지를 보내고 다시 실행")
