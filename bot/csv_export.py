"""CSV export module for token holder data"""
import csv
import os
from typing import List, Dict, Any
from database import TokenHolderDB

def export_to_csv(db: TokenHolderDB, csv_path: str = "token_holders.csv") -> str:
    """
    Export token holder data to CSV file
    
    Args:
        db: TokenHolderDB instance
        csv_path: Path to output CSV file
        
    Returns:
        Path to the created CSV file
    """
    # Get all holders from database
    holders = db.get_all_holders()
    
    # Write to CSV
    with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = [
            'address',
            'current_balance',
            'previous_balance',
            'tag',
            'is_top_holder',
            'first_seen',
            'last_updated',
            'balance_changed_at'
        ]
        
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for holder in holders:
            writer.writerow({
                'address': holder.get('address', ''),
                'current_balance': holder.get('current_balance', 0),
                'previous_balance': holder.get('previous_balance', '') if holder.get('previous_balance') else '',
                'tag': holder.get('tag', 'holder'),
                'is_top_holder': 'Yes' if holder.get('is_top_holder', 0) else 'No',
                'first_seen': holder.get('first_seen', ''),
                'last_updated': holder.get('last_updated', ''),
                'balance_changed_at': holder.get('balance_changed_at', '') if holder.get('balance_changed_at') else ''
            })
    
    return csv_path

