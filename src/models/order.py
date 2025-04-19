from typing import List, Optional, Dict, Union, Literal
from dataclasses import dataclass, asdict, fields
from datetime import datetime
import json
from src.models.market_data import OrderSideType, OrderType

@dataclass
class Trade:
    """주문 체결 정보"""
    market: str           # 마켓의 유일 키
    uuid: str            # 체결의 고유 아이디
    price: float           # 체결 가격
    volume: float          # 체결 양
    funds: float           # 체결된 총 가격
    side: str            # 체결 종류
    created_at: datetime      # 체결 시각

    @classmethod
    def from_dict(cls, data: dict) -> Optional['Trade']:
        """딕셔너리에서 Trade 객체 생성"""
        try:
            return cls(
                market=data.get('market', ''),
                uuid=data.get('uuid', ''),
                price=float(data.get('price', 0.0)),
                volume=float(data.get('volume', 0.0)),
                funds=float(data.get('funds', 0.0)),
                side=data.get('side', ''),
                created_at=datetime.fromisoformat(data.get('created_at', ''))
            )
        except Exception:
            return None
    
    def to_dict(self) -> Dict:
        """Trade 객체를 딕셔너리로 변환"""
        return asdict(self)
    
    def to_json(self) -> str:
        """Trade 객체를 JSON 문자열로 변환"""
        return json.dumps(self.to_dict())


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
    created_at: str                 # 주문 생성 시각 (2024-04-18T12:00:00+09:00)
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
    
    @property
    def total_volume(self) -> float:
        """체결 내역의 총 수량을 반환합니다."""
        return sum(float(trade.volume) for trade in self.trades)
    
    @property
    def price_per_unit(self) -> float:
        """
        평균 체결 단가 (Volume-Weighted Average Price)를 계산합니다.
        (모든 체결의 price * volume 합) / (모든 체결의 volume 합)
        체결 내역이 없으면 0.0을 반환합니다.
        """
        if not self.trades:
            return 0.0

        total_value = 0.0
        total_volume = 0.0

        for trade in self.trades:
            try:
                # trade.price와 trade.volume이 유효한 숫자인지 확인
                trade_price = float(trade.price)
                trade_volume = float(trade.volume)
                
                total_value += trade_price * trade_volume
                total_volume += trade_volume
            except (ValueError, TypeError):
                # 유효하지 않은 데이터가 있는 경우 해당 체결은 건너뜁니다.
                # 필요시 로깅 추가 가능: logging.warning(f"Invalid trade data found: {trade}")
                continue 

        if total_volume > 0:
            return total_value / total_volume
        else:
            # 체결 내역은 있으나 유효한 volume 합이 0인 경우
            return 0.0

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

            # --- 안전한 숫자 형식 변환 헬퍼 함수 ---
            def safe_float(value, default=0.0):
                """값을 float으로 안전하게 변환, 실패 시 기본값 반환"""
                if value is None: return default
                try: return float(value)
                except (ValueError, TypeError): return default

            def safe_int(value, default=0):
                """값을 int로 안전하게 변환, 실패 시 기본값 반환"""
                if value is None: return default
                try: return int(value)
                except (ValueError, TypeError): return default
            # --- 헬퍼 함수 끝 ---

            # 각 필드에 안전한 변환 적용
            merged_data['trades_count'] = safe_int(merged_data.get('trades_count'))
            merged_data['paid_fee'] = safe_float(merged_data.get('paid_fee'))
            merged_data['remaining_fee'] = safe_float(merged_data.get('remaining_fee'), None) # None 가능 필드
            merged_data['price'] = safe_float(merged_data.get('price'), None) # None 가능 필드
            merged_data['reserved_fee'] = safe_float(merged_data.get('reserved_fee'), None) # None 가능 필드
            merged_data['volume'] = safe_float(merged_data.get('volume'), None) # None 가능 필드
            merged_data['remaining_volume'] = safe_float(merged_data.get('remaining_volume'), None) # None 가능 필드

            # locked 필드 처리 (매수/매도 구분 없이 float으로 변환 시도)
            locked_value = merged_data.get('locked')
            merged_data['locked'] = safe_float(locked_value, None) if locked_value is not None else None

            # executed_volume은 클래스 정의에 따라 str 타입 유지
            
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