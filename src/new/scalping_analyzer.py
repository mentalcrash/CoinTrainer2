from src.models.order import OrderResponse
from src.new.strategy.parameter.signal_strategy import SignalStrategy
from typing import Optional
from dataclasses import dataclass
from datetime import datetime


# market=self.market,
#             entry_price=entry_order.price_per_unit,
#             exit_price=exit_order.price_per_unit,
#             volume=entry_order.total_volume,
#             pnl=pnl,
#             acc_pnl=self.acc_pnl,
#             trade_count=self.total_trade_count,
#             win_count=self.acc_win_count,
#             entry_total_price=self.acc_entry_total_price,
#             fee=self.acc_fee,
#             acc_elapsed_seconds=elapsed_seconds + self.acc_elapsed_seconds,
#             holding_seconds=holding_seconds,
#             should_stop=should_stop,
#             stop_reason=stop_reason

@dataclass
class Result:
    market: str
    entry_price: float
    exit_price: float
    volume: float
    pnl: float
    acc_pnl: float
    trade_count: int
    win_count: int
    entry_total_price: float
    holding_seconds: int
    acc_elapsed_seconds: int
    should_stop: bool
    fee: float
    stop_reason: Optional[str] = None
    entry_reason: Optional[str] = None
    exit_reason: Optional[str] = None
    
class ScalpingAnalyzer:
    MAX_CONSECUTIVE_LOSSES = 3
    MAX_PROFIT_RATE = -0.02

    def __init__(self,
                 market: str,
                 acc_pnl: float = 0,
                 total_trade_count: int = 0,
                 acc_win_count: int = 0,
                 acc_entry_total_price: float = 0,
                 acc_fee: float = 0,
                 acc_elapsed_seconds: int = 0):
        self.market = market
        self.acc_pnl = acc_pnl
        self.total_trade_count = total_trade_count
        self.acc_win_count = acc_win_count
        self.acc_entry_total_price = acc_entry_total_price
        self.acc_fee = acc_fee
        self.acc_elapsed_seconds = acc_elapsed_seconds
        
        self.consecutive_losses = 0
        self.created_at = datetime.now()
    
    def analyze(self, entry_order: OrderResponse, exit_order: OrderResponse, entry_reason: Optional[str] = None, exit_reason: Optional[str] = None) -> Result:
        pnl = ((exit_order.price_per_unit - entry_order.price_per_unit) * entry_order.total_volume)
        fee = float(entry_order.paid_fee) + float(exit_order.paid_fee)
        pnl -= fee
        
        if pnl > 0:
            self.acc_win_count += 1
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
        self.acc_pnl += pnl
        self.total_trade_count += 1
        
        self.acc_win_rate = self.acc_win_count / self.total_trade_count
        
        self.acc_entry_total_price += entry_order.price_per_unit * entry_order.total_volume
        
        # 수익률
        self.acc_profit_rate = self.acc_pnl / self.acc_entry_total_price
        self.acc_fee += fee
        
        holding_seconds = (exit_order.created_at - entry_order.created_at).total_seconds()
        
        elapsed_seconds = (datetime.now() - self.created_at).total_seconds()
        acc_elapsed_seconds = elapsed_seconds + self.acc_elapsed_seconds
        
        acc_hours = acc_elapsed_seconds / 60 / 60
        
        should_stop = False
        stop_reason = None
        win_rate = self.acc_win_count / self.total_trade_count
        if self.total_trade_count >= 5 and win_rate <= 0.1:
            should_stop = True
            stop_reason = "승률 초과, 총 5회 거래 후 승률 10% 이하"
        elif self.total_trade_count >= 10 and win_rate <= 0.25:
            should_stop = True
            stop_reason = "승률 초과, 총 10회 거래 후 승률 20% 이하"
        elif self.total_trade_count >= 15 and win_rate <= 0.4:
            should_stop = True
            stop_reason = "승률 초과, 총 15회 거래 후 승률 40% 이하"
        elif self.total_trade_count >= 20 and win_rate <= 0.5:
            should_stop = True
            stop_reason = "승률 초과, 총 20회 거래 후 승률 50% 이하"
        elif acc_hours >= 1 and self.total_trade_count <= 2:
            should_stop = True
            stop_reason = "총 거래 횟수 미달"
        
        return Result(
            market=self.market,
            entry_price=entry_order.price_per_unit,
            exit_price=exit_order.price_per_unit,
            volume=entry_order.total_volume,
            pnl=pnl,
            acc_pnl=self.acc_pnl,
            trade_count=self.total_trade_count,
            win_count=self.acc_win_count,
            entry_total_price=self.acc_entry_total_price,
            fee=self.acc_fee,
            acc_elapsed_seconds=elapsed_seconds + self.acc_elapsed_seconds,
            holding_seconds=holding_seconds,
            should_stop=should_stop,
            stop_reason=stop_reason,
            entry_reason=entry_reason,
            exit_reason=exit_reason
        )