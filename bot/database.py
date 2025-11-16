"""Database module for tracking token holders"""
import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional, Any

# Address tags configuration
ADDRESS_TAGS = {
    "EXPkq4YLioHm4kvFR29j3G6uVsk9FzgoH3ibfv8ye7s2": "liquidity pool",
    "XJz4E9GHenAK1cjd1kQyFBDjcM81RSytb4XWYvriKT4": "locked by dev",
    "E7Srs8zZqkwvGXw4xxC6WHMx5cHcFeHiX1rHz3uCn8En": "Team",
    "Dd7cVLQwg14KzkRPHHKVQg9fGNovpe2hFJJpRFbY3NDg": "team"
}

class TokenHolderDB:
    """Database manager for token holders"""
    
    def __init__(self, db_path: str = "token_holders.db"):
        """
        Initialize database connection
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.conn = None
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        
        cursor = self.conn.cursor()
        
        # Create token_holders table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS token_holders (
                address TEXT PRIMARY KEY,
                current_balance REAL NOT NULL,
                previous_balance REAL,
                tag TEXT NOT NULL DEFAULT 'holder',
                is_top_holder INTEGER NOT NULL DEFAULT 1,
                first_seen TIMESTAMP NOT NULL,
                last_updated TIMESTAMP NOT NULL,
                balance_changed_at TIMESTAMP
            )
        """)
        
        # Create balance_history table to track balance changes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS balance_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT NOT NULL,
                old_balance REAL,
                new_balance REAL NOT NULL,
                changed_at TIMESTAMP NOT NULL,
                FOREIGN KEY (address) REFERENCES token_holders(address)
            )
        """)
        
        # Create index for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_is_top_holder 
            ON token_holders(is_top_holder)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tag 
            ON token_holders(tag)
        """)
        
        self.conn.commit()
        print(f"✅ Database initialized: {self.db_path}")
    
    def get_address_tag(self, address: str) -> str:
        """Get tag for an address"""
        return ADDRESS_TAGS.get(address, "holder")
    
    def save_holders(self, holders: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Save or update token holders data
        
        Args:
            holders: List of holder dictionaries with 'address' and 'balance'
            
        Returns:
            Dictionary with statistics about the save operation
        """
        cursor = self.conn.cursor()
        now = datetime.utcnow().isoformat()
        
        # Get current top holder addresses
        current_top_addresses = {h['address'] for h in holders}
        
        # Get all existing addresses from database
        cursor.execute("SELECT address, current_balance, is_top_holder FROM token_holders")
        existing_data = {row['address']: {
            'balance': row['current_balance'],
            'is_top_holder': row['is_top_holder']
        } for row in cursor.fetchall()}
        
        stats = {
            'new_addresses': 0,
            'updated_addresses': 0,
            'balance_changes': 0,
            'dropped_from_top': 0,
            'added_to_top': 0
        }
        
        # Process each holder
        for holder in holders:
            address = holder['address']
            balance = float(holder['balance'])
            tag = self.get_address_tag(address)
            
            if address in existing_data:
                # Address exists - update it
                existing = existing_data[address]
                old_balance = existing['balance']
                was_top_holder = existing['is_top_holder']
                
                # Check if balance changed
                balance_changed = abs(old_balance - balance) > 0.0001  # Small threshold for float comparison
                
                if balance_changed:
                    # Record balance change
                    cursor.execute("""
                        INSERT INTO balance_history (address, old_balance, new_balance, changed_at)
                        VALUES (?, ?, ?, ?)
                    """, (address, old_balance, balance, now))
                    stats['balance_changes'] += 1
                
                # Update holder record
                cursor.execute("""
                    UPDATE token_holders 
                    SET current_balance = ?,
                        previous_balance = ?,
                        tag = ?,
                        is_top_holder = 1,
                        last_updated = ?,
                        balance_changed_at = CASE WHEN ? THEN ? ELSE balance_changed_at END
                    WHERE address = ?
                """, (
                    balance,
                    old_balance if balance_changed else None,
                    tag,
                    now,
                    balance_changed,
                    now if balance_changed else None,
                    address
                ))
                
                stats['updated_addresses'] += 1
                
                # Track if address was added back to top
                if not was_top_holder:
                    stats['added_to_top'] += 1
            else:
                # New address - insert it
                cursor.execute("""
                    INSERT INTO token_holders 
                    (address, current_balance, previous_balance, tag, is_top_holder, first_seen, last_updated)
                    VALUES (?, ?, ?, ?, 1, ?, ?)
                """, (address, balance, None, tag, now, now))
                stats['new_addresses'] += 1
        
        # Mark addresses that are no longer in top 20
        all_existing_addresses = set(existing_data.keys())
        dropped_addresses = all_existing_addresses - current_top_addresses
        
        if dropped_addresses:
            cursor.execute("""
                UPDATE token_holders 
                SET is_top_holder = 0,
                    last_updated = ?
                WHERE address IN ({})
            """.format(','.join('?' * len(dropped_addresses))), 
            [now] + list(dropped_addresses))
            stats['dropped_from_top'] = len(dropped_addresses)
        
        self.conn.commit()
        return stats
    
    def get_all_holders(self, include_dropped: bool = True) -> List[Dict[str, Any]]:
        """
        Get all token holders from database
        
        Args:
            include_dropped: Whether to include addresses no longer in top 20
            
        Returns:
            List of holder dictionaries
        """
        cursor = self.conn.cursor()
        
        if include_dropped:
            cursor.execute("""
                SELECT address, current_balance, previous_balance, tag, is_top_holder, 
                       first_seen, last_updated, balance_changed_at
                FROM token_holders
                ORDER BY current_balance DESC
            """)
        else:
            cursor.execute("""
                SELECT address, current_balance, previous_balance, tag, is_top_holder, 
                       first_seen, last_updated, balance_changed_at
                FROM token_holders
                WHERE is_top_holder = 1
                ORDER BY current_balance DESC
            """)
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    def get_holder_by_address(self, address: str) -> Optional[Dict[str, Any]]:
        """Get holder information by address"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT address, current_balance, previous_balance, tag, is_top_holder, 
                   first_seen, last_updated, balance_changed_at
            FROM token_holders
            WHERE address = ?
        """, (address,))
        
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_balance_history(self, address: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get balance change history for an address"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT old_balance, new_balance, changed_at
            FROM balance_history
            WHERE address = ?
            ORDER BY changed_at DESC
            LIMIT ?
        """, (address, limit))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None

