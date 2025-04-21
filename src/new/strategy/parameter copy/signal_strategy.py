from abc import ABC, abstractmethod
from typing import List, Tuple
from src.new.api.bithumb.client import BithumbApiClient
from src.new.models.bithumb.response import Candle, Ticker, Orderbook
from src.new.strategy.strategy_params import StrategyParams
from src.new.calculator.target_calculator import TargetCalculator

class SignalStrategy(ABC):
    def __init__(self, market: str, params: StrategyParams):
        self.api_client = BithumbApiClient()
        self.market = market
        self.target_calculator = TargetCalculator(self.market)
        self.params = params
        
        self.entry_price: float = None
        self.target_price: float = None
        self.stop_loss_price: float = None
    
    @abstractmethod
    def get_name(self) -> str:
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        pass
      
    @abstractmethod
    def should_buy(self) -> bool:
        """매수 시그널 발생 여부"""
        pass

    @abstractmethod
    def should_sell(self, current_price: float) -> Tuple[bool, str]:
        pass
    
    def set_entry_price(self, price: float):
        self.entry_price = price
        self.target_price, self.stop_loss_price = self.target_calculator.calculate(self.entry_price)
    
    def update_params(self, params: StrategyParams):
        """파라미터 업데이트"""
        self.params = params