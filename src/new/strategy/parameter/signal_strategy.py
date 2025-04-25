from src.new.models.bithumb.response import Trade
from abc import ABC, abstractmethod
from typing import List, Tuple
from src.new.api.bithumb.client import BithumbApiClient
from src.new.strategy.strategy_params import StrategyParams
from src.new.calculator.target_calculator import TargetCalculator
from datetime import datetime, timedelta
import logging
from math import ceil, floor

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
    def should_buy(self) -> Tuple[bool, str]:
        """매수 시그널 발생 여부"""
        pass

    def should_sell(self, current_price: float) -> Tuple[bool, str]:
        if self.target_price is None:   # 포지션이 없을 때
            return False, "포지션 없음"

        if current_price >= self.target_price:
            return True, f"목표가 도달 – 현재가 {int(current_price)}, 목표가 {int(self.target_price)}"
        if current_price <= self.stop_loss_price:
            return True, f"손절가 도달 – 현재가 {int(current_price)}, 손절가 {int(self.stop_loss_price)}"
        if datetime.now() - self.entry_time > timedelta(minutes=5):
            return True, "10초 경과 – 시간 기반 청산"

        # (선택) 추가 Trailing-Stop · 호가창 급변 로직 위치
        return False, "매도 신호 없음"
        
    def set_entry_price(self, price: float) -> Tuple[float, float]:
        # 필요하다면 초봉 데이터 생서
        trades: List[Trade] = self.api_client.get_trades(self.market, count=200).trades
        trades.sort(key=lambda x: x.timestamp)
        
        orderbook = self.api_client.get_orderbook(self.market).orderbooks[0]
        tick_size = abs(float(orderbook.orderbook_units[0].ask_price) -
                        float(orderbook.orderbook_units[1].ask_price))
        # ==== 파라미터 ====
        take_ticks = 3
        stop_ticks = 2
        take_rate = 0.002
        stop_rate = 0.001
        # ================

        target_by_tick = ceil(price + tick_size * take_ticks)
        stop_by_tick   = floor(price - tick_size * stop_ticks)
        target_by_rate = ceil(price * (1 + take_rate))
        stop_by_rate   = floor(price * (1 - stop_rate))

        self.entry_price = price
        self.target_price = max(target_by_tick, target_by_rate)
        self.stop_loss_price = min(stop_by_tick, stop_by_rate)
        self.entry_time = datetime.now()

        return self.target_price, self.stop_loss_price
    
    def update_params(self, params: StrategyParams):
        """파라미터 업데이트"""
        self.params = params
        
    def set_target_and_stop_loss_price(self, entry_price: float, target_price: float, stop_loss_price: float):
        self.entry_time = datetime.now()
        self.entry_price = entry_price
        self.target_price = target_price
        self.stop_loss_price = stop_loss_price
        
        
        
        
        
        # **Candle**
        # market: str #  시장 정보 (예: KRW-BTC)
        # candle_date_time_utc: str # UTC 기준 캔들 생성 시각
        # candle_date_time_kst: str # KST 기준 캔들 생성 시각
        # opening_price: float # 시가
        # high_price: float # 고가
        # low_price: float # 저가
        # trade_price: float # 종가(체결가)
        # timestamp: int # 타임스탬프 (밀리초)
        # candle_acc_trade_price: float # 누적 거래 금액
        # candle_acc_trade_volume: float # 누적 거래량
        # unit: int # 분 단위 (예: 1분, 3분, 5분, 10분, 15분, 30분, 60분, 240분)
        # 사용전 정렬이 되어있는지 확인
        # candles: List[Candle] = self.api_client.get_candles(self.market, interval="1m", limit=30).candles