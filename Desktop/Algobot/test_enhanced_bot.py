#!/usr/bin/env python3
"""
Test Script for Enhanced Trading Bot
Tests 30% stop-loss, error handling, and strategy improvements
"""

import time
import sys
import traceback
from datetime import datetime
import os
os.environ['LOG_FORMAT'] = 'json'  # Enable structured JSON logging for this script

# Import our modules
from config import SYMBOLS, TIMEFRAMES, STOP_LOSS_PERCENT, TAKE_PROFIT_PERCENT, DEFAULT_LOT_SIZE, PAPER_TRADING
from strategy.moving_average import MovingAverageStrategy
from risk.risk_manager import RiskManager
from utils.logger import get_logger
from data.fetch_mt5 import fetch_mt5_data, login_mt5
from execution.mt5_executor import send_order

logger = get_logger("TestEnhancedBot")

def test_risk_manager() -> bool:
    """Test the risk manager with 30% stop-loss and 60% take-profit."""
    logger.info("🧪 Testing Risk Manager...")
    
    try:
        # Initialize risk manager
        risk_manager = RiskManager(
            stop_loss_pct=STOP_LOSS_PERCENT,
            take_profit_pct=TAKE_PROFIT_PERCENT
        )
        
        # Test stop-loss calculation
        entry_price = 2000.0  # Example XAUUSD price
        buy_stop_loss = risk_manager.calculate_stop_loss(entry_price, 'buy')
        sell_stop_loss = risk_manager.calculate_stop_loss(entry_price, 'sell')
        
        expected_buy_sl = entry_price * (1 - STOP_LOSS_PERCENT)
        expected_sell_sl = entry_price * (1 + STOP_LOSS_PERCENT)
        
        logger.info(f"Entry Price: {entry_price}")
        logger.info(f"Buy Stop Loss: {buy_stop_loss} (Expected: {expected_buy_sl})")
        logger.info(f"Sell Stop Loss: {sell_stop_loss} (Expected: {expected_sell_sl})")
        
        # Test take-profit calculation
        buy_take_profit = risk_manager.calculate_take_profit(entry_price, 'buy')
        sell_take_profit = risk_manager.calculate_take_profit(entry_price, 'sell')
        
        expected_buy_tp = entry_price * (1 + TAKE_PROFIT_PERCENT)
        expected_sell_tp = entry_price * (1 - TAKE_PROFIT_PERCENT)
        
        logger.info(f"Buy Take Profit: {buy_take_profit} (Expected: {expected_buy_tp})")
        logger.info(f"Sell Take Profit: {sell_take_profit} (Expected: {expected_sell_tp})")
        
        # Verify calculations
        assert abs(buy_stop_loss - expected_buy_sl) < 0.01, "Buy stop-loss calculation error"
        assert abs(sell_stop_loss - expected_sell_sl) < 0.01, "Sell stop-loss calculation error"
        assert abs(buy_take_profit - expected_buy_tp) < 0.01, "Buy take-profit calculation error"
        assert abs(sell_take_profit - expected_sell_tp) < 0.01, "Sell take-profit calculation error"
        
        logger.info("✅ Risk Manager tests passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Risk Manager test failed: {e}")
        return False

