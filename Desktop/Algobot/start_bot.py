#!/usr/bin/env python3
"""
AlgoBot Startup Script

This script handles the startup process for the AlgoBot trading system,
including connection management, error recovery, and proper initialization.
"""

import os
import sys
import time
import subprocess
from datetime import datetime

os.environ['LOG_FORMAT'] = 'json'  # Enable structured JSON logging for this script

def run_error_recovery():
    """Run the error recovery script"""
    print("🛠️ Running error recovery...")
    try:
        result = subprocess.run([sys.executable, 'error_recovery.py'], 
                              capture_output=True, text=True, timeout=60)
        print(result.stdout)
        if result.stderr:
            print("Warnings:", result.stderr)
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print("❌ Error recovery timed out")
        return False
    except Exception as e:
        print(f"❌ Error running recovery script: {e}")
        return False

def check_mt5_connection():
    """Quick check if MT5 is accessible"""
    try:
        import MetaTrader5 as mt5
        from config import MT5_LOGIN, MT5_PASSWORD, MT5_SERVER
        
        if not mt5.initialize():
            return False
        
        authorized = mt5.login(
            login=MT5_LOGIN,
            password=MT5_PASSWORD,
            server=MT5_SERVER,
            timeout=30000
        )
        
        if not authorized:
            mt5.shutdown()
            return False
        
        account_info = mt5.account_info()
        mt5.shutdown()
        
        return account_info is not None
        
    except Exception:
        return False

def start_bot():
    """Start the AlgoBot"""
    print("🚀 Starting AlgoBot...")
    
    try:
        # Import and run the main bot
        from main import run_strategy
        
        print("✅ Starting trading strategy...")
        success = run_strategy()
        
        if success:
            print("✅ AlgoBot completed successfully")
        else:
            print("❌ AlgoBot encountered errors")
            
        return success
        
    except KeyboardInterrupt:
        print("\n🛑 AlgoBot stopped by user")
        return True
    except Exception as e:
        print(f"❌ Fatal error in AlgoBot: {e}")
        return False

def main():
    """Main startup function"""
    print("🤖 AlgoBot Startup Script")
    print("=" * 50)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Step 1: Check if we're in the right directory
    if not os.path.exists('main.py'):
        print("❌ main.py not found. Please run this script from the AlgoBot directory.")
        return False
    
    # Step 2: Run diagnostics first
    print("🔍 Running system diagnostics...")
    try:
        result = subprocess.run([sys.executable, 'diagnose_bot.py'], 
                              capture_output=True, text=True, timeout=120)
        print(result.stdout)
        if result.stderr:
            print("Warnings:", result.stderr)
        
        if result.returncode != 0:
            print("❌ Diagnostics failed. Please fix the issues before running the bot.")
            print("\n💡 Run the diagnostic tool manually:")
            print("python diagnose_bot.py")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Diagnostics timed out")
        return False
    except Exception as e:
        print(f"❌ Error running diagnostics: {e}")
        return False
    
    print("✅ Diagnostics passed")
    print()
    
    # Step 3: Start the bot
    print("🚀 Initializing AlgoBot...")
    success = start_bot()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ AlgoBot startup completed successfully")
    else:
        print("❌ AlgoBot startup failed")
    
    return success

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Startup script error: {e}")
        sys.exit(1) 