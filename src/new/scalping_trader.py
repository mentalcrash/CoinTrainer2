import logging
import time
import os
from typing import Optional, Literal
from src.new.api.bithumb.client import BithumbApiClient
from src.new.strategy.VolatilityBreakoutSignal import VolatilityBreakoutSignal
from src.new.strategy.rsi_stoch_vwap_signal import RSIStochVWAPSignal
from src.new.models.bithumb.response import CandlesResponse, TickerResponse, OrderbookResponse
from src.models.order import OrderRequest, OrderResponse
from src.discord_notifier import DiscordNotifier
from src.account import Account
from src.trading_order import TradingOrder
from src.trading_logger import TradingLogger
from src.new.calculator.carget_calculator import TargetCalculator
from src.new.strategy.signal_strategy import SignalStrategy
MonitorResult = Literal["target", "stop_loss", "error"]

class ScalpingTrader:
    def __init__(self, market: str):
        """
        스캘핑 트레이더 초기화
        """
        self.market = market # 마켓 정보 저장
        self.api_client = BithumbApiClient()
        self.account = Account(
            api_key=os.getenv("BITHUMB_API_KEY"),
            secret_key=os.getenv("BITHUMB_SECRET_KEY")
        )
        self.is_position = False
        self.loop_interval = 15.0

        # 로깅 설정 - 기본 로거 가져오기
        # self.logger 대신 self.base_logger 사용
        self.base_logger = logging.getLogger(__name__) 
        
        self.discord_notifier = DiscordNotifier(os.getenv("DISCORD_WEBHOOK_URL"))
        self.trading_order = TradingOrder(
            api_key=os.getenv("BITHUMB_API_KEY"),
            secret_key=os.getenv("BITHUMB_SECRET_KEY")
        )
        
        self.trading_logger = TradingLogger()
        
        self.max_consecutive_losses = 3
        self.consecutive_losses = 0

    # --- 로깅 헬퍼 메서드 추가 ---
    def _log(self, level, msg, *args, **kwargs):
        """내부 로깅 헬퍼. 메시지에 마켓 프리픽스를 추가합니다."""
        # exc_info=True 와 같은 인자를 올바르게 처리하기 위해 kwargs 사용
        extra = kwargs.pop('extra', None)
        exc_info = kwargs.pop('exc_info', None)
        stack_info = kwargs.pop('stack_info', None)
        
        log_msg = f"[{self.market}] {msg}" # 마켓 프리픽스 추가
        self.base_logger.log(level, log_msg, *args, 
                             exc_info=exc_info, stack_info=stack_info, extra=extra, **kwargs)

    def info(self, msg, *args, **kwargs):
        self._log(logging.INFO, msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self._log(logging.WARNING, msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self._log(logging.ERROR, msg, *args, **kwargs)

    def debug(self, msg, *args, **kwargs):
        # 디버그 레벨 로그가 필요하다면 추가
        self._log(logging.DEBUG, msg, *args, **kwargs)
        
    def critical(self, msg, *args, **kwargs):
        self._log(logging.CRITICAL, msg, *args, **kwargs)
    # --- 로깅 헬퍼 메서드 끝 ---

    def fetch_market_data(self) -> tuple[CandlesResponse, TickerResponse, OrderbookResponse]:
        """시장의 캔들, 티커, 호가 데이터를 가져옵니다."""
        self.info("📥 시장 데이터 수집 시작") # self.logger.info -> self.info
        candles = self.api_client.get_candles(self.market, interval="1m", limit=30).candles
        ticker = self.api_client.get_ticker(self.market)
        orderbook = self.api_client.get_orderbook(self.market)
        return candles, ticker, orderbook

    def analyze_market(self, strategy: SignalStrategy) -> bool:
        """시장 데이터를 분석하여 매수 신호 여부를 판단"""
        decision = strategy.should_buy()
        self.info(f"📊 분석 결과: {'매수 신호 감지' if decision else '신호 없음'}") # self.logger.info -> self.info
        return decision

    def execute_entry_order(self) -> Optional[OrderResponse]:
        """시장가 매수 주문 실행"""
        krw_balance = self.account.get_balance('KRW')
        if not krw_balance:
            self.warning("❗ KRW 잔고 정보를 가져올 수 없습니다.") # self.logger.warning -> self.warning
            return None
        
        available_balance = float(krw_balance['balance'])
        locked_balance = float(krw_balance['locked'])
        if available_balance <= 0:
            self.warning("❗ KRW 잔고 부족으로 매수 불가") # self.logger.warning -> self.warning
            return None
        
        order_amount = available_balance * 0.03
        self.info(f"🟢 매수 주문 실행 시작 - 주문 금액: {order_amount:,.0f} KRW") # self.logger.info -> self.info

        order_request = OrderRequest(
            market=self.market,
            side="bid",
            order_type="price",
            price=order_amount,
            volume=None
        )
        order_response = self.trading_order.create_order_v2(order_request)
        self.info(f"🛒 매수 주문 전송 완료 - 주문 ID: {order_response.uuid}") # self.logger.info -> self.info

        completed_order = self.wait_order_completion(order_response)  
        return completed_order

    def execute_exit_order(self, volume: float) -> Optional[OrderResponse]:
        """시장가 매도 주문 실행"""
        self.info(f"🔴 매도 주문 실행 시작 - 수량: {volume}") # self.logger.info -> self.info
        
        # if monitor_result == "target":
        #     order_request = OrderRequest(
        #         market=self.market,
        #         side="ask",
        #         order_type="limit",
        #         price=price,
        #         volume=volume
        #     )
        # elif monitor_result == "stop_loss":
        #     order_request = OrderRequest(
        #         market=self.market,
        #         side="ask",
        #         order_type="market",
        #         price=None,
        #         volume=volume
        #     )
            
        order_request = OrderRequest(
            market=self.market,
            side="ask",
            order_type="market",
            price=None,
            volume=volume    
        )
        
        order_response = self.trading_order.create_order_v2(order_request)
        self.info(f"📤 매도 주문 전송 완료 - 주문 ID: {order_response.uuid}\n{order_request}") # self.logger.info -> self.info

        completed_order = self.wait_order_completion(order_response)  
        if completed_order:
            self.info(f"✅ 매도 주문 체결 완료\n{completed_order.to_json()}") # self.logger.info -> self.info
            return completed_order
        else:
            self.info("❗ 매도 주문 체결 실패") # self.logger.warning -> self.warning
            try:
                cancel_order = self.trading_order.cancel_order_v2(order_response.uuid)
                self.info(f"❗ 매도 주문 취소 완료\n{cancel_order.to_json()}") # self.logger.warning -> self.warning
            except Exception as e:
                self.info(f"❗ 매도 주문 취소 실패: {e}\nuuid:{order_response.uuid}") # self.logger.error -> self.error
                # 마지막으로 주문처리 확인
            return self.wait_order_completion(order_response)  

    def wait_order_completion(self, order_response: OrderResponse) -> Optional[OrderResponse]:
        """HTTP polling 방식으로 주문 체결 여부 확인"""
        MAX_RETRIES = 10
        backoff_schedule = [0.5, 0.5, 0.5, 1.0, 1.0, 1.0, 2.0, 2.0, 2.0, 2.0]

        self.info(f"⏳ 주문 체결 대기 시작 (ID: {order_response.uuid})") # self.logger.info -> self.info

        for i in range(MAX_RETRIES):
            completed_order = self.trading_order.get_order_v2(order_response.uuid)

            if completed_order and completed_order.state == "done":
                self.info(f"✅ 주문 체결 완료 - 체결가: {completed_order.price_per_unit}") # self.logger.info -> self.info
                return completed_order
            elif completed_order and completed_order.state in ["cancel", "error"]:
                self.warning(f"❌ 주문 체결 실패 또는 취소 - 상태: {completed_order.state}") # self.logger.warning -> self.warning
                return None
            else:
                self.info(f"⏳ 주문 체결 대기 중 - 체결 상태: {completed_order.state}") # self.logger.info -> self.info

            time.sleep(backoff_schedule[i])

        self.warning("⏱️ 주문 체결 실패 - 최대 재시도 초과") # self.logger.warning -> self.warning
        return None

    def calculate_targets(self, current_price: float, profit_rate: float = 0.002, loss_rate: float = 0.001) -> tuple[int, int]:
        """목표가와 손절가 계산"""
        target_price = int(current_price * (1 + profit_rate))
        if target_price == int(current_price):
            target_price = int(current_price) + 3
        stop_loss_price = int(current_price * (1 - loss_rate))
        if stop_loss_price == int(current_price):
            stop_loss_price = int(current_price) - 2    
        # self.debug(f"🎯 목표가/손절가 계산됨: Target={target_price}, StopLoss={stop_loss_price}") # 필요시 debug 사용
        return target_price, stop_loss_price

    def monitor_position(self, order_response: OrderResponse, strategy: SignalStrategy, hold_duration_seconds: int = 0) -> str:
        """포지션 상태를 감시하며 목표가/손절가 도달 여부 판단"""
        entry_price = order_response.price_per_unit
        target_price, stop_loss_price = self.calculate_targets(entry_price)
        interval_sec = 1
        self.info(f"👀 포지션 모니터링 시작 (평균 진입가: {entry_price:,.0f}, 목표가: {target_price:,}, 손절가: {stop_loss_price:,}), 강제 홀드: {hold_duration_seconds}초") # self.logger.info -> self.info
        time.sleep(hold_duration_seconds)
        while True:
            ticker = self.api_client.get_ticker(self.market)
            current_price = float(ticker.tickers[0].trade_price)

            should_sell, reason = strategy.should_sell(current_price, target_price, stop_loss_price)
            if should_sell:
                self.info(f"📈 매도 조건 달성") # self.logger.info -> self.info
                return reason
            else:
                # 주기적인 상태 로깅 (옵션)
                # self.debug(f"현재가: {current_price:,.0f}") 
                time.sleep(interval_sec)
        return None

    def run_once(self):
        """단일 트레이딩 사이클 실행"""
        self.info("▶️ 트레이딩 사이클 시작") # self.logger.info -> self.info
        entry_order = None # entry_order 초기화
        
        if not self.is_position:
            candles, ticker, orderbook = self.fetch_market_data()
            strategy = RSIStochVWAPSignal(candles, ticker, orderbook)
            if not self.analyze_market(strategy):
                self.info("🟡 매수 신호 없음 - 사이클 종료") # self.logger.info -> self.info
                return

            entry_order = self.execute_entry_order()
            if not entry_order:
                self.warning("❗ 매수 주문 실패") # self.logger.warning -> self.warning
                return
        
        if entry_order: # 매수 주문이 성공했을 때만 진입
            self.is_position = True
            # target_price, stop_loss_price = self.calculate_targets(entry_order.price_per_unit)
            target_price, stop_loss_price = TargetCalculator.from_orderbook(entry_order.price_per_unit, orderbook.orderbooks[0])
            self.discord_notifier.send_start_scalping(entry_order, target_price, stop_loss_price)
            
            def monitoring():
                reason = self.monitor_position(entry_order, strategy, hold_duration_seconds=5)
                exit_order = self.execute_exit_order(entry_order.total_volume)
                
                if exit_order and exit_order.state == "done":
                    self.info(f"💰 매도 완료 - 체결가: {exit_order.price_per_unit}, 수익률 계산 가능") # self.logger.info -> self.info
                    self.discord_notifier.send_end_scalping(entry_order, exit_order, reason)
                    self.trading_logger.log_scalping_result(entry_order, exit_order)
                    pnl = ((exit_order.price_per_unit - entry_order.price_per_unit) * entry_order.total_volume) - entry_order.paid_fee - exit_order.paid_fee
                    if pnl < 0:
                        self.consecutive_losses += 1
                    else:
                        self.consecutive_losses = 0
                else:
                    self.warning("❗ 매도 주문 실패 다시 매도 주문 시도") # self.logger.warning -> self.warning
                    monitoring()
                    
            monitoring()

            self.is_position = False
            self.info("⛔ 트레이딩 사이클 종료") # self.logger.info -> self.info
        else:
            # self.is_position이 True인데 entry_order가 없는 경우는 현재 로직상 발생하기 어려우나,
            # 예외적인 상황을 대비하여 로그 추가 가능
            self.warning("⚠️ 포지션 진입 상태이나 유효한 진입 주문 정보가 없습니다.")

    def run_forever(self, life_time: int = 3600, loop_interval: int = 15):
        """무한 루프 실행"""
        start_time = time.time()   
        self.info(f"🔁 무한 트레이딩 루프 진입 (life_time: {life_time}초, loop_interval: {loop_interval}초)") # self.logger.info -> self.info
        while time.time() - start_time < life_time:
            try:
                self.run_once()
            except Exception as e:
                self.error(f"[ERROR] run_once 중 예외 발생: {e}", exc_info=True) # self.logger.error -> self.error

            time.sleep(loop_interval)
            
            if self.max_consecutive_losses <= self.consecutive_losses:
                self.info("🔴 최대 연속 손실 횟수 도달 - 트레이딩 종료") # self.logger.info -> self.info
                break
