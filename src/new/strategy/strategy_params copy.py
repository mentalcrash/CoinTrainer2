from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import List, Tuple
from src.new.api.bithumb.client import BithumbApiClient
from src.new.models.bithumb.response import Candle, Ticker, Orderbook

class StrategyParams(ABC):
    document_version: int = 1
    version: int = 1
    
    @abstractmethod
    def get_prompt(self) -> str:
        pass
    
    @abstractmethod
    def to_str_list(self) -> List[str]:
        pass
    
    @abstractmethod
    def from_str_list(self, str_list: List[str]) -> 'StrategyParams':
        pass
    
    @abstractmethod
    def from_dict(self, dict: dict) -> 'StrategyParams':
        pass

