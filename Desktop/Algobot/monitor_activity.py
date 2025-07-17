#!/usr/bin/env python3
"""
Monitor Trading Bot Activity
Check current status and trading activity
"""

import time
import sys
from datetime import datetime
from data.fetch_mt5 import get_account_info, login_mt5
from execution.mt5_executor import get_open_positions
from utils.logger import get_logger

logger = get_logger("MonitorActivity")

def check_bot_status():
    """Check the current bot status and trading activity"""
    try:
        # Check MT5 connection
        if not login_mt5():
            logger.error("❌ Failed to connect to MT5")
            return False
        
        # Get account info
        account_info = get_account_info()
        if account_info:
            logger.info("📊 Account Status:")
            logger.info(f"   Balance: ${account_info.get('balance', 0.0):.2f}")
            logger.info(f"   Equity: ${account_info.get('equity', 0.0):.2f}")
            logger.info(f"   Profit: ${account_info.get('profit', 0.0):.2f}")
            logger.info(f"   Margin: ${account_info.get('margin', 0.0):.2f}")
            logger.info(f"   Free Margin: ${account_info.get('free_margin', 0.0):.2f}")
        
        # Get open positions
        positions = get_open_positions()
        if positions:
            logger.info(f"📈 Open Positions: {len(positions)}")
            for pos in positions:
                logger.info(f"   {pos.symbol}: {pos.type} {pos.volume} lots at {pos.price_open}")
                logger.info(f"      Stop Loss: {pos.sl}, Take Profit: {pos.tp}")
                logger.info(f"      Profit: ${pos.profit:.2f}")
        else:
            logger.info("📉 No open positions")
        
        # Check current time and trading hours
        current_time = datetime.now()
        logger.info(f"⏰ Current Time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error checking bot status: {e}")
        return False

def monitor_continuously():
    """Monitor bot activity continuously"""
    logger.info("🔍 Starting continuous monitoring...")
    logger.info("Press Ctrl+C to stop monitoring")
    
    try:
        while True:
            print("\n" + "="*50)
            print(f"📊 BOT STATUS CHECK - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("="*50)
            
            check_bot_status()
            
            print("\n⏳ Waiting 30 seconds for next check...")
            time.sleep(30)
            
    except KeyboardInterrupt:
        logger.info("🛑 Monitoring stopped by user")
    except Exception as e:
        logger.error(f"❌ Monitoring error: {e}")

def main():
    """Main monitoring function"""
    logger.info("🚀 Starting Bot Activity Monitor...")
    
    if len(sys.argv) > 1 and sys.argv[1] == "continuous":
        monitor_continuously()
    else:
        # Single status check
        check_bot_status()
        logger.info("✅ Status check completed")

if __name__ == "__main__":
    main() 