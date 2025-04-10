import json
from datetime import datetime
from typing import Dict, Optional

import requests
from requests import Response
from src.models.market_data import TradeExecutionResult
from src.utils.log_manager import LogManager, LogCategory

class DiscordNotifier:
    def __init__(self, webhook_url: str, log_manager: LogManager):
        """Discord 웹훅을 통해 알림을 보내는 클래스

        Args:
            webhook_url (str): Discord 웹훅 URL
            log_manager (LogManager): 로깅을 담당할 LogManager 인스턴스
        """
        self.webhook_url = webhook_url
        self.log_manager = log_manager

    def _send_message(self, content: str, embeds: Optional[list] = None) -> Response:
        """Discord로 메시지를 전송합니다.

        Args:
            content (str): 메시지 내용
            embeds (Optional[list], optional): Discord 임베드. Defaults to None.

        Returns:
            Response: 요청 응답
        """
        data = {"content": content}
        if embeds:
            data["embeds"] = embeds

        response = requests.post(
            self.webhook_url,
            data=json.dumps(data),
            headers={"Content-Type": "application/json"},
        )

        if response.status_code != 204:
            self.log_manager.log(
                category=LogCategory.ERROR,
                message="Discord 메시지 전송 실패",
                data={
                    "status_code": response.status_code,
                    "response": response.text
                }
            )
        
        return response

    def _format_number(self, value) -> str:
        """숫자를 포맷팅합니다."""
        try:
            if isinstance(value, str):
                value = float(value)
            return f"{value:,.0f}"
        except (ValueError, TypeError):
            return str(value)

    def send_trade_notification(self, result: TradeExecutionResult) -> None:
        """매매 실행 결과를 Discord로 전송합니다."""
        try:
            # 기본 정보 추출
            symbol = result.decision_result.symbol
            decision = result.decision_result.decision
            analysis = result.decision_result.analysis
            order_info = result.order_info
            order_result = result.order_result

            # 이모지 설정
            action_emoji = "🔵" if order_info.side == "bid" else "🔴"
            
            # 가격 정보 포맷팅 (None 값 처리)
            price = order_info.price if order_info and order_info.price is not None else 0
            volume = order_info.volume if order_info and order_info.volume is not None else 0
            amount = order_info.krw_amount if order_info and order_info.krw_amount is not None else 0
            
            # 자산 정보 포맷팅
            balance = analysis.asset_info.balance if analysis and analysis.asset_info else 0
            current_value = analysis.asset_info.current_value if analysis and analysis.asset_info else 0
            profit_loss_rate = analysis.asset_info.profit_loss_rate if analysis and analysis.asset_info else 0
            
            # 메시지 생성
            message = (
                f"{action_emoji} **{symbol} {order_info.side.upper()}**\n"
                f"```\n"
                f"가격: {price:,.0f} KRW\n"
                f"수량: {volume:.8f}\n"
                f"금액: {amount:,.0f} KRW\n"
                f"상태: {order_result.state if order_result else '미체결'}\n"
                f"보유량: {balance:.8f}\n"
                f"평가금액: {current_value:,.0f} KRW\n"
                f"수익률: {profit_loss_rate:.2f}%\n"
                f"판단근거: {decision.reason}\n"
                f"```"
            )

            # Discord로 전송
            self._send_message(message)
            
            self.log_manager.log(
                category=LogCategory.DISCORD,
                message=f"{symbol} 매매 알림 전송 완료",
                data={
                    "symbol": symbol,
                    "action": order_info.side,
                    "price": price,
                    "volume": volume,
                    "amount": amount
                }
            )
            
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ERROR,
                message=f"Discord 매매 알림 전송 실패: {str(e)}",
                data={"error": str(e)}
            )

    def send_error_notification(self, error_message: str) -> None:
        """에러 메시지를 Discord로 전송합니다.

        Args:
            error_message (str): 에러 메시지
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        embed = {
            "title": "⚠️ 에러 발생",
            "color": 0xff0000,
            "description": error_message,
            "footer": {"text": now}
        }

        self._send_message("", [embed])
        self.log_manager.log(
            category=LogCategory.DISCORD,
            message="에러 알림 전송 완료",
            data={"error_message": error_message}
        ) 