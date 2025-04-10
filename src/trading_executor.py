from typing import Dict, Optional
from datetime import datetime
from src.trading_decision_maker import TradingDecisionMaker
from src.trading_order import TradingOrder
from src.utils.log_manager import LogManager, LogCategory

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
        
    def _calculate_order_amount(
        self,
        symbol: str,
        decision: Dict,
        asset_info: Dict
    ) -> Dict:
        """스캘핑 트레이딩을 위한 주문 정보를 계산합니다.

        Args:
            symbol: 거래 심볼 (예: XRP)
            decision: 매매 판단 결과
            asset_info: 자산 정보

        Returns:
            Dict: {
                "side": "bid" | "ask",        # 매수/매도 구분
                "order_type": "limit" | "price" | "market",  # 주문 타입
                "price": float | None,        # 주문 가격 (지정가, 시장가 매수 시 필수)
                "volume": float | None,       # 주문 수량 (지정가, 시장가 매도 시 필수)
            }
        """
        try:
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
            confidence_multiplier = decision['confidence']  # 0.0 ~ 1.0
            
            # 최종 주문 비율 계산
            base_ratio = risk_ratios[decision['risk_level']]
            final_ratio = base_ratio * confidence_multiplier
            
            if decision['action'] == "매수":
                side = "bid"
                # 매수 가능 금액 계산
                available_krw = asset_info['krw_balance']
                max_order_amount = min(
                    available_krw * MAX_ORDER_RATIO,  # 최대 주문 비율 제한
                    available_krw * final_ratio       # 리스크/확신도 기반 주문 금액
                )
                
                # 최소 주문 금액 확인
                order_amount = max(max_order_amount, MIN_ORDER_AMOUNT)
                
                # 실제 주문 가능한 금액으로 조정
                order_amount = min(order_amount, available_krw)
                
                # 주문 가격과 수량 계산
                price = order_amount
                volume = None
                
                # 매수는 시장가 주문 사용 (price)
                order_type = "price"
                
                if self.log_manager:
                    self.log_manager.log(
                        category=LogCategory.TRADING,
                        message=f"{symbol} 매수 주문 계산",
                        data={
                            "available_krw": available_krw,
                            "risk_level": decision['risk_level'],
                            "confidence": decision['confidence'],
                            "final_ratio": final_ratio,
                            "order_amount": order_amount,
                            "price": price,
                            "volume": volume,
                            "order_type": order_type
                        }
                    )
                
            elif decision['action'] == "매도":
                side = "ask"
                # 매도 가능 수량 계산 (거래 중인 수량 제외)
                available_volume = asset_info['balance'] - asset_info.get('locked', 0)
                
                if available_volume <= 0:
                    if self.log_manager:
                        self.log_manager.log(
                            category=LogCategory.TRADING,
                            message=f"{symbol} 매도 가능 수량 없음",
                            data={
                                "balance": asset_info['balance'],
                                "locked": asset_info.get('locked', 0)
                            }
                        )
                    return {
                        "side": "none",
                        "order_type": "none",
                        "price": 0,
                        "volume": 0,
                        "krw_amount": 0
                    }
                
                # 전량 매도
                volume = available_volume
                
                # 매도는 지정가 주문 사용
                order_type = "limit"
                price = decision['entry_price']
                
                # 예상 주문 금액 계산
                krw_amount = volume * price
                
                # 최소 주문 금액 확인
                if krw_amount < MIN_ORDER_AMOUNT:
                    if self.log_manager:
                        self.log_manager.log(
                            category=LogCategory.TRADING,
                            message=f"{symbol} 매도 금액이 최소 주문 금액보다 작음",
                            data={
                                "krw_amount": krw_amount,
                                "min_order_amount": MIN_ORDER_AMOUNT
                            }
                        )
                    return {
                        "side": "none",
                        "order_type": "none",
                        "price": 0,
                        "volume": 0,
                        "krw_amount": 0
                    }
                
                if self.log_manager:
                    self.log_manager.log(
                        category=LogCategory.TRADING,
                        message=f"{symbol} 매도 주문 계산 (전량 매도)",
                        data={
                            "available_volume": available_volume,
                            "price": price,
                            "volume": volume,
                            "krw_amount": krw_amount,
                            "order_type": order_type
                        }
                    )
            
            else:  # 관망
                return {
                    "side": "none",
                    "order_type": "none",
                    "price": 0,
                    "volume": 0,
                    "krw_amount": 0
                }
            
            return {
                "side": side,
                "order_type": order_type,
                "price": price,
                "volume": round(volume, 8) if volume is not None else None  # 소수점 8자리까지 반올
            }
        except Exception as e:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message="주문 계산 실패",
                    data={"error": str(e)}
                )
            return {
                "side": "none",
                "order_type": "none",
                "price": 0,
                "volume": 0,
                "krw_amount": 0
            }
        
    def execute_trade(
        self,
        symbol: str,
        max_age_hours: int = 24,
        limit: int = 5,
        dev_mode: bool = False
    ) -> Dict:
        """매매 실행
        
        Args:
            symbol: 심볼 (예: 'BTC')
            max_age_hours: 뉴스 수집 시 최대 기사 나이 (시간)
            limit: 수집할 뉴스 기사 수
            dev_mode: 개발 모드 여부
            
        Returns:
            Dict: 매매 실행 결과
        """
        try:
            self.log_manager.log(
                category=LogCategory.TRADING,
                message=f"{symbol} 매매 실행 시작",
                data={
                    "max_age_hours": max_age_hours,
                    "limit": limit,
                    "dev_mode": dev_mode
                }
            )
            
            # 1. 매매 판단 수행
            decision_result = self.decision_maker.make_decision(
                symbol=symbol,
                max_age_hours=max_age_hours,
                limit=limit,
                dev_mode=dev_mode
            )
            
            if not decision_result['success']:
                error_msg = f"매매 판단 실패: {decision_result.get('error')}"
                raise Exception(error_msg)
                
            decision = decision_result['decision']
            asset_info = decision_result['asset_info']

            # 2. 매매 판단이 '관망'인 경우 종료
            if decision['action'] == '관망':
                self.log_manager.log(
                    category=LogCategory.TRADING,
                    message=f"{symbol} 관망 판단으로 매매 미실행",
                    data={
                        "decision": decision,
                        "asset_info": asset_info
                    }
                )
                return {
                    'success': True,
                    'decision': decision,
                    'asset_info': asset_info,
                    'order_result': None,
                    'market_data': decision_result['market_data'],
                    'next_decision_time': decision['next_decision']['interval_minutes'],
                }
                
            # 3. 주문 정보 계산
            order_info = self._calculate_order_amount(symbol, decision, asset_info)
            
            # 4. 관망이거나 주문 계산 실패 시 종료
            if order_info['side'] == 'none' or order_info['order_type'] == 'none':
                self.log_manager.log(
                    category=LogCategory.TRADING,
                    message=f"{symbol} 주문 계산 실패로 매매 미실행",
                    data=order_info
                )
                return {
                    'success': True,
                    'decision': decision,
                    'asset_info': asset_info,
                    'order_result': None,
                    'market_data': decision_result['market_data'],
                    'next_decision_time': decision['next_decision']['interval_minutes'],
                }
            
            # 5. 주문 실행
            self.log_manager.log(
                category=LogCategory.TRADING,
                message=f"{symbol} 주문 실행",
                data={
                    "symbol": symbol,
                    "side": order_info['side'],
                    "order_type": order_info['order_type'],
                    "price": order_info['price'],
                    "volume": order_info['volume']
                }
            )
            
            order_result = self.order.create_order(
                symbol=symbol,
                side=order_info['side'],
                order_type=order_info['order_type'],
                price=order_info['price'],
                volume=order_info['volume']
            )
            
            # 6. 주문 결과 반환
            return {
                'success': True,
                'decision': decision,
                'order_result': order_result,
                'market_data': decision_result['market_data'],
                'next_decision_time': decision['next_decision']['interval_minutes'],
                'asset_info': asset_info,
                'order_info': order_info  # 주문 정보도 함께 반환
            }
            
        except Exception as e:
            error_msg = f"매매 실행 실패: {str(e)}"
            self.log_manager.log(
                category=LogCategory.ERROR,
                message=error_msg,
                data={"error": str(e)}
            )
            return {
                'success': False,
                'error': error_msg
            } 