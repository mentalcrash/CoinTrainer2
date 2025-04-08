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
from typing import Dict, Optional, Union, Literal
from src.utils.log_manager import LogManager, LogCategory

class TradingOrder:
    """주문 처리를 담당하는 클래스"""
    
    def __init__(self, api_key: str = None, secret_key: str = None, log_manager: LogManager = None):
        """
        Args:
            api_key (str, optional): Bithumb API 키
            secret_key (str, optional): Bithumb Secret 키
            log_manager (LogManager, optional): 로그 매니저
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
        side: Literal['bid', 'ask'],
        order_type: Literal['limit', 'price', 'market'],
        price: Optional[float] = None,
        volume: Optional[float] = None
    ) -> Dict:
        endpoint = f"{self.base_url}/v1/orders"
        
        params = {
            'market': f'KRW-{symbol}',
            'side': side,            
            'ord_type': order_type
        }

        if price:
            params['price'] = price
        if volume:
            params['volume'] = volume

        authorization_token = self._create_auth_token(params)
        headers = {
            'Authorization': authorization_token,
            'Content-Type': 'application/json'
        }
            
        try:
            response = requests.post(endpoint, data=json.dumps(params), headers=headers)
            response.raise_for_status()
            data = response.json()
            
            if data:
                order_data = data
                self._save_order_data(symbol, order_data)
                return order_data
            else:
                if self.log_manager:
                    self.log_manager.log(
                        category=LogCategory.ERROR,
                        message="주문 생성 실패",
                        data={"message": data.get('message'), "symbol": symbol}
                    )
                return {}
                
        except Exception as e:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message="주문 생성 중 오류 발생",
                    data={"error": str(e), "symbol": symbol, "response": str(response)}
                )
            return {}
            
    def get_order(self, symbol: str, order_id: str) -> Dict:
        """개별 주문 조회
        
        Args:
            symbol (str): 심볼 (예: 'BTC')
            order_id (str): 주문 ID
            
        Returns:
            Dict: 주문 정보를 담은 딕셔너리
        """
        endpoint = f"{self.base_url}/info/order_detail"
        params = {
            'order_currency': symbol,
            'order_id': order_id
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
                        message="주문 조회 실패",
                        data={"message": data.get('message'), "symbol": symbol, "order_id": order_id}
                    )
                return {}
                
        except Exception as e:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message="주문 조회 중 오류 발생",
                    data={"error": str(e), "symbol": symbol, "order_id": order_id}
                )
            return {}
            
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
            
    def _save_order_data(self, symbol: str, order_data: Dict) -> None:
        """주문 데이터 저장
        
        Args:
            symbol (str): 심볼
            order_data (Dict): 저장할 주문 데이터
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f".temp/{timestamp}/logs/05_order_{symbol}_{timestamp}.json"
        
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(order_data, f, ensure_ascii=False, indent=2)
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.SYSTEM,
                    message=f"{symbol} order_data 저장 완료",
                    data={"filename": filename}
                )
        except Exception as e:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message="주문 데이터 저장 실패",
                    data={"error": str(e), "symbol": symbol}
                ) 