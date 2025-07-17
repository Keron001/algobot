#!/usr/bin/env python3
"""
Error Recovery Script for AlgoBot

This script helps diagnose and fix common issues with the AlgoBot trading system.
Run this script if you encounter connection or trading issues.
"""

import os
import sys
import time
import psutil
import subprocess
from datetime import datetime

os.environ['LOG_FORMAT'] = 'json'  # Enable structured JSON logging for this script

def check_mt5_process():
    """Check if MT5 terminal is running"""
    print("🔍 Checking MT5 terminal process...")
    
    mt5_processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if 'terminal' in proc.info['name'].lower() or 'metatrader' in proc.info['name'].lower():
                mt5_processes.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    if mt5_processes:
        print(f"✅ Found {len(mt5_processes)} MT5 process(es):")
        for proc in mt5_processes:
            print(f"   PID: {proc.info['pid']}, Name: {proc.info['name']}")
        return True
    else:
        print("❌ No MT5 terminal process found")
        return False

def kill_mt5_processes():
    """Kill all MT5 processes"""
    print("🔄 Killing MT5 processes...")
    
    killed = 0
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if 'terminal' in proc.info['name'].lower() or 'metatrader' in proc.info['name'].lower():
                proc.terminate()
                killed += 1
                print(f"   Killed process {proc.info['pid']}")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    if killed > 0:
        print(f"✅ Killed {killed} MT5 process(es)")
        time.sleep(2)  # Give processes time to terminate
    else:
        print("ℹ️ No MT5 processes to kill")

def start_mt5_terminal():
    """Start MT5 terminal"""
    print("🚀 Starting MT5 terminal...")
    
    mt5_paths = [
        r"C:\Program Files\MetaTrader 5\terminal64.exe",
        r"C:\Program Files (x86)\MetaTrader 5\terminal64.exe"
    ]
    
    for path in mt5_paths:
        if os.path.exists(path):
            try:
                subprocess.Popen([path], shell=True)
                print(f"✅ Started MT5 from: {path}")
                time.sleep(10)  # Give MT5 time to start
                return True
            except Exception as e:
                print(f"❌ Failed to start MT5 from {path}: {e}")
    
    print("❌ Could not start MT5 terminal. Please start it manually.")
    return False

def test_mt5_connection():
    """Test MT5 connection"""
    print("🔗 Testing MT5 connection...")
    
    try:
        import MetaTrader5 as mt5
        from config import MT5_LOGIN, MT5_PASSWORD, MT5_SERVER
        
        # Initialize MT5
        mt5.initialize()  # type: ignore
        
        # Login to MT5
        authorized = mt5.login(  # type: ignore
            login=MT5_LOGIN,
            password=MT5_PASSWORD,
            server=MT5_SERVER,
            timeout=60000
        )
        
        if not authorized:
            error = mt5.last_error()  # type: ignore
            print(f"❌ Failed to login to MT5: {error}")
            mt5.shutdown()  # type: ignore
            return False
        
        # Get account info
        account_info = mt5.account_info()  # type: ignore
        if account_info is None:
            print("❌ Failed to get account info")
            mt5.shutdown()  # type: ignore
            return False
        
        print("✅ MT5 connection successful!")
        print(f"   Account: {account_info.login}")
        print(f"   Server: {MT5_SERVER}")
        print(f"   Balance: {account_info.balance:.2f} {account_info.currency}")
        print(f"   Trading Allowed: {'Yes' if account_info.trade_allowed else 'No'}")
        
        mt5.shutdown()  # type: ignore
        return True
        
    except ImportError:
        print("❌ MetaTrader5 module not found. Please install it with: pip install MetaTrader5")
        return False
    except Exception as e:
        print(f"❌ Error testing MT5 connection: {e}")
        return False

def check_python_dependencies():
    """Check if all required Python packages are installed"""
    print("📦 Checking Python dependencies...")
    
    required_packages = [
        'MetaTrader5',
        'pandas',
        'numpy',
        'matplotlib',
        'scikit-learn',
        'psutil',
        'pytz'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} - MISSING")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n📋 Install missing packages with:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    else:
        print("✅ All required packages are installed")
        return True

def check_config_file():
    """Check if config file exists and is valid"""
    print("⚙️ Checking configuration file...")
    
    if not os.path.exists('config.py'):
        print("❌ config.py file not found")
        return False
    
    try:
        from config import MT5_LOGIN, MT5_PASSWORD, MT5_SERVER, SYMBOLS
        print("✅ config.py file is valid")
        print(f"   Login: {MT5_LOGIN}")
        print(f"   Server: {MT5_SERVER}")
        print(f"   Symbols: {SYMBOLS}")
        return True
    except ImportError as e:
        print(f"❌ Error importing config: {e}")
        return False

def main():
    """Main recovery function"""
    print("🛠️ AlgoBot Error Recovery Tool")
    print("=" * 50)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Check dependencies
    deps_ok = check_python_dependencies()
    print()
    
    # Check config
    config_ok = check_config_file()
    print()
    
    # Check MT5 process
    mt5_running = check_mt5_process()
    print()
    
    if not mt5_running:
        print("🔄 MT5 terminal not running. Attempting to start...")
        if start_mt5_terminal():
            time.sleep(5)
            mt5_running = check_mt5_process()
    
    if mt5_running:
        print("🔗 Testing MT5 connection...")
        connection_ok = test_mt5_connection()
        print()
        
        if connection_ok:
            print("✅ All checks passed! Your AlgoBot should work now.")
        else:
            print("❌ MT5 connection failed. Please check your credentials and try again.")
    else:
        print("❌ MT5 terminal is not running. Please start it manually.")
    
    print("\n" + "=" * 50)
    print("Recovery process completed.")

if __name__ == "__main__":
    main() 