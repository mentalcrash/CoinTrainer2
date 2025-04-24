from typing import Tuple, List
from src.new.strategy.parameter.signal_strategy import SignalStrategy
from src.new.strategy.strategy_params import StrategyParams
from src.new.models.bithumb.response import Candle, Orderbook, Trade, OrderbookUnit


class TemplateSignal(SignalStrategy):
    def __init__(self, market: str, params: StrategyParams):
        super().__init__(market, params)
        self.market = market

    def get_name(self) -> str:
        return "Template Name"
    
    def get_description(self) -> str:
        return "Template description"

    # 매수를 결정하기 위한 함수 (캐싱하지 않고 실시간 데이터 호출)
    def should_buy(self) -> Tuple[bool, float, float]:
        # 실시간 Candle 데이터 호출 (캐싱 없음)
        candles_response = self.api_client.get_candles(self.market, interval="1m", limit=30)
        if not candles_response or not candles_response.candles:
            self.logger.warning("캔들 데이터 API 호출 실패로 매수 판단 보류")
            return False, 0.0, 0.0

        candles: List[Candle] = candles_response.candles
        candles.sort(key=lambda c: c.timestamp)  # 오름차순 정렬 명시적으로 보장

        # 실시간 Orderbook 데이터 호출
        orderbook_response = self.api_client.get_orderbook(self.market)
        if not orderbook_response or not orderbook_response.orderbooks:
            self.logger.warning("호가창 데이터 API 호출 실패로 매수 판단 보류")
            return False, 0.0, 0.0

        orderbook: Orderbook = orderbook_response.orderbooks[0]
        orderbook_units: List[OrderbookUnit] = orderbook.orderbook_units

        # 실시간 최근 체결(trade) 데이터 호출
        trades_response = self.api_client.get_trades(self.market, count=1)
        if not trades_response or not trades_response.trades:
            self.logger.warning("최근 체결 데이터 API 호출 실패로 매수 판단 보류")
            return False, 0.0, 0.0

        trades: List[Trade] = trades_response.trades
        trades.sort(key=lambda t: t.timestamp)  # 오름차순 정렬 명시적으로 보장

        # ---------------------------------------------------
        # 여기서부터 지표 계산, ATR 기반 목표가와 손절가 설정 등
        # 매수 조건 평가 로직을 구체적으로 작성하십시오.
        # ---------------------------------------------------

        # 조건 예시 (구체적 로직으로 반드시 변경 필요)
        should_enter_trade = True  # 실제 조건 평가 로직 필요

        current_price = trades[-1].trade_price
        atr_value = 50.0  # 실제 ATR 계산으로 변경 필요 (예시용 고정값)

        # 목표가와 손절가를 ATR의 0.5배로 예시 설정
        target_price = current_price + (atr_value * 0.5)
        stop_loss_price = current_price - (atr_value * 0.5)

        # 최종 결정 결과 상세 로그
        self.logger.info(
            f"매수 판단: {should_enter_trade}, 현재가: {current_price}, "
            f"목표가: {target_price}, 손절가: {stop_loss_price}, ATR: {atr_value}"
        )

        return should_enter_trade, target_price, stop_loss_price