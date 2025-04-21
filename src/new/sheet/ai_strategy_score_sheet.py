from src.new.sheet.sheet import Sheet
from dataclasses import dataclass, fields
from typing import List

@dataclass
class AiStrategyScoreSheetData:
    market: str
    version: int    
    pnl: float
    trade_count: int
    win_count: int
    entry_total_price: float
    fee: float
    elapsed_seconds: int
    
    def to_str_list(self) -> List[str]:
        return [
            self.market,
            str(self.version),
            str(self.pnl),
            str(self.trade_count),
            str(self.win_count),
            str(self.entry_total_price),
            str(self.fee),
            str(self.elapsed_seconds)
        ]
    
    @classmethod
    def from_str_list(cls, str_list: List[str]) -> 'AiStrategyScoreSheetData':
        return AiStrategyScoreSheetData(
            market=str_list[0],
            version=int(str_list[1]),
            pnl=float(str_list[2]),
            trade_count=int(str_list[3]),
            win_count=int(str_list[4]),
            entry_total_price=float(str_list[5]),
            fee=float(str_list[6]),
            elapsed_seconds=int(str_list[7])
        )
    
    @classmethod
    def from_dict(cls, dict: dict) -> 'AiStrategyScoreSheetData':
        return AiStrategyScoreSheetData(
            market=dict['market'],
            version=int(dict['version']),
            pnl=float(dict['pnl']),
            trade_count=int(dict['trade_count']),    
            win_count=int(dict['win_count']),    
            entry_total_price=float(dict['entry_total_price']),    
            fee=float(dict['fee']),    
            elapsed_seconds=int(dict['elapsed_seconds'])
        )
    
class AiStrategyScoreSheet(Sheet):
    def __init__(self):
        super().__init__()
        
    def get_sheet_name(self) -> str:
        return "Ai Strategy Score"
    
    def get_headers(self) -> list[str]:
        return [field.name for field in fields(AiStrategyScoreSheetData)]
    
    def append(self, data: AiStrategyScoreSheetData):
        self.trading_logger.append_values(self.get_sheet_name(), [data.to_str_list()])