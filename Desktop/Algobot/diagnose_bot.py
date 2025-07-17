#!/usr/bin/env python3
"""
AlgoBot Diagnostic Script

This script helps diagnose issues with the AlgoBot trading system.
Run this script to identify specific problems before running the main bot.
"""

import sys
import traceback
from datetime import datetime
import os
os.environ['LOG_FORMAT'] = 'json'  # Enable structured JSON logging for this script

def test_imports():
    """Test if all required modules can be imported"""
    print("Testing module imports...")
    
    modules_to_test = [
        'MetaTrader5',
        'pandas',
        'numpy',
        'pytz',
        'psutil'
    ]
    
    failed_imports = []
    
    for module in modules_to_test:
        try:
            __import__(module)
            print(f"OK {module}")
        except ImportError as e:
            print(f"ERROR {module} - {e}")
            failed_imports.append(module)
    
    if failed_imports:
        print(f"\nInstall missing modules with:")
        print(f"pip install {' '.join(failed_imports)}")
        return False
    
    return True

def test_config():
    """Test if configuration can be loaded"""
    print("\nTesting configuration...")
    
    try:
        from config import (
            SYMBOLS, TIMEFRAMES, DEFAULT_LOT_SIZE, MAGIC_NUMBER,
            MT5_LOGIN, MT5_PASSWORD, MT5_SERVER
        )
        print("OK Configuration loaded successfully")
        print(f"   Symbols: {SYMBOLS}")
        print(f"   Timeframes: {TIMEFRAMES}")
        print(f"   Lot Size: {DEFAULT_LOT_SIZE}")
        print(f"   Magic Number: {MAGIC_NUMBER}")
        print(f"   Login: {MT5_LOGIN}")
        print(f"   Server: {MT5_SERVER}")
        return True
    except Exception as e:
        print(f"ERROR Configuration error: {e}")
        return False

def test_mt5_connection():
    """Test MT5 connection"""
    print("\nTesting MT5 connection...")
    
    try:
        import MetaTrader5 as mt5
        from config import MT5_LOGIN, MT5_PASSWORD, MT5_SERVER
        
        # Initialize MT5
        if not mt5.initialize():  # type: ignore
            error = mt5.last_error()  # type: ignore
            print(f"ERROR Failed to initialize MT5: {error}")
            return False
        
        # Login to MT5
        authorized = mt5.login(  # type: ignore
            login=MT5_LOGIN,
            password=MT5_PASSWORD,
            server=MT5_SERVER,
            timeout=30000
        )
        
        if not authorized:
            error = mt5.last_error()  # type: ignore
            print(f"ERROR Failed to login to MT5: {error}")
            mt5.shutdown()  # type: ignore
            return False
        
        # Get account info
        account_info = mt5.account_info()  # type: ignore
        if account_info is None:
            print("ERROR Failed to get account info")
            mt5.shutdown()  # type: ignore
            return False
        
        print("OK MT5 connection successful!")
        print(f"   Account: {account_info.login}")
        print(f"   Balance: {account_info.balance:.2f} {account_info.currency}")
        print(f"   Trading Allowed: {'Yes' if account_info.trade_allowed else 'No'}")
        
        mt5.shutdown()  # type: ignore
        return True
        
    except Exception as e:
        print(f"ERROR MT5 connection error: {e}")
        return False

