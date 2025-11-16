"""FastAPI Server with OpenKitx403 Middleware - Solana Token Holder Data"""
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from openkitx403 import (
    OpenKit403Middleware,
    require_openkitx403_user,
    OpenKit403User
)
import uvicorn
import os
from datetime import datetime
from dotenv import load_dotenv
from solana_data import SolanaDataFetcher

# Load environment variables from .env file
# This will load from .env in the server directory, or parent directory
env_path = os.path.join(os.path.dirname(__file__), '.env')
if not os.path.exists(env_path):
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(env_path)

app = FastAPI(title="Solana Bot API - Token Holder Data")

# Configuration from environment variables (loaded from .env or system env)
SOLANA_RPC_URL = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
TOKEN_MINT = os.getenv("TOKEN_MINT", "")

# Initialize Solana data fetcher
solana_fetcher = None
# Extract API key from RPC URL if present
HELIUS_API_KEY = None
if 'api-key=' in SOLANA_RPC_URL:
    try:
        HELIUS_API_KEY = SOLANA_RPC_URL.split('api-key=')[1].split('&')[0].split('?')[0]
    except:
        pass

if TOKEN_MINT:
    try:
        solana_fetcher = SolanaDataFetcher(SOLANA_RPC_URL, TOKEN_MINT, api_key=HELIUS_API_KEY)
        print(f"✅ Initialized Solana fetcher for token: {TOKEN_MINT}")
        print(f"📡 Using RPC endpoint: {SOLANA_RPC_URL}")
        if HELIUS_API_KEY:
            print(f"🔑 Helius API key detected - enhanced API methods enabled")
    except Exception as e:
        print(f"⚠️  Warning: Could not initialize Solana fetcher: {e}")
        print("   Server will run but token data will not be available")
else:
    print("⚠️  Warning: TOKEN_MINT not set. Set it via environment variable:")
    print("   export TOKEN_MINT='YourTokenMintAddress'")

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add OpenKit403 middleware
app.add_middleware(
    OpenKit403Middleware,
    audience=os.getenv("API_AUDIENCE", "http://localhost:8000"),
    issuer=os.getenv("ISSUER", "bot-api-v1"),
    ttl_seconds=int(os.getenv("TTL_SECONDS", "60")),
    bind_method_path=True,
    excluded_paths=["/", "/docs", "/openapi.json", "/redoc", "/health", "/config"]
)

# Public endpoints
@app.get("/")
async def root():
    return {
        "message": "Solana Bot API - Token Holder Data",
        "status": "running",
        "solana_configured": solana_fetcher is not None,
        "token_mint": TOKEN_MINT if TOKEN_MINT else "Not configured",
        "rpc_url": SOLANA_RPC_URL
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "Solana Bot API"}

@app.get("/config")
async def config():
    """Get current configuration (public endpoint)"""
    return {
        "solana_rpc_url": SOLANA_RPC_URL,
        "token_mint": TOKEN_MINT if TOKEN_MINT else None,
        "solana_configured": solana_fetcher is not None
    }

# Protected endpoint - Token holder data
@app.get("/api/data")
async def get_data(user: OpenKit403User = Depends(require_openkitx403_user)):
    """Get SPL token holder data from Solana blockchain"""
    
    if not solana_fetcher:
        return {
            "error": "Solana fetcher not configured",
            "message": "Please set TOKEN_MINT and SOLANA_RPC_URL environment variables",
            "wallet": user.address,
            "data": [],
            "count": 0
        }
    
    try:
        # Get token info first
        token_info = solana_fetcher.get_token_info()
        
        # Get token holders (getTokenLargestAccounts returns top 20)
        holders = solana_fetcher.get_token_holders(limit=20)
        
        # Format data for bot
        data_points = []
        for i, holder in enumerate(holders[:20], 1):  # Limit to 20 (max available)
            data_points.append({
                "id": i,
                "holder_address": holder["address"],
                "balance": holder["balance"],
                "balance_raw": holder["balance_raw"],
                "rank": i,
                "timestamp": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
            })
        
        return {
            "wallet": user.address,
            "token_info": token_info,
            "data": data_points,
            "count": len(data_points),
            "total_holders": len(holders),
            "timestamp": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
            "note": "If holders=0, check server logs. May need Helius enhanced APIs or different RPC provider."
        }
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in get_data: {error_details}")
        return {
            "error": str(e),
            "wallet": user.address,
            "data": [],
            "count": 0,
            "token_info": solana_fetcher.get_token_info() if solana_fetcher else None
        }

# Protected endpoint - Token holder statistics
@app.get("/api/token/stats")
async def get_token_stats(user: OpenKit403User = Depends(require_openkitx403_user)):
    """Get token holder statistics"""
    
    if not solana_fetcher:
        return {
            "error": "Solana fetcher not configured",
            "wallet": user.address
        }
    
    try:
        stats = solana_fetcher.get_holder_stats()
        token_info = solana_fetcher.get_token_info()
        
        return {
            "wallet": user.address,
            "token_info": token_info,
            "stats": stats,
            "timestamp": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        }
    except Exception as e:
        return {
            "error": str(e),
            "wallet": user.address
        }

# Protected endpoint - Submit result
@app.post("/api/submit")
async def submit_result(
    result: dict,
    user: OpenKit403User = Depends(require_openkitx403_user)
):
    return {
        "success": True,
        "message": f"Result submitted by {user.address}",
        "result": result
    }

# Protected endpoint - Bot status
@app.get("/api/bot/status")
async def bot_status(user: OpenKit403User = Depends(require_openkitx403_user)):
    return {
        "bot_wallet": user.address,
        "status": "active",
        "last_run": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
        "tasks_completed": 42,
        "token_mint": TOKEN_MINT if TOKEN_MINT else "Not configured"
    }

if __name__ == "__main__":
    import socket
    
    # Get host and port from environment or use defaults
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    audience = os.getenv("API_AUDIENCE", "http://localhost:8000")
    
    # Check if .env file was loaded
    env_file_used = os.path.exists(env_path)
    
    print("="*60)
    print("🚀 Starting Solana Bot API Server")
    print("="*60)
    if env_file_used:
        print(f"📄 Configuration: Loaded from .env file")
        print(f"   {env_path}")
    else:
        print(f"📄 Configuration: Using environment variables")
    print(f"📡 Server: http://{host}:{port}")
    print(f"🌐 Solana RPC: {SOLANA_RPC_URL}")
    print(f"🪙 Token Mint: {TOKEN_MINT if TOKEN_MINT else 'Not configured (set TOKEN_MINT in .env)'}")
    print(f"✅ Solana Fetcher: {'Initialized' if solana_fetcher else 'Not configured'}")
    if not TOKEN_MINT:
        print("")
        print("⚠️  WARNING: TOKEN_MINT not set!")
        print("   Create a .env file with TOKEN_MINT=YourTokenAddress")
        print("   Or set it as environment variable")
    print("="*60)
    
    if host == "0.0.0.0":
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            print(f"🌐 Network access: http://{local_ip}:{port}")
        except:
            pass
    
    uvicorn.run(app, host=host, port=port)

