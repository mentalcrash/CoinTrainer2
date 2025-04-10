from dataclasses import dataclass, asdict
from typing import Literal, Optional, Dict, Any, Union, ClassVar
from datetime import datetime
import json

PriceTrendType = Literal["상승", "하락", "횡보"]
VolumeTrendType = Literal["상승", "하락", "횡보"]
SignalType = Literal["매수", "매도", "중립"]
MomentumType = Literal["강세", "약세", "중립"]
VolumeSignalType = Literal["활발", "침체", "중립"]
OrderbookType = Literal["매수세", "매도세", "중립"]
MarketStateType = Literal["안정", "불안정"]
OverallSignalType = Literal["매수", "매도", "관망"]
EntryTimingType = Literal["즉시", "대기"]
ActionType = Literal["매수", "매도", "관망"]
RiskLevelType = Literal["상", "중", "하"]
OrderSideType = Literal["bid", "ask", "none"]
OrderType = Literal["limit", "price", "market", "none"]

@dataclass
class CurrentPrice:
    """현재가 정보"""
    symbol: str            # 심볼
    trade_price: float    # 현재가
    opening_price: float  # 시가
    high_price: float     # 고가
    low_price: float      # 저가
    prev_closing_price: float  # 전일종가
    change: str           # RISE(상승)/EVEN(보합)/FALL(하락)
    change_price: float   # 변화액의 절대값
    change_rate: float    # 변화율의 절대값
    signed_change_price: float  # 부호가 있는 변화액
    signed_change_rate: float   # 부호가 있는 변화율
    trade_volume: float   # 가장 최근 거래량
    acc_trade_price: float      # 누적 거래대금
    acc_trade_price_24h: float  # 24시간 누적 거래대금
    acc_trade_volume: float     # 누적 거래량
    acc_trade_volume_24h: float # 24시간 누적 거래량
    timestamp: int        # 타임스탬프

@dataclass
class MarketOverview:
    """분봉 기준 시장 개요 데이터"""
    current_price: float = 0.0       # 현재가
    ma1: Optional[float] = 0.0       # 1분 이동평균
    ma3: Optional[float] = 0.0       # 3분 이동평균
    ma5: Optional[float] = 0.0       # 5분 이동평균
    rsi_1: Optional[float] = 50.0    # 1분 RSI
    rsi_3: Optional[float] = 50.0    # 3분 RSI
    volatility_3m: Optional[float] = 0.0  # 3분 변동성
    volatility_5m: Optional[float] = 0.0  # 5분 변동성
    price_trend_1m: PriceTrendType = "횡보"    # 1분 가격 추세
    volume_trend_1m: VolumeTrendType = "횡보"  # 1분 거래량 추세
    vwap_3m: Optional[float] = 0.0   # 3분 VWAP
    bb_width: Optional[float] = 0.0  # 볼린저 밴드 폭
    order_book_ratio: Optional[float] = 1.0  # 매수/매도 호가 비율
    spread: Optional[float] = 0.0    # 호가 스프레드
    premium_rate: Optional[float] = 0.0  # 선물 프리미엄/디스카운트
    funding_rate: Optional[float] = 0.0  # 선물 펀딩비율
    price_stability: Optional[float] = 1.0  # 가격 안정성 점수

    @classmethod
    def from_dict(cls, data: Dict) -> 'MarketOverview':
        """딕셔너리로부터 MarketOverview 객체를 생성합니다."""
        processed_data = {}
        for key, value in data.items():
            if key in ['price_trend_1m', 'volume_trend_1m']:
                processed_data[key] = str(value) if value is not None else "횡보"
            elif isinstance(value, (int, float, str)):
                try:
                    processed_data[key] = float(value) if value is not None else 0.0
                except (ValueError, TypeError):
                    processed_data[key] = 0.0
            else:
                processed_data[key] = value
        return cls(**processed_data)

    def to_dict(self) -> Dict:
        """MarketOverview 객체를 딕셔너리로 변환합니다."""
        return {
            'current_price': self.current_price,
            'ma1': self.ma1 if self.ma1 is not None else 0.0,
            'ma3': self.ma3 if self.ma3 is not None else 0.0,
            'ma5': self.ma5 if self.ma5 is not None else 0.0,
            'rsi_1': self.rsi_1 if self.rsi_1 is not None else 50.0,
            'rsi_3': self.rsi_3 if self.rsi_3 is not None else 50.0,
            'volatility_3m': self.volatility_3m if self.volatility_3m is not None else 0.0,
            'volatility_5m': self.volatility_5m if self.volatility_5m is not None else 0.0,
            'price_trend_1m': self.price_trend_1m,
            'volume_trend_1m': self.volume_trend_1m,
            'vwap_3m': self.vwap_3m if self.vwap_3m is not None else 0.0,
            'bb_width': self.bb_width if self.bb_width is not None else 0.0,
            'order_book_ratio': self.order_book_ratio if self.order_book_ratio is not None else 1.0,
            'spread': self.spread if self.spread is not None else 0.0,
            'premium_rate': self.premium_rate if self.premium_rate is not None else 0.0,
            'funding_rate': self.funding_rate if self.funding_rate is not None else 0.0,
            'price_stability': self.price_stability if self.price_stability is not None else 1.0
        }