def test_symbol_availability():
    """Test if trading symbols are available"""
    print("\nTesting symbol availability...")
    
    try:
        import MetaTrader5 as mt5
        from config import SYMBOLS, MT5_LOGIN, MT5_PASSWORD, MT5_SERVER
        
        # Connect to MT5
        if not mt5.initialize():  # type: ignore
            print("ERROR Failed to initialize MT5")
            return False
        
        authorized = mt5.login(  # type: ignore
            login=MT5_LOGIN,
            password=MT5_PASSWORD,
            server=MT5_SERVER,
            timeout=30000
        )
        
        if not authorized:
            print("ERROR Failed to login to MT5")
            mt5.shutdown()  # type: ignore
            return False
        
        # Test each symbol
        for symbol in SYMBOLS:
            print(f"Testing symbol: {symbol}")
            
            # Try to select symbol
            if not mt5.symbol_select(symbol, True):  # type: ignore
                error = mt5.last_error()  # type: ignore
                print(f"ERROR Failed to select {symbol}: {error}")
                continue
            
            # Get symbol info
            symbol_info = mt5.symbol_info(symbol)  # type: ignore
            if symbol_info is None:
                print(f"ERROR No info available for {symbol}")
                continue
            
            # Check if symbol is visible
            if not symbol_info.visible:
                print(f"ERROR {symbol} is not visible in Market Watch")
                continue
            
            # Check if we can get tick data
            tick = mt5.symbol_info_tick(symbol)  # type: ignore
            if tick is None:
                print(f"ERROR No tick data available for {symbol}")
                continue
            
            print(f"OK {symbol} is available for trading")
            print(f"   Bid: {tick.bid}, Ask: {tick.ask}")
            print(f"   Spread: {(tick.ask - tick.bid):.5f}")
        
        mt5.shutdown()  # type: ignore
        return True
        
    except Exception as e:
        print(f"ERROR Symbol availability test error: {e}")
        return False

def test_strategy_components():
    """Test strategy components"""
    print("\nTesting strategy components...")
    
    try:
        from strategy.moving_average import MovingAverageStrategy
        from strategy.base import BaseStrategy
        import pandas as pd
        
        # Create test data
        test_data = pd.DataFrame({
            'open': [100, 101, 102, 103, 104],
            'high': [101, 102, 103, 104, 105],
            'low': [99, 100, 101, 102, 103],
            'close': [101, 102, 103, 104, 105],
            'volume': [1000, 1100, 1200, 1300, 1400]
        })
        
        # Test strategy creation
        strategy = MovingAverageStrategy(
            data=test_data,
            short_window=2,
            long_window=3,
            lot_size=0.01
        )
        
        # Test signal generation
        signals = strategy.generate_signals()
        
        if signals is not None and not signals.empty:
            print("OK Strategy signal generation successful")
            print(f"   Generated {len(signals)} signals")
            return True
        else:
            print("ERROR Strategy signal generation failed")
            return False
        
    except Exception as e:
        print(f"ERROR Strategy component test error: {e}")
        traceback.print_exc()
        return False

def test_trade_manager():
    """Test trade manager initialization"""
    print("\nTesting TradeManager...")
    
    try:
        from execution.trade_manager import TradeManager
        from config import DEFAULT_LOT_SIZE
        
        # This will test the TradeManager initialization
        # We'll use a try-catch to see if it fails
        try:
            trade_manager = TradeManager("XAUUSD", lot_size=DEFAULT_LOT_SIZE)
            print("OK TradeManager initialization successful")
            return True
        except Exception as e:
            print(f"ERROR TradeManager initialization failed: {e}")
            return False
        
    except Exception as e:
        print(f"ERROR TradeManager test error: {e}")
        return False

def main():
    """Run all diagnostic tests"""
    print("AlgoBot Diagnostic Tool")
    print("=" * 50)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    tests = [
        ("Module Imports", test_imports),
        ("Configuration", test_config),
        ("MT5 Connection", test_mt5_connection),
        ("Symbol Availability", test_symbol_availability),
        ("Strategy Components", test_strategy_components),
        ("Trade Manager", test_trade_manager)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"ERROR: {test_name} test crashed: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 50)
    print("DIAGNOSTIC RESULTS:")
    print("=" * 50)
    
    all_passed = True
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"{test_name}: {status}")
        if not result:
            all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("All tests passed! Your AlgoBot should work correctly.")
    else:
        print("Some tests failed. Please fix the issues before running the bot.")
        print("\nCommon solutions:")
        print("1. Install missing packages: pip install -r requirements.txt")
        print("2. Start MetaTrader 5 terminal")
        print("3. Check your MT5 login credentials in config.py")
        print("4. Ensure symbols are available in your MT5 account")
    
    return all_passed

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Diagnostic tool error: {e}")
        traceback.print_exc()
        sys.exit(1) 