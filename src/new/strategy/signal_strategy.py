from abc import ABC, abstractmethod
from typing import List
from src.new.models.bithumb.response import Candle, Ticker, Orderbook

class SignalStrategy(ABC):
    def __init__(self, candles: List[Candle], ticker: Ticker, orderbook: Orderbook):
        self.candles = sorted(candles, key=lambda c: c.timestamp)
        self.ticker = ticker
        self.orderbook = orderbook
        
        print(self.candles)

    @abstractmethod
    def should_buy(self) -> bool:
        """매수 시그널 발생 여부"""
        pass

    @abstractmethod
    def should_sell(self, current_price: float, target_price: float, stop_loss_price: float) -> bool:
        """매도 시그널 발생 여부"""
        pass