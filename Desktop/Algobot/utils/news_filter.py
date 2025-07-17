"""
News Filter Module
Avoid trading during high-impact news events
"""

import pandas as pd
from datetime import datetime, timedelta
from utils.logger import get_logger
from config import AVOID_NEWS, MINUTES_BEFORE_NEWS, MINUTES_AFTER_NEWS

logger = get_logger("NewsFilter")

class NewsFilter:
    def __init__(self):
        self.news_events = []
        self.is_enabled = AVOID_NEWS
        
    def add_news_event(self, event_time, currency, impact="high", description=""):
        """Add a news event to the filter."""
        event = {
            'time': event_time,
            'currency': currency,
            'impact': impact,
            'description': description
        }
        self.news_events.append(event)
        logger.info(f"Added news event: {currency} at {event_time} ({impact} impact)")
    
    def is_news_time(self, symbol, current_time=None):
        """Check if current time is near a news event for the symbol's currency."""
        if not self.is_enabled:
            return False
            
        if current_time is None:
            current_time = datetime.now()
            
        # Extract currency from symbol
        currency = self._extract_currency(symbol)
        if not currency:
            return False
            
        # Check for news events in the time window
        for event in self.news_events:
            if event['currency'] == currency and event['impact'] == 'high':
                event_time = event['time']
                time_diff = abs((current_time - event_time).total_seconds() / 60)
                
                if time_diff <= (MINUTES_BEFORE_NEWS + MINUTES_AFTER_NEWS):
                    logger.warning(f"News filter active: {currency} news at {event_time}")
                    return True
                    
        return False
    
    def _extract_currency(self, symbol):
        """Extract currency from symbol (e.g., XAUUSD -> USD)."""
        if symbol.startswith('XAU'):
            return 'USD'  # Gold is typically quoted in USD
        elif len(symbol) >= 6:
            return symbol[3:6]  # Extract base currency
        return None
    
    def get_safe_trading_window(self, symbol):
        """Get the next safe trading window for a symbol."""
        if not self.is_enabled:
            return True
            
        currency = self._extract_currency(symbol)
        if not currency:
            return True
            
        current_time = datetime.now()
        
        # Find the next news event for this currency
        for event in sorted(self.news_events, key=lambda x: x['time']):
            if event['currency'] == currency and event['impact'] == 'high':
                event_time = event['time']
                
                # If we're before the news event
                if current_time < event_time:
                    time_to_news = (event_time - current_time).total_seconds() / 60
                    if time_to_news > MINUTES_BEFORE_NEWS:
                        return True
                    else:
                        return False
                        
        return True
    
    def load_news_calendar(self, calendar_data):
        """Load news calendar from external data source."""
        # This would integrate with a news API or calendar
        # For now, we'll use a simple implementation
        pass 