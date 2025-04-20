from abc import ABC, abstractmethod
from src.trading_logger import TradingLogger
from typing import List, Dict


class Sheet(ABC):
    def __init__(self):
        self.trading_logger = TradingLogger()
        self.trading_logger.create_sheet(self.get_sheet_name(), self.get_headers())
    
    def get_data_many(self, conditions: dict) -> List[Dict]:
        data = self.trading_logger.query_many(conditions=conditions, sheet_name=self.get_sheet_name())    
        if data:
            return data
        return None
    
    def update_data(self, conditions: dict, updates: dict) -> Dict:
        data = self.trading_logger.update_data(conditions=conditions, updates=updates, sheet_name=self.get_sheet_name())
        if data:
            return data
        return None
    
    @abstractmethod
    def append(self, data: dict):
        pass
    
    @abstractmethod
    def get_sheet_name(self) -> str:
        pass
    
    @abstractmethod
    def get_headers(self) -> list[str]:
        pass
    
    