@dataclass
class TradingSignals:
    """스캘핑 매매 신호 데이터"""
    price_signal: SignalType        # 가격 신호 (매수/매도/중립)
    momentum_signal: MomentumType   # 모멘텀 신호 (강세/약세/중립)
    volume_signal: VolumeSignalType # 거래량 신호 (활발/침체/중립)
    orderbook_signal: OrderbookType # 호가창 신호 (매수세/매도세/중립)
    futures_signal: SignalType      # 선물 신호 (매수/매도/중립)
    market_state: MarketStateType   # 시장 상태 (안정/불안정)
    overall_signal: OverallSignalType # 종합 신호 (매수/매도/관망)
    signal_strength: float          # 신호 강도 (0.0 ~ 1.0)
    entry_timing: EntryTimingType   # 진입 타이밍 (즉시/대기)

@dataclass
class AssetInfo:
    """계정 자산 정보 데이터"""
    balance: float            # 보유 수량
    locked: float            # 거래중 수량
    avg_buy_price: float     # 매수 평균가
    current_value: float     # 현재 평가금액
    profit_loss: float       # 평가손익
    profit_loss_rate: float  # 수익률(%)
    krw_balance: float       # 보유 현금(KRW)
    krw_locked: float        # 거래중인 현금(KRW)

@dataclass
class AnalysisResult:
    """종합 분석 결과 데이터"""
    success: bool                    # 분석 성공 여부
    market_data: MarketOverview  # 시장 데이터
    signals: TradingSignals      # 매매 신호
    asset_info: AssetInfo        # 자산 정보
    timestamp: datetime              # 분석 시간

@dataclass
class NextDecision:
    """다음 판단 시점 정보"""
    interval_minutes: float  # 0.5 | 1 | 2 | 3 | 5 | 10 | 30
    reason: str            # 대기 시간 선택 이유 (최대 50자)

@dataclass
class TradingDecision:
    """GPT-4 매매 판단 결과"""
    action: ActionType           # 매수/매도/관망
    reason: str                  # 판단 이유 (최대 100자)
    confidence: float           # 확신도 (0.0 ~ 1.0)
    risk_level: RiskLevelType   # 위험도
    next_decision: NextDecision # 다음 판단 시점
    entry_price: Optional[float] = None  # 매수/매도 희망가격
    stop_loss: Optional[float] = None   # 손절가격
    take_profit: Optional[float] = None # 목표가격

    @classmethod
    def from_dict(cls, data: Dict) -> 'TradingDecision':
        """딕셔너리로부터 TradingDecision 객체를 생성합니다.
        
        Args:
            data (Dict): 매매 판단 데이터 딕셔너리
            
        Returns:
            TradingDecision: 생성된 TradingDecision 객체
        """
        # 가격 필드 처리
        entry_price = data.get('entry_price')
        stop_loss = data.get('stop_loss')
        take_profit = data.get('take_profit')
        
        # 숫자 변환 시도
        try:
            entry_price = float(entry_price) if entry_price is not None else None
        except (ValueError, TypeError):
            entry_price = None
            
        try:
            stop_loss = float(stop_loss) if stop_loss is not None else None
        except (ValueError, TypeError):
            stop_loss = None
            
        try:
            take_profit = float(take_profit) if take_profit is not None else None
        except (ValueError, TypeError):
            take_profit = None
            
        # confidence 처리 (필수 필드)
        try:
            confidence = float(data.get('confidence', 0.0))
        except (ValueError, TypeError):
            confidence = 0.0
            
        # next_decision 처리
        next_decision_data = data.get('next_decision', {
            'interval_minutes': 5,
            'reason': '기본 대기 시간'
        })
        next_decision = NextDecision(
            interval_minutes=float(next_decision_data.get('interval_minutes', 5)),
            reason=str(next_decision_data.get('reason', '기본 대기 시간'))
        )
        
        return cls(
            action=data.get('action', '관망'),
            reason=data.get('reason', ''),
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            confidence=confidence,
            risk_level=data.get('risk_level', '중'),
            next_decision=next_decision
        )

    def to_dict(self) -> Dict:
        """TradingDecision 객체를 딕셔너리로 변환합니다."""
        return {
            'action': self.action,
            'reason': self.reason,
            'entry_price': self.entry_price,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'confidence': self.confidence,
            'risk_level': self.risk_level,
            'next_decision': asdict(self.next_decision)
        }

