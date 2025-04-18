from src.new.models.bithumb.response import Orderbook, Ticker
from src.new.api.bithumb.client import BithumbApiClient
from typing import List, Dict
import os


class ScalpingCandidateSelector:
    def __init__(self):
        self.bithumb_api = BithumbApiClient()

    def get_all_tickers(self) -> List[Ticker]:
        all_market_info = self.bithumb_api.get_all_market_info()
        ticker_list = []
        for i in range(0, len(all_market_info.market_info), 200):
            markets = ', '.join([market_info.market for market_info in all_market_info.market_info[i: i + 200]])
            res = self.bithumb_api.get_ticker(markets)
            ticker_list.extend(res.tickers)
        return ticker_list
    
    def is_orderbook_depth_sufficient(self, orderbook: Orderbook, depth: int = 5) -> bool:
        """매수·매도 호가 깊이 확인"""
        orderbook_units = orderbook.orderbook_units
        ask_prices = [float(item.ask_price) for item in orderbook_units]
        bid_prices = [float(item.bid_price) for item in orderbook_units]
        
        return (
            len(ask_prices) >= depth and
            len(bid_prices) >= depth
        )

    def estimate_tick_size(self, orderbook: Orderbook) -> float:
        """틱 크기 계산 (상위 2개의 호가 차이)"""
        try:
            ask_prices = [float(x.ask_price) for x in orderbook.orderbook_units[:2]]
            bid_prices = [float(x.bid_price) for x in orderbook.orderbook_units[:2]]
            if len(ask_prices) < 2 or len(bid_prices) < 2:
                return 0.0
            return max(abs(ask_prices[0] - ask_prices[1]), abs(bid_prices[0] - bid_prices[1]))
        except:
            return 0.0

    def is_scalping_candidate(self, ticker: Ticker):
        
        first_condition = ticker.acc_trade_price_24h > 10_000_000_000 and ticker.change_rate > 0.02 and ticker.acc_trade_volume_24h > 100_000 and ticker.trade_price > 100
        if not first_condition:
            return False
        
        orderbook = self.bithumb_api.get_orderbook(ticker.market)
        if not self.is_orderbook_depth_sufficient(orderbook.orderbooks[0]):
            return False
        
        tick_size = self.estimate_tick_size(orderbook.orderbooks[0])
        if tick_size < 1.0:
            return False
        
        return True

    def select_candidates(self) -> List[Ticker]:
        """최종 스캘핑 가능 코인 리스트 반환"""
        all_data = self.get_all_tickers()
        candidates = [ticker for ticker in all_data if self.is_scalping_candidate(ticker)]
        return candidates
