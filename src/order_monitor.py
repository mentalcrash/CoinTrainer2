import asyncio
from typing import Optional, Dict, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass

from src.trading_order import TradingOrder, OrderResponse
from src.trading_logger import LogManager, LogCategory
from src.trading_logger import TradingLogger
from src.trading_executor import TradeExecutionResult

@dataclass
class OrderMonitorConfig:
    """주문 모니터링 설정"""
    check_interval: float = 1.0           # 주문 상태 확인 간격 (초)
    timeout: float = 60.0                 # 주문 체결 대기 시간 (초)
    max_retries: int = 3                  # 재시도 횟수
    partial_fill_timeout: float = 30.0    # 부분 체결 대기 시간 (초)

class OrderMonitor:
    """주문 모니터링 클래스"""
    
    def __init__(
        self,
        trading_order: TradingOrder,
        trading_logger: TradingLogger,
        log_manager: Optional[LogManager] = None,
        config: Optional[OrderMonitorConfig] = None
    ):
        """
        Args:
            trading_order (TradingOrder): 주문 처리 객체
            trading_logger (TradingLogger): 로그 관리 객체
            log_manager (Optional[LogManager]): 로그 관리 객체
            config (Optional[OrderMonitorConfig]): 모니터링 설정
        """
        self.trading_order = trading_order
        self.trading_logger = trading_logger
        self.log_manager = log_manager
        self.config = config or OrderMonitorConfig()
        
        # 모니터링 중인 주문 목록
        self.monitoring_orders: Dict[str, TradeExecutionResult] = {}
        
    async def start_monitoring(
        self,
        order_id: str,
    ) -> None:
        """주문 모니터링 시작"""
        if self.log_manager:
            self.log_manager.log(
                category=LogCategory.MONITOR,
                message=f"주문 모니터링 시작",
                data={
                    "order_id": order_id,
                    "config": {
                        "check_interval": self.config.check_interval,
                        "timeout": self.config.timeout,
                        "max_retries": self.config.max_retries,
                        "partial_fill_timeout": self.config.partial_fill_timeout
                    }
                }
            )
            
        order_request = self.trading_logger.query_many(
            conditions={
                "Order UUID": order_id
            },
            sheet_name="order_request"
        )
        
        order_state = order_request[0].get('Order State', None)
        if order_state == "complete" or order_state == "cancel":
            # logging
            return   
            
        self.monitoring_orders[order_id] = order_request
        
        try:
            await self._monitor_order(
                order_id=order_id,
            )
        except Exception as e:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.MONITOR_ERROR,
                    message=f"주문 모니터링 중 오류 발생",
                    data={
                        "order_id": order_id,
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "monitoring_duration": (datetime.now() - self.monitoring_orders[order_id]["start_time"]).total_seconds()
                    }
                )
            
    async def _monitor_order(
        self,
        order_id: str,
    ) -> None:
        """주문 상태 모니터링"""
        order_info = self.monitoring_orders[order_id]
        
        while True:
            try:
                # 주문 상태 조회
                order_response = self.trading_order.get_order(order_id)
                
                # 주문 상태별 처리
                if order_response.state == "done":
                    self.trading_logger.log_order_response(order_response)
                    self.trading_logger.update_data(
                        conditions={
                            "Order UUID": order_id
                        },
                        updates={
                            "Order State": "complete"
                        },
                        sheet_name="order_request"
                    )
                    break
                
            except Exception as e:
                if self.log_manager:
                    self.log_manager.log(
                        category=LogCategory.MONITOR_ERROR,
                        message=f"[주문 모니터링 중 예외 발생",
                        data={
                            "order_id": order_id,
                            "error_type": type(e).__name__,
                            "error_message": str(e),
                            "last_state": order_info.get("last_state")
                        }
                    )
                break
                
            await asyncio.sleep(self.config.check_interval)
            
    async def _handle_order_filled(
        self,
        order: OrderResponse,
        on_filled: Optional[Callable[[OrderResponse], None]]
    ) -> None:
        """주문 체결 완료 처리"""
        if self.log_manager:
            self.log_manager.log(
                category=LogCategory.TRADE,
                message="주문 체결 완료",
                data={
                    "order_id": order.uuid,
                    "market": order.market,
                    "price": order.price,
                    "executed_volume": order.executed_volume,
                    "trades_count": order.trades_count
                }
            )
            
        # 거래 정보 시트에 기록
        trade_data = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "market": order.market,
            "side": order.side,
            "price": order.price,
            "volume": order.executed_volume,
            "fee": order.paid_fee,
            "total": str(float(order.price) * float(order.executed_volume))
        }
        await self.trading_logger.log_trade(trade_data)
        
        # 콜백 실행
        if on_filled:
            on_filled(order)
            
    async def _handle_order_cancelled(self, order: OrderResponse) -> None:
        """주문 취소 처리"""
        if self.log_manager:
            self.log_manager.log(
                category=LogCategory.TRADE,
                message="주문 취소됨",
                data={
                    "order_id": order.uuid,
                    "market": order.market,
                    "executed_volume": order.executed_volume
                }
            )
            
    async def _handle_order_timeout(
        self,
        order: OrderResponse,
        on_timeout: Optional[Callable[[str], None]]
    ) -> None:
        """주문 타임아웃 처리"""
        if self.log_manager:
            self.log_manager.log(
                category=LogCategory.TRADE,
                message="주문 타임아웃",
                data={
                    "order_id": order.uuid,
                    "market": order.market,
                    "state": order.state,
                    "executed_volume": order.executed_volume
                }
            )
            
        if on_timeout:
            on_timeout(order.uuid)
            
    async def _handle_partial_fill_timeout(self, order: OrderResponse) -> None:
        """부분 체결 타임아웃 처리"""
        if self.log_manager:
            self.log_manager.log(
                category=LogCategory.TRADE,
                message="부분 체결 타임아웃",
                data={
                    "order_id": order.uuid,
                    "market": order.market,
                    "executed_volume": order.executed_volume,
                    "remaining_volume": order.remaining_volume
                }
            )