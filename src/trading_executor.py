from typing import Dict, Optional
from datetime import datetime
from src.trading_decision_maker import TradingDecisionMaker
from src.trading_order import TradingOrder
from src.utils.log_manager import LogManager, LogCategory
from src.models.market_data import (
    TradingDecisionResult, AssetInfo, OrderInfo,
    OrderSideType, OrderType, OrderResult, TradeExecutionResult
)

class TradingExecutor:
    """매매 판단 결과를 실제 주문으로 실행하는 클래스"""
    
    def __init__(
        self,
        bithumb_api_key: str,
        bithumb_secret_key: str,
        openai_api_key: str,
        log_manager: LogManager
    ):
        """초기화
        
        Args:
            bithumb_api_key: 빗썸 API 키
            bithumb_secret_key: 빗썸 Secret 키
            openai_api_key: OpenAI API 키
            log_manager: 로그 매니저
        """
        self.decision_maker = TradingDecisionMaker(
            bithumb_api_key=bithumb_api_key,
            bithumb_secret_key=bithumb_secret_key,
            openai_api_key=openai_api_key,
            log_manager=log_manager
        )
        self.order = TradingOrder(
            api_key=bithumb_api_key,
            secret_key=bithumb_secret_key,
            log_manager=log_manager
        )
        self.log_manager = log_manager
        
    def _get_order_info(
        self,
        symbol: str,
        decision_result: TradingDecisionResult
    ) -> OrderInfo:
        """매매 판단 결과를 기반으로 주문 정보를 생성합니다.

        Args:
            symbol: 거래 심볼 (예: XRP)
            decision_result: 매매 판단 결과

        Returns:
            OrderInfo: 주문 정보 데이터클래스
        """
        try:
            decision = decision_result.decision
            asset_info = decision_result.analysis.asset_info
            
            # 관망인 경우 즉시 반환
            if decision.action == "관망":
                return OrderInfo(
                    side="none",
                    order_type="none",
                    price=0,
                    volume=0,
                    krw_amount=0
                )
            
            # 기본 설정
            MIN_ORDER_AMOUNT = 5000  # 최소 주문 금액 (KRW)
            MAX_ORDER_RATIO = 0.5    # 최대 주문 비율 (자산의 50%)
            
            # 리스크 레벨에 따른 주문 비율 조정
            risk_ratios = {
                "상": 0.25,    # 위험도 높음 -> 25%
                "중": 0.5,   # 위험도 중간 -> 50%
                "하": 1     # 위험도 낮음 -> 100%
            }
            
            # 확신도에 따른 주문 비율 추가 조정
            confidence_multiplier = decision.confidence  # 0.0 ~ 1.0
            
            # 최종 주문 비율 계산
            base_ratio = risk_ratios[decision.risk_level]
            final_ratio = base_ratio * confidence_multiplier
            
            if decision.action == "매수":
                # 매수 가능 금액 계산
                available_krw = asset_info.krw_balance                
                # 실제 주문 가능한 금액으로 조정
                order_amount = available_krw * 0.995
                
                if order_amount < MIN_ORDER_AMOUNT:
                    return OrderInfo(
                        side="none",
                        order_type="none",
                        price=0,
                        volume=0,
                        krw_amount=0
                    )
                
                order_info = OrderInfo(
                    side="bid",
                    order_type="price",
                    price=order_amount,
                    volume=None,
                    krw_amount=order_amount
                )
                
            elif decision.action == "매도":
                # 매도 가능 수량 계산 (거래 중인 수량 제외)
                available_volume = asset_info.balance - asset_info.locked
                current_price = decision.entry_price  # 진입가격을 현재가로 사용

                if available_volume <= 0:
                    return OrderInfo(
                        side="none",
                        order_type="none",
                        price=0,
                        volume=0,
                        krw_amount=0
                    )
                
                # 전량 매도
                volume = available_volume
                
                # 예상 주문 금액 계산
                krw_amount = volume * current_price

                # 최소 주문 금액 확인
                if krw_amount < MIN_ORDER_AMOUNT:
                    return OrderInfo(
                        side="none",
                        order_type="none",
                        price=0,
                        volume=0,
                        krw_amount=0
                    )
                
                order_info = OrderInfo(
                    side="ask",
                    order_type="market",
                    price=None,
                    volume=round(volume, 8),
                    krw_amount=krw_amount
                )
            
            # 주문 정보 생성 결과 로깅
            if self.log_manager:
                if order_info.side == "none":
                    self.log_manager.log(
                        category=LogCategory.TRADING,
                        message=f"{symbol} 주문 불가",
                        data={
                            "symbol": symbol,
                            "action": decision.action,
                            "reason": "최소 주문 금액 미달" if decision.action == "매수" else "매도 가능 수량 없음"
                        }
                    )
                else:
                    self.log_manager.log(
                        category=LogCategory.TRADING,
                        message=f"{symbol} {decision.action} 주문 정보 생성 완료",
                        data={
                            "symbol": symbol,
                            "order_info": order_info.__dict__,
                            "risk_level": decision.risk_level,
                            "confidence": decision.confidence,
                            "final_ratio": final_ratio if decision.action == "매수" else None
                        }
                    )
            
            return order_info
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message=f"{symbol} 주문 정보 생성 실패",
                    data={"symbol": symbol, "error": str(e)}
                )
            raise

    def execute_trade(
        self,
        symbol: str
    ) -> TradeExecutionResult:
        """매매 실행
        
        Args:
            symbol: 심볼 (예: 'BTC')
            
        Returns:
            TradeExecutionResult: 매매 실행 결과
        """
        try:
            # 1. 매매 판단 수행
            decision_result = self.decision_maker.make_decision(symbol)
                
            # 2. 주문 정보 생성
            order_info = self._get_order_info(symbol, decision_result)
        
            # 3. 주문 실행
            order_result: Optional[OrderResult] = None
            if order_info.side != 'none' and order_info.order_type != 'none':
                order_result = self.order.create_order(
                    symbol=symbol,
                    order_info=order_info
                )

            # 4. 실행 결과 생성
            result = TradeExecutionResult(
                success=True,
                decision_result=decision_result,
                order_info=order_info,
                order_result=order_result
            )

            # 5. 성공 로깅
            self.log_manager.log(
                category=LogCategory.TRADING,
                message=f"{symbol} 매매 실행 완료",
                data=result.to_dict()
            )
            
            return result
            
        except Exception as e:
            error_msg = f"{symbol} 매매 실행 실패: {str(e)}"
            self.log_manager.log(
                category=LogCategory.ERROR,
                message=error_msg
            )
            raise