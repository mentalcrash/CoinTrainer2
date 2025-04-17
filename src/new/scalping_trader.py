import logging
import time
import os
from typing import Optional
from src.new.api.bithumb.client import BithumbApiClient
from src.new.strategy.VolatilityBreakoutSignal import VolatilityBreakoutSignal
from src.models.order import OrderRequest, OrderResponse
from src.discord_notifier import DiscordNotifier
from src.account import Account
from src.trading_order import TradingOrder
from src.trading_logger import TradingLogger

class ScalpingTrader:
    def __init__(self, market: str):
        """
        스캘핑 트레이더 초기화
        """
        self.api_client = BithumbApiClient()
        self.account = Account(
            api_key=os.getenv("BITHUMB_API_KEY"),
            secret_key=os.getenv("BITHUMB_SECRET_KEY")
        )
        self.market = market
        self.is_position = False
        self.loop_interval = 15.0

        # 로깅 설정
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        self.discord_notifier = DiscordNotifier(os.getenv("DISCORD_WEBHOOK_URL"))
        self.trading_order = TradingOrder(
            api_key=os.getenv("BITHUMB_API_KEY"),
            secret_key=os.getenv("BITHUMB_SECRET_KEY")
        )
        
        self.trading_logger = TradingLogger()

    def fetch_market_data(self):
        """시장의 캔들, 티커, 호가 데이터를 가져옵니다."""
        self.logger.info("📥 시장 데이터 수집 시작")
        candles = self.api_client.get_candles(self.market, interval="1m", limit=30).candles
        ticker = self.api_client.get_ticker(self.market)
        orderbook = self.api_client.get_orderbook(self.market)
        return candles, ticker, orderbook

    def analyze_market(self, candles, ticker, orderbook) -> bool:
        """시장 데이터를 분석하여 매수 신호 여부를 판단"""
        strategy = VolatilityBreakoutSignal(candles, ticker, orderbook)
        decision = strategy.should_buy()
        self.logger.info(f"📊 분석 결과: {'매수 신호 감지' if decision else '신호 없음'}")
        return decision

    def execute_entry_order(self) -> Optional[OrderResponse]:
        """시장가 매수 주문 실행"""
        krw_balance = self.account.get_balance('KRW')
        if not krw_balance:
            return None
        
        available_balance = float(krw_balance['balance'])
        locked_balance = float(krw_balance['locked'])
        if available_balance <= 0:
            self.logger.warning("❗ KRW 잔고 부족으로 매수 불가")
            return None
        
        order_amount = available_balance * 0.2
        self.logger.info(f"🟢 매수 주문 실행 시작 - 주문 금액: {order_amount:,.0f} KRW")

        order_request = OrderRequest(
            market=self.market,
            side="bid",
            order_type="price",
            price=order_amount,
            volume=None
        )
        order_response = self.trading_order.create_order_v2(order_request)
        self.logger.info(f"🛒 매수 주문 전송 완료 - 주문 ID: {order_response.uuid}")

        completed_order = self.wait_order_completion(order_response)  
        return completed_order

    def execute_exit_order(self, volume: float):
        """시장가 매도 주문 실행"""
        self.logger.info(f"🔴 매도 주문 실행 시작 - 수량: {volume}")
        order_request = OrderRequest(
            market=self.market,
            side="ask",
            order_type="market",
            price=None,
            volume=volume
        )
        order_response = self.trading_order.create_order_v2(order_request)
        self.logger.info(f"📤 매도 주문 전송 완료 - 주문 ID: {order_response.uuid}")

        completed_order = self.wait_order_completion(order_response)  
        return completed_order

    def wait_order_completion(self, order_response: OrderResponse) -> Optional[OrderResponse]:
        """HTTP polling 방식으로 주문 체결 여부 확인"""
        MAX_RETRIES = 10
        backoff_schedule = [0.5, 0.5, 0.5, 1.0, 1.0, 1.0, 2.0, 2.0, 2.0, 2.0]

        self.logger.info(f"⏳ 주문 체결 대기 시작 (ID: {order_response.uuid})")

        for i in range(MAX_RETRIES):
            completed_order = self.trading_order.get_order_v2(order_response.uuid)

            if completed_order and completed_order.state == "done":
                self.logger.info(f"✅ 주문 체결 완료 - 체결가: {completed_order.price}, 수량: {completed_order.volume}")
                return completed_order
            elif completed_order and completed_order.state in ["cancel", "error"]:
                self.logger.warning(f"❌ 주문 체결 실패 또는 취소 - 상태: {completed_order.state}")
                return None

            time.sleep(backoff_schedule[i])

        self.logger.warning("⏱️ 주문 체결 실패 - 최대 재시도 초과")
        return None

    def calculate_targets(self, current_price: float, profit_rate: float = 0.005, loss_rate: float = 0.00025) -> tuple[int, int]:
        """목표가와 손절가 계산"""
        target_price = int(current_price * (1 + profit_rate))
        stop_loss_price = int(current_price * (1 - loss_rate))
        return target_price, stop_loss_price

    def monitor_position(self, order_response: OrderResponse):
        """포지션 상태를 감시하며 목표가/손절가 도달 여부 판단"""
        target_price, stop_loss_price = self.calculate_targets(order_response.price/order_response.volume)
        interval_sec = 1

        self.logger.info(f"👀 포지션 모니터링 시작 (목표가: {target_price}, 손절가: {stop_loss_price})")

        while True:
            ticker = self.api_client.get_ticker(self.market)
            current_price = float(ticker.tickers[0].trade_price)

            if current_price >= target_price:
                self.logger.info(f"📈 목표가 도달 → 현재가: {current_price} ≥ {target_price}")
                break
            elif current_price <= stop_loss_price:
                self.logger.info(f"📉 손절가 도달 → 현재가: {current_price} ≤ {stop_loss_price}")
                break
            else:
                time.sleep(interval_sec)

    def run_once(self):
        """단일 트레이딩 사이클 실행"""
        self.logger.info("▶️ 트레이딩 사이클 시작")
        if not self.is_position:
            candles, ticker, orderbook = self.fetch_market_data()
            if not self.analyze_market(candles, ticker, orderbook):
                self.logger.info("🟡 매수 신호 없음 - 사이클 종료")
                return

            entry_order = self.execute_entry_order()
            if not entry_order:
                self.logger.warning("❗ 매수 주문 실패")
                return

        self.is_position = True
        
        self.discord_notifier.send_start_scalping(entry_order)
        
        self.monitor_position(entry_order)

        exit_order = self.execute_exit_order(entry_order.volume)
        if exit_order:
            self.logger.info(f"💰 매도 완료 - 체결가: {exit_order.price}, 수익률 계산 가능")
            self.discord_notifier.send_end_scalping(entry_order, exit_order)
            self.trading_logger.log_scalping_result(entry_order, exit_order)
        else:
            self.logger.warning("❗ 매도 주문 실패")

        self.is_position = False
        self.logger.info("⛔ 트레이딩 사이클 종료")

    def run_forever(self):
        """무한 루프 실행"""
        self.logger.info("🔁 무한 트레이딩 루프 진입")
        while True:
            try:
                self.run_once()
            except Exception as e:
                self.logger.error(f"[ERROR] run_once 중 예외 발생: {e}", exc_info=True)

            time.sleep(self.loop_interval)