import json
from datetime import datetime
from typing import Dict, Optional, Any

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

    def _create_order_message(self, result: TradeExecutionResult) -> str:
        """주문 실행 결과로부터 디스코드 메시지를 생성합니다."""
        try:
            order_info = result.order_result
            decision = result.decision_result.decision
            market_data = result.decision_result.analysis.market_data
            
            def safe_str(value: Any) -> str:
                """None이나 빈 값을 안전하게 문자열로 변환합니다."""
                return str(value) if value is not None else "N/A"
            
            def safe_float(value: Any) -> str:
                """숫자 값을 안전하게 포맷팅합니다."""
                try:
                    if value is None:
                        return "N/A"
                    float_val = float(value)
                    return f"{float_val:,.2f}" if float_val != 0 else "N/A"
                except (ValueError, TypeError):
                    return "N/A"
            
            def safe_percent(value: Any) -> str:
                """퍼센트 값을 안전하게 포맷팅합니다."""
                try:
                    if value is None:
                        return "N/A"
                    float_val = float(value)
                    return f"{float_val:.1f}%" if float_val != 0 else "N/A"
                except (ValueError, TypeError):
                    return "N/A"
            
            # 기본 정보 설정
            action_emoji = "🔵" if order_info and order_info.side == "bid" else "🔴"
            symbol = result.decision_result.symbol.upper() if result.decision_result and result.decision_result.symbol else "Unknown"
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 가격 정보 포맷팅
            price = safe_float(order_info.price if order_info else None)
            confidence = safe_percent(decision.confidence)
            risk_level = safe_str(decision.risk_level)
            entry_price = safe_float(decision.entry_price)
            take_profit = safe_float(decision.take_profit)
            stop_loss = safe_float(decision.stop_loss)
            state = safe_str(order_info.state if order_info else "미체결")
            reason = safe_str(decision.reason)
            next_interval = safe_str(decision.next_decision.interval_minutes if decision.next_decision else "N/A")
            
            # 메시지 생성
            message = f"""
{action_emoji} **{symbol} 주문 알림** | {timestamp}
━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 **주문 정보**
• 상태: `{state}`
• 주문가: `{price}`
• 진입가: `{entry_price}`
• 목표가: `{take_profit}`
• 손절가: `{stop_loss}`

📈 **매매 판단**
• 확신도: `{confidence}`
• 리스크: `{risk_level}`
• 근거: `{reason}`
• 다음 판단: `{next_interval}분 후`

📊 **시장 분석**
• 이동평균선: MA1 `{market_data.ma1:,.0f}` | MA5 `{market_data.ma5:,.0f}` | MA20 `{market_data.ma20:,.0f}`
• RSI: 1분 `{market_data.rsi_1:.1f}` | 3분 `{market_data.rsi_3:.1f}` | 14분 `{market_data.rsi_14:.1f}`
• 변동성: 3분 `{market_data.volatility_3m:.2f}%` | 15분 `{market_data.volatility_15m:.2f}%`
• 캔들 분석: 강도 `{market_data.candle_strength}` (비율 `{market_data.candle_body_ratio:.2f}`)
• 5분 신고점: 고가 `{"갱신" if market_data.new_high_5m else "미갱신"}` | 저가 `{"갱신" if market_data.new_low_5m else "미갱신"}`
• 선물 지표: 프리미엄 `{market_data.premium_rate:.3f}%` | 펀딩비 `{market_data.funding_rate:.4f}%`
━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
            
            return message
            
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ERROR,
                message=f"디스코드 메시지 생성 실패: {str(e)}",
                data={"symbol": result.decision_result.symbol if result.decision_result else "Unknown"}
            )
            return "⚠️ 메시지 생성 중 오류가 발생했습니다."

    def send_trade_notification(self, result: TradeExecutionResult) -> None:
        """매매 실행 결과를 Discord로 전송합니다."""
        try:     
            # 메시지 생성
            message = self._create_order_message(result)

            # Discord로 전송
            self._send_message(message)
            
            self.log_manager.log(
                category=LogCategory.DISCORD,
                message=f"매매 알림 전송 완료",
                data={
                    "message": message
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