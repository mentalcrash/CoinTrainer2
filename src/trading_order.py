import os
import json
import uuid
import time
import jwt
import hashlib
import logging
import requests
from datetime import datetime
from urllib.parse import urlencode
from typing import Dict, Optional, Union, Literal, List
from src.utils.log_manager import LogManager, LogCategory
from src.models.market_data import OrderResult, OrderSideType, OrderType, OrderInfo
from src.models.order import OrderRequest, OrderResponse

class TradingOrder:
    """주문 처리를 담당하는 클래스"""
    
    def __init__(self, api_key: str = None, secret_key: str = None, log_manager: Optional[LogManager] = None):
        """
        Args:
            api_key (str, optional): Bithumb API 키
            secret_key (str, optional): Bithumb Secret 키
            log_manager (Optional[LogManager]): 로그 매니저 (선택사항)
        """
        self.api_key = api_key or os.getenv('BITHUMB_API_KEY')
        self.secret_key = secret_key or os.getenv('BITHUMB_SECRET_KEY')
        self.base_url = "https://api.bithumb.com"
        self.log_manager = log_manager
        
        # 로깅 설정
        self.logger = logging.getLogger(__name__)
        
    def _create_auth_token(self, params: Dict) -> str:
        """인증 토큰 생성
        
        Args:
            params (Dict): API 요청 파라미터
            
        Returns:
            str: 인증 토큰
        """
        query = urlencode(params).encode()
        hash = hashlib.sha512()
        hash.update(query)
        query_hash = hash.hexdigest()
        
        payload = {
            'access_key': self.api_key,
            'nonce': str(uuid.uuid4()),
            'timestamp': round(time.time() * 1000),
            'query_hash': query_hash,
            'query_hash_alg': 'SHA512'
        }
        
        jwt_token = jwt.encode(payload, self.secret_key)
        return f'Bearer {jwt_token}'
        
    def get_order_chance(self, symbol: str) -> Dict:
        """주문 가능 정보 조회
        
        Args:
            symbol (str): 심볼 (예: 'BTC')
            
        Returns:
            Dict: 주문 가능 정보를 담은 딕셔너리
        """
        endpoint = f"{self.base_url}/v1/orders/chance"
        param = {
            'market': f'KRW-{symbol}'
        }
        
        authorization_token = self._create_auth_token(param)
        headers = {
            'Authorization': authorization_token
        }
        
        try:
            # Call API
            response = requests.get(endpoint, params=param, headers=headers)
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message=f"주문 가능 정보 조회 실패",
                    data={"error": str(e), "symbol": symbol}
                )
            return {}
            
    def create_order(
        self,
        symbol: str,
        order_info: OrderInfo
    ) -> OrderResult:
        """주문을 생성합니다.
        
        Args:
            symbol: 거래 심볼 (예: 'BTC')
            order_info: 주문 정보 객체
            
        Returns:
            OrderResult: 주문 실행 결과
            
        Raises:
            Exception: API 호출 실패 시 발생
        """
        try:
            # API 요청 준비
            endpoint = f"{self.base_url}/v1/orders"
            params = {
                'market': f'KRW-{symbol}',
                'side': order_info.side,
                'ord_type': order_info.order_type
            }
            
            if order_info.price:
                params['price'] = order_info.price
            if order_info.volume:
                params['volume'] = order_info.volume
            
            # API 호출
            headers = {
                'Authorization': self._create_auth_token(params),
                'Content-Type': 'application/json'
            }
            
            response = requests.post(endpoint, data=json.dumps(params), headers=headers)
            response.raise_for_status()
            data = response.json()
            
            if not data or 'error' in data:
                raise Exception(f"API Error: {data.get('error', {}).get('message', 'Unknown error')}")
            
            # 주문 결과 생성
            order_result = OrderResult.from_dict(data)
            
            # 주문 결과 로깅
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.TRADING,
                    message=f"{symbol} {order_info.side} 주문 {'완료' if order_result.state == 'done' else '접수'}",
                    data={
                        "symbol": symbol,
                        "order_result": order_result.to_dict()
                    }
                )
            
            return order_result
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message=f"{symbol} {order_info.side} 주문 실패",
                    data={
                        "symbol": symbol,
                        "error": str(e)
                    }
                )
            raise
        
    def create_order_v2(
        self,
        order_request: OrderRequest
    ) -> OrderResponse:
        """주문을 생성합니다.
        
        Args:
            symbol: 거래 심볼 (예: 'BTC')
            order_info: 주문 정보 객체
            
        Returns:
            OrderResult: 주문 실행 결과
            
        Raises:
            Exception: API 호출 실패 시 발생
        """
        try:
            # API 요청 준비
            endpoint = f"{self.base_url}/v1/orders"
            params = {
                'market': order_request.market,
                'side': order_request.side,
                'ord_type': order_request.order_type
            }
            
            if order_request.price:
                params['price'] = order_request.price
            if order_request.volume:
                params['volume'] = order_request.volume
            
            # API 호출
            headers = {
                'Authorization': self._create_auth_token(params),
                'Content-Type': 'application/json'
            }
            
            response = requests.post(endpoint, data=json.dumps(params), headers=headers)
            response.raise_for_status()
            data = response.json()
            
            if not data or 'error' in data:
                raise Exception(f"API Error: {data.get('error', {}).get('message', 'Unknown error')}")
            
            # 주문 결과 생성
            order_res = OrderResponse.from_dict(data)
            
            # 주문 결과 로깅
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.TRADING,
                    message=f"{order_request.market} {order_request.side} 주문 {'완료' if order_res.state == 'done' else '접수'}",
                    data={
                        "symbol": order_request.market,
                        "order_result": order_res.to_dict()
                    }
                )
            
            return order_res
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message=f"{order_request.market} {order_request.side} 주문 실패",
                    data={
                        "symbol": order_request.market,
                        "error": str(e)
                    }
                )
            raise
     
    def get_order_v2(self, order_id: str) -> OrderResponse:
        """개별 주문 조회
        
        Args:
            symbol (str): 심볼 (예: 'BTC')
            order_id (str): 주문 ID
            
        Returns:
            Optional[OrderResponse]: 주문 정보를 담은 OrderResponse 객체 또는 None
        """
        endpoint = f"{self.base_url}/v1/order"
        params = {
            'uuid': order_id
        }
        
        headers = {
            'Authorization': self._create_auth_token(params)
        }
        
        if self.log_manager:
            self.log_manager.log(
                category=LogCategory.API,
                message="빗썸 API: 주문 조회 요청",
                data={
                    "order_id": order_id,
                    "endpoint": endpoint
                }
            )
        
        try:
            response = requests.get(endpoint, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
            order_res = OrderResponse.from_dict(data)
                
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.API,
                    message="빗썸 API: 주문 조회 성공",
                    data={
                        "order_id": order_id,
                        "response_status": response.status_code,
                        "order_result": order_res
                    }
                )
            return order_res
        except requests.exceptions.RequestException as e:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message="빗썸 API: 주문 조회 네트워크 오류",
                    data={
                        "order_id": order_id,
                        "error_type": type(e).__name__,
                        "error_message": str(e)
                    }
                )
            raise
        except Exception as e:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message="빗썸 API: 주문 조회 중 예외 발생",
                    data={
                        "order_id": order_id,
                        "error_type": type(e).__name__,
                        "error_message": str(e)
                    }
                )
            raise
     
            
    def get_order(self, order_id: str) -> OrderResult:
        """개별 주문 조회
        
        Args:
            symbol (str): 심볼 (예: 'BTC')
            order_id (str): 주문 ID
            
        Returns:
            Optional[OrderResult]: 주문 정보를 담은 OrderResult 객체 또는 None
        """
        endpoint = f"{self.base_url}/v1/order"
        params = {
            'uuid': order_id
        }
        
        headers = {
            'Authorization': self._create_auth_token(params)
        }
        
        if self.log_manager:
            self.log_manager.log(
                category=LogCategory.API,
                message="빗썸 API: 주문 조회 요청",
                data={
                    "order_id": order_id,
                    "endpoint": endpoint
                }
            )
        
        try:
            response = requests.get(endpoint, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
            order_result = OrderResult.from_dict(data)
                
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.API,
                    message="빗썸 API: 주문 조회 성공",
                    data={
                        "order_id": order_id,
                        "response_status": response.status_code,
                        "order_result": order_result
                    }
                )
            return order_result
        except requests.exceptions.RequestException as e:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message="빗썸 API: 주문 조회 네트워크 오류",
                    data={
                        "order_id": order_id,
                        "error_type": type(e).__name__,
                        "error_message": str(e)
                    }
                )
            raise
        except Exception as e:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message="빗썸 API: 주문 조회 중 예외 발생",
                    data={
                        "order_id": order_id,
                        "error_type": type(e).__name__,
                        "error_message": str(e)
                    }
                )
            raise
            
    def cancel_order(self, symbol: str, order_id: str) -> Dict:
        """주문 취소
        
        Args:
            symbol (str): 심볼 (예: 'BTC')
            order_id (str): 취소할 주문 ID
            
        Returns:
            Dict: 취소 결과를 담은 딕셔너리
        """
        endpoint = f"{self.base_url}/trade/cancel"
        params = {
            'order_currency': symbol,
            'order_id': order_id,
            'type': 'bid'  # 또는 'ask', 취소할 주문의 종류에 따라
        }
        
        headers = {
            'Authorization': self._create_auth_token(params),
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.post(endpoint, data=json.dumps(params), headers=headers)
            response.raise_for_status()
            data = response.json()
            
            if data.get('status') == '0000':
                return data.get('data', {})
            else:
                if self.log_manager:
                    self.log_manager.log(
                        category=LogCategory.ERROR,
                        message="주문 취소 실패",
                        data={"message": data.get('message'), "symbol": symbol, "order_id": order_id}
                    )
                return {}
                
        except Exception as e:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message="주문 취소 중 오류 발생",
                    data={"error": str(e), "symbol": symbol, "order_id": order_id}
                )
            return {} 