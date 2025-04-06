import os
import requests
import time
import jwt
import uuid
from typing import Dict, List, Optional, Union

class Account:
    def __init__(self, api_key: str, secret_key: str):
        """빗썸 계정 API 클래스 초기화
        
        Args:
            api_key (str): 빗썸 API 키
            secret_key (str): 빗썸 Secret 키
        """
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = "https://api.bithumb.com"
    
    def _create_jwt_token(self) -> str:
        """JWT 토큰 생성"""
        payload = {
            'access_key': self.api_key,
            'nonce': str(uuid.uuid4()),
            'timestamp': round(time.time() * 1000)
        }
        jwt_token = jwt.encode(payload, self.secret_key, algorithm='HS256')
        return f'Bearer {jwt_token}'

    def get_balance(self) -> Optional[List[Dict]]:
        """계정 잔고 조회
            
        Returns:
            Optional[List[Dict]]: 
                - 성공시: [{
                    'currency': str,        # 화폐 코드 (예: BTC)
                    'balance': float,       # 주문 가능 수량
                    'locked': float,        # 주문중 묶여있는 수량
                    'avg_buy_price': float, # 매수평균가
                    'avg_buy_price_modified': bool,  # 매수평균가 수정 여부
                    'unit_currency': str    # 평단가 기준 화폐
                }, ...]
                - 오류 발생시: None
        """
        headers = {
            'Authorization': self._create_jwt_token()
        }
        
        try:
            response = requests.get(
                f"{self.base_url}/v1/accounts",
                headers=headers
            )
            
            if response.status_code == 200:
                result = response.json()
                if isinstance(result, list):  # 응답이 리스트인 경우
                    return [self._format_balance_item(item) for item in result]
                else:
                    print(f"예상치 못한 응답 형식: {result}")
                    return None
            else:
                print(f"HTTP 오류: {response.status_code}")
                print(f"응답 내용: {response.text}")
                return None
                
        except Exception as e:
            print(f"잔고 조회 중 오류 발생: {e}")
            return None
            
    def _format_balance_item(self, data: Dict) -> Dict:
        """잔고 데이터 포맷팅
        
        Args:
            data (Dict): API 응답의 개별 자산 데이터
            
        Returns:
            Dict: 포맷팅된 잔고 정보
        """
        return {
            'currency': data['currency'],
            'balance': float(data['balance']),
            'locked': float(data['locked']),
            'avg_buy_price': float(data['avg_buy_price']),
            'avg_buy_price_modified': bool(data['avg_buy_price_modified']),
            'unit_currency': data['unit_currency']
        }