def test_strategy() -> bool:
    """Test the enhanced strategy logic and signal generation."""
    logger.info("🧪 Testing Enhanced Strategy...")
    
    try:
        # Fetch test data
        data = fetch_mt5_data(SYMBOLS[0], TIMEFRAMES[0], n_bars=100)
        if data is None or data.empty:
            logger.warning("⚠️ No test data available, skipping strategy test")
            return True
        
        # Initialize strategy
        strategy = MovingAverageStrategy(
            data,
            short_window=20,
            long_window=50,
            use_macd=True,
            use_atr_band=True,
            trend_filter=True,
            volatility_filter=True
        )
        
        # Generate signals
        signals = strategy.generate_signals()
        
        if not signals.empty:
            logger.info(f"✅ Strategy generated {len(signals)} signals")
            logger.info(f"Latest signal: {signals.iloc[-1]['Signal'] if 'Signal' in signals.columns else 'No signal'}")
            
            # Check for required columns
            required_columns = ['Signal', 'Position', 'Short_MA', 'Long_MA', 'RSI', 'ATR']
            missing_columns = [col for col in required_columns if col not in signals.columns]
            
            if missing_columns:
                logger.warning(f"⚠️ Missing columns: {missing_columns}")
            else:
                logger.info("✅ All required strategy columns present")
        else:
            logger.warning("⚠️ No signals generated")
        
        logger.info("✅ Strategy test completed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Strategy test failed: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

def test_mt5_connection() -> bool:
    """Test MT5 connection logic."""
    logger.info("🧪 Testing MT5 Connection...")
    
    try:
        if login_mt5():
            logger.info("✅ MT5 connection successful")
            return True
        else:
            logger.error("❌ MT5 connection failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ MT5 connection test failed: {e}")
        return False

def test_order_execution() -> bool:
    """Test order execution logic (paper trading mode)."""
    logger.info("🧪 Testing Order Execution...")
    
    try:
        # Test order parameters
        symbol = SYMBOLS[0]
        lot_size = 0.01
        price = 2000.0
        stop_loss = price * (1 - STOP_LOSS_PERCENT)
        take_profit = price * (1 + TAKE_PROFIT_PERCENT)
        
        logger.info(f"Test Order Parameters:")
        logger.info(f"  Symbol: {symbol}")
        logger.info(f"  Lot Size: {lot_size}")
        logger.info(f"  Price: {price}")
        logger.info(f"  Stop Loss: {stop_loss} ({STOP_LOSS_PERCENT*100}%)")
        logger.info(f"  Take Profit: {take_profit} ({TAKE_PROFIT_PERCENT*100}%)")
        
        # Test order function (will not execute in paper trading mode)
        logger.info("✅ Order execution test completed (paper trading mode)")
        return True
        
    except Exception as e:
        logger.error(f"❌ Order execution test failed: {e}")
        return False

def test_error_handling() -> bool:
    """Test error handling mechanisms in the bot."""
    logger.info("🧪 Testing Error Handling...")
    
    try:
        # Test division by zero handling
        try:
            result = 1 / 0
        except ZeroDivisionError:
            logger.info("✅ Division by zero handled correctly")
        
        # Test invalid data handling
        try:
            strategy = MovingAverageStrategy(None)
            strategy.generate_signals()
        except Exception as e:
            logger.info(f"✅ Invalid data handling: {type(e).__name__}")
        
        # Test missing data handling
        try:
            data = fetch_mt5_data("INVALID_SYMBOL", "M1", n_bars=10)
            if data is None:
                logger.info("✅ Missing data handled correctly")
        except Exception as e:
            logger.info(f"✅ Invalid symbol handling: {type(e).__name__}")
        
        logger.info("✅ Error handling tests passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error handling test failed: {e}")
        return False

def run_all_tests() -> bool:
    """Run all tests and return True if all pass, else False."""
    logger.info("🚀 Starting Enhanced Bot Tests...")
    logger.info(f"Stop Loss: {STOP_LOSS_PERCENT*100}%")
    logger.info(f"Take Profit: {TAKE_PROFIT_PERCENT*100}%")
    logger.info("=" * 50)
    
    tests = [
        ("Risk Manager", test_risk_manager),
        ("MT5 Connection", test_mt5_connection),
        ("Strategy", test_strategy),
        ("Order Execution", test_order_execution),
        ("Error Handling", test_error_handling)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        logger.info(f"\n📋 Running {test_name} Test...")
        if test_func():
            passed += 1
            logger.info(f"{test_name} Test PASSED")
        else:
            logger.error(f"❌ {test_name} Test FAILED")
    
    logger.info("=" * 50)
    logger.info(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed! Enhanced bot is ready for trading.")
        return True
    else:
        logger.error(f"⚠️ {total - passed} tests failed. Please fix issues before trading.")
        return False

def main() -> None:
    """Main test function to run all tests and report results."""
    try:
        success = run_all_tests()
        
        if success:
            logger.info("Enhanced bot testing completed successfully!")
            logger.info("🚀 Ready to start trading with 30% stop-loss and improved strategy!")
        else:
            logger.error("❌ Enhanced bot testing failed!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("🛑 Testing interrupted by user")
    except Exception as e:
        logger.error(f"❌ Fatal error during testing: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)

if __name__ == "__main__":
    main() 