@dataclass
class TradingDecisionResult:
    """매매 판단 종합 결과"""
    success: bool                    # 판단 성공 여부
    symbol: str                      # 심볼
    timestamp: datetime              # 판단 시간
    analysis: AnalysisResult         # 분석 결과
    decision: TradingDecision        # GPT-4 매매 판단
    error: Optional[str] = None      # 에러 메시지 (실패 시)

@dataclass
class OrderInfo:
    """주문 정보"""
    side: OrderSideType          # 매수/매도 구분
    order_type: OrderType        # 주문 타입
    price: Optional[float]       # 주문 가격
    volume: Optional[float]      # 주문 수량
    krw_amount: Optional[float] = None  # KRW 주문 금액

    def to_dict(self) -> Dict:
        """OrderInfo 객체를 딕셔너리로 변환

        Returns:
            Dict: 변환된 딕셔너리
        """
        return asdict(self)

@dataclass
class OrderResult:
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

    # 에러 발생 시 사용되는 필드
    error: Optional[str] = None     # 에러 메시지

    @classmethod
    def from_dict(cls, data: Dict) -> 'OrderResult':
        """딕셔너리로부터 OrderResult 객체 생성

        Args:
            data (Dict): 주문 결과 데이터 딕셔너리

        Returns:
            OrderResult: 생성된 OrderResult 객체
        """
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
        
        return cls(**merged_data)

    @classmethod
    def from_json(cls, json_str: str) -> 'OrderResult':
        """JSON 문자열로부터 OrderResult 객체 생성

        Args:
            json_str (str): 주문 결과 JSON 문자열

        Returns:
            OrderResult: 생성된 OrderResult 객체
        """
        data = json.loads(json_str)
        return cls.from_dict(data)

    def to_dict(self) -> Dict:
        """OrderResult 객체를 딕셔너리로 변환

        Returns:
            Dict: 변환된 딕셔너리
        """
        return asdict(self)

    def to_json(self) -> str:
        """OrderResult 객체를 JSON 문자열로 변환

        Returns:
            str: 변환된 JSON 문자열
        """
        return json.dumps(self.to_dict())

@dataclass
class TradeExecutionResult:
    """매매 실행 결과"""
    success: bool                                # 실행 성공 여부
    decision_result: TradingDecisionResult      # 매매 판단 결과
    order_info: OrderInfo      # 주문 정보
    order_result: Optional[OrderResult] = None  # 주문 실행 결과
    error: Optional[str] = None                 # 에러 메시지

    def to_dict(self) -> Dict:
        """TradeExecutionResult 객체를 딕셔너리로 변환

        Returns:
            Dict: 변환된 딕셔너리
        """
        return {
            'success': self.success,
            'decision_result': self.decision_result.__dict__ if self.decision_result else None,
            'order_info': self.order_info.to_dict() if self.order_info else None,
            'order_result': self.order_result.to_dict() if self.order_result else None,
            'error': self.error
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'TradeExecutionResult':
        """딕셔너리로부터 TradeExecutionResult 객체 생성

        Args:
            data (Dict): 매매 실행 결과 데이터 딕셔너리

        Returns:
            TradeExecutionResult: 생성된 TradeExecutionResult 객체
        """
        return cls(
            success=data.get('success', False),
            decision_result=TradingDecisionResult(**data['decision_result']) if data.get('decision_result') else None,
            order_info=OrderInfo(**data['order_info']) if data.get('order_info') else None,
            order_result=OrderResult.from_dict(data['order_result']) if data.get('order_result') else None,
            error=data.get('error')
        ) 