#!/usr/bin/env python3
"""
Start Enhanced Trading Bot
Simple script to start the enhanced trading bot with 30% stop-loss
"""

import sys
import os
from datetime import datetime

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

os.environ['LOG_FORMAT'] = 'json'  # Enable structured JSON logging for this script

try:
    from enhanced_trader import EnhancedTrader
    from config import STOP_LOSS_PERCENT, TAKE_PROFIT_PERCENT, SYMBOLS, PAPER_TRADING, MAX_POSITIONS
    from utils.logger import get_logger
    
    logger = get_logger("StartEnhancedBot")
    
    def main() -> None:
        """
        Start the enhanced trading bot using centralized config values.
        """
        logger.info("🚀 Starting Enhanced Trading Bot...")
        logger.info(f"📊 Configuration:")
        logger.info(f"   Stop Loss: {STOP_LOSS_PERCENT*100}%")
        logger.info(f"   Take Profit: {TAKE_PROFIT_PERCENT*100}%")
        logger.info(f"   Symbols: {SYMBOLS}")
        logger.info(f"   Time: {datetime.now()}")
        logger.info("=" * 50)
        # Initialize and start the enhanced trader
        trader = EnhancedTrader(
            paper_trading=PAPER_TRADING,  # Use config value
            max_positions=MAX_POSITIONS
        )
        try:
            trader.start()
        except KeyboardInterrupt:
            logger.info("🛑 Shutdown requested by user")
            trader.stop()
        except Exception as e:
            logger.error(f"❌ Fatal error: {e}")
            trader.stop()
            sys.exit(1)
    
    if __name__ == "__main__":
        main()
        
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Please ensure all required modules are available")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error starting enhanced bot: {e}")
    sys.exit(1) 