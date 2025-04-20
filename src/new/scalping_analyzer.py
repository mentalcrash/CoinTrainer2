from src.models.order import OrderResponse
from src.new.strategy.parameter.signal_strategy import SignalStrategy
from typing import Optional
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Result:
    entry_price: float
    exit_price: float
    volume: float
    pnl: float
    profit_rate: float
    acc_pnl: float
    trade_count: int
    win_count: int
    loss_count: int
    win_rate: float
    loss_rate: float
    entry_total_price: float
    exit_total_price: float
    acc_profit_rate: float
    holding_seconds: int
    acc_elapsed_seconds: int
    should_stop: bool
    stop_reason: Optional[str] = None
    
    
class ScalpingAnalyzer:
    MAX_CONSECUTIVE_LOSSES = 3
    MAX_PROFIT_RATE = -0.02

    def __init__(self,
                 market: str,
                 acc_pnl: float = 0,
                 total_trade_count: int = 0,
                 acc_win_count: int = 0,
                 acc_loss_count: int = 0,
                 acc_win_rate: float = 0,
                 acc_loss_rate: float = 0,
                 acc_entry_total_price: float = 0,
                 acc_exit_total_price: float = 0,
                 acc_profit_rate: float = 0,
                 acc_elapsed_seconds: int = 0):
        self.market = market
        self.acc_pnl = acc_pnl
        self.total_trade_count = total_trade_count
        self.acc_win_count = acc_win_count
        self.acc_loss_count = acc_loss_count
        self.acc_win_rate = acc_win_rate
        self.acc_loss_rate = acc_loss_rate
        self.acc_entry_total_price = acc_entry_total_price
        self.acc_exit_total_price = acc_exit_total_price
        self.acc_profit_rate = acc_profit_rate
        self.acc_elapsed_seconds = acc_elapsed_seconds
        
        self.consecutive_losses = 0
        self.created_at = datetime.now()
    
    def analyze(self, entry_order: OrderResponse, exit_order: OrderResponse) -> Result:
        pnl = ((exit_order.price_per_unit - entry_order.price_per_unit) * entry_order.total_volume) - float(entry_order.paid_fee) - float(exit_order.paid_fee)
        profit_rate = pnl / entry_order.price_per_unit * entry_order.total_volume 
        
        if pnl > 0:
            self.acc_win_count += 1
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
            self.acc_loss_count += 1
        self.acc_pnl += pnl
        self.total_trade_count += 1
        
        self.acc_win_rate = self.acc_win_count / self.total_trade_count
        self.acc_loss_rate = self.acc_loss_count / self.total_trade_count
        
        self.acc_entry_total_price += entry_order.price_per_unit * entry_order.total_volume
        self.acc_exit_total_price += exit_order.price_per_unit * exit_order.total_volume - float(exit_order.paid_fee) - float(entry_order.paid_fee)
        
        # 수익률
        self.acc_profit_rate += (self.acc_exit_total_price - self.acc_entry_total_price) / self.acc_entry_total_price
        
        holding_seconds = (exit_order.created_at - entry_order.created_at).total_seconds()
        
        elapsed_seconds = (datetime.now() - self.created_at).total_seconds()
        
        should_stop = False
        stop_reason = None
        if self.consecutive_losses >= self.MAX_CONSECUTIVE_LOSSES:
            should_stop = True
            stop_reason = "연속 손실 횟수 초과"
        elif self.acc_profit_rate <= self.MAX_PROFIT_RATE:
            should_stop = True
            stop_reason = "손실률 초과"
        
        return Result(
            entry_price=entry_order.price_per_unit,
            exit_price=exit_order.price_per_unit,
            volume=entry_order.total_volume,
            pnl=pnl,
            profit_rate=profit_rate,
            acc_pnl=self.acc_pnl,
            trade_count=self.total_trade_count,
            win_count=self.acc_win_count,
            loss_count=self.acc_loss_count,
            win_rate=self.acc_win_rate,
            loss_rate=self.acc_loss_rate,
            entry_total_price=self.acc_entry_total_price,
            exit_total_price=self.acc_exit_total_price,
            acc_profit_rate=self.acc_profit_rate,
            holding_seconds=holding_seconds,
            acc_elapsed_seconds=elapsed_seconds + self.acc_elapsed_seconds,
            should_stop=should_stop,
            stop_reason=stop_reason
        )