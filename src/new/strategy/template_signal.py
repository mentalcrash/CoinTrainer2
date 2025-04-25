from typing import Tuple, List
from datetime import datetime, timedelta
from src.new.strategy.parameter.signal_strategy import SignalStrategy
from src.new.strategy.strategy_params import StrategyParams
from src.new.models.bithumb.response import Orderbook, Trade, OrderbookUnit
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
        trades: List[Trade] = self.api_client.get_trades(self.market, count=200).trades
        trades.sort(key=lambda x: x.timestamp)
        
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
        
        return result