from typing import List, Optional, Dict, Union, Literal
from dataclasses import dataclass, asdict
from datetime import datetime
import json
from src.models.market_data import OrderSideType, OrderType

@dataclass
class Trade:
    """주문 체결 정보"""
    market: str           # 마켓의 유일 키
    uuid: str            # 체결의 고유 아이디
    price: str           # 체결 가격
    volume: str          # 체결 양
    funds: str           # 체결된 총 가격
    side: str            # 체결 종류
    created_at: str      # 체결 시각

    @classmethod
    def from_dict(cls, data: dict) -> Optional['Trade']:
        """딕셔너리에서 Trade 객체 생성"""
        try:
            return cls(
                market=data.get('market', ''),
                uuid=data.get('uuid', ''),
                price=data.get('price', '0'),
                volume=data.get('volume', '0'),
                funds=data.get('funds', '0'),
                side=data.get('side', ''),
                created_at=data.get('created_at', '')
            )
        except Exception:
            return None


@dataclass
class OrderRequest:
    """주문 요청 정보"""
    market: str                  # KRW-BTC
    side: OrderSideType          # 매수/매도 구분
    order_type: OrderType        # 주문 타입
    price: Optional[float]       # 주문 가격
    volume: Optional[float]      # 주문 수량

    def to_dict(self) -> Dict:
        """OrderRequest 객체를 딕셔너리로 변환

        Returns:
            Dict: 변환된 딕셔너리
        """
        return asdict(self)


@dataclass
class OrderResponse:
    """주문 실행 결과"""
    # 공통 필드
    uuid: str                        # 주문 ID
    side: OrderSideType             # 주문 방향 ("bid" 또는 "ask")
    ord_type: OrderType             # 주문 타입
    state: Literal[                 # 주문 상태
        'wait',                     # 체결 대기
        'done',                     # 전체 체결 완료
        'cancel'                    # 주문 취소
    ]
    market: str                     # 마켓 정보
    created_at: str                 # 주문 생성 시각
    trades_count: int               # 거래 횟수
    paid_fee: float                 # 지불된 수수료
    executed_volume: str            # 체결된 수량

    # 매수 주문일 때 추가되는 필드
    price: Optional[float] = None        # 주문 가격
    reserved_fee: Optional[float] = None # 예약된 수수료
    remaining_fee: Optional[float] = None # 남은 수수료
    locked: Optional[Union[float, str]] = None  # 잠긴 금액(매수 시 KRW) 또는 수량(매도 시 코인)

    # 매도 주문일 때 추가되는 필드
    volume: Optional[float] = None          # 주문 수량
    remaining_volume: Optional[float] = None # 남은 수량

    # 체결 목록
    trades: List[Trade] = None

    @classmethod
    def from_dict(cls, data: Dict) -> Optional['OrderResponse']:
        """딕셔너리로부터 OrderResponse 객체 생성

        Args:
            data (Dict): 주문 결과 데이터 딕셔너리

        Returns:
            Optional[OrderResponse]: 생성된 OrderResponse 객체
        """
        try:
            # 필수 필드가 없는 경우 기본값 설정
            required_fields = {
                'uuid': '',
                'side': 'none',
                'ord_type': 'none',
                'state': 'wait',
                'market': '',
                'created_at': datetime.now().isoformat(),
                'trades_count': 0,
                'paid_fee': 0.0,
                'executed_volume': '0'
            }
            
            # 딕셔너리 데이터와 기본값 병합
            merged_data = {**required_fields, **data}
            
            # 숫자 형식 변환
            if 'price' in merged_data and merged_data['price']:
                merged_data['price'] = float(merged_data['price'])
            if 'reserved_fee' in merged_data and merged_data['reserved_fee']:
                merged_data['reserved_fee'] = float(merged_data['reserved_fee'])
            if 'volume' in merged_data and merged_data['volume']:
                merged_data['volume'] = float(merged_data['volume'])
            if 'remaining_volume' in merged_data and merged_data['remaining_volume']:
                merged_data['remaining_volume'] = float(merged_data['remaining_volume'])
            if 'locked' in merged_data and merged_data['locked']:
                # locked는 매수/매도에 따라 다른 타입 사용
                if merged_data['side'] == 'bid':
                    merged_data['locked'] = float(merged_data['locked'])
            
            # 체결 목록 변환
            trades = [
                Trade.from_dict(trade_data) 
                for trade_data in data.get('trades', [])
                if trade_data is not None
            ]
            merged_data['trades'] = trades
            
            return cls(**merged_data)
        except Exception:
            return None

    @classmethod
    def from_json(cls, json_str: str) -> Optional['OrderResponse']:
        """JSON 문자열로부터 OrderResponse 객체 생성

        Args:
            json_str (str): 주문 결과 JSON 문자열

        Returns:
            Optional[OrderResponse]: 생성된 OrderResponse 객체
        """
        try:
            data = json.loads(json_str)
            return cls.from_dict(data)
        except Exception:
            return None

    def to_dict(self) -> Dict:
        """OrderResponse 객체를 딕셔너리로 변환

        Returns:
            Dict: 변환된 딕셔너리
        """
        return asdict(self)

    def to_json(self) -> str:
        """OrderResponse 객체를 JSON 문자열로 변환

        Returns:
            str: 변환된 JSON 문자열
        """
        return json.dumps(self.to_dict()) 