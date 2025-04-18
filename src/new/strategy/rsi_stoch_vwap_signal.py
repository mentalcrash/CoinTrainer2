from src.new.strategy.signal_strategy import SignalStrategy
from src.new.models.bithumb.response import Candle, Ticker, Orderbook
from src.new.calculator.rsi_calculator import RSICalculator
from src.new.calculator.stoch_rsi_calculator import StochRSICalculator
from src.new.calculator.vwap_calculator import VWAPCalculator

class RSIStochVWAPSignal(SignalStrategy):
    def should_buy(self) -> bool:
        if len(self.candles) < 30:
            return False

        # 1. RSI 50선 돌파
        rsi = RSICalculator(self.candles).calculate(period=14)
        is_rsi_break = rsi[-2] < 50 and rsi[-1] >= 50

        # 2. StochRSI 골든크로스
        stoch_k, stoch_d = StochRSICalculator(self.candles).calculate(stoch_period=14)
        is_stoch_cross = stoch_k[-2] < stoch_d[-2] and stoch_k[-1] > stoch_d[-1]

        # 3. VWAP 상회
        vwap = VWAPCalculator(self.candles).calculate(period=20)
        current_price = self.candles[-1].trade_price
        is_above_vwap = current_price > vwap[-1]

        # 종합 판단
        return is_rsi_break and is_stoch_cross and is_above_vwap

    def should_sell(self, current_price: float, target_price: float, stop_loss_price: float, hold_force: bool = False) -> bool:
        if current_price >= target_price:
            return True
        elif hold_force:
            return False
        elif current_price <= stop_loss_price:
            return True
        else:
            # RSI가 50 아래로 내려가면 조정 가능성
            rsi = RSICalculator(self.candles).calculate(period=14)
            return rsi[-1] < 50