from typing import Tuple, List
from datetime import datetime, timedelta
from src.new.strategy.parameter.signal_strategy import SignalStrategy
from src.new.strategy.strategy_params import StrategyParams
from src.new.models.bithumb.response import Candle, Orderbook, Trade, OrderbookUnit
from math import ceil, floor

class TemplateSignal(SignalStrategy):
    def __init__(self, market: str, params: StrategyParams):
        super().__init__(market, params)
        self.market = market

        # 진입 후 값 저장용
        self.entry_price: float | None = None
        self.target_price: float | None = None
        self.stop_loss_price: float | None = None
        self.entry_time: datetime | None = None

    def get_name(self) -> str:
        return "Template Name"
    
    def get_description(self) -> str:
        return "Template description"

    # ========================== 매수 ==========================
    # 매수를 결정하기 위한 함수
    def should_buy(self) -> Tuple[bool, str]:
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
        candles: List[Candle] = self.api_client.get_candles(self.market, interval="1m", limit=30).candles
        
        # **Orderbook**
        # market: str # 시장 정보 (예: KRW-BTC)
        # timestamp: int # 타임스탬프 (밀리초)
        # total_ask_size: float # 총 매도 주문 수량
        # total_bid_size: float # 총 매수 주문 수량
        # orderbook_units: List[OrderbookUnit] # 호가 단위 목록
        
        # **OrderbookUnit**
        # ask_price: float # 매도 호가
        # bid_price: float # 매수 호가
        # ask_size: float # 매도 주문 수량
        # bid_size: float # 매수 주문 수량
        orderbook: Orderbook = self.api_client.get_orderbook(self.market).orderbooks[0]
        
        # **Trade**
        # market: str # 마켓 구분 코드 (예: KRW-BTC)
        # trade_date_utc: str # 체결 일자(UTC 기준) 포맷: yyyy-MM-dd
        # trade_time_utc: str # 체결 시각(UTC 기준) 포맷: HH:mm:ss
        # timestamp: int # 체결 타임스탬프
        # trade_price: float # 체결 가격
        # trade_volume: float # 체결량
        # prev_closing_price: float # 전일 종가(UTC 0시 기준)
        # change_price: float # 변화량
        # ask_bid: str # 매도/매수 (ASK: 매도, BID: 매수)
        # sequential_id: Optional[int] # 체결 번호(Unique)
        # 사용전 정렬이 되어있는지 확인
        trades: List[Trade] = self.api_client.get_trades(self.market, count=1).trades
        
        return result
    
    def set_entry_price(self, price: float) -> Tuple[float, float]:
        orderbook = self.api_client.get_orderbook(self.market).orderbooks[0]
        tick_size = abs(float(orderbook.orderbook_units[0].ask_price) -
                        float(orderbook.orderbook_units[1].ask_price))
        # ==== 파라미터 ====
        take_ticks = 2
        stop_ticks = 2
        take_rate = 0.0005
        stop_rate = 0.00025
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
    
    # ========================== 매도 ==========================
    def should_sell(self, current_price: float) -> Tuple[bool, str]:
        if self.target_price is None:   # 포지션이 없을 때
            return False, "포지션 없음"

        if current_price >= self.target_price:
            return True, f"목표가 도달 – 현재가 {int(current_price)}, 목표가 {int(self.target_price)}"
        if current_price <= self.stop_loss_price:
            return True, f"손절가 도달 – 현재가 {int(current_price)}, 손절가 {int(self.stop_loss_price)}"
        if datetime.now() - self.entry_time > timedelta(minutes=10):
            return True, "10분 경과 – 시간 기반 청산"

        # (선택) 추가 Trailing-Stop · 호가창 급변 로직 위치
        return False, "매도 신호 없음"