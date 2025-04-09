import time
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional

from src.trading_executor import TradingExecutor
from src.discord_notifier import DiscordNotifier
from src.utils.log_manager import LogManager, LogCategory
from src.trading_logger import TradingLogger

class TradingScheduler:
    def __init__(
        self,
        trading_executor: TradingExecutor,
        log_manager: LogManager,
        trading_logger: TradingLogger,
        discord_notifier: Optional[DiscordNotifier] = None,
        dev_mode: bool = True
    ):
        """트레이딩 스케줄러

        Args:
            trading_executor (TradingExecutor): 트레이딩 실행기
            log_manager (LogManager): 로그 매니저
            trading_logger (TradingLogger): 구글 시트 로거
            discord_notifier (Optional[DiscordNotifier], optional): Discord 알림 전송기. Defaults to None.
            dev_mode (bool, optional): 개발 모드 여부. Defaults to True.
        """
        self.trading_executor = trading_executor
        self.discord_notifier = discord_notifier
        self.dev_mode = dev_mode
        self.is_running = False
        self.next_execution_time = None
        self.log_manager = log_manager
        self.trading_logger = trading_logger

    def _calculate_next_execution_time(self, interval_minutes: int) -> datetime:
        """다음 실행 시간을 계산합니다.

        Args:
            interval_minutes (int): 다음 실행까지의 간격 (분)

        Returns:
            datetime: 다음 실행 시간
        """
        return datetime.now() + timedelta(minutes=interval_minutes)

    def _wait_until_next_execution(self):
        """다음 실행 시간까지 대기합니다."""
        if not self.next_execution_time:
            return

        while datetime.now() < self.next_execution_time:
            remaining_seconds = (self.next_execution_time - datetime.now()).total_seconds()
            if remaining_seconds > 0:
                self.log_manager.log(
                    category=LogCategory.SYSTEM,
                    message="다음 실행 대기 중",
                    data={"remaining_seconds": int(remaining_seconds)}
                )
                time.sleep(min(remaining_seconds, 60))  # 최대 1분씩 대기

    def _handle_trading_result(
        self,
        symbol: str,
        decision: Dict,
        asset_info: Dict,
        market_data: Dict,
        order_result: Optional[Dict] = None,
    ):
        """트레이딩 결과를 처리합니다.

        Args:
            symbol (str): 매매 심볼
            decision (Dict): 매매 판단 정보
            order_result (Dict): 주문 실행 결과
            asset_info (Dict): 자산 정보
        """
        try:
            # 고유 ID 생성 (타임스탬프 + UUID)
            execution_id = f"exec_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"
            
            # 매매 판단 기록
            self.trading_logger.log_decision(
                id=execution_id,
                symbol=symbol,
                decision_data=decision
            )
            
            # 자산 현황 기록
            self.trading_logger.log_asset_status(
                id=execution_id,
                symbol=symbol,
                asset_data=asset_info
            )

            self.trading_logger.log_market_data(
                id=execution_id,
                symbol=symbol,
                market_data=market_data
            )
            
            # 주문 실행 결과가 있는 경우 기록
            if order_result:
                self.trading_logger.log_trade(
                    id=execution_id,
                    order_result=order_result
                )

            # Discord 알림 전송
            if self.discord_notifier and decision["decision"] != "관망":
                try:
                    self.discord_notifier.send_trade_notification(
                        symbol, decision, asset_info, order_result
                    )
                except Exception as e:
                    error_msg = f"Discord 알림 전송 실패: {str(e)}"
                    self.log_manager.log(
                        category=LogCategory.ERROR,
                        message=error_msg,
                        data={"error": str(e)}
                    )

            # 다음 실행 시간 설정
            interval_minutes = int(decision["next_decision"]["interval_minutes"])
            self.next_execution_time = self._calculate_next_execution_time(interval_minutes)
            self.log_manager.log(
                category=LogCategory.SYSTEM,
                message="다음 실행 시간 설정",
                data={
                    "symbol": symbol,
                    "next_execution_time": self.next_execution_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "interval_minutes": interval_minutes
                }
            )
            
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ERROR,
                message="트레이딩 결과 처리 실패",
                data={
                    "symbol": symbol,
                    "error": str(e)
                }
            )
            raise

    def _handle_error(self, error: Exception):
        """에러를 처리합니다.

        Args:
            error (Exception): 발생한 에러
        """
        error_message = f"트레이딩 실행 중 에러 발생: {str(error)}"
        self.log_manager.log(
            category=LogCategory.ERROR,
            message=error_message,
            data={"traceback": str(error)}
        )

        # Discord 에러 알림 전송
        if self.discord_notifier:
            try:
                self.discord_notifier.send_error_notification(error_message)
                self.log_manager.log(
                    category=LogCategory.DISCORD,
                    message="Discord 에러 알림 전송 완료"
                )
            except Exception as e:
                error_msg = f"Discord 에러 알림 전송 실패: {str(e)}"
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message=error_msg,
                    data={"error": str(e)}
                )

        # 에러 발생 시 30분 후에 다시 시도
        self.next_execution_time = self._calculate_next_execution_time(30)
        self.log_manager.log(
            category=LogCategory.SYSTEM,
            message="에러로 인한 재시도 시간 설정",
            data={"next_execution_time": self.next_execution_time.strftime("%Y-%m-%d %H:%M:%S")}
        )

    def start(self, symbol: str):
        """트레이딩을 시작합니다.

        Args:
            symbol (str): 매매할 심볼 (예: BTC)
        """
        # 새로운 트레이딩 세션 시작
        self.log_manager.start_new_trading_session(symbol)
        self.log_manager.log(
            category=LogCategory.SYSTEM,
            message=f"{symbol} 자동 매매 시작",
            data={"dev_mode": self.dev_mode}
        )
        
        self.is_running = True
        max_age_hours = 0.25  # 첫 실행시 기본값

        while self.is_running:
            try:
                # 다음 실행 시간까지 대기
                self._wait_until_next_execution()

                # 트레이딩 실행
                self.log_manager.log(
                    category=LogCategory.SYSTEM,
                    message=f"{symbol} 매매 실행 시작",
                    data={"max_age_hours": max_age_hours}
                )
                
                result = self.trading_executor.execute_trade(
                    symbol=symbol,
                    dev_mode=self.dev_mode,
                    limit=15,
                    max_age_hours=max_age_hours
                )

                # 다음 실행을 위한 max_age_hours 설정
                interval_minutes = int(result['decision']["next_decision"]["interval_minutes"])
                max_age_hours = float(interval_minutes) / 60
                self.log_manager.log(
                    category=LogCategory.SYSTEM,
                    message="뉴스 수집 기간 설정",
                    data={
                        "max_age_hours": max_age_hours,
                        "interval_minutes": interval_minutes
                    }
                )

                # 결과 처리
                self._handle_trading_result(
                    symbol=symbol,
                    decision=result['decision'],
                    order_result=result.get("order_result"),
                    asset_info=result["asset_info"],
                    market_data=result["decision_result"]["market_data"]
                )

            except Exception as e:
                self._handle_error(e)
                max_age_hours = 0.25  # 에러 발생 시 기본값으로 리셋

            except KeyboardInterrupt:
                self.log_manager.log(
                    category=LogCategory.SYSTEM,
                    message="프로그램 종료 요청"
                )
                break

    def stop(self):
        """트레이딩을 중지합니다."""
        self.log_manager.log(
            category=LogCategory.SYSTEM,
            message="트레이딩 중지"
        )
        self.is_running = False
        self.log_manager.stop() 