from src.new.sheet.sheet import Sheet
from dataclasses import dataclass
from typing import List

@dataclass
class StrategyScoreSheetData:
    strategy: str
    market: str
    document_version: int
    version: int    
    pnl: float
    profit_rate: float
    trade_count: int
    win_count: int
    loss_count: int
    win_rate: float
    loss_rate: float
    entry_total_price: float
    exit_total_price: float
    elapsed_seconds: int
    
    def to_str_list(self) -> List[str]:
        return [
            str(self.strategy),
            self.market,
            str(self.document_version),
            str(self.version),
            str(self.pnl),
            str(self.profit_rate),
            str(self.trade_count),
            str(self.win_count),
            str(self.loss_count),
            str(self.win_rate),
            str(self.loss_rate),
            str(self.entry_total_price),
            str(self.exit_total_price),
            str(self.elapsed_seconds)
        ]
    
    @classmethod
    def from_str_list(cls, str_list: List[str]) -> 'StrategyScoreSheetData':
        return StrategyScoreSheetData(
            strategy=str_list[0],
            market=str_list[1],
            document_version=int(str_list[2]),
            version=int(str_list[3]),
            pnl=float(str_list[4]),
            profit_rate=float(str_list[5]),
            trade_count=int(str_list[6]),
            win_count=int(str_list[7]),
            loss_count=int(str_list[8]),
            win_rate=float(str_list[9]),
            loss_rate=float(str_list[10]),
            entry_total_price=float(str_list[11]),
            exit_total_price=float(str_list[12]),
            elapsed_seconds=int(str_list[13])
        )
    
    @classmethod
    def from_dict(cls, dict: dict) -> 'StrategyScoreSheetData':
        return StrategyScoreSheetData(
            strategy=dict['strategy'],
            market=dict['market'],
            document_version=int(dict['document_version']),
            version=int(dict['version']),
            pnl=float(dict['pnl']),
            profit_rate=float(dict['profit_rate']),    
            trade_count=int(dict['trade_count']),    
            win_count=int(dict['win_count']),    
            loss_count=int(dict['loss_count']),    
            win_rate=float(dict['win_rate']),    
            loss_rate=float(dict['loss_rate']),    
            entry_total_price=float(dict['entry_total_price']),    
            exit_total_price=float(dict['exit_total_price']),    
            elapsed_seconds=int(dict['elapsed_seconds'])
        )
    
class StrategyScoreSheet(Sheet):
    def __init__(self):
        super().__init__()
        
    def get_sheet_name(self) -> str:
        return "Strategy Score"
    
    def get_headers(self) -> list[str]:
        return ["strategy", "market", "document_version", "version", "pnl", "profit_rate", "trade_count", "win_count", "loss_count", "win_rate", "loss_rate", "entry_total_price", "exit_total_price", "elapsed_seconds"]
    
    def append(self, data: StrategyScoreSheetData):
        self.trading_logger.append_values(self.get_sheet_name(), [data.to_str_list()])