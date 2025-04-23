from abc import ABC, abstractmethod
from typing import List, Tuple
from src.new.api.bithumb.client import BithumbApiClient
from src.new.models.bithumb.response import Candle, Ticker, Orderbook
from src.new.strategy.strategy_params import StrategyParams
from src.new.calculator.target_calculator import TargetCalculator
import logging

class SignalStrategy(ABC):
    def __init__(self, market: str, params: StrategyParams):
        self.api_client = BithumbApiClient()
        self.market = market
        self.target_calculator = TargetCalculator(self.market)
        self.params = params
        
        self.entry_price: float = None
        self.target_price: float = None
        self.stop_loss_price: float = None
        self.logger = logging.getLogger()
    
    @abstractmethod
    def get_name(self) -> str:
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        pass
      
    @abstractmethod
    def should_buy(self) -> Tuple[bool, float, float]:
        """매수 시그널 발생 여부"""
        pass

    def should_sell(self, current_price: float) -> Tuple[bool, str]:
        if current_price >= self.target_price:
            return True, f'목표가에 도달했습니다\n현재가 {int(current_price)}, 목표가 {int(self.target_price)}'
        elif current_price <= self.stop_loss_price:
            return True, f'손절가에 도달했습니다\n현재가 {int(current_price)}, 손절가 {int(self.stop_loss_price)}'
        return False, "매도 신호 없음"
    
    def set_entry_price(self, price: float):
        self.entry_price = price
        self.target_price, self.stop_loss_price = self.target_calculator.calculate(self.entry_price)
    
    def update_params(self, params: StrategyParams):
        """파라미터 업데이트"""
        self.params = params
        
    def set_target_and_stop_loss_price(self, entry_price: float, target_price: float, stop_loss_price: float):
        self.entry_price = entry_price
        self.target_price = target_price
        self.stop_loss_price = stop_loss_price