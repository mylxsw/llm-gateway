#!/usr/bin/env python3
"""
Database migration checker and applier for is_stream column.
Run this script from the backend directory to add the is_stream column if missing.
"""

import sqlite3
import sys
from pathlib import Path

def check_and_add_is_stream_column(db_path: str = "./llm_gateway.db"):
    """Check if is_stream column exists and add it if missing."""
    
    db_file = Path(db_path)
    if not db_file.exists():
        print(f"❌ Database file not found: {db_path}")
        print(f"   Expected location: {db_file.absolute()}")
        print("\nPlease run this script from the backend directory where the database is located.")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check current schema
        cursor.execute("PRAGMA table_info(request_logs);")
        columns = cursor.fetchall()
        
        if not columns:
            print(f"❌ Table 'request_logs' not found in database")
            return False
        
        # Check if is_stream column exists
        column_names = [col[1] for col in columns]
        
        if 'is_stream' in column_names:
            print("✅ Column 'is_stream' already exists in request_logs table")
            
            # Check some recent records to see their is_stream values
            cursor.execute("""
                SELECT id, is_stream, 
                       CASE WHEN response_body LIKE '%"type": "stream"%' THEN 'should_be_stream' ELSE 'non_stream' END as expected
                FROM request_logs 
                ORDER BY id DESC 
                LIMIT 5
            """)
            recent_logs = cursor.fetchall()
            
            if recent_logs:
                print("\n📊 Recent log entries:")
                print("ID | is_stream | Expected (from response_body)")
                print("-" * 50)
                for log in recent_logs:
                    print(f"{log[0]:4d} | {log[1]:9} | {log[2]}")
                    
                # Check for mismatches
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM request_logs 
                    WHERE is_stream = 0 
                    AND response_body LIKE '%"type": "stream"%'
                """)
                mismatch_count = cursor.fetchone()[0]
                
                if mismatch_count > 0:
                    print(f"\n⚠️  Warning: Found {mismatch_count} stream requests incorrectly marked as non-stream")
                    print("   These are old records that were created before the is_stream field was properly saved.")
                    print("   New requests should have the correct value.")
            
            conn.close()
            return True
        
        # Column doesn't exist, add it
        print("⚠️  Column 'is_stream' not found. Adding it now...")
        cursor.execute("ALTER TABLE request_logs ADD COLUMN is_stream BOOLEAN NOT NULL DEFAULT 0;")
        conn.commit()
        print("✅ Successfully added 'is_stream' column to request_logs table")
        
        conn.close()
        return True
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "./llm_gateway.db"
    
    print("=" * 60)
    print("Database Migration Checker - is_stream column")
    print("=" * 60)
    print(f"\nChecking database: {db_path}")
    print()
    
    success = check_and_add_is_stream_column(db_path)
    
    if success:
        print("\n" + "=" * 60)
        print("✅ Migration check complete!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Restart your backend service")
        print("2. Make a NEW stream request")
        print("3. Check the logs page - new requests should show the wave icon")
    else:
        print("\n" + "=" * 60)
        print("❌ Migration check failed!")
        print("=" * 60)
        sys.exit(1)
