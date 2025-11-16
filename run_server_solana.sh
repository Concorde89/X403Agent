#!/bin/bash
# Run Solana-enabled server with virtual environment activated

cd "$(dirname "$0")"
source venv/bin/activate

# Load .env file if it exists
if [ -f ".env" ]; then
    echo "📄 Loading configuration from .env file..."
    # Export variables from .env file (simple parser, handles comments and empty lines)
    export $(grep -v '^#' .env | grep -v '^$' | xargs)
    echo "✅ Configuration loaded"
elif [ -f "server/.env" ]; then
    echo "📄 Loading configuration from server/.env file..."
    export $(grep -v '^#' server/.env | grep -v '^$' | xargs)
    echo "✅ Configuration loaded"
else
    echo "⚠️  No .env file found. Using environment variables or defaults."
fi

# Check if TOKEN_MINT is set (from .env or environment)
if [ -z "$TOKEN_MINT" ]; then
    echo ""
    echo "⚠️  Warning: TOKEN_MINT not set!"
    echo ""
    echo "Please set it in .env file:"
    echo "  TOKEN_MINT=YourTokenMintAddress"
    echo ""
    echo "Or set it as environment variable:"
    echo "  export TOKEN_MINT='YourTokenMintAddress'"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

cd server
python3 server_solana.py

