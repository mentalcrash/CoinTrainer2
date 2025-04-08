import os
import requests
import time
import jwt
import uuid
from typing import Dict, List, Optional, Union
from src.utils.log_manager import LogManager, LogCategory

class Account:
    def __init__(self, api_key: str, secret_key: str, log_manager: Optional[LogManager] = None):
        """빗썸 계정 API 클래스 초기화
        
        Args:
            api_key (str): 빗썸 API 키
            secret_key (str): 빗썸 Secret 키
            log_manager (Optional[LogManager]): 로그 매니저 (선택사항)
        """
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = "https://api.bithumb.com"
        self.log_manager = log_manager
    
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
        if self.log_manager:
            self.log_manager.log(
                category=LogCategory.API,
                message="빗썸 API: 계정 잔고 조회 요청"
            )
        
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
                    formatted_result = [self._format_balance_item(item) for item in result]
                    
                    if self.log_manager:
                        total_balance = sum(item['balance'] * item['avg_buy_price'] 
                                         for item in formatted_result 
                                         if item['unit_currency'] == 'KRW')
                        
                        self.log_manager.log(
                            category=LogCategory.API,
                            message="빗썸 API: 계정 잔고 조회 성공",
                            data={
                                "request_url": f"{self.base_url}/v1/accounts",
                                "response_status": response.status_code
                            }
                        )
                        
                        self.log_manager.log(
                            category=LogCategory.ASSET,
                            message="계정 자산 정보 업데이트",
                            data={
                                "total_balance_krw": total_balance,
                                "assets_count": len(formatted_result),
                                "balances": formatted_result
                            }
                        )
                    
                    return formatted_result
                else:
                    error_msg = f"예상치 못한 응답 형식: {result}"
                    if self.log_manager:
                        self.log_manager.log(
                            category=LogCategory.API,
                            message="빗썸 API: 잔고 조회 실패 - 잘못된 응답 형식",
                            data={
                                "request_url": f"{self.base_url}/v1/accounts",
                                "response_status": response.status_code,
                                "response": result
                            }
                        )
                    print(error_msg)
                    return None
            else:
                error_msg = f"HTTP 오류: {response.status_code}"
                if self.log_manager:
                    self.log_manager.log(
                        category=LogCategory.API,
                        message="빗썸 API: 잔고 조회 실패 - HTTP 오류",
                        data={
                            "request_url": f"{self.base_url}/v1/accounts",
                            "response_status": response.status_code,
                            "response": response.text
                        }
                    )
                print(error_msg)
                print(f"응답 내용: {response.text}")
                return None
                
        except Exception as e:
            error_msg = f"잔고 조회 중 오류 발생: {e}"
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.API,
                    message="빗썸 API: 잔고 조회 실패 - 예외 발생",
                    data={
                        "request_url": f"{self.base_url}/v1/accounts",
                        "error": str(e)
                    }
                )
            print(error_msg)
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