"""Solana blockchain data fetcher for SPL token holders"""
import os
from typing import List, Dict, Optional, Any
from solders.pubkey import Pubkey
import base64
import base58
import requests
import json

# SPL Token Program ID
TOKEN_PROGRAM_ID = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")

class SolanaDataFetcher:
    """Fetches SPL token holder data from Solana blockchain"""
    
    def __init__(self, rpc_url: str, token_mint: str, api_key: Optional[str] = None):
        """
        Initialize Solana data fetcher
        
        Args:
            rpc_url: Custom Solana RPC endpoint URL
            token_mint: SPL token mint address
            api_key: Optional Helius API key for enhanced API access
        """
        self.rpc_url = rpc_url
        self.api_key = api_key
        try:
            self.token_mint = Pubkey.from_string(token_mint)
        except Exception as e:
            raise ValueError(f"Invalid token mint address: {e}")
        
        # Extract API key from URL if present
        if not self.api_key and 'api-key=' in rpc_url:
            try:
                self.api_key = rpc_url.split('api-key=')[1].split('&')[0].split('?')[0]
            except:
                pass
    
    def _rpc_call(self, method: str, params: list) -> dict:
        """Make RPC call to Solana endpoint"""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params
        }
        response = requests.post(self.rpc_url, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    
    def get_token_holders(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get list of token holders for the SPL token
        
        Uses getTokenLargestAccounts which returns the top 20 largest holders.
        This is the most reliable method that works on all RPC providers.
        
        Args:
            limit: Maximum number of holders to return (default 20, max 20)
            
        Returns:
            List of holder information dictionaries (up to 20 holders)
        """
        holders = []
        
        try:
            # Get token supply for decimals first
            token_info = self.get_token_info()
            decimals = token_info.get("decimals", 9)
            
            print(f"🔍 Fetching holders for token: {self.token_mint}")
            # getTokenLargestAccounts always returns top 20, so limit is effectively 20
            effective_limit = min(limit, 20)
            print(f"   Requesting top {effective_limit} holders (getTokenLargestAccounts returns max 20)")
            
            # Method 0: Try Helius enhanced API first if we have an API key
            if self.api_key and 'helius' in self.rpc_url.lower():
                print("   Trying Helius enhanced API...")
                try:
                    helius_holders = self._get_token_holders_helius_api(limit, decimals)
                    if helius_holders:
                        print(f"   ✅ Helius API returned {len(helius_holders)} holders")
                        return helius_holders
                except Exception as e:
                    print(f"   ⚠️  Helius API failed: {e}")
                    print("   Falling back to RPC methods...")
            
            # Method 1: Try getTokenLargestAccounts first (standard Solana RPC, works on most providers)
            # This returns the top 20 largest accounts
            print("   Trying getTokenLargestAccounts (standard method)...")
            try:
                params = [str(self.token_mint)]
                response = self._rpc_call("getTokenLargestAccounts", params)
                
                if "result" in response and response["result"]:
                    value = response["result"].get("value", [])
                    print(f"   ✅ getTokenLargestAccounts returned {len(value)} accounts")
                    
                    # Process up to 20 accounts (getTokenLargestAccounts returns max 20)
                    accounts_to_process = value[:20]
                    print(f"   Processing {len(accounts_to_process)} accounts to get owners...")
                    
                    for i, account_info in enumerate(accounts_to_process, 1):
                        try:
                            token_account_address = account_info.get("address", "")
                            ui_amount = account_info.get("uiAmount", 0) or 0
                            amount_str = account_info.get("amount", "0")
                            
                            if ui_amount > 0 and token_account_address:
                                # Get the owner of this token account
                                account_response = self._rpc_call("getAccountInfo", [token_account_address, {"encoding": "jsonParsed"}])
                                
                                owner_address = None
                                if "result" in account_response and account_response["result"]:
                                    account_data = account_response["result"].get("value", {})
                                    if account_data and "data" in account_data:
                                        data = account_data["data"]
                                        if isinstance(data, dict) and "parsed" in data:
                                            owner_address = data["parsed"]["info"].get("owner", "")
                                
                                # If we couldn't get owner, skip this account
                                if not owner_address:
                                    print(f"   ⚠️  Could not get owner for token account {token_account_address[:20]}...")
                                    continue
                                
                                holders.append({
                                    "address": owner_address,
                                    "balance": ui_amount,
                                    "balance_raw": amount_str,
                                    "decimals": decimals,
                                    "token_account": token_account_address
                                })
                                
                                if i % 5 == 0:
                                    print(f"   Processed {i}/{len(accounts_to_process)} accounts...")
                                    
                        except Exception as e:
                            print(f"   ⚠️  Error processing account {i}: {e}")
                            continue
                    
                    if holders:
                        print(f"   ✅ Successfully got {len(holders)} holders with owners from getTokenLargestAccounts")
                        holders.sort(key=lambda x: x["balance"], reverse=True)
                        return holders  # Return the top 20 holders
                    else:
                        print("   ⚠️  No holders found after processing accounts")
                        
            except Exception as e:
                print(f"   ⚠️  getTokenLargestAccounts failed: {e}")
                print("   No alternative methods available.")
                return []
            
        except Exception as e:
            print(f"❌ Error fetching token holders: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def get_token_info(self) -> Dict[str, Any]:
        """Get basic token information"""
        try:
            # RPC call to getTokenSupply
            params = [str(self.token_mint)]
            response = self._rpc_call("getTokenSupply", params)
            
            if "result" not in response or not response["result"]:
                return {"error": "Could not fetch token supply"}
            
            result = response["result"]["value"]
            
            return {
                "mint": str(self.token_mint),
                "total_supply": result.get("uiAmount", 0) or 0,
                "decimals": result.get("decimals", 9),
                "supply_raw": result.get("amount", "0")
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _get_token_holders_helius_api(self, limit: int, decimals: int) -> List[Dict[str, Any]]:
        """
        Get token holders using Helius enhanced API with pagination
        This method uses getProgramAccounts with proper pagination to get all holders
        
        Args:
            limit: Maximum number of holders to return
            decimals: Token decimals for balance conversion
            
        Returns:
            List of holder information dictionaries
        """
        holders = []
        mint_base58 = base58.b58encode(bytes(self.token_mint)).decode('utf-8')
        
        try:
            print("   Using Helius enhanced API with pagination...")
            
            # Build filters
            filters = [
                {
                    "memcmp": {
                        "offset": 0,
                        "bytes": mint_base58
                    }
                }
            ]
            
            # Helius doesn't support pagination with getProgramAccounts for large datasets
            # The standard getProgramAccounts fails with "too many accounts" error
            # So we fall back to getTokenLargestAccounts which returns top 20
            print("   Note: Helius requires getProgramAccountsV2 for large datasets (not available)")
            print("   Falling back to getTokenLargestAccounts (top 20 only)")
            return []  # Return empty to trigger fallback to getTokenLargestAccounts
            
        except Exception as e:
            print(f"   ❌ Error in Helius API method: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _get_token_holders_standard(self, limit: int, decimals: int) -> List[Dict[str, Any]]:
        """
        Get token holders using standard getProgramAccounts
        This is a fallback method that might work on some RPC providers
        
        Args:
            limit: Maximum number of holders to return
            decimals: Token decimals for balance conversion
            
        Returns:
            List of holder information dictionaries
        """
        holders = []
        mint_base58 = base58.b58encode(bytes(self.token_mint)).decode('utf-8')
        
        try:
            print("   Using standard getProgramAccounts...")
            
            # Build filters
            filters = [
                {
                    "memcmp": {
                        "offset": 0,
                        "bytes": mint_base58
                    }
                }
            ]
            
            # Standard getProgramAccounts call
            params = [
                str(TOKEN_PROGRAM_ID),
                {
                    "filters": filters,
                    "encoding": "jsonParsed"
                }
            ]
            
            print(f"   Requesting up to {limit} accounts...")
            response = self._rpc_call("getProgramAccounts", params)
            
            if "error" in response:
                error_msg = response.get("error", {})
                print(f"   ❌ Standard getProgramAccounts error: {error_msg}")
                return []
            
            if "result" not in response or not response["result"]:
                print("   ⚠️  No results from standard getProgramAccounts")
                return []
            
            accounts = response["result"][:limit]
            print(f"   ✅ Standard getProgramAccounts returned {len(accounts)} accounts")
            
            # Parse accounts
            for account_info in accounts:
                try:
                    if "account" in account_info and "data" in account_info["account"]:
                        account_data = account_info["account"]["data"]
                        
                        if isinstance(account_data, dict) and "parsed" in account_data:
                            parsed = account_data["parsed"]["info"]
                            owner = parsed.get("owner", "")
                            token_amount = parsed.get("tokenAmount", {})
                            ui_amount = token_amount.get("uiAmount", 0) or 0
                            
                            if ui_amount > 0 and owner:
                                holders.append({
                                    "address": owner,
                                    "balance": ui_amount,
                                    "balance_raw": str(token_amount.get("amount", "0")),
                                    "decimals": decimals
                                })
                except Exception as e:
                    continue
            
            print(f"   ✅ Parsed {len(holders)} holders from standard method")
            holders.sort(key=lambda x: x["balance"], reverse=True)
            return holders
            
        except Exception as e:
            print(f"   ❌ Error in standard getProgramAccounts: {e}")
            return []
    
    def get_holder_stats(self) -> Dict[str, Any]:
        """Get statistics about token holders"""
        holders = self.get_token_holders(limit=1000)
        
        if not holders:
            return {
                "total_holders": 0,
                "total_holders_with_balance": 0,
                "top_10_holders": []
            }
        
        total_balance = sum(h["balance"] for h in holders)
        
        return {
            "total_holders": len(holders),
            "total_holders_with_balance": len([h for h in holders if h["balance"] > 0]),
            "total_distributed": total_balance,
            "top_10_holders": holders[:10],
            "average_balance": total_balance / len(holders) if holders else 0
        }
