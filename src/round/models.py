from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Literal, Union, Tuple, Dict
from src.models.order import OrderResponse
from src.models.market_data import TradeExecutionResult

class RoundStatus:
    """라운드의 상태를 정의합니다."""
    CREATED = 'created'          # 라운드 생성됨
    WATCHING = 'watching'        # 매수 기회 탐색 중
    ENTRY_READY = 'entry_ready'  # 매수 시그널 발생
    ENTRY_ORDERED = 'entry_ordered'  # 매수 주문 발생
    HOLDING = 'holding'          # 매수 완료, 포지션 보유 중
    EXIT_READY = 'exit_ready'    # 매도 시그널 발생
    EXIT_ORDERED = 'exit_ordered'  # 매도 주문 발생
    COMPLETED = 'completed'      # 정상 종료
    FAILED = 'failed'            # 비정상 종료

    @classmethod
    def is_valid_status(cls, status: str) -> bool:
        """주어진 상태가 유효한지 확인합니다."""
        return status in [
            cls.CREATED, cls.WATCHING, 
            cls.ENTRY_READY, cls.ENTRY_ORDERED,
            cls.HOLDING, 
            cls.EXIT_READY, cls.EXIT_ORDERED,
            cls.COMPLETED, cls.FAILED
        ]

    @classmethod
    def can_transition_to(cls, current: str, next_status: str) -> bool:
        """현재 상태에서 다음 상태로 전환이 가능한지 확인합니다."""
        valid_transitions = {
            cls.CREATED: [cls.WATCHING, cls.FAILED],
            cls.WATCHING: [cls.ENTRY_READY, cls.FAILED],
            cls.ENTRY_READY: [cls.ENTRY_ORDERED, cls.WATCHING, cls.FAILED],
            cls.ENTRY_ORDERED: [cls.HOLDING, cls.WATCHING, cls.FAILED],
            cls.HOLDING: [cls.EXIT_READY, cls.FAILED],
            cls.EXIT_READY: [cls.EXIT_ORDERED, cls.HOLDING, cls.FAILED],
            cls.EXIT_ORDERED: [cls.COMPLETED, cls.HOLDING, cls.FAILED],
            cls.COMPLETED: [],  # 종료 상태에서는 전환 불가
            cls.FAILED: []      # 실패 상태에서는 전환 불가
        }
        return next_status in valid_transitions.get(current, [])

@dataclass
class RoundOrder:
    """라운드 내 주문 정보"""
    order_id: str                    # 주문 ID
    timestamp: datetime              # 주문 시각
    price: float                     # 주문 가격
    volume: float                    # 주문 수량
    type: Literal['entry', 'exit']   # 주문 타입 (진입/청산)
    status: Literal[                 # 주문 상태
        'waiting',                   # 대기
        'pending',                   # 진행 중
        'completed',                 # 완료
        'canceled',                  # 취소됨
        'failed'                     # 실패
    ]
    order_result: Optional[OrderResponse] = None  # 실제 주문 결과

@dataclass
class RoundMetrics:
    """라운드 성과 지표"""
    entry_price: float               # 진입 가격
    current_price: float             # 현재 가격
    profit_loss: float              # 손익
    profit_loss_rate: float         # 수익률
    holding_time: int               # 보유 시간 (분)
    max_profit_rate: float          # 최대 수익률
    max_loss_rate: float           # 최대 손실률
    volatility: float              # 변동성

@dataclass
class TradingRound:
    """매매 라운드 정보"""
    id: str                         # 라운드 ID
    symbol: str                     # 거래 심볼
    start_time: datetime           # 시작 시각
    status: Literal[                # 라운드 상태
        'waiting',                  # 매수 대기
        'buying',                   # 매수 중
        'holding',                  # 보유 중
        'selling',                  # 매도 중
        'completed',                # 완료
        'failed'                    # 실패
    ]
    
    # 목표 설정
    take_profit: Optional[float] = None  # 목표가
    stop_loss: Optional[float] = None    # 손절가
    
    # 주문 정보
    entry_order: Optional[RoundOrder] = None    # 진입 주문
    exit_order: Optional[RoundOrder] = None     # 청산 주문
    
    # 성과 지표
    metrics: Optional[RoundMetrics] = None      # 라운드 성과 지표
    
    # 매매 판단 히스토리
    decision_history: List[TradeExecutionResult] = None  # 매매 판단 기록
    
    # 종료 정보
    end_time: Optional[datetime] = None         # 종료 시각
    exit_reason: Optional[str] = None           # 종료 사유
    entry_reason: Optional[str] = None           # 매수 진입 이유

    def __post_init__(self):
        """초기화 후 처리"""
        if self.decision_history is None:
            self.decision_history = []
        if self.entry_reason is None:
            self.entry_reason = ""

    @property
    def is_active(self) -> bool:
        """현재 라운드가 활성 상태인지 확인"""
        return self.status in ['waiting', 'buying', 'holding', 'selling']

    @property
    def is_completed(self) -> bool:
        """라운드가 완료되었는지 확인"""
        return self.status in ['completed', 'failed']

    @property
    def duration(self) -> int:
        """라운드 진행 시간 (분)"""
        end = self.end_time or datetime.now()
        return int((end - self.start_time).total_seconds() / 60)

    def add_decision(self, result: TradeExecutionResult):
        """매매 판단 결과를 히스토리에 추가"""
        self.decision_history.append(result)

    def update_metrics(self, current_price: float):
        """성과 지표 업데이트"""
        if not self.entry_order or not self.entry_order.price:
            return

        profit_loss = current_price - self.entry_order.price
        profit_loss_rate = (profit_loss / self.entry_order.price) * 100

        self.metrics = RoundMetrics(
            entry_price=self.entry_order.price,
            current_price=current_price,
            profit_loss=profit_loss,
            profit_loss_rate=profit_loss_rate,
            holding_time=self.duration,
            max_profit_rate=max(profit_loss_rate, self.metrics.max_profit_rate if self.metrics else profit_loss_rate),
            max_loss_rate=min(profit_loss_rate, self.metrics.max_loss_rate if self.metrics else profit_loss_rate),
            volatility=0.0  # TODO: 변동성 계산 로직 추가
        ) 

    def to_dict(self) -> Dict:
        """라운드 정보를 딕셔너리로 변환합니다."""
        return {
            "id": self.id,
            "symbol": self.symbol,
            "status": self.status,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "take_profit": self.take_profit if self.take_profit is not None else None,
            "stop_loss": self.stop_loss if self.stop_loss is not None else None,
            "entry_order": self.entry_order.to_dict() if self.entry_order else None,
            "exit_order": self.exit_order.to_dict() if self.exit_order else None,
            "metrics": self.metrics.to_dict() if self.metrics else None,
            "decision_history": self.decision_history,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "exit_reason": self.exit_reason,
            "entry_reason": self.entry_reason,
            "duration": str(self.end_time - self.start_time) if self.end_time else None
        }

@dataclass
class GPTEntryDecision:
    """GPT의 매수 진입 결정 데이터"""
    should_enter: bool           # 매수 진입 여부
    target_profit_rate: float    # 목표 수익률 (%)
    stop_loss_rate: float       # 손절 수익률 (%)
    reasons: List[str]          # 판단 근거
    current_price: float        # 현재가
    target_price: float         # 목표가
    stop_loss_price: float      # 손절가
    timestamp: datetime         # 결정 시간 