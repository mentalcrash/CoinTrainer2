from abc import ABC, abstractmethod
from typing import List, Tuple
from src.new.api.bithumb.client import BithumbApiClient
from src.new.models.bithumb.response import Candle, Ticker, Orderbook

class SignalStrategy(ABC):
    def __init__(self, market: str):
        self.market = market
        self.api_client = BithumbApiClient()
        
    @abstractmethod
    def should_buy(self) -> bool:
        """매수 시그널 발생 여부"""
        pass

    @abstractmethod
    def should_sell(self, current_price: float, target_price: float, stop_loss_price: float) -> Tuple[bool, str]:
        """매도 시그널 발생 여부"""
        pass