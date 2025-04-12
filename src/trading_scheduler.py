import time
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional, List

from src.trading_executor import TradingExecutor
from src.discord_notifier import DiscordNotifier
from src.utils.log_manager import LogManager, LogCategory
from src.trading_logger import TradingLogger
from src.models.market_data import TradeExecutionResult

class TradingScheduler:
    def __init__(
        self,
        trading_executor: TradingExecutor,
        log_manager: LogManager,
        trading_logger: TradingLogger,
        discord_notifier: Optional[DiscordNotifier] = None,
        dev_mode: bool = True,
        max_history_size: int = 10  # 최대 히스토리 크기
    ):
        """트레이딩 스케줄러

        Args:
            trading_executor (TradingExecutor): 트레이딩 실행기
            log_manager (LogManager): 로그 매니저
            trading_logger (TradingLogger): 구글 시트 로거
            discord_notifier (Optional[DiscordNotifier], optional): Discord 알림 전송기. Defaults to None.
            dev_mode (bool, optional): 개발 모드 여부. Defaults to True.
            max_history_size (int, optional): 캐싱할 최대 히스토리 크기. Defaults to 10.
        """
        self.trading_executor = trading_executor
        self.discord_notifier = discord_notifier
        self.dev_mode = dev_mode
        self.is_running = False
        self.next_execution_time = None
        self.log_manager = log_manager
        self.trading_logger = trading_logger
        self.max_history_size = max_history_size
        
        # 매매 판단 히스토리를 저장할 딕셔너리 (심볼별로 관리)
        self.decision_history: Dict[str, List[TradeExecutionResult]] = {}

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

    def _add_to_history(self, symbol: str, result: TradeExecutionResult):
        """매매 판단 결과를 히스토리에 추가합니다.
        관망이 아닌 실제 매매 결정만 저장합니다.

        Args:
            symbol (str): 매매 심볼
            result (TradeExecutionResult): 매매 실행 결과
        """
        try:
            # 관망인 경우 저장하지 않음
            if result.decision_result.decision.action == "관망":
                return
                
            # 심볼에 대한 히스토리가 없으면 초기화
            if symbol not in self.decision_history:
                self.decision_history[symbol] = []
                
            # 히스토리에 추가
            self.decision_history[symbol].append(result)
            
            # 최대 크기를 초과하면 가장 오래된 항목 제거
            if len(self.decision_history[symbol]) > self.max_history_size:
                self.decision_history[symbol].pop(0)
                
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.SYSTEM,
                    message=f"{symbol} 매매 판단 히스토리 추가",
                    data={
                        "action": result.decision_result.decision.action,
                        "history_size": len(self.decision_history[symbol])
                    }
                )
                
        except Exception as e:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message=f"{symbol} 매매 판단 히스토리 추가 실패",
                    data={"error": str(e)}
                )

    def get_decision_history(self, symbol: str) -> List[TradeExecutionResult]:
        """특정 심볼의 매매 판단 히스토리를 조회합니다.

        Args:
            symbol (str): 매매 심볼

        Returns:
            List[TradeExecutionResult]: 매매 판단 히스토리 목록
        """
        return self.decision_history.get(symbol, [])

    def _handle_trading_result(
        self,
        symbol: str,
        result: TradeExecutionResult,
    ):
        """트레이딩 결과를 처리합니다.

        Args:
            symbol (str): 매매 심볼
            result (TradeExecutionResult): 매매 실행 결과
        """
        try:
            # 매매 판단 히스토리에 추가
            self._add_to_history(symbol, result)
            
            # 실행 실패 또는 관망인 경우 처리하지 않음
            if not result.success or result.decision_result.decision.action == "관망":
                return
            
            if not result.order_result:
                return
                
            # 통합된 매매 기록
            self.trading_logger.log_order_record(
                symbol=symbol,
                result=result
            )
            
            self.trading_logger.log_order_response(
                order_result=result.order_result
            )

            # Discord 알림 전송
            if self.discord_notifier:
                self.discord_notifier.send_trade_notification(
                    result=result
                )
            
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ERROR,
                message=f"{symbol} 트레이딩 결과 처리 실패: {str(e)}"
            )
            raise

    def _handle_error(self, error: Exception):
        """에러를 처리합니다.

        Args:
            error (Exception): 발생한 에러
        """
        
            

    def start(self, symbol: str):
        """트레이딩을 시작합니다.

        Args:
            symbol (str): 매매할 심볼 (예: BTC)
        """
        # 새로운 트레이딩 세션 시작
        self.log_manager.start_new_trading_session(symbol)
        self.log_manager.log(
            category=LogCategory.SYSTEM,
            message=f"{symbol} 자동매매 스케줄러 시작",
            data={"dev_mode": self.dev_mode}
        )
        
        self.is_running = True

        while self.is_running:
            try:
                # 다음 실행 시간까지 대기
                self._wait_until_next_execution()

                # 트레이딩 실행
                result = self.trading_executor.execute_trade(symbol)

                interval_minutes = int(result.decision_result.decision.next_decision.interval_minutes)
                self.next_execution_time = self._calculate_next_execution_time(interval_minutes)

                # 결과 처리
                self._handle_trading_result(
                    symbol=symbol,
                    result=result
                )

            except Exception as e:
                self.next_execution_time = self._calculate_next_execution_time(1)
                error_message = f"트레이딩 실행 중 에러 발생: {str(e)}"
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message=error_message,
                    data={"traceback": str(e)}
                )

                # Discord 에러 알림 전송
                self.discord_notifier.send_error_notification(error_message)
            except KeyboardInterrupt:
                self.log_manager.log(
                    category=LogCategory.SYSTEM,
                    message=f"{symbol} 자동매매 스케줄러 종료 요청"
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