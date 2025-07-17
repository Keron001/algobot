import MetaTrader5 as mt5
from utils.logger import get_logger
from config import MT5_LOGIN, MT5_PASSWORD, MT5_SERVER, MT5_TIMEOUT, MAGIC_NUMBER, DEVIATION
from data.fetch_mt5 import login_mt5

logger = get_logger("MT5Executor")

def send_order(symbol, lot, order_type, price, sl=None, tp=None, comment="AlgoBot"):
    """Send order to MT5 with proper login and error handling"""
    if not login_mt5():
        logger.error("Failed to login to MT5 for order execution")
        return None
    
    try:
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot,
            "type": order_type,
            "price": price,
            "deviation": DEVIATION,
            "magic": MAGIC_NUMBER,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        if sl:
            request["sl"] = sl
        if tp:
            request["tp"] = tp
            
        result = mt5.order_send(request)
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Order send failed: {result.retcode} - {result.comment}")
            return None
        else:
            logger.info(f"Order sent successfully: {symbol} {lot} lots at {price}")
            return result
            
    except Exception as e:
        logger.error(f"Error sending order: {e}")
        return None
    finally:
        mt5.shutdown()

def get_open_positions():
    """Get all open positions for the bot"""
    if not login_mt5():
        return []
    
    try:
        positions = mt5.positions_get()
        if positions is None:
            logger.error("Failed to get open positions")
            return []
        
        # Filter positions by magic number
        bot_positions = [pos for pos in positions if pos.magic == MAGIC_NUMBER]
        logger.info(f"Found {len(bot_positions)} open positions for bot")
        return bot_positions
        
    except Exception as e:
        logger.error(f"Error getting open positions: {e}")
        return []
    finally:
        mt5.shutdown()

def close_position(ticket):
    """Close a specific position by ticket"""
    if not login_mt5():
        return False
    
    try:
        position = mt5.positions_get(ticket=ticket)
        if not position:
            logger.error(f"Position with ticket {ticket} not found")
            return False
        
        position = position[0]
        
        # Determine order type for closing
        if position.type == mt5.POSITION_TYPE_BUY:
            order_type = mt5.ORDER_TYPE_SELL
            price = mt5.symbol_info_tick(position.symbol).bid
        else:
            order_type = mt5.ORDER_TYPE_BUY
            price = mt5.symbol_info_tick(position.symbol).ask
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": position.symbol,
            "volume": position.volume,
            "type": order_type,
            "position": ticket,
            "price": price,
            "deviation": DEVIATION,
            "magic": MAGIC_NUMBER,
            "comment": "AlgoBot Close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Failed to close position {ticket}: {result.retcode}")
            return False
        else:
            logger.info(f"Successfully closed position {ticket}")
            return True
            
    except Exception as e:
        logger.error(f"Error closing position {ticket}: {e}")
        return False
    finally:
        mt5.shutdown() 

def update_stop_loss(symbol, new_sl):
    """Update the stop loss for an open position by symbol."""
    if not login_mt5():
        logger.error("Failed to login to MT5 for SL update")
        return False
    try:
        positions = mt5.positions_get(symbol=symbol)
        if not positions or len(positions) == 0:
            logger.error(f"No open position found for {symbol} to update SL")
            return False
        position = positions[0]  # Assume one position per symbol for this bot
        result = mt5.order_send({
            "action": mt5.TRADE_ACTION_SLTP,
            "position": position.ticket,
            "symbol": symbol,
            "sl": new_sl,
            "tp": position.tp,
            "magic": MAGIC_NUMBER,
            "comment": "Trailing Stop Update",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        })
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Failed to update SL for {symbol}: {result.retcode} - {result.comment}")
            return False
        else:
            logger.info(f"Stop loss updated for {symbol} to {new_sl}")
            return True
    except Exception as e:
        logger.error(f"Error updating stop loss for {symbol}: {e}")
        return False
    finally:
        mt5.shutdown() 