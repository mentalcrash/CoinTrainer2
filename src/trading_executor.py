import logging
from typing import Dict, Optional
from datetime import datetime
from src.trading_decision_maker import TradingDecisionMaker
from src.trading_order import TradingOrder
from src.utils.logger import setup_logger

logger = setup_logger('trading_executor')

class TradingExecutor:
    """매매 판단 결과를 실제 주문으로 실행하는 클래스"""
    
    def __init__(
        self,
        bithumb_api_key: str,
        bithumb_secret_key: str,
        openai_api_key: str
    ):
        """초기화
        
        Args:
            bithumb_api_key: 빗썸 API 키
            bithumb_secret_key: 빗썸 Secret 키
            openai_api_key: OpenAI API 키
        """
        self.decision_maker = TradingDecisionMaker(
            bithumb_api_key=bithumb_api_key,
            bithumb_secret_key=bithumb_secret_key,
            openai_api_key=openai_api_key
        )
        self.order = TradingOrder(
            api_key=bithumb_api_key,
            secret_key=bithumb_secret_key
        )
        
    def _calculate_order_amount(
        self,
        symbol: str,
        decision: Dict,
        asset_info: Dict
    ) -> tuple:
        """주문 수량과 가격을 계산
        
        Args:
            symbol: 심볼 (예: 'BTC')
            decision: 매매 판단 결과
            asset_info: 자산 정보
            
        Returns:
            tuple: (주문 수량, 주문 가격)
        """
        # 매수/매도 수량 계산 (보유자산 대비 %)
        quantity_percent = float(decision['quantity_percent']) / 100
        
        if decision['decision'] == '매수':
            # 매수 가능한 KRW 잔고 확인
            available_krw = float(asset_info.get('krw_balance', 0))
            order_amount = available_krw * quantity_percent
            # 목표가로 매수 수량 계산
            volume = None
            price = order_amount
        else:  # 매도
            # 매도 가능한 코인 수량 확인
            available_coin = float(asset_info.get('balance', 0))
            volume = available_coin * quantity_percent
            price = None
            
        return volume, price
        
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
            # 1. 매매 판단 수행
            decision_result = self.decision_maker.make_decision(
                symbol=symbol,
                max_age_hours=max_age_hours,
                limit=limit,
                dev_mode=dev_mode
            )
            
            if not decision_result['success']:
                raise Exception(f"매매 판단 실패: {decision_result.get('error')}")
                
            decision = decision_result['decision']
            asset_info = decision_result['asset_info']

            # 2. 매매 판단이 '관망'인 경우 종료
            if decision['decision'] == '관망':
                logger.info(f"{symbol} 관망 판단으로 매매 실행하지 않음")
                return {
                    'success': True,
                    'decision': decision,
                    'asset_info': asset_info,
                    'order_result': None
                }
                
            # 3. 주문 수량과 가격 계산
            volume, price = self._calculate_order_amount(symbol, decision, asset_info)
            
            # 4. 주문 실행
            side = 'bid' if decision['decision'] == '매수' else 'ask'
            order_type = 'price' if side == 'bid' else 'market'
            
            order_result = self.order.create_order(
                symbol=symbol,
                side=side,
                order_type=order_type,
                price=price,
                volume=volume
            )
            
            if not order_result:
                raise Exception("주문 생성 실패")
                
            # 5. 결과 반환
            return {
                'success': True,
                'decision': decision,
                'order_result': order_result,
                'decision_result': decision_result,
                'next_decision_time': decision['next_decision']['interval_minutes'],
                'asset_info': asset_info
            }
            
        except Exception as e:
            error_msg = f"매매 실행 실패: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg
            } 