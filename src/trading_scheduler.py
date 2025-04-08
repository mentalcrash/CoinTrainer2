import logging
import time
import os
from datetime import datetime, timedelta
from typing import Dict, Optional

from src.trading_executor import TradingExecutor
from src.discord_notifier import DiscordNotifier
from src.trading_logger import TradingLogger
from src.utils.logger import setup_logger

logger = setup_logger('trading_scheduler')

class TradingScheduler:
    def __init__(
        self,
        trading_executor: TradingExecutor,
        discord_notifier: Optional[DiscordNotifier] = None,
        dev_mode: bool = True
    ):
        """트레이딩 스케줄러

        Args:
            trading_executor (TradingExecutor): 트레이딩 실행기
            discord_notifier (Optional[DiscordNotifier], optional): Discord 알림 전송기. Defaults to None.
            dev_mode (bool, optional): 개발 모드 여부. Defaults to True.
        """
        self.trading_executor = trading_executor
        self.discord_notifier = discord_notifier
        self.dev_mode = dev_mode
        self.is_running = False
        self.next_execution_time = None
        
        # 트레이딩 로거 초기화
        credentials_path = os.getenv('GOOGLE_CREDENTIALS_PATH')
        if not credentials_path:
            raise ValueError("GOOGLE_CREDENTIALS_PATH 환경 변수가 설정되지 않았습니다.")
        
        self.trading_logger = TradingLogger(credentials_path)

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
                logger.info(f"다음 실행까지 {remaining_seconds:.0f}초 대기...")
                time.sleep(min(remaining_seconds, 60))  # 최대 1분씩 대기

    def _handle_trading_result(
        self,
        symbol: str,
        decision: Dict,
        asset_info: Dict,
        order_result: Optional[Dict] = None,
    ):
        """트레이딩 결과를 처리합니다.

        Args:
            symbol (str): 매매 심볼
            decision (Dict): 매매 판단 정보
            order_result (Dict): 주문 실행 결과
            asset_info (Dict): 자산 정보
        """
        # try:
        #     # 1. 매매 기록 저장
        #     if order_result:
        #         self.trading_logger.log_trade(order_result)
            
        #     # 2. 매매 판단 저장
        #     decision_data = {
        #         'symbol': symbol,
        #         'decision': decision['decision'],
        #         'target_price': decision.get('target_price'),
        #         'stop_loss': decision.get('stop_loss'),
        #         'confidence': decision.get('confidence'),
        #         'reasons': decision.get('reasons', []),
        #         'risk_factors': decision.get('risk_factors', [])
        #     }
        #     self.trading_logger.log_decision(decision_data)
            
        #     # 3. 자산 현황 저장
        #     self.trading_logger.log_asset_status(asset_info)
            
        #     # 4. 성과 지표 저장 (성과 지표는 자산 정보를 기반으로 계산)
        #     performance_data = {
        #         'symbol': symbol,
        #         'daily_roi': asset_info.get('daily_roi', 0),
        #         'weekly_roi': asset_info.get('weekly_roi', 0),
        #         'monthly_roi': asset_info.get('monthly_roi', 0),
        #         'total_profit_loss': asset_info.get('total_profit_loss', 0),
        #         'win_rate': asset_info.get('win_rate', 0)
        #     }
        #     self.trading_logger.log_performance(performance_data)
            
        # except Exception as e:
        #     logger.error(f"트레이딩 결과 로깅 실패: {str(e)}", exc_info=True)

        # Discord 알림 전송
        if self.discord_notifier:
            try:
                self.discord_notifier.send_trade_notification(
                    symbol, decision, asset_info, order_result
                )
            except Exception as e:
                logger.error(f"Discord 알림 전송 실패: {str(e)}")

        # 다음 실행 시간 설정
        interval_minutes = decision["next_decision"]["interval_minutes"]
        self.next_execution_time = self._calculate_next_execution_time(interval_minutes)
        logger.info(f"다음 실행 시간: {self.next_execution_time}")

    def _handle_error(self, error: Exception):
        """에러를 처리합니다.

        Args:
            error (Exception): 발생한 에러
        """
        error_message = f"트레이딩 실행 중 에러 발생: {str(error)}"
        logger.error(error_message, exc_info=True)

        # Discord 에러 알림 전송
        if self.discord_notifier:
            try:
                self.discord_notifier.send_error_notification(error_message)
            except Exception as e:
                logger.error(f"Discord 에러 알림 전송 실패: {str(e)}", exc_info=True)

        # 에러 발생 시 30분 후에 다시 시도
        self.next_execution_time = self._calculate_next_execution_time(30)
        logger.info(f"에러로 인해 {self.next_execution_time}에 다시 시도합니다.")

    def start(self, symbol: str):
        """트레이딩을 시작합니다.

        Args:
            symbol (str): 매매할 심볼 (예: BTC)
        """
        logger.info(f"{symbol} 자동 매매 시작...")
        self.is_running = True
        max_age_hours = 0.25  # 첫 실행시 기본값

        while self.is_running:
            try:
                # 다음 실행 시간까지 대기
                self._wait_until_next_execution()

                # 트레이딩 실행
                logger.info(f"{symbol} 매매 실행...")
                result = self.trading_executor.execute_trade(
                    symbol=symbol,
                    dev_mode=self.dev_mode,
                    limit=15,
                    max_age_hours=max_age_hours
                )

                # 다음 실행을 위한 max_age_hours 설정
                interval_minutes = result['decision']["next_decision"]["interval_minutes"]
                max_age_hours = interval_minutes / 60
                logger.info(f"다음 실행의 뉴스 수집 기간: {max_age_hours:.2f}시간")

                # 결과 처리
                self._handle_trading_result(
                    symbol=symbol,
                    decision=result['decision'],
                    order_result=result.get("order_result"),
                    asset_info=result["asset_info"]
                )

            except Exception as e:
                self._handle_error(e)
                max_age_hours = 1  # 에러 발생 시 기본값으로 리셋

            except KeyboardInterrupt:
                logger.info("프로그램 종료 요청됨...")
                self.stop()
                break

    def stop(self):
        """트레이딩을 중지합니다."""
        logger.info("트레이딩 중지...")
        self.is_running = False 