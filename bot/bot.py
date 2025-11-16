"""Automated Bot with OpenKitx403 Authentication"""
import json
import time
import os
from pathlib import Path
from dotenv import load_dotenv
from solders.keypair import Keypair
from openkitx403_client import OpenKit403Client
from database import TokenHolderDB
from git_publisher import publish_csv
from csv_export import export_to_csv

# Load environment variables from .env file
# Try to load from server directory first, then project root
env_paths = [
    os.path.join(os.path.dirname(__file__), '..', 'server', '.env'),
    os.path.join(os.path.dirname(__file__), '..', '.env'),
]
for env_path in env_paths:
    if os.path.exists(env_path):
        load_dotenv(env_path)
        break

def load_keypair(filepath: str) -> Keypair:
    """Load Solana keypair from JSON file"""
    with open(filepath, 'r') as f:
        secret_key = json.load(f)
    return Keypair.from_json(secret_key)

def main():
    print("🤖 Starting Solana Bot...")
    
    # Load keypair
    keypair = load_keypair('./keypair.json')
    print(f"✅ Loaded keypair: {keypair.pubkey()}")
    
    # Initialize database
    db_path = os.getenv('DB_PATH', 'token_holders.db')
    db = TokenHolderDB(db_path)
    print(f"💾 Database ready: {db_path}")
    
    # Create client
    client = OpenKit403Client(keypair)
    
    # Main bot loop
    try:
        while True:
            try:
                print("\n" + "="*50)
                print(f"⏰ Running at {time.strftime('%H:%M:%S')}")
                
                # 1. Fetch data
                print("📥 Fetching data from Solana server...")
                response = client.authenticate(
                    'http://localhost:8000/api/data',
                    method='GET'
                )
                data = response.json()
                
                # Print token info and sample data
                print(f"✅ Received {data.get('count', 0)} data points")
                
                # Print token information
                if 'token_info' in data:
                    token_info = data['token_info']
                    print(f"🪙 Token: {token_info.get('mint', 'N/A')[:20]}...")
                    print(f"   Supply: {token_info.get('total_supply', 0):,.0f}")
                
                # Print first 3-4 holders
                if 'data' in data and len(data['data']) > 0:
                    print(f"\n📊 Top Holders (showing first {min(4, len(data['data']))}):")
                    for i, holder in enumerate(data['data'][:4], 1):
                        address = holder.get('holder_address', 'N/A')
                        balance = holder.get('balance', 0)
                        print(f"   {i}. {address[:20]}... | Balance: {balance:,.2f}")
                
                if 'total_holders' in data:
                    print(f"   Total holders: {data['total_holders']}")
                
                # 2. Save holders to database
                print("💾 Saving holders to database...")
                if 'data' in data and len(data['data']) > 0:
                    # Convert data format to database format
                    holders = []
                    for item in data['data']:
                        holders.append({
                            'address': item.get('holder_address', ''),
                            'balance': item.get('balance', 0)
                        })
                    
                stats = db.save_holders(holders)
                print(f"   ✅ Saved to database:")
                print(f"      - New addresses: {stats['new_addresses']}")
                print(f"      - Updated addresses: {stats['updated_addresses']}")
                print(f"      - Balance changes: {stats['balance_changes']}")
                print(f"      - Dropped from top: {stats['dropped_from_top']}")
                print(f"      - Added to top: {stats['added_to_top']}")
                
                # Export to CSV and publish to GitHub
                print("\n📊 Exporting to CSV...")
                try:
                    csv_path = export_to_csv(db, "token_holders.csv")
                    print(f"   ✅ CSV exported: {csv_path}")
                    
                    # Publish CSV to GitHub
                    print("\n📤 Publishing CSV to GitHub...")
                    github_token = os.getenv('GITHUB_TOKEN')
                    if github_token:
                        print("   🔑 Using GitHub token from environment")
                    else:
                        print("   ⚠️  No GITHUB_TOKEN found in .env file")
                    
                    # Use X403Agent repository for CSV publishing
                    repo_name = os.getenv('GITHUB_REPO_NAME', 'X403Agent')
                    github_username = os.getenv('GITHUB_USERNAME', 'Concorde89')
                    
                    publish_result = publish_csv(
                        csv_path=csv_path,
                        repo_path="..",
                        branch=os.getenv('GIT_BRANCH', 'main'),
                        push=os.getenv('GIT_PUSH', 'true').lower() == 'true',
                        github_token=github_token,
                        target_repo=repo_name,
                        github_username=github_username
                    )
                    
                    if publish_result["commit"]:
                        print(f"   📝 Commit: {publish_result['commit']['message']}")
                    
                    if publish_result["push"]:
                        if publish_result["push"]["success"]:
                            print(f"   ✅ Push: {publish_result['push']['message']}")
                        else:
                            print(f"   ⚠️  Push: {publish_result['push']['message']}")
                    
                    if publish_result["success"]:
                        print("   ✅ CSV published successfully to GitHub")
                    else:
                        print("   ⚠️  CSV commit succeeded but push may have failed")
                except Exception as e:
                    print(f"   ⚠️  Failed to export/publish CSV: {e}")
                    import traceback
                    traceback.print_exc()
                    print("   (Database saved locally, but CSV not published)")
                
                # 3. Process data (simulate work)
                print("⚙️  Processing data...")
                time.sleep(2)
                
                processed_result = {
                    "processed_count": data['count'],
                    "average_value": "calculated",
                    "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ')
                }
                
                # 4. Submit result
                print("📤 Submitting result...")
                submit_response = client.authenticate(
                    'http://localhost:8000/api/submit',
                    method='POST',
                    json_data=processed_result
                )
                submit_data = submit_response.json()
                
                if submit_data['success']:
                    print("✅ Result submitted successfully")
                
                # 5. Check bot status
                print("📊 Checking status...")
                status_response = client.authenticate(
                    'http://localhost:8000/api/bot/status',
                    method='GET'
                )
                status = status_response.json()
                print(f"✅ Bot status: {status['status']}")
                print(f"   Tasks completed: {status['tasks_completed']}")
                
                # Wait before next run (configurable via BOT_RUN_INTERVAL_MINUTES)
                run_interval_minutes = int(os.getenv('BOT_RUN_INTERVAL_MINUTES', '5'))
                run_interval_seconds = run_interval_minutes * 60
                print(f"\n😴 Waiting {run_interval_minutes} minutes before next run...")
                time.sleep(run_interval_seconds)
                
            except Exception as e:
                print(f"❌ Error: {e}")
                import traceback
                traceback.print_exc()
                print("Retrying in 10 seconds...")
                time.sleep(10)
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    finally:
        # Close database connection on exit
        db.close()
        print("💾 Database connection closed")

if __name__ == "__main__":
    main()

