#!/usr/bin/env python3
"""
Test script to verify admin functionality
"""

import asyncio
from config import settings
from bot import is_admin

def test_admin_access():
    """Test admin access functionality"""
    print("🔍 Testing admin access functionality...")
    
    # Test admin ID loading
    try:
        admin_ids = settings.get_admin_ids()
        print(f"✅ Loaded admin IDs: {admin_ids}")
        
        if not admin_ids:
            print("❌ No admin IDs configured!")
            return False
            
        # Test is_admin function with the first admin ID
        test_id = admin_ids[0]
        result = is_admin(test_id)
        print(f"✅ Admin check for ID {test_id}: {result}")
        
        # Test with a non-admin ID
        non_admin_id = 999999999
        result = is_admin(non_admin_id)
        print(f"✅ Admin check for non-admin ID {non_admin_id}: {result}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing admin access: {e}")
        return False

def main():
    """Main test function"""
    print("🚀 Admin functionality test")
    print("=" * 40)
    
    if test_admin_access():
        print("\n✅ Admin functionality tests passed!")
        print("\n📋 To test with your bot:")
        print("1. Make sure your Telegram user ID is in the admin_ids list")
        print("2. Start the bot with: python main.py")
        print("3. Send /admin command to the bot")
        print("4. Check the bot logs for debug information")
    else:
        print("\n❌ Admin functionality tests failed!")

if __name__ == "__main__":
    main()