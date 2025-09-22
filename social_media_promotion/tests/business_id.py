import requests
import json

# ===============================
# CONFIG
# ===============================
# Use the same BOT_TOKEN from your main script
BOT_TOKEN = ""
URL = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"

# ===============================
# SCRIPT
# ===============================
def get_business_connection_id():
    """Fetches updates from Telegram and looks for the business_connection event."""
    print("Fetching updates from Telegram...")
    print("Make sure you have recently connected your business account to this bot.")
    
    try:
        # We add a timeout to avoid waiting forever
        response = requests.get(URL, params={'timeout': 100})
        response.raise_for_status()  # Will raise an exception for HTTP errors
        
        updates = response.json()
        
        if not updates.get('ok'):
            print(f"Error from Telegram API: {updates.get('description')}")
            return None

        if not updates['result']:
            print("\nNo new updates found.")
            print("Try this: In your Telegram app, go to Settings > Business > Telegram Bot, disconnect the bot, and then connect it again. Then run this script immediately.")
            return None

        found_id = None
        for update in updates['result']:
            if 'business_connection' in update:
                connection_info = update['business_connection']
                business_id = connection_info['id']
                user_name = connection_info['user'].get('first_name', '')
                
                print("\n" + "="*40)
                print("✅ SUCCESS: Found a business connection update!")
                print(f"Connected User: {user_name}")
                print(f"Business Connection ID: {business_id}")
                print("="*40 + "\n")
                
                print("COPY THIS ID and use it in your main script.")
                found_id = business_id

        if not found_id:
            print("\nCould not find a 'business_connection' update.")
            print("Please ensure the bot was connected recently and try again.")
            print("Raw updates received:")
            print(json.dumps(updates, indent=2))
            
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    get_business_connection_id()
