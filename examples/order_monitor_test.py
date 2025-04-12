import asyncio
import os
from datetime import datetime
from dotenv import load_dotenv

from src.order_monitor import OrderMonitor
from src.trading_order import TradingOrder
from src.trading_logger import TradingLogger
from src.utils.log_manager import LogManager, LogCategory

# 환경 변수 로드
load_dotenv()

async def main():
    """메인 비동기 함수"""
    trading_logger = TradingLogger()
    trading_order = TradingOrder()
    order_monitor = OrderMonitor(
        trading_order=trading_order,
        trading_logger=trading_logger,
    )
    
    order_request = trading_logger.query_many(
        conditions={
            "Order State": "wait"
        },
        sheet_name="order_request"
    )
    
    for order in order_request:
        order_id = order["Order UUID"]
        await order_monitor.start_monitoring(order_id)

if __name__ == "__main__":   
    # 비동기 이벤트 루프 실행
    asyncio.run(main()) 