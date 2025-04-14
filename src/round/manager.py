import os
import uuid
import json
import requests
from datetime import datetime
from typing import Optional, List, Dict, Tuple, Type, Union
from src.utils.log_manager import LogManager, LogCategory
from src.models.market_data import TradeExecutionResult
from src.models.order import OrderRequest, OrderResponse
from .models import TradingRound, RoundOrder, RoundMetrics, RoundStatus, GPTEntryDecision, GPTExitDecision
from src.trading_analyzer import TradingAnalyzer
import time
from src.account import Account
from src.trading_order import TradingOrder
import threading
from src.models.market_data import MarketOverview
import traceback
from src.discord_notifier import DiscordNotifier
from google import genai
from .models import ModelEntryResponse, ModelExitResponse
from typing import Literal, Union
from src.ticker import Ticker


class RoundManager:
    """매매 라운드 관리자"""
    
    def __init__(
        self,
        log_manager: LogManager,
        max_active_rounds: int = 1,  # 동시 활성 라운드 수 제한
        max_history_size: int = 50   # 완료된 라운드 히스토리 크기
    ):
        self.log_manager = log_manager
        self.log_manager.start_logging_thread()
        
        self.max_active_rounds = max_active_rounds
        self.max_history_size = max_history_size
        
        # 라운드 관리
        self.active_rounds: Dict[str, TradingRound] = {}    # 활성 라운드
        self.completed_rounds: List[TradingRound] = []      # 완료된 라운드
        
        self.analyzer = TradingAnalyzer(
            api_key=os.getenv("BITHUMB_API_KEY"),
            secret_key=os.getenv("BITHUMB_SECRET_KEY"),
            log_manager=self.log_manager
        )   
        
        self.account = Account(
            api_key=os.getenv("BITHUMB_API_KEY"),
            secret_key=os.getenv("BITHUMB_SECRET_KEY"),
            log_manager=self.log_manager
        )
        
        self.order = TradingOrder(
            api_key=os.getenv("BITHUMB_API_KEY"),
            secret_key=os.getenv("BITHUMB_SECRET_KEY"),
            log_manager=self.log_manager
        )
        
        self.discord_notifier = DiscordNotifier(os.getenv("DISCORD_WEBHOOK_URL"), log_manager)
        
        self.gemini = genai.Client(api_key=os.getenv("GOOGLE_GEMINI_API_KEY"))
        
        self.ticker = Ticker(log_manager)
     
    def run(self, symbol: str):
        """무한 라운딩을 실행합니다.
        
        Args:
            symbol (str): 트레이딩 심볼
        """
        ROUND_INTERVAL = 60  # 라운드 간 대기 시간 (초)
        MAX_RETRIES = 3  # 최대 재시도 횟수
        
        def _handle_round_error(round_id: str, error: Exception, retry_count: int) -> None:
            """라운드 에러를 처리합니다."""
            self.log_manager.log(
                category=LogCategory.ROUND_ERROR,
                message=f"라운드 실패 (재시도 {retry_count}/{MAX_RETRIES})",
                data={
                    "round_id": round_id,
                    "symbol": symbol,
                    "error": str(error)
                }
            )
            self.discord_notifier.send_error_notification(
                f"라운드 실패 (재시도 {retry_count}/{MAX_RETRIES})\n"
                f"라운드: {round_id}\n"
                f"에러: {error}"
            )
        
        def _execute_single_round() -> bool:
            """단일 라운드를 실행합니다."""
            try:
                # 1. 라운드 생성
                round = self.create_round(symbol)
                if not round:
                    return False
                    
                round_id = round.id
                
                # 2. 관찰 시작
                if not self.start_watching(round_id):
                    self.log_manager.log(
                        category=LogCategory.ROUND_ERROR,
                        message="라운드 관찰 실패",
                        data={"round_id": round_id, "symbol": symbol}
                    )
                    return False
                
                if not self.discord_notifier.send_start_round_notification(round):
                    self.log_manager.log(
                        category=LogCategory.ROUND_ERROR,
                        message="라운드 시작 알림 전송 실패",
                        data={"round_id": round_id, "symbol": symbol}
                    )
                    return False
                
                # 3. 모니터링 시작
                if not self.start_monitoring(round_id):
                    self.log_manager.log(
                        category=LogCategory.ROUND_ERROR,
                        message="라운드 모니터링 실패",
                        data={"round_id": round_id, "symbol": symbol}
                    )
                    return False
                
                # 4. 라운드 종료 처리
                summary = self.get_round(round_id)
                
                if not self.discord_notifier.send_end_round_notification(round):
                    self.log_manager.log(
                        category=LogCategory.ROUND_ERROR,
                        message="라운드 종료 알림 전송 실패",
                        data={"round_id": round_id, "symbol": symbol}
                    )
                    return False
                
                # 5. 성공 로깅
                self.log_manager.log(
                    category=LogCategory.ROUND,
                    message="라운드 완료",
                    data={
                        "round_id": round_id,
                        "symbol": symbol,
                        "summary": summary
                    }
                )
                self.active_rounds.pop(round_id)
                
                return True
                
            except Exception as e:
                self.log_manager.log(
                    category=LogCategory.ROUND_ERROR,
                    message="라운드 실행 중 오류 발생",
                    data={
                        "round_id": round_id if 'round_id' in locals() else None,
                        "symbol": symbol,
                        "error": str(e)
                    }
                )
                return False
        
        # 무한 라운딩 시작
        self.log_manager.log(
            category=LogCategory.ROUND,
            message="무한 라운딩 시작",
            data={
                "symbol": symbol,
                "round_interval": ROUND_INTERVAL,
                "max_retries": MAX_RETRIES
            }
        )
        
        while True:
            retry_count = 0
            round_success = False
            
            # 재시도 로직
            while retry_count < MAX_RETRIES and not round_success:
                try:
                    round_success = _execute_single_round()
                    if round_success:
                        retry_count = 0  # 성공 시 재시도 카운트 초기화
                    else:
                        retry_count += 1
                        if retry_count < MAX_RETRIES:
                            self.log_manager.log(
                                category=LogCategory.ROUND_WARNING,
                                message=f"라운드 재시도 ({retry_count}/{MAX_RETRIES})",
                                data={"symbol": symbol}
                            )
                            time.sleep(ROUND_INTERVAL)  # 재시도 전 대기
                            
                except Exception as e:
                    retry_count += 1
                    _handle_round_error(
                        'round_id' if 'round_id' in locals() else None,
                        e,
                        retry_count
                    )
                    if retry_count < MAX_RETRIES:
                        time.sleep(ROUND_INTERVAL)  # 재시도 전 대기
            
            # 최대 재시도 횟수 초과 시 알림
            if retry_count >= MAX_RETRIES:
                self.discord_notifier.send_error_notification(
                    f"라운드 최대 재시도 횟수 초과\n"
                    f"심볼: {symbol}\n"
                    f"다음 라운드 시작까지 {ROUND_INTERVAL}초 대기"
                )
            
            # 다음 라운드 전 대기
            self.log_manager.log(
                category=LogCategory.ROUND,
                message="다음 라운드 대기 중",
                data={
                    "symbol": symbol,
                    "wait_time": ROUND_INTERVAL,
                    "last_round_success": round_success
                }
            )
            time.sleep(ROUND_INTERVAL)

    def create_round(
        self,
        symbol: str
    ) -> Optional[TradingRound]:
        """새로운 매매 라운드를 생성합니다.
        
        Args:
            symbol (str): 거래 심볼
            
        Returns:
            Optional[TradingRound]: 생성된 라운드 또는 None
        """
        try:
            # 동시 활성 라운드 수 제한 확인
            if len(self.active_rounds) >= self.max_active_rounds:
                self.log_manager.log(
                    category=LogCategory.ROUND,
                    message=f"최대 활성 라운드 수 초과: {len(self.active_rounds)}/{self.max_active_rounds}"
                )
                return None
            
            # 이미 해당 심볼의 활성 라운드가 있는지 확인
            if any(r.symbol == symbol for r in self.active_rounds.values()):
                self.log_manager.log(
                    category=LogCategory.ROUND,
                    message=f"이미 활성화된 {symbol} 라운드가 있습니다."
                )
                return None
            
            # 새 라운드 생성
            round_id = str(uuid.uuid4())
            new_round = TradingRound(
                id=round_id,
                symbol=symbol,
                start_time=datetime.now(),
                status=RoundStatus.CREATED
            )
            
            # 활성 라운드에 추가
            self.active_rounds[round_id] = new_round
            
            self.log_manager.log(
                category=LogCategory.ROUND,
                message=f"새로운 {symbol} 라운드 생성",
                data={
                    "round_id": round_id,
                    "symbol": symbol
                }
            )
            
            return new_round
            
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ROUND_ERROR,
                message=f"라운드 생성 실패: {str(e)}",
                data={"symbol": symbol}
            )
            return None

    def set_round_targets(
        self,
        round_id: str,
        take_profit: float,
        stop_loss: float,
        current_price: float
    ) -> bool:
        """라운드의 목표가와 손절가를 설정합니다.
        
        Args:
            round_id (str): 라운드 ID
            take_profit (float): 목표가
            stop_loss (float): 손절가
            current_price (float): 현재 시장 가격
            
        Returns:
            bool: 설정 성공 여부
        """
        try:
            trading_round = self.active_rounds.get(round_id)
            if not trading_round:
                return False
            
            # 목표가와 손절가 설정
            trading_round.take_profit = take_profit
            trading_round.stop_loss = stop_loss
            
            self.log_manager.log(
                category=LogCategory.ROUND,
                message=f"라운드 목표가/손절가 설정",
                data={
                    "round_id": round_id,
                    "symbol": trading_round.symbol,
                    "take_profit": take_profit,
                    "stop_loss": stop_loss,
                    "current_price": current_price,
                    "profit_rate": ((take_profit - current_price) / current_price) * 100,
                    "loss_rate": ((current_price - stop_loss) / current_price) * 100
                }
            )
            
            return True
            
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ROUND_ERROR,
                message=f"목표가/손절가 설정 실패: {str(e)}",
                data={"round_id": round_id}
            )
            return False
    
    def get_round(self, round_id: str) -> Optional[TradingRound]:
        """특정 라운드를 조회합니다."""
        return self.active_rounds.get(round_id)
    
    def get_active_round_by_symbol(self, symbol: str) -> Optional[TradingRound]:
        """심볼의 활성 라운드를 조회합니다."""
        for round in self.active_rounds.values():
            if round.symbol == symbol:
                return round
        return None
    
    def update_round_status(
        self,
        round_id: str,
        new_status: str,
        reason: Optional[List[str]] = None
    ) -> bool:
        """라운드의 상태를 업데이트합니다.
        
        Args:
            round_id (str): 라운드 ID
            new_status (str): 새로운 상태
            reason (Optional[str]): 상태 변경 이유
            
        Returns:
            bool: 업데이트 성공 여부
        """
        try:
            trading_round = self.active_rounds.get(round_id)
            if not trading_round:
                self.log_manager.log(
                    category=LogCategory.ROUND_ERROR,
                    message="라운드를 찾을 수 없음",
                    data={"round_id": round_id}
                )
                return False
                
            # 이전 상태 저장
            previous_status = trading_round.status
            
            # 상태 업데이트
            trading_round.status = new_status
            
            # ENTRY_READY 상태일 때 매수 이유 저장
            if new_status == RoundStatus.ENTRY_READY and reason:
                trading_round.entry_reason = reason
                
            # 상태별 추가 처리
            if new_status == RoundStatus.COMPLETED:
                trading_round.end_time = datetime.now()
                trading_round.exit_reason = reason
            elif new_status == RoundStatus.FAILED:
                trading_round.end_time = datetime.now()
                trading_round.exit_reason = f"실패: {reason}" if reason else "알 수 없는 실패"
                
            self.log_manager.log(
                category=LogCategory.ROUND,
                message="라운드 상태 변경",
                data={
                    "round_id": round_id,
                    "previous_status": previous_status,
                    "new_status": new_status,
                    "reason": reason,
                    "entry_reason": trading_round.entry_reason if new_status == RoundStatus.ENTRY_READY else None
                }
            )
            
            return True
            
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ROUND_ERROR,
                message=f"라운드 상태 업데이트 실패: {str(e)}",
                data={
                    "round_id": round_id,
                    "new_status": new_status,
                    "reason": reason
                }
            )
            return False
    
    def add_order_to_round(
        self,
        round_id: str,
        order_response: OrderResponse,
        order_type: str
    ) -> bool:
        """라운드에 주문을 추가합니다."""
        try:
            trading_round = self.active_rounds.get(round_id)
            if not trading_round:
                return False
            
            # 총 거래량과 평균 체결가 계산
            total_volume = sum(float(trade.volume) for trade in order_response.trades) if order_response.trades else 0.0
            avg_price = (
                sum(float(trade.price) * float(trade.volume) for trade in order_response.trades) / total_volume
                if total_volume > 0 else 0.0
            )
            
            # 주문 객체 생성
            order = RoundOrder(
                order_id=order_response.uuid,
                timestamp=datetime.now(),
                price=avg_price,
                volume=total_volume,
                type=order_type,
                status='completed' if order_response.state == 'complete' else 'pending',
                order_result=order_response
            )
            
            # 주문 타입에 따라 저장
            if order_type == 'entry':
                trading_round.entry_order = order
                log_category = LogCategory.ROUND_ENTRY
            else:
                trading_round.exit_order = order
                log_category = LogCategory.ROUND_EXIT
            
            self.log_manager.log(
                category=log_category,
                message=f"라운드에 {order_type} 주문 추가",
                data={
                    "round_id": round_id,
                    "order_id": order_response.uuid,
                    "avg_price": avg_price,
                    "total_volume": total_volume,
                    "trades_count": len(order_response.trades) if order_response.trades else 0,
                    "state": order_response.state
                }
            )
            
            return True
            
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ROUND_ERROR,
                message=f"주문 추가 중 오류 발생: {str(e)}",
                data={
                    "round_id": round_id,
                    "order_type": order_type
                }
            )
            return False
    
    def add_decision_to_round(
        self,
        round_id: str,
        result: TradeExecutionResult
    ) -> bool:
        """라운드에 매매 판단을 추가합니다."""
        try:
            trading_round = self.active_rounds.get(round_id)
            if not trading_round:
                return False
                
            trading_round.add_decision(result)
            
            self.log_manager.log(
                category=LogCategory.TRADING,
                message="매매 판단 추가",
                data={
                    "round_id": round_id,
                    "action": result.decision_result.decision.action,
                    "success": result.success
                }
            )
            
            return True
            
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ERROR,
                message=f"매매 판단 추가 실패: {str(e)}",
                data={"round_id": round_id}
            )
            return False
    
    def update_round_metrics(
        self,
        round_id: str,
        current_price: float
    ) -> bool:
        """라운드의 성과 지표를 업데이트합니다."""
        try:
            trading_round = self.active_rounds.get(round_id)
            if not trading_round:
                return False
                
            trading_round.update_metrics(current_price)
            
            # 목표가/손절가 도달 여부 확인
            if trading_round.metrics:
                if current_price >= trading_round.take_profit:
                    self.update_round_status(
                        round_id=round_id,
                        new_status=RoundStatus.COMPLETED,
                        reason='목표가 도달'
                    )
                elif current_price <= trading_round.stop_loss:
                    self.update_round_status(
                        round_id=round_id,
                        new_status=RoundStatus.COMPLETED,
                        reason='손절가 도달'
                    )
            
            self.log_manager.log(
                category=LogCategory.ROUND_METRICS,
                message="라운드 성과 지표 업데이트",
                data={
                    "round_id": round_id,
                    "current_price": current_price,
                    "metrics": trading_round.metrics.to_dict() if trading_round.metrics else None
                }
            )
            
            return True
            
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ROUND_ERROR,
                message=f"성과 지표 업데이트 실패: {str(e)}",
                data={"round_id": round_id}
            )
            return False
    
    def get_round_summary(self, round_id: str) -> Optional[Dict]:
        """라운드의 요약 정보를 반환합니다."""
        try:
            trading_round = self.active_rounds.get(round_id)
            if not trading_round:
                trading_round = next(
                    (r for r in self.completed_rounds if r.id == round_id),
                    None
                )
            if not trading_round:
                return None
                
            # 기본 정보
            summary = {
                "id": trading_round.id,
                "symbol": trading_round.symbol,
                "status": trading_round.status,
                "duration": trading_round.duration,
                "entry_price": trading_round.entry_order.price if trading_round.entry_order else None,
                "current_metrics": trading_round.metrics.to_dict() if trading_round.metrics else None,
                "take_profit": trading_round.take_profit,
                "stop_loss": trading_round.stop_loss,
                "exit_reason": trading_round.exit_reason,
                "decision_count": len(trading_round.decision_history)
            }
            
            # 모니터링 관련 정보 추가
            if trading_round.status == RoundStatus.HOLDING:
                summary.update({
                    "monitoring_status": {
                        "last_check_time": trading_round.last_check_time.isoformat() if hasattr(trading_round, 'last_check_time') else None,
                        "current_price": trading_round.current_price if hasattr(trading_round, 'current_price') else None,
                        "profit_loss_rate": trading_round.metrics.profit_loss_rate if trading_round.metrics else None,
                        "holding_time": trading_round.holding_time if hasattr(trading_round, 'holding_time') else None
                    }
                })
            
            return summary
            
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ERROR,
                message=f"라운드 요약 정보 생성 실패: {str(e)}",
                data={"round_id": round_id}
            )
            return None

    def execute_entry_process(self, round_id: str) -> bool:
        """매수 진입 프로세스를 실행합니다.
        
        Args:
            round_id (str): 라운드 ID
            
        Returns:
            bool: 성공 여부
            
        Note:
            전체 매수 진입 프로세스를 관리합니다:
            1. 라운드 상태 검증
            2. 주문 생성 및 실행
            3. 주문 체결 대기 및 확인
            4. 포지션 보유 상태로 전환
        """
        try:
            # 1. 라운드 상태 검증
            trading_round = self.active_rounds.get(round_id)
            if not trading_round:
                self._log_entry_error(round_id, "라운드를 찾을 수 없음")
                return False
                
            if trading_round.status != RoundStatus.ENTRY_READY:
                self._log_entry_error(
                    round_id,
                    "부적절한 라운드 상태",
                    {
                        "current_status": trading_round.status,
                        "required_status": RoundStatus.ENTRY_READY
                    }
                )
                return False
            
            # 2. 주문 생성 및 실행
            try:
                # 2-1. 프로세스 시작 로깅
                self.log_manager.log(
                    category=LogCategory.ROUND_ENTRY,
                    message="매수 진입 프로세스 시작",
                    data={
                        "round_id": round_id,
                        "symbol": trading_round.symbol,
                        "take_profit": trading_round.take_profit,
                        "stop_loss": trading_round.stop_loss
                    }
                )
                
                # 2-2. 주문 생성
                order_request = self.create_entry_order(round_id)
                if not order_request:
                    self._log_entry_error(round_id, "주문 생성 실패")
                    return False
                
                # 2-3. 주문 실행
                order_response = self.execute_entry_order(round_id, order_request)
                if not order_response:
                    self._log_entry_error(
                        round_id,
                        "주문 실행 실패",
                        {"order_request": order_request.to_dict()}
                    )
                    return False
                
                # 2-4. 주문 상태 기록
                if not self.confirm_entry_order(round_id, order_response):
                    self._log_entry_error(
                        round_id,
                        "주문 상태 기록 실패",
                        {"order_response": order_response.to_dict()}
                    )
                    return False
                
            except Exception as e:
                self._log_entry_error(
                    round_id,
                    f"주문 생성/실행 중 오류: {str(e)}",
                    {"error": str(e)}
                )
                return self._revert_to_watching(round_id, "주문 생성/실행 실패")
            
            # 3. 주문 체결 대기 및 확인
            try:
                completed_order = self.wait_order_completion(order_response)
                if not completed_order:
                    self._log_entry_error(
                        round_id,
                        "주문 체결 실패",
                        {"order_id": order_response.uuid}
                    )
                    return self._revert_to_watching(round_id, "주문 체결 실패")
                
                # 주문 정보 라운드에 추가
                if not self.add_order_to_round(round_id, completed_order, 'entry'):
                    self._log_entry_error(
                        round_id,
                        "주문 정보 추가 실패",
                        {"completed_order": completed_order.to_dict()}
                    )
                    return self._revert_to_watching(round_id, "주문 정보 추가 실패")
                
            except Exception as e:
                self._log_entry_error(
                    round_id,
                    f"주문 체결 확인 중 오류: {str(e)}",
                    {"error": str(e)}
                )
                return self._revert_to_watching(round_id, "주문 체결 확인 실패")
            
            # 4. 포지션 보유 상태로 전환
            try:
                if not self.update_round_status(
                    round_id=round_id,
                    new_status=RoundStatus.HOLDING,
                    reason=self._get_entry_completion_message(completed_order)
                ):
                    self._log_entry_error(
                        round_id,
                        "상태 전환 실패",
                        {"completed_order": completed_order.to_dict()}
                    )
                    return False
                
                # 성공 로깅
                self.log_manager.log(
                    category=LogCategory.ROUND_ENTRY,
                    message="매수 진입 프로세스 완료",
                    data={
                        "round_id": round_id,
                        "symbol": trading_round.symbol,
                        "entry_price": completed_order.price,
                        "entry_volume": completed_order.volume,
                        "take_profit": trading_round.take_profit,
                        "stop_loss": trading_round.stop_loss,
                        "trades_count": len(completed_order.trades) if completed_order.trades else 0
                    }
                )
                
                return True
                
            except Exception as e:
                self._log_entry_error(
                    round_id,
                    f"상태 전환 중 오류: {str(e)}",
                    {"error": str(e)}
                )
                return False
            
        except Exception as e:
            self._log_entry_error(
                round_id,
                f"매수 진입 프로세스 중 예외 발생: {str(e)}",
                {"error": str(e)}
            )
            return self._revert_to_watching(round_id, "예외 발생")
    
    def _log_entry_error(self, round_id: str, message: str, additional_data: dict = None) -> None:
        """매수 진입 관련 에러를 로깅합니다."""
        data = {"round_id": round_id}
        if additional_data:
            data.update(additional_data)
            
        self.log_manager.log(
            category=LogCategory.ROUND_ERROR,
            message=f"매수 진입 실패: {message}",
            data=data
        )
    
    def _revert_to_watching(self, round_id: str, reason: str) -> bool:
        """watching 상태로 복귀하고 False를 반환합니다."""
        self.revert_to_watching(round_id, f"{reason}로 관찰 상태로 복귀")
        return False
    
    def _get_entry_completion_message(self, completed_order) -> str:
        """매수 완료 메시지를 생성합니다."""
        trades_info = ""
        if completed_order.trades:
            trades_count = len(completed_order.trades)
            trades_info = f" ({trades_count}건 체결)"
            
        return (
            f"매수 주문 체결 완료{trades_info} "
            f"(체결가: {completed_order.price}, 수량: {completed_order.volume})"
        )

    def start_watching(
        self,
        round_id: str,
        interval: float = 60,
        max_watching_time: float = 9999.0
    ) -> bool:
        """라운드를 시작하고 매수 기회를 지속적으로 탐색합니다."""
        try:
            trading_round = self.active_rounds.get(round_id)
            if not trading_round:
                self.log_manager.log(
                    category=LogCategory.ROUND_ERROR,
                    message="라운드를 찾을 수 없음",
                    data={"round_id": round_id}
                )
                return False
            
            # 상태 전환
            if not self.update_round_status(round_id, RoundStatus.WATCHING, "매수 기회 탐색 시작"):
                return False
            
            start_time = datetime.now()
            watch_count = 0
            
            while True:
                watch_count += 1
                current_time = datetime.now()
                elapsed_minutes = (current_time - start_time).total_seconds() / 60
                
                # 최대 관찰 시간 초과 확인
                if elapsed_minutes >= max_watching_time:
                    self.update_round_status(
                        round_id=round_id,
                        new_status=RoundStatus.FAILED,
                        reason=f"최대 관찰 시간 초과 ({max_watching_time}분)"
                    )
                    return False
                
                # 라운드 상태 재확인
                trading_round = self.active_rounds.get(round_id)
                if not trading_round or trading_round.status != RoundStatus.WATCHING:
                    return False
                
                try:
                    # 시장 정보 수집
                    market_data = self.analyzer.get_market_overview(trading_round.symbol)
                    
                    self.log_manager.log(
                        category=LogCategory.ROUND,
                        message=f"시장 정보 수집 (#{watch_count})",
                        data={
                            "round_id": round_id,
                            "symbol": trading_round.symbol,
                            "current_price": market_data.current_price,
                            "rsi_14": market_data.rsi_14,
                            "volatility_15m": market_data.volatility_15m,
                            "price_trend": market_data.price_trend_1m,
                            "volume_trend": market_data.volume_trend_1m,
                            "candle_strength": market_data.candle_strength,
                            "elapsed_minutes": elapsed_minutes
                        }
                    )
                    
                    # GPT 매수 진입 결정 요청
                    entry_decision = self.get_entry_decision(round_id, market_data, model_type="gemini")
                    
                    if not entry_decision:
                        self.log_manager.log(
                            category=LogCategory.ROUND_ERROR,
                            message="GPT 매수 진입 결정 실패",
                            data={"round_id": round_id}
                        )
                        time.sleep(interval)
                        continue
                    
                    # 매수 진입이 추천되는 경우
                    if entry_decision.should_enter:
                        # 목표가와 손절가 설정
                        if not self.set_round_targets(
                            round_id=round_id,
                            take_profit=entry_decision.target_price,
                            stop_loss=entry_decision.stop_loss_price,
                            current_price=market_data.current_price
                        ):
                            self.log_manager.log(
                                category=LogCategory.ROUND_ERROR,
                                message="목표가/손절가 설정 실패",
                                data={"round_id": round_id}
                            )
                            time.sleep(interval)
                            continue
                        
                        # 매수 준비 상태로 전환
                        if self.prepare_entry(round_id, entry_decision.reasons):
                            # 매수 진입 프로세스 실행
                            if self.execute_entry_process(round_id):
                                self.log_manager.log(
                                    category=LogCategory.ROUND,
                                    message="매수 진입 결정 및 실행 완료",
                                    data={
                                        "round_id": round_id,
                                        "target_price": entry_decision.target_price,
                                        "stop_loss_price": entry_decision.stop_loss_price,
                                        "reasons": entry_decision.reasons,
                                        "watch_count": watch_count,
                                        "elapsed_minutes": elapsed_minutes
                                    }
                                )
                                return True
                            else:
                                # 매수 실패 시 watching 상태로 복귀
                                self.revert_to_watching(round_id, "매수 주문 실패")
                                time.sleep(interval)
                                continue
                    else:
                        self.log_manager.log(
                            category=LogCategory.ROUND,
                            message="매수 진입 보류",
                            data={
                                "round_id": round_id,
                                "reasons": entry_decision.reasons,
                                "watch_count": watch_count,
                                "elapsed_minutes": elapsed_minutes
                            }
                        )
                    
                    # 다음 분석까지 대기
                    time.sleep(interval)
                    
                except Exception as e:
                    self.log_manager.log(
                        category=LogCategory.ROUND_ERROR,
                        message=f"시장 정보 수집 실패: {str(e)}",
                        data={
                            "round_id": round_id,
                            "symbol": trading_round.symbol,
                            "watch_count": watch_count,
                            "elapsed_minutes": elapsed_minutes
                        }
                    )
                    time.sleep(interval)  # 에러 발생 시에도 대기 후 재시도
                    continue
                    
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ROUND_ERROR,
                message=f"라운드 시작 실패: {str(e)}",
                data={"round_id": round_id}
            )
            return False

    def prepare_entry(self, round_id: str, reason: List[str]) -> bool:
        """매수 시그널이 발생하여 진입 준비 상태로 변경합니다."""
        return self.update_round_status(round_id, RoundStatus.ENTRY_READY, reason)

    def confirm_entry_order(self, round_id: str, order_response: OrderResponse) -> bool:
        """매수 주문 결과를 라운드에 기록합니다."""
        try:

            # 주문 정보를 라운드에 추가
            if self.add_order_to_round(round_id, order_response, 'entry'):
                # 상태 업데이트
                return self.update_round_status(
                    round_id=round_id,
                    new_status=RoundStatus.ENTRY_ORDERED,
                    reason=f"매수 주문 완료 (주문번호: {order_response.uuid})"
                )
            
            return False
            
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ROUND_ERROR,
                message=f"매수 주문 확인 중 오류 발생: {str(e)}",
                data={
                    "round_id": round_id,
                    "order_response": order_response.to_dict() if order_response else None
                }
            )
            return False

    def confirm_entry_execution(self, round_id: str) -> bool:
        """매수가 체결되어 포지션을 보유하게 되었음을 기록합니다."""
        return self.update_round_status(round_id, RoundStatus.HOLDING, "매수 주문 체결")

    def confirm_exit_order(self, round_id: str, order_response: OrderResponse) -> bool:
        """매도 주문 결과를 라운드에 기록합니다.
        
        Args:
            round_id (str): 라운드 ID
            order_response (OrderResponse): 주문 응답 객체
            
        Returns:
            bool: 성공 여부
        """
        try:
            # 주문 정보를 라운드에 추가
            if self.add_order_to_round(round_id, order_response, 'exit'):
                # 상태 업데이트
                return self.update_round_status(
                    round_id=round_id,
                    new_status=RoundStatus.EXIT_ORDERED,
                    reason=f"매도 주문 완료 (주문번호: {order_response.uuid})"
                )
            
            return False
            
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ROUND_ERROR,
                message=f"매도 주문 확인 중 오류 발생: {str(e)}",
                data={
                    "round_id": round_id,
                    "order_response": order_response.to_dict() if order_response else None
                }
            )
            return False

    def revert_to_watching(self, round_id: str, reason: str) -> bool:
        """진입/청산 시도를 취소하고 관찰 상태로 되돌립니다."""
        trading_round = self.active_rounds.get(round_id)
        if not trading_round:
            return False
            
        if trading_round.status in [RoundStatus.ENTRY_READY, RoundStatus.ENTRY_ORDERED]:
            return self.update_round_status(round_id, RoundStatus.WATCHING, reason)
        return False

    def _generate_market_prompt(self, round_id: str, market_data: MarketOverview) -> Tuple[str, str]:
        """시장 데이터를 기반으로 GPT에게 전달할 프롬프트를 생성합니다.
        
        Args:
            round_id (str): 라운드 ID
            market_data (MarketOverview): 시장 데이터
            
        Returns:
            Tuple[str, str]: (시스템 프롬프트, 사용자 프롬프트) 튜플
        """
        trading_round = self.active_rounds.get(round_id)
        if not trading_round:
            return "", ""
            
        # 시스템 프롬프트 정의
        system_prompt = """당신은 초단기 암호화폐 매매에 특화된 스캘핑 트레이딩 전문가입니다.
지금 당신은 실시간 시장 데이터를 기반으로 매수 진입 가능성을 평가해야 합니다.

어떤 조건도 강제하지 않으며, 아래의 시장 정보를 종합적으로 해석하여
지금 시점에서의 매수 진입 여부를 자유롭게 판단하십시오.

당신의 임무:
1. 시장 데이터를 바탕으로 현재 매수 진입이 타당한지 결정
2. 진입이 타당하다면, 목표가(target_price)와 손절가(stop_loss_price)를 제시
3. 판단 이유는 반드시 3가지로 구체적으로 설명
4. 수익 실현 가능성과 리스크를 균형 있게 고려

단, 다음은 반드시 지켜야 합니다:
- 목표가는 반드시 현재가보다 높게 (정수)
- 손절가는 반드시 현재가보다 낮게 (정수)
- 응답은 반드시 아래 JSON 형식을 따를 것:

{
  "should_enter": true/false,
  "target_price": 0,
  "stop_loss_price": 0,
  "reasons": [
    "첫 번째 근거",
    "두 번째 근거",
    "세 번째 근거"
  ]
}
"""
            
        user_prompt = f"""
현재 {trading_round.symbol} 매수 진입 기회를 분석해 주세요.

[기본 시장 정보]
- 현재가: {market_data.current_price:,.0f}원
- 거래량 동향(1분): {market_data.volume_trend_1m}
- 가격 동향(1분): {market_data.price_trend_1m}
- 캔들 강도: {market_data.candle_strength} (실체비율: {market_data.candle_body_ratio:.1%})

[기술적 지표]
- RSI: 3분({market_data.rsi_3:.1f}), 7분({market_data.rsi_7:.1f})
- 이동평균: MA1({market_data.ma1:,.0f}), MA3({market_data.ma3:,.0f}), MA5({market_data.ma5:,.0f}), MA10({market_data.ma10:,.0f})
- 변동성: 3분({market_data.volatility_3m:.2f}%), 5분({market_data.volatility_5m:.2f}%), 10분({market_data.volatility_10m:.2f}%)
- VWAP(3분): {market_data.vwap_3m:,.0f}원
- 볼린저밴드 폭: {market_data.bb_width:.2f}%

[호가 분석]
- 매수/매도 비율: {market_data.order_book_ratio:.2f}
- 스프레드: {market_data.spread:.3f}%

[특이사항]
- 5분 신고가 돌파: {'O' if market_data.new_high_5m else 'X'}
- 5분 신저가 돌파: {'O' if market_data.new_low_5m else 'X'}

{{
    "should_enter": true/false,
    "target_price": 0,     
    "stop_loss_price": 0,
    "reasons": [
        "첫 번째 근거",
        "두 번째 근거",
        "세 번째 근거"
    ]
}}
"""
        
        self.log_manager.log(
            category=LogCategory.ROUND,
            message="매수 진입 프롬프트 생성",
            data={
                "round_id": round_id,
                "symbol": trading_round.symbol,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt
            }
        )
        
        return system_prompt, user_prompt

    def _parse_gpt_entry_response(
        self,
        round_id: str,
        response: dict,
        current_price: float
    ) -> Optional[GPTEntryDecision]:
        """GPT의 매수 진입 응답을 파싱하여 결정 객체를 생성합니다.
        
        Args:
            round_id (str): 라운드 ID
            response (str): GPT의 JSON 응답
            current_price (float): 현재 시장 가격
            
        Returns:
            Optional[GPTEntryDecision]: 파싱된 결정 객체 또는 None
        """
        try:
            # 1. 응답 검증
            data = response
            
            # 5. 필수 필드 검증
            required_fields = ['should_enter', 'target_price', 'stop_loss_price', 'reasons']
            if not all(field in data for field in required_fields):
                raise ValueError("필수 필드 누락")
            
            # 6. 데이터 타입 검증
            if not isinstance(data['should_enter'], bool):
                raise ValueError("should_enter must be boolean")
            if not isinstance(data['target_price'], (int, float)):
                raise ValueError("target_price must be number")
            if not isinstance(data['stop_loss_price'], (int, float)):
                raise ValueError("stop_loss_price must be number")
            if not isinstance(data['reasons'], list) or len(data['reasons']) != 3:
                raise ValueError("reasons must be array of 3 strings")
            
            # 7. 수익률 계산
            target_profit_rate = ((data['target_price'] - current_price) / current_price) * 100
            stop_loss_rate = ((data['stop_loss_price'] - current_price) / current_price) * 100
            
            # 8. 결정 객체 생성
            decision = GPTEntryDecision(
                should_enter=data['should_enter'],
                target_profit_rate=target_profit_rate,
                stop_loss_rate=stop_loss_rate,
                reasons=data['reasons'],
                current_price=current_price,
                target_price=data['target_price'],
                stop_loss_price=data['stop_loss_price'],
                timestamp=datetime.now()
            )
            
            self.log_manager.log(
                category=LogCategory.ROUND,
                message="GPT 매수 진입 응답 파싱 완료",
                data={
                    "round_id": round_id,
                    "should_enter": decision.should_enter,
                    "target_price": decision.target_price,
                    "stop_loss_price": decision.stop_loss_price,
                    "target_profit_rate": decision.target_profit_rate,
                    "stop_loss_rate": decision.stop_loss_rate
                }
            )
            
            return decision
            
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ROUND_ERROR,
                message=f"GPT 매수 진입 응답 파싱 실패: {str(e)}",
                data={
                    "round_id": round_id,
                    "response": response,
                    "error": str(e)
                }
            )
            return None

    def _parse_gpt_exit_response(
        self,
        round_id: str,
        response: dict,
        current_price: float
    ) -> Optional[GPTExitDecision]:
        """GPT의 매도 청산 응답을 파싱합니다.
        
        Args:
            round_id (str): 라운드 ID
            response (str): GPT의 JSON 응답
            current_price (float): 현재 시장 가격
            
        Returns:
            Optional[GPTExitDecision]: 파싱된 결정 객체 또는 None
        """
        try:
            # 4. JSON 파싱
            data = response
            
            # 5. 필수 필드 검증
            required_fields = ['should_exit', 'reasons']
            if not all(field in data for field in required_fields):
                raise ValueError("필수 필드 누락")
            
            # 6. 데이터 타입 검증
            if not isinstance(data['should_exit'], bool):
                raise ValueError("should_exit must be boolean")
            if not isinstance(data['reasons'], list) or len(data['reasons']) != 3:
                raise ValueError("reasons must be array of 3 strings")
            
            # 7. 결정 객체 생성
            trading_round = self.active_rounds.get(round_id)
            if not trading_round:
                raise ValueError("라운드를 찾을 수 없음")
                
            # 현재 수익률 계산
            profit_loss_rate = ((current_price - trading_round.entry_order.price) / trading_round.entry_order.price) * 100
            
            decision = GPTExitDecision(
                should_exit=data['should_exit'],
                reasons=data['reasons'],
                current_price=current_price,
                profit_loss_rate=profit_loss_rate,
                timestamp=datetime.now()
            )
            
            # 8. 결과 로깅
            self.log_manager.log(
                category=LogCategory.ROUND,
                message="GPT 매도 청산 응답 파싱 완료",
                data={
                    "round_id": round_id,
                    "should_exit": decision.should_exit,
                    "reasons": decision.reasons,
                    "current_price": decision.current_price,
                    "profit_loss_rate": decision.profit_loss_rate
                }
            )
            
            return decision
            
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ROUND_ERROR,
                message=f"GPT 매도 청산 응답 파싱 실패: {str(e)}",
                data={
                    "round_id": round_id,
                    "response": response,
                    "error": str(e)
                }
            )
            return None

    def _call_gemini(
        self,
        prompt: str,
        response_schema: Union[Type[ModelEntryResponse], Type[ModelExitResponse]]
    ) -> Optional[Union[ModelEntryResponse, ModelExitResponse]]:
        
        response = self.gemini.models.generate_content(
            model="gemini-2.0-flash", 
            config={
                'response_mime_type': 'application/json',
                'response_schema': response_schema,
            },  
            contents=prompt
        )
        return response.parsed

    def _call_gpt(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,  # 더 결정적인 응답을 위해 0.1로 낮춤
        model: str = "gpt-4o-mini-2024-07-18",
    ) -> Optional[Dict]:
        """GPT API를 호출하여 응답을 받습니다.
        
        Args:
            system_prompt (str): GPT의 역할을 정의하는 시스템 프롬프트
            user_prompt (str): 실제 질문/요청 내용
            temperature (float): 응답의 창의성 정도 (0.0 ~ 1.0)
            
        Returns:
            Optional[Dict]: 파싱된 JSON 응답 또는 None
            
        Note:
            GPT-4-mini 사용 이유:
            1. 구조화된 데이터 분석에 충분한 성능
            2. 정형화된 JSON 응답 생성 가능
            3. 빠른 응답 속도와 낮은 비용
            4. 기술적 분석에 필요한 충분한 이해도
        """
        try:
            headers = {
                "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ],
                "temperature": temperature,
                "max_tokens": 300,  # 응답 길이도 줄임
                "response_format": { "type": "json_object" }
            }
            
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code != 200:
                self.log_manager.log(
                    category=LogCategory.ROUND_ERROR,
                    message="GPT API 호출 실패",
                    data={
                        "status_code": response.status_code,
                        "response": response.text
                    }
                )
                return None
                
            response_data = response.json()
            
            # 응답 데이터 로깅
            self.log_manager.log(
                category=LogCategory.ROUND,
                message="GPT API 응답 수신",
                data={"response": response_data}
            )
            
            if not response_data or "choices" not in response_data:
                self.log_manager.log(
                    category=LogCategory.ROUND_ERROR,
                    message="GPT API 응답 형식 오류",
                    data={"response": response_data}
                )
                return None
                
            content = response_data["choices"][0]["message"]["content"]
            
            try:
                # JSON 파싱
                decision_dict = json.loads(content)
                
                self.log_manager.log(
                    category=LogCategory.ROUND,
                    message="GPT 응답 파싱 완료",
                    data={"decision": decision_dict}
                )
                
                return decision_dict
                
            except json.JSONDecodeError as e:
                self.log_manager.log(
                    category=LogCategory.ROUND_ERROR,
                    message="GPT 응답 JSON 파싱 실패",
                    data={
                        "error": str(e),
                        "content": content
                    }
                )
                return None
                
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ROUND_ERROR,
                message="GPT API 호출 중 예외 발생",
                data={"error": str(e)}
            )
            return None

    def get_entry_decision(
        self, 
                        round_id: str,
                        market_data: MarketOverview,
                        model_type: Literal["gpt", "gemini"]   
                           ) -> Optional[GPTEntryDecision]:
        """시장 데이터를 분석하여 매수 진입 결정을 얻습니다.
        
        Args:
            round_id (str): 라운드 ID
            market_data: 시장 데이터
            
        Returns:
            Optional[GPTEntryDecision]: 매수 진입 결정 또는 None
        """
        try:            
            # 사용자 프롬프트 생성
            system_prompt, user_prompt = self._generate_market_prompt(round_id, market_data)
            if not system_prompt or not user_prompt:
                return None
            
            if model_type == "gpt":
                # GPT 호출
                response = self._call_gpt(system_prompt, user_prompt, model="gpt-4o-2024-11-20")
                decision = self._parse_gpt_entry_response(round_id, response, market_data.current_price)
            elif model_type == "gemini":
                # Gemini 호출
                parsed = self._call_gemini(f"""
                                           {system_prompt}
                                           {user_prompt}
                                           """, ModelEntryResponse)
                target_profit_rate = ((parsed.target_price - market_data.current_price) / market_data.current_price) * 100
                stop_loss_rate = ((parsed.stop_loss_price - market_data.current_price) / market_data.current_price) * 100
                decision = GPTEntryDecision(
                    should_enter=parsed.should_enter,
                    target_profit_rate=target_profit_rate,
                    stop_loss_rate=stop_loss_rate,
                    reasons=parsed.reasons,
                    current_price=market_data.current_price,
                    target_price=parsed.target_price,
                    stop_loss_price=parsed.stop_loss_price,
                    timestamp=datetime.now()
                )
            # 응답 파싱
            return decision
            
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ROUND_ERROR,
                message="매수 진입 결정 실패",
                data={
                    "round_id": round_id,
                    "error": str(e)
                }
            )
            return None

    def create_entry_order(self, round_id: str) -> Optional[OrderRequest]:
        """매수 주문을 생성합니다."""
        try:
            trading_round = self.active_rounds.get(round_id)
            if not trading_round or trading_round.status != RoundStatus.ENTRY_READY:
                self.log_manager.log(
                    category=LogCategory.ROUND_ERROR,
                    message="매수 주문 생성 실패: 라운드 상태 부적합",
                    data={
                        "round_id": round_id,
                        "status": trading_round.status if trading_round else None
                    }
                )
                return None
            
            # KRW 잔고 조회
            krw_balance = self.account.get_balance('KRW')
            if not krw_balance:
                self.log_manager.log(
                    category=LogCategory.ROUND_ERROR,
                    message="매수 주문 생성 실패: KRW 잔고 조회 실패",
                    data={"round_id": round_id}
                )
                return None
            
            available_balance = float(krw_balance['balance'])
            if available_balance <= 0:
                self.log_manager.log(
                    category=LogCategory.ROUND_ERROR,
                    message="매수 주문 생성 실패: KRW 잔고 부족",
                    data={
                        "round_id": round_id,
                        "krw_balance": available_balance
                    }
                )
                return None
            
            # 주문 금액 계산 (총 잔고의 10%)
            RATIO = 0.2
            order_amount = available_balance * RATIO
            
            # 주문 생성
            order_request = OrderRequest(
                market=f'KRW-{trading_round.symbol}',
                side='bid',
                price=order_amount,
                order_type="price",
                volume=None
            )
            
            self.log_manager.log(
                category=LogCategory.ROUND_ENTRY,
                message="매수 주문 생성",
                data={
                    "round_id": round_id,
                    "symbol": trading_round.symbol,
                    "order_amount": order_amount,
                    "available_balance": available_balance
                }
            )
            
            return order_request
            
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ROUND_ERROR,
                message=f"매수 주문 생성 중 오류 발생: {str(e)}",
                data={"round_id": round_id}
            )
            return None

    def execute_entry_order(self, round_id: str, order_request: OrderRequest) -> Optional[OrderResponse]:
        """매수 주문을 실행하고 결과를 반환합니다.
        
        Args:
            round_id (str): 라운드 ID
            order_request (OrderRequest): 주문 요청 객체
            
        Returns:
            Optional[OrderResponse]: 주문 응답 객체 또는 None
            
        Note:
            - 주문 실행 전 라운드 상태 검증
            - 실제 거래소 API를 통한 주문 실행
            - 주문 실행 결과에 대한 상세 로깅
        """
        try:
            # 1. 라운드 상태 검증
            trading_round = self.active_rounds.get(round_id)
            if not trading_round:
                self.log_manager.log(
                    category=LogCategory.ROUND_ERROR,
                    message="매수 주문 실행 실패: 라운드를 찾을 수 없음",
                    data={"round_id": round_id}
                )
                return None
                
            if trading_round.status != RoundStatus.ENTRY_READY:
                self.log_manager.log(
                    category=LogCategory.ROUND_ERROR,
                    message="매수 주문 실행 실패: 부적절한 라운드 상태",
                    data={
                        "round_id": round_id,
                        "current_status": trading_round.status,
                        "required_status": RoundStatus.ENTRY_READY
                    }
                )
                return None
            
            # 2. 주문 요청 검증
            if not order_request.market or not order_request.price:
                self.log_manager.log(
                    category=LogCategory.ROUND_ERROR,
                    message="매수 주문 실행 실패: 잘못된 주문 정보",
                    data={
                        "round_id": round_id,
                        "market": order_request.market,
                        "price": order_request.price
                    }
                )
                return None
            
            # 3. 주문 실행 전 로깅
            self.log_manager.log(
                category=LogCategory.ROUND_ENTRY,
                message="매수 주문 실행 시작",
                data={
                    "round_id": round_id,
                    "symbol": trading_round.symbol,
                    "order_request": {
                        "market": order_request.market,
                        "side": order_request.side,
                        "price": order_request.price,
                        "order_type": order_request.order_type
                    }
                }
            )
            
            # 4. 주문 실행
            order_response = self.order.create_order_v2(order_request)
            if not order_response:
                self.log_manager.log(
                    category=LogCategory.ROUND_ERROR,
                    message="매수 주문 실행 실패: API 응답 없음",
                    data={
                        "round_id": round_id,
                        "order_request": order_request.to_dict()
                    }
                )
                return None
            
            # 6. 주문 실행 결과 로깅
            self.log_manager.log(
                category=LogCategory.ROUND_ENTRY,
                message="매수 주문 실행 완료",
                data={
                    "round_id": round_id,
                    "order_id": order_response.uuid,
                    "initial_state": order_response.state,
                    "price": order_response.price,
                    "volume": order_response.volume
                }
            )
            
            return order_response
            
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ROUND_ERROR,
                message=f"매수 주문 실행 중 예외 발생: {str(e)}",
                data={
                    "round_id": round_id,
                    "order_request": order_request.to_dict() if order_request else None
                }
            )
            return None

    def wait_order_completion(self, order_response: OrderResponse) -> Optional[OrderResponse]:
        """주문 완료를 대기합니다.
        
        Args:
            order_response (OrderResponse): 초기 주문 응답
            
        Returns:
            Optional[OrderResponse]: 완료된 주문 응답 또는 None
            
        Note:
            - 최대 10회까지 0.5초 간격으로 주문 상태를 확인
            - complete: 주문 완료, wait: 대기 중, 그 외(cancel, error 등)는 실패로 처리
        """
        try:
            MAX_RETRIES = 10
            RETRY_INTERVAL = 0.5
            retry_count = 0
            
            while retry_count < MAX_RETRIES:
                wait_res = self.order.get_order_v2(order_response.uuid)
                if not wait_res:
                    self.log_manager.log(
                        category=LogCategory.ROUND_ERROR,
                        message="주문 상태 조회 실패",
                        data={
                            "order_id": order_response.uuid,
                            "retry_count": retry_count
                        }
                    )
                    return None
                
                if wait_res.state == 'done':
                    self.log_manager.log(
                        category=LogCategory.ROUND_ENTRY,
                        message="주문 체결 완료",
                        data={
                            "order_id": wait_res.uuid,
                            "price": wait_res.price,
                            "volume": wait_res.volume,
                            "retry_count": retry_count
                        }
                    )
                    return wait_res
                    
                elif wait_res.state == 'wait':
                    self.log_manager.log(
                        category=LogCategory.ROUND,
                        message=f"주문 체결 대기 중... ({retry_count + 1}/{MAX_RETRIES})",
                        data={
                            "order_id": wait_res.uuid,
                            "state": wait_res.state
                        }
                    )
                    time.sleep(RETRY_INTERVAL)
                    retry_count += 1
                    
                else:  # cancel, error 등
                    self.log_manager.log(
                        category=LogCategory.ROUND_ERROR,
                        message=f"주문 실패: {wait_res.state}",
                        data={
                            "order_id": wait_res.uuid,
                            "state": wait_res.state,
                            "error_code": wait_res.error_code if hasattr(wait_res, 'error_code') else None,
                            "error_message": wait_res.error_message if hasattr(wait_res, 'error_message') else None
                        }
                    )
                    return None
            
            # 최대 재시도 횟수 초과
            self.log_manager.log(
                category=LogCategory.ROUND_ERROR,
                message="주문 체결 대기 시간 초과",
                data={
                    "order_id": order_response.uuid,
                    "max_retries": MAX_RETRIES,
                    "total_wait_time": MAX_RETRIES * RETRY_INTERVAL
                }
            )
            return None
            
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ROUND_ERROR,
                message=f"주문 완료 대기 중 오류 발생: {str(e)}",
                data={
                    "order_id": order_response.uuid
                }
            )
            return None

    def create_exit_order(self, round_id: str) -> Optional[OrderRequest]:
        """매도 주문을 생성합니다.
        
        Args:
            round_id (str): 라운드 ID
            
        Returns:
            Optional[OrderRequest]: 생성된 주문 요청 객체
            
        Note:
            1. 라운드 상태 검증
            2. 진입 주문 정보 확인
            3. 잔고 조회
            4. 매도 주문 생성
        """
        try:
            # 1. 라운드 상태 검증
            trading_round = self.active_rounds.get(round_id)
            if not trading_round:
                self._log_exit_error(round_id, "라운드를 찾을 수 없음")
                return None
                
            if trading_round.status != RoundStatus.EXIT_READY:
                self._log_exit_error(
                    round_id,
                    "부적절한 라운드 상태",
                    {
                        "current_status": trading_round.status,
                        "required_status": RoundStatus.EXIT_READY
                    }
                )
                return None
            
            # 2. 진입 주문 정보 확인
            if not trading_round.entry_order:
                self._log_exit_error(
                    round_id,
                    "진입 주문 정보 없음",
                    {"symbol": trading_round.symbol}
                )
                return None
            
            # 3. 잔고 조회
            balance = self.account.get_balance(trading_round.symbol)
            if not balance or float(balance['balance']) <= 0:
                self._log_exit_error(
                    round_id,
                    "매도 가능 잔고 없음",
                    {
                        "symbol": trading_round.symbol,
                        "balance": balance
                    }
                )
                return None
            
            # 4. 매도 주문 생성
            order_request = OrderRequest(
                market=f"KRW-{trading_round.symbol}",
                side="ask",
                order_type="market",
                price=None,
                volume=float(balance['balance'])
            )
            
            # 5. 로깅
            self.log_manager.log(
                category=LogCategory.ROUND_EXIT,
                message="매도 주문 생성 완료",
                data={
                    "round_id": round_id,
                    "symbol": trading_round.symbol,
                    "volume": order_request.volume,
                    "order_type": order_request.order_type
                }
            )
            
            return order_request
            
        except Exception as e:
            self._log_exit_error(
                round_id,
                f"매도 주문 생성 실패: {str(e)}",
                {"error": str(e)}
            )
            return None

    def execute_exit_order(self, round_id: str, order_request: OrderRequest) -> Optional[OrderResponse]:
        """매도 주문을 실행하고 결과를 반환합니다.
        
        Args:
            round_id (str): 라운드 ID
            order_request (OrderRequest): 주문 요청 객체
            
        Returns:
            Optional[OrderResponse]: 주문 응답 객체 또는 None
            
        Note:
            - 주문 실행 전 라운드 상태 검증
            - 실제 거래소 API를 통한 주문 실행
            - 주문 실행 결과에 대한 상세 로깅
        """
        try:
            # 1. 라운드 상태 검증
            trading_round = self.active_rounds.get(round_id)
            if not trading_round:
                self._log_exit_error(
                    round_id,
                    "매도 주문 실행 실패: 라운드를 찾을 수 없음"
                )
                return None
                
            if trading_round.status != RoundStatus.EXIT_READY:
                self._log_exit_error(
                    round_id,
                    "매도 주문 실행 실패: 부적절한 라운드 상태",
                    {
                        "current_status": trading_round.status,
                        "required_status": RoundStatus.EXIT_READY
                    }
                )
                return None
            
            # 2. 주문 요청 검증
            if not order_request.market or not order_request.volume:
                self._log_exit_error(
                    round_id,
                    "매도 주문 실행 실패: 잘못된 주문 정보",
                    {
                        "market": order_request.market,
                        "volume": order_request.volume
                    }
                )
                return None
            
            # 3. 주문 실행 전 로깅
            self.log_manager.log(
                category=LogCategory.ROUND_EXIT,
                message="매도 주문 실행 시작",
                data={
                    "round_id": round_id,
                    "symbol": trading_round.symbol,
                    "order_request": {
                        "market": order_request.market,
                        "side": order_request.side,
                        "volume": order_request.volume,
                        "order_type": order_request.order_type
                    }
                }
            )
            
            # 4. 주문 실행
            order_response = self.order.create_order_v2(order_request)
            if not order_response:
                self._log_exit_error(
                    round_id,
                    "매도 주문 실행 실패: API 응답 없음",
                    {"order_request": order_request.to_dict()}
                )
                return None
            
            # 5. 주문 실행 결과 로깅
            self.log_manager.log(
                category=LogCategory.ROUND_EXIT,
                message="매도 주문 실행 완료",
                data={
                    "round_id": round_id,
                    "order_id": order_response.uuid,
                    "initial_state": order_response.state,
                    "price": order_response.price,
                    "volume": order_response.volume
                }
            )
            
            return order_response
            
        except Exception as e:
            self._log_exit_error(
                round_id,
                f"매도 주문 실행 중 예외 발생: {str(e)}",
                {
                    "error": str(e),
                    "order_request": order_request.to_dict() if order_request else None
                }
            )
            return None

    def start_monitoring(self, round_id: str) -> bool:
        """포지션 모니터링을 시작합니다.
        
        Args:
            round_id (str): 모니터링할 라운드 ID
            
        Returns:
            bool: 모니터링 시작 성공 여부
        """
        MAX_RETRIES = 3
        MONITORING_INTERVAL = 0.5  # seconds
        ERROR_RETRY_INTERVAL = 0.5  # seconds
        
        def _validate_round() -> Optional[TradingRound]:
            """라운드 상태를 검증합니다."""
            trading_round = self.get_round(round_id)
            if not trading_round:
                self.log_manager.log(
                    category=LogCategory.ROUND_ERROR,
                    message="모니터링 시작 실패: 라운드를 찾을 수 없음",
                    data={"round_id": round_id}
                )
                return None
                
            if trading_round.status != RoundStatus.HOLDING:
                self.log_manager.log(
                    category=LogCategory.ROUND_ERROR,
                    message="모니터링 시작 실패: 라운드가 HOLDING 상태가 아님",
                    data={
                        "round_id": round_id,
                        "current_status": trading_round.status,
                        "expected_status": RoundStatus.HOLDING
                    }
                )
                return None
                
            return trading_round
            
        def _start_monitoring_log(trading_round: TradingRound) -> None:
            """모니터링 시작을 로깅합니다."""
            self.log_manager.log(
                category=LogCategory.ROUND,
                message="포지션 모니터링 시작",
                data={
                    "round_id": round_id,
                    "symbol": trading_round.symbol,
                    "entry_price": trading_round.entry_order.price,
                    "target_price": trading_round.take_profit,
                    "stop_loss_price": trading_round.stop_loss,
                    "current_status": trading_round.status,
                    "monitoring_interval": MONITORING_INTERVAL
                }
            )
        
        try:
            # 1. 라운드 검증
            trading_round = _validate_round()
            if not trading_round:
                return False
                
            # 2. 모니터링 시작 로깅
            _start_monitoring_log(trading_round)
            
            # 3. 모니터링 루프
            retry_count = 0
            
            while True:
                try:
                    # # 시장 정보 수집
                    # market_data = self.analyzer.get_market_overview(trading_round.symbol)
                    # balance = self.account.get_balance(trading_round.symbol)
                    
                    # # 매도 결정 획득
                    # decision = self.get_exit_decision(
                    #     round_id,
                    #     market_data=market_data,
                    #     balance=balance,
                    #     trading_round=trading_round,
                    #     model_type="gemini"
                    # )
                    
                    current_price = self.ticker.get_current_price(trading_round.symbol)
                    if not current_price:
                        raise Exception("현재가 조회 실패")
                    
                    if current_price.trade_price >= trading_round.take_profit:
                        if self.update_round_status(round_id, RoundStatus.EXIT_READY):
                            return self.execute_exit_process(round_id, f'[목표가{trading_round.take_profit} 도달]')
                    
                    if current_price.trade_price <= trading_round.stop_loss:
                        if self.update_round_status(round_id, RoundStatus.EXIT_READY):
                            return self.execute_exit_process(round_id, f'[손절가{trading_round.stop_loss} 도달]')
                    
                    # # 매도 결정 처리
                    # if decision and decision.should_exit:
                    #     if self.update_round_status(round_id, RoundStatus.EXIT_READY):
                    #         return self.execute_exit_process(round_id, decision.reasons)
                    
                    # 재시도 카운터 초기화 (성공적인 모니터링)
                    # retry_count = 0
                    
                    time.sleep(MONITORING_INTERVAL)
                    
                except Exception as e:
                    retry_count += 1
                    self.log_manager.log(
                        category=LogCategory.ROUND_WARNING,
                        message=f"모니터링 중 오류 발생 (재시도 {retry_count}/{MAX_RETRIES})",
                        data={
                            "round_id": round_id,
                            "error": str(e),
                            "retry_count": retry_count
                        }
                    )
                    
                    if retry_count >= MAX_RETRIES:
                        raise Exception(f"최대 재시도 횟수 초과: {str(e)}")
                        
                    time.sleep(ERROR_RETRY_INTERVAL)
            
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ROUND_ERROR,
                message="모니터링 실패",
                data={
                    "round_id": round_id,
                    "error": str(e),
                    "stacktrace": traceback.format_exc()
                }
            )
            return False

    def execute_exit_process(self, round_id: str, reasons: List[str]) -> bool:
        """매도 청산 프로세스를 실행합니다.
        
        Args:
            round_id (str): 라운드 ID
            reasons (List[str]): 청산 이유 목록
            
        Returns:
            bool: 성공 여부
            
        Note:
            전체 매도 청산 프로세스를 관리합니다:
            1. 라운드 상태 검증
            2. 주문 생성 및 실행
            3. 주문 체결 대기 및 확인
            4. 라운드 종료 처리
        """
        try:
            # 1. 라운드 상태 검증
            trading_round = self.active_rounds.get(round_id)
            if not trading_round:
                self._log_exit_error(round_id, "라운드를 찾을 수 없음")
                return False
                
            if trading_round.status != RoundStatus.EXIT_READY:
                self._log_exit_error(
                    round_id,
                    "부적절한 라운드 상태",
                    {
                        "current_status": trading_round.status,
                        "required_status": RoundStatus.EXIT_READY
                    }
                )
                return False
            
            # 2. 주문 생성 및 실행
            try:
                # 2-1. 프로세스 시작 로깅
                self.log_manager.log(
                    category=LogCategory.ROUND_EXIT,
                    message="매도 청산 프로세스 시작",
                    data={
                        "round_id": round_id,
                        "symbol": trading_round.symbol,
                        "reasons": reasons
                    }
                )
                
                # 2-2. 주문 생성
                order_request = self.create_exit_order(round_id)
                if not order_request:
                    self._log_exit_error(round_id, "주문 생성 실패")
                    return False
                
                # 2-3. 주문 실행
                order_response = self.execute_exit_order(round_id, order_request)
                if not order_response:
                    self._log_exit_error(
                        round_id,
                        "주문 실행 실패",
                        {"order_request": order_request.to_dict()}
                    )
                    return False
                
                # 2-4. 주문 상태 기록
                if not self.confirm_exit_order(round_id, order_response):
                    self._log_exit_error(
                        round_id,
                        "주문 상태 기록 실패",
                        {"order_response": order_response.to_dict()}
                    )
                    return False
                
            except Exception as e:
                self._log_exit_error(
                    round_id,
                    f"주문 생성/실행 중 오류: {str(e)}",
                    {"error": str(e)}
                )
                return self._revert_to_holding(round_id, "주문 생성/실행 실패")
            
            # 3. 주문 체결 대기 및 확인
            try:
                completed_order = self.wait_order_completion(order_response)
                if not completed_order:
                    self._log_exit_error(
                        round_id,
                        "주문 체결 실패",
                        {"order_id": order_response.uuid}
                    )
                    return self._revert_to_holding(round_id, "주문 체결 실패")
                
                # 주문 정보 라운드에 추가
                if not self.add_order_to_round(round_id, completed_order, 'exit'):
                    self._log_exit_error(
                        round_id,
                        "주문 정보 추가 실패",
                        {"completed_order": completed_order.to_dict()}
                    )
                    return self._revert_to_holding(round_id, "주문 정보 추가 실패")
                
            except Exception as e:
                self._log_exit_error(
                    round_id,
                    f"주문 체결 확인 중 오류: {str(e)}",
                    {"error": str(e)}
                )
                return self._revert_to_holding(round_id, "주문 체결 확인 실패")
            
            # 4. 라운드 종료 처리
            try:
                # 최종 성과 지표 업데이트
                self.update_round_metrics(round_id, trading_round.exit_order.price)
                
                # 라운드 완료 상태로 전환
                if not self.update_round_status(
                    round_id=round_id,
                    new_status=RoundStatus.COMPLETED,
                    reason=reasons
                ):
                    self._log_exit_error(
                        round_id,
                        "상태 전환 실패",
                        {"completed_order": completed_order.to_dict()}
                    )
                    return False
                
                # 성공 로깅
                self.log_manager.log(
                    category=LogCategory.ROUND_EXIT,
                    message="매도 청산 프로세스 완료",
                    data={
                        "round_id": round_id,
                        "symbol": trading_round.symbol,
                        "exit_price": completed_order.price,
                        "exit_volume": completed_order.volume,
                        "profit_loss": trading_round.metrics.profit_loss if trading_round.metrics else None,
                        "profit_loss_rate": trading_round.metrics.profit_loss_rate if trading_round.metrics else None,
                        "trades_count": len(completed_order.trades) if completed_order.trades else 0,
                        "reasons": reasons
                    }
                )
                
                return True
                
            except Exception as e:
                self._log_exit_error(
                    round_id,
                    f"라운드 종료 처리 중 오류: {str(e)}",
                    {"error": str(e)}
                )
                return False
            
        except Exception as e:
            self._log_exit_error(
                round_id,
                f"매도 청산 프로세스 중 예외 발생: {str(e)}",
                {"error": str(e)}
            )
            return self._revert_to_holding(round_id, "예외 발생")
    
    def _log_exit_error(self, round_id: str, message: str, additional_data: dict = None) -> None:
        """매도 청산 관련 에러를 로깅합니다."""
        data = {"round_id": round_id}
        if additional_data:
            data.update(additional_data)
            
        self.log_manager.log(
            category=LogCategory.ROUND_ERROR,
            message=f"매도 청산 실패: {message}",
            data=data
        )
    
    def _get_exit_completion_message(self, completed_order, reasons: List[str]) -> str:
        """매도 완료 메시지를 생성합니다."""
        trades_info = ""
        if completed_order.trades:
            trades_count = len(completed_order.trades)
            trades_info = f" ({trades_count}건 체결)"
            
        reasons_text = "\n- " + "\n- ".join(reasons)
        
        return (
            f"매도 주문 체결 완료{trades_info} "
            f"(체결가: {completed_order.price}, 수량: {completed_order.volume})\n"
            f"청산 이유:{reasons_text}"
        )

    def _generate_exit_prompt(
        self,
        round_id: str,
        market_data: MarketOverview,
        balance: Dict,
        trading_round: TradingRound
    ) -> Tuple[str, str]:
        """매도 시그널 감지를 위한 프롬프트를 생성합니다.
        
        Args:
            round_id (str): 라운드 ID
            market_data (MarketOverview): 시장 데이터
            balance (Dict): 보유 잔고 정보
            trading_round (TradingRound): 트레이딩 라운드 정보
            
        Returns:
            Tuple[str, str]: (시스템 프롬프트, 사용자 프롬프트) 튜플
        """
        # 시스템 프롬프트 정의
        system_prompt = """당신은 암호화폐 초단타(스캘핑) 트레이딩의 청산 전문가입니다.
1~5분 단위로 시장을 파악하여, 현재 보유 중인 포지션을 유지할지 청산(매도)할지 빠르고 정확하게 결정합니다.

당신의 임무:
1. 제공된 시장 데이터를 종합적으로 분석
2. 현 시점에서 매도 청산 여부를 결정 (should_exit: true/false)
3. 판단의 근거(reasons)를 정확히 3가지 작성

리스크 관리 원칙:
- 목표가(take_profit) 근접 또는 초과 시, 수익 실현 기회 확보
- 손절가(stop_loss) 근접 또는 하회 시, 손실 최소화 우선
- 사소한 변동(±0.1% 이하)만으로 성급하게 청산하지 말 것
- 여러 지표 간 충돌 시, 확실한 하락 전환 신호가 없으면 관망(유지)

추가 규칙 (무분별한 청산 방지):
1. "should_exit"를 true로 결정하려면 **다음 조건 중 최소 2가지 이상**이 충족되어야 함:
   - (1) 현재가가 목표가(또는 손절가)에 사실상 도달(±0.1% 이내)해 수익 실현 혹은 손실 제한이 필요
   - (2) 주요 지표(RSI, 거래량, 호가 흐름 등)에서 **뚜렷한 하락 전환 신호**가 2개 이상 동시 발생
   - (3) 이미 충분한 수익률(예: 0.5%~1% 이상)을 달성했고, 추가 상승 여력이 매우 낮다고 판단
   - (4) 최근 가격 변동성이 높아지고 급락 위험이 확실해, 빠른 청산으로 손실 확대를 방지
2. 지표가 애매하거나 일부만 부정적으로 보이면, 성급히 true 결론 내리지 말 것
3. 응답 형식: 반드시 JSON 형태
{
  "should_exit": true/false,
  "reasons": [
      "첫 번째 근거",
      "두 번째 근거",
      "세 번째 근거"
  ]
}

목표: 지나친 조기 청산(소폭 이익/손실에 즉시 매도)을 피하고,
확실한 하락 전환 신호 또는 손절/목표가 근접에만 청산을 결정한다.
"""
        
        profit_loss_rate = ((market_data.current_price - trading_round.entry_order.price) / trading_round.entry_order.price) * 100
        # 사용자 프롬프트 생성
        user_prompt = f"""
현재 보유 중인 {trading_round.symbol} 포지션의 청산 여부를 분석해 주세요.

[포지션 정보]
- 진입가: {trading_round.entry_order.price:,.0f}원
- 현재가: {market_data.current_price:,.0f}원
- 목표가: {trading_round.take_profit:,.0f}원
- 손절가: {trading_round.stop_loss:,.0f}원
- 현재 수익률: {profit_loss_rate:.2f}%

[기본 시장 정보]
- 거래량 동향(1분): {market_data.volume_trend_1m}
- 가격 동향(1분): {market_data.price_trend_1m}
- 캔들 강도: {market_data.candle_strength} (실체비율: {market_data.candle_body_ratio:.1%})

[기술적 지표]
- RSI: 3분({market_data.rsi_3:.1f}), 7분({market_data.rsi_7:.1f})
- 이동평균: MA3({market_data.ma3:,.0f}), MA5({market_data.ma5:,.0f}), MA10({market_data.ma10:,.0f})
- 변동성: 3분({market_data.volatility_3m:.2f}%), 5분({market_data.volatility_5m:.2f}%)
- VWAP(3분): {market_data.vwap_3m:,.0f}원
- 볼린저밴드 폭: {market_data.bb_width:.2f}%

[호가 분석]
- 매수/매도 비율: {market_data.order_book_ratio:.2f}
- 스프레드: {market_data.spread:.3f}%

[특이사항]
- 5분 신고가 돌파: {'O' if market_data.new_high_5m else 'X'}
- 5분 신저가 돌파: {'O' if market_data.new_low_5m else 'X'}

위 데이터를 종합적으로 판단하여,
system_prompt에서 제시된 원칙(조건 중 2가지 이상 충족 시 청산)과
아래 JSON 형식을 따라 응답해 주세요:

{{
    "should_exit": true/false,
    "reasons": [
        "첫 번째 근거",
        "두 번째 근거",
        "세 번째 근거"
    ]
}}

- 사소한 변동(±0.1% 이하)만으로 청산 결정을 내리지 않도록 주의
- 목표가 또는 손절가에 사실상 근접(±0.1% 이내)했는지 여부도 고려
- 최소 세 가지 근거를 제시해 주세요.
"""
        
        self.log_manager.log(
            category=LogCategory.ROUND,
            message="매도 시그널 프롬프트 생성",
            data={
                "round_id": round_id,
                "symbol": trading_round.symbol,
                "current_profit_rate": f"{profit_loss_rate:.2f}%",
                "system_prompt_length": len(system_prompt),
                "user_prompt_length": len(user_prompt)
            }
        )
        
        return system_prompt, user_prompt

    def get_exit_decision(
        self,
        round_id: str,
        market_data: MarketOverview,
        balance: Dict,
        trading_round: TradingRound,
        model_type: Literal["gpt", "gemini"]
    ) -> Optional[GPTExitDecision]:
        """시장 데이터를 분석하여 매도 청산 결정을 얻습니다.
        
        Args:
            round_id (str): 라운드 ID
            market_data (MarketOverview): 시장 데이터
            
        Returns:
            Optional[Dict]: {
                'should_exit': bool,
                'reasons': List[str]
            }
        """
        try:       
            # 3. 프롬프트 생성
            system_prompt, user_prompt = self._generate_exit_prompt(
                round_id=round_id,
                market_data=market_data,
                balance=balance,
                trading_round=trading_round
            )
            
            if not system_prompt or not user_prompt:
                self.log_manager.log(
                    category=LogCategory.ROUND_ERROR,
                    message="청산 결정 실패: 프롬프트 생성 실패",
                    data={"round_id": round_id}
                )
                return None
                
            if model_type == "gpt":
                # GPT 호출  
                response = self._call_gpt(system_prompt, user_prompt)
                if not response:
                    self.log_manager.log(
                        category=LogCategory.ROUND_ERROR,
                        message="청산 결정 실패: GPT 응답 없음",
                        data={"round_id": round_id}
                    )
                    return None
            
                decision = self._parse_gpt_exit_response(round_id, response, market_data.current_price)
            elif model_type == "gemini":
                # Gemini 호출
                parsed = self._call_gemini(f"""
                                           {system_prompt}
                                           {user_prompt}
                                           """, ModelExitResponse)
                profit_loss_rate = ((market_data.current_price - trading_round.entry_order.price) / trading_round.entry_order.price) * 100
                decision = GPTExitDecision(
                    should_exit=parsed.should_exit,
                    reasons=parsed.reasons,
                    current_price=market_data.current_price,
                    profit_loss_rate=profit_loss_rate,
                    timestamp=datetime.now()    
                )
            # 응답 파싱
            return decision
            
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ROUND_ERROR,
                message="청산 결정 중 오류 발생",
                data={
                    "round_id": round_id,
                    "error": str(e)
                }
            )
            return None
            
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ROUND_ERROR,
                message="청산 결정 중 오류 발생",
                data={
                    "round_id": round_id,
                    "error": str(e)
                }
            )
            return None 

    def _revert_to_holding(self, round_id: str, reason: str) -> bool:
        """holding 상태로 복귀하고 False를 반환합니다."""
        self.revert_to_holding(round_id, f"{reason}로 보유 상태로 복귀")
        return False

    def revert_to_holding(self, round_id: str, reason: str) -> bool:
        """청산 시도를 취소하고 보유 상태로 되돌립니다."""
        trading_round = self.active_rounds.get(round_id)
        if not trading_round:
            return False
            
        if trading_round.status in [RoundStatus.EXIT_READY, RoundStatus.EXIT_ORDERED]:
            return self.update_round_status(round_id, RoundStatus.HOLDING, reason)
        return False