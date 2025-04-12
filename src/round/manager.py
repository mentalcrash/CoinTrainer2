import os
import uuid
import json
import requests
from datetime import datetime
from typing import Optional, List, Dict, Tuple
from src.utils.log_manager import LogManager, LogCategory
from src.models.market_data import TradeExecutionResult
from src.models.order import OrderRequest, OrderResponse
from .models import TradingRound, RoundOrder, RoundMetrics, RoundStatus, GPTEntryDecision
from src.trading_analyzer import TradingAnalyzer
import time
from src.account import Account
from src.trading_order import TradingOrder

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
        reason: Optional[str] = None
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
            
            # 주문 객체 생성
            order = RoundOrder(
                order_id=order_response.uuid,
                timestamp=datetime.now(),
                price=float(order_response.price) if order_response.price else 0.0,
                volume=float(order_response.volume) if order_response.volume else 0.0,
                type=order_type,
                status='completed' if order_response.state == 'complete' else 'pending',
                order_response=order_response
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
                    "price": order.price,
                    "volume": order.volume,
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
                    "metrics": trading_round.metrics._asdict() if trading_round.metrics else None
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
                
            return {
                "id": trading_round.id,
                "symbol": trading_round.symbol,
                "status": trading_round.status,
                "duration": trading_round.duration,
                "entry_price": trading_round.entry_order.price if trading_round.entry_order else None,
                "current_metrics": trading_round.metrics._asdict() if trading_round.metrics else None,
                "take_profit": trading_round.take_profit,
                "stop_loss": trading_round.stop_loss,
                "exit_reason": trading_round.exit_reason,
                "decision_count": len(trading_round.decision_history)
            }
            
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
        """
        try:
            # 1. 주문 생성
            order_request = self.create_entry_order(round_id)
            if not order_request:
                self.log_manager.log(
                    category=LogCategory.ROUND_ERROR,
                    message="매수 주문 생성 실패",
                    data={"round_id": round_id}
                )
                return False
            
            # 2. 주문 실행
            order_response = self.execute_entry_order(round_id, order_request)
            
            # 3. 주문 결과 확인
            if self.confirm_entry_order(round_id, order_response):
                wait_res = self.wait_order_completion(order_response)
                if wait_res:
                    # 4. 보유 상태로 전환
                    return self.update_round_status(round_id, RoundStatus.HOLDING, "매수 주문 체결")
                else:
                    return False
            else:
                return False

        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ROUND_ERROR,
                message=f"매수 진입 프로세스 실패: {str(e)}",
                data={"round_id": round_id}
            )
            return False

    def start_watching(
        self,
        round_id: str,
        interval: float = 30.0,
        max_watching_time: float = 120.0
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
                    entry_decision = self.get_entry_decision(round_id, market_data)
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
                        reasons = "\n".join([f"- {reason}" for reason in entry_decision.reasons])
                        if self.prepare_entry(round_id, f"매수 시그널 발생:\n{reasons}"):
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

    def prepare_entry(self, round_id: str, reason: str) -> bool:
        """매수 시그널이 발생하여 진입 준비 상태로 변경합니다."""
        return self.update_round_status(round_id, RoundStatus.ENTRY_READY, reason)

    def confirm_entry_order(self, round_id: str, order_response: OrderResponse) -> bool:
        """매수 주문 결과를 라운드에 기록합니다."""
        try:
            if not order_response or order_response.state != 'complete':
                return False
            
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

    def prepare_exit(self, round_id: str, reason: str) -> bool:
        """매도 시그널이 발생하여 청산 준비 상태로 변경합니다."""
        return self.update_round_status(round_id, RoundStatus.EXIT_READY, reason)

    def confirm_exit_order(self, round_id: str, order_result: OrderResult) -> bool:
        """매도 주문이 발생했음을 기록합니다."""
        if self.add_order_to_round(round_id, order_result, 'exit'):
            return self.update_round_status(
                round_id, 
                RoundStatus.EXIT_ORDERED,
                f"매도 주문 발생: {order_result.uuid}"
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

    def revert_to_holding(self, round_id: str, reason: str) -> bool:
        """청산 시도를 취소하고 보유 상태로 되돌립니다."""
        trading_round = self.active_rounds.get(round_id)
        if not trading_round:
            return False
            
        if trading_round.status in [RoundStatus.EXIT_READY, RoundStatus.EXIT_ORDERED]:
            return self.update_round_status(round_id, RoundStatus.HOLDING, reason)
        return False

    def _generate_market_prompt(self, round_id: str, market_data) -> Tuple[str, str]:
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
        system_prompt = """당신은 암호화폐 스캘핑 트레이딩 전문가입니다. 
1~5분 단위 초단기 전략을 사용하며, 기술 지표와 시장 데이터를 종합적으로 분석하여 
신속하고 명확한 매매 판단을 합니다. 

당신의 주요 임무:
1. 제공된 시장 데이터를 종합적으로 분석
2. 현재 시점의 매수 진입 적절성 판단
3. 적정 목표가와 손절가 제시 (반드시 실제 가격으로)
4. 판단의 근거를 명확하게 제시 (정확히 3가지)

리스크 관리 원칙:
- 수수료를 고려한 실현 가능한 수익 추구
- 손실 위험 최소화를 위한 적절한 손절가 설정
- 기술적 지표들의 신뢰도 검증
- 시장 변동성과 추세의 지속성 고려

응답은 반드시 지정된 JSON 형식을 따라야 하며, 
모든 가격은 정수로 제시하고 
목표가는 현재가보다 높게, 손절가는 현재가보다 낮게 설정해야 합니다."""
            
        # 사용자 프롬프트 생성
        user_prompt = f"""
현재 {trading_round.symbol} 매수 진입 기회를 분석해 주세요.

[기본 시장 정보]
- 현재가: {market_data.current_price:,.0f}원
- 거래량 동향: {market_data.volume_trend_1m}
- 가격 동향: {market_data.price_trend_1m}
- 캔들 강도: {market_data.candle_strength} (실체비율: {market_data.candle_body_ratio:.1%})

[기술적 지표]
- RSI: 1분({market_data.rsi_1:.1f}), 3분({market_data.rsi_3:.1f}), 7분({market_data.rsi_7:.1f}), 14분({market_data.rsi_14:.1f})
- 이동평균: MA1({market_data.ma1:,.0f}), MA3({market_data.ma3:,.0f}), MA5({market_data.ma5:,.0f}), MA10({market_data.ma10:,.0f})
- 변동성: 3분({market_data.volatility_3m:.2f}%), 5분({market_data.volatility_5m:.2f}%), 10분({market_data.volatility_10m:.2f}%)
- VWAP(3분): {market_data.vwap_3m:,.0f}원
- 볼린저밴드 폭: {market_data.bb_width:.2f}%

[호가 분석]
- 매수/매도 비율: {market_data.order_book_ratio:.2f}
- 스프레드: {market_data.spread:.3f}%

[선물 시장]
- 프리미엄률: {market_data.premium_rate:.2f}%
- 펀딩비율: {market_data.funding_rate:.3f}%
- 가격 안정성: {market_data.price_stability}

[특이사항]
- 5분 신규 고가 돌파: {'O' if market_data.new_high_5m else 'X'}
- 5분 신규 저가 돌파: {'O' if market_data.new_low_5m else 'X'}

위 데이터를 종합적으로 분석하여 다음 형식의 JSON으로 응답해 주세요:

{{
    "should_enter": true/false,
    "target_price": 0,      // 목표가 (원), 반드시 현재가보다 높게
    "stop_loss_price": 0,   // 손절가 (원), 반드시 현재가보다 낮게
    "reasons": [
        "첫 번째 근거",
        "두 번째 근거",
        "세 번째 근거"
    ]
}}"""
        
        self.log_manager.log(
            category=LogCategory.ROUND,
            message="매수 진입 프롬프트 생성",
            data={
                "round_id": round_id,
                "symbol": trading_round.symbol,
                "system_prompt_length": len(system_prompt),
                "user_prompt_length": len(user_prompt)
            }
        )
        
        return system_prompt, user_prompt

    def _parse_gpt_response(
        self,
        round_id: str,
        response: str,
        current_price: float
    ) -> Optional[GPTEntryDecision]:
        """GPT의 JSON 응답을 파싱하여 결정 객체를 생성합니다.
        
        Args:
            round_id (str): 라운드 ID
            response (str): GPT의 JSON 응답
            current_price (float): 현재 시장 가격
            
        Returns:
            Optional[GPTEntryDecision]: 파싱된 결정 객체 또는 None
        """
        try:
            # JSON 파싱
            data = json.loads(response)
            
            # 필수 필드 검증
            required_fields = ['should_enter', 'target_price', 'stop_loss_price', 'reasons']
            if not all(field in data for field in required_fields):
                raise ValueError("필수 필드 누락")
            
            # 데이터 타입 검증
            if not isinstance(data['should_enter'], bool):
                raise ValueError("should_enter must be boolean")
            if not isinstance(data['target_price'], (int, float)):
                raise ValueError("target_price must be number")
            if not isinstance(data['stop_loss_price'], (int, float)):
                raise ValueError("stop_loss_price must be number")
            if not isinstance(data['reasons'], list) or len(data['reasons']) != 3:
                raise ValueError("reasons must be array of 3 strings")
                
            # 가격 범위 검증
            if data['target_price'] <= current_price:
                raise ValueError("target_price must be higher than current price")
            if data['stop_loss_price'] >= current_price:
                raise ValueError("stop_loss_price must be lower than current price")
            
            # 수익률 계산
            target_profit_rate = ((data['target_price'] - current_price) / current_price) * 100
            stop_loss_rate = ((data['stop_loss_price'] - current_price) / current_price) * 100
            
            # 결정 객체 생성
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
                message="GPT 응답 파싱 완료",
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
                message=f"GPT 응답 파싱 실패: {str(e)}",
                data={
                    "round_id": round_id,
                    "response": response
                }
            )
            return None 

    def _call_gpt(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1  # 더 결정적인 응답을 위해 0.1로 낮춤
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
                "model": "gpt-4o-mini-2024-07-18",
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

    def get_entry_decision(self, round_id: str, market_data) -> Optional[GPTEntryDecision]:
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
                
            # GPT 호출
            response = self._call_gpt(system_prompt, user_prompt)
            if not response:
                return None
                
            # 응답 파싱
            return self._parse_gpt_response(round_id, json.dumps(response), market_data.current_price)
            
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
            balances = self.account.get_balance(trading_round.symbol)
            krw_balance = 0.0
            for balance in balances:
                if balance['currency'] == 'KRW':
                    krw_balance = float(balance['balance'])
                    break
            
            if krw_balance <= 0:
                self.log_manager.log(
                    category=LogCategory.ROUND_ERROR,
                    message="매수 주문 생성 실패: KRW 잔고 부족",
                    data={
                        "round_id": round_id,
                        "krw_balance": krw_balance
                    }
                )
                return None
            
            # 주문 금액 계산 (총 잔고의 10%)
            RATIO = 0.1
            order_amount = krw_balance * RATIO
            
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
                    "krw_balance": krw_balance
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
        """매수 주문을 실행하고 결과를 반환합니다."""
        try:
            trading_round = self.active_rounds.get(round_id)
            if not trading_round or trading_round.status != RoundStatus.ENTRY_READY:
                self.log_manager.log(
                    category=LogCategory.ROUND_ERROR,
                    message="매수 주문 실행 실패: 라운드 상태 부적합",
                    data={
                        "round_id": round_id,
                        "status": trading_round.status if trading_round else None
                    }
                )
                return None
            
            # 주문 실행
            order_response = self.order.create_order_v2(order_request)
            if not order_response:
                self.log_manager.log(
                    category=LogCategory.ROUND_ERROR,
                    message="매수 주문 실행 실패: API 응답 없음",
                    data={"round_id": round_id}
                )
                return None
            
            return order_response
            
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ROUND_ERROR,
                message=f"매수 주문 실행 중 오류 발생: {str(e)}",
                data={"round_id": round_id}
            )
            return None

    def wait_order_completion(self, order_response: OrderResponse) -> Optional[OrderResponse]:
        """주문 완료 대기"""
        # 주문 상태 확인 (최대 10회, 0.5초 간격)
        MAX_RETRIES = 10
        RETRY_INTERVAL = 0.5
        
        for _ in range(MAX_RETRIES):
            if order_response.state == 'complete':
                return order_response
            elif order_response.state == 'wait':
                time.sleep(RETRY_INTERVAL)
                order_response = self.order.get_order_v2(order_response.uuid)
                if not order_response:
                    break
            else:  # cancel, error 등
                self.log_manager.log(
                    category=LogCategory.ROUND_ERROR,
                    message=f"매수 주문 실패: {order_response.state}",
                    data={
                        "round_id": round_id,
                        "order_response": order_response.to_dict()
                    }
                )
                return None

    def create_exit_order(self, round_id: str) -> Optional[OrderRequest]:
        """매도 주문을 생성합니다.
        
        Args:
            round_id (str): 라운드 ID
            
        Returns:
            Optional[OrderRequest]: 생성된 주문 요청 객체
        """
        try:
            trading_round = self.active_rounds.get(round_id)
            if not trading_round or trading_round.status != RoundStatus.EXIT_READY:
                return None
            
            if not trading_round.entry_order:
                self.log_manager.log(
                    category=LogCategory.ROUND_ERROR,
                    message="진입 주문 정보 없음",
                    data={"round_id": round_id}
                )
                return None
            
            # 시장 데이터 조회
            market_data = self.analyzer.get_market_overview(trading_round.symbol)
            if not market_data:
                self.log_manager.log(
                    category=LogCategory.ROUND_ERROR,
                    message="시장 데이터 조회 실패",
                    data={"round_id": round_id}
                )
                return None
            
            # 주문 생성
            order_request = OrderRequest(
                symbol=trading_round.symbol,
                side="sell",
                price=market_data.current_price,  # 시장가 주문
                quantity=trading_round.entry_order.quantity,  # 진입 수량과 동일
                order_type="market",
                time_in_force="IOC",  # Immediate Or Cancel
                client_order_id=f"exit_{round_id}"
            )
            
            self.log_manager.log(
                category=LogCategory.ROUND_EXIT,
                message="매도 주문 생성",
                data={
                    "round_id": round_id,
                    "symbol": order_request.symbol,
                    "price": order_request.price,
                    "quantity": order_request.quantity
                }
            )
            
            return order_request
            
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ROUND_ERROR,
                message=f"매도 주문 생성 실패: {str(e)}",
                data={"round_id": round_id}
            )
            return None

    def execute_exit_order(self, round_id: str, order_request: OrderRequest) -> bool:
        """매도 주문을 실행합니다.
        
        Args:
            round_id (str): 라운드 ID
            order_request (OrderRequest): 주문 요청 객체
            
        Returns:
            bool: 실행 성공 여부
        """
        try:
            trading_round = self.active_rounds.get(round_id)
            if not trading_round or trading_round.status != RoundStatus.EXIT_READY:
                return False
            
            # TODO: 거래소 API를 통한 실제 주문 실행
            # order_result = exchange_api.create_order(order_request)
            
            # 임시 테스트용 주문 결과
            order_result = OrderResult(
                order_id=str(uuid.uuid4()),
                symbol=order_request.symbol,
                side=order_request.side,
                price=order_request.price,
                quantity=order_request.quantity,
                status="FILLED",
                transaction_time=datetime.now(),
                client_order_id=order_request.client_order_id
            )
            
            # 주문 결과 처리
            if order_result.status in ["FILLED", "PARTIALLY_FILLED"]:
                if self.confirm_exit_order(round_id, order_result):
                    # 최종 성과 지표 업데이트
                    self.update_round_metrics(round_id, order_result.price)
                    
                    self.log_manager.log(
                        category=LogCategory.ROUND_EXIT,
                        message="매도 주문 실행 성공",
                        data={
                            "round_id": round_id,
                            "order_id": order_result.order_id,
                            "price": order_result.price,
                            "quantity": order_result.quantity,
                            "profit_loss": trading_round.metrics.profit_loss if trading_round.metrics else None,
                            "profit_loss_rate": trading_round.metrics.profit_loss_rate if trading_round.metrics else None
                        }
                    )
                    return True
            
            return False
            
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ROUND_ERROR,
                message=f"매도 주문 실행 실패: {str(e)}",
                data={"round_id": round_id}
            )
            return False 