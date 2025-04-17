import json
from datetime import datetime
from typing import Dict, Optional, Any

import requests
from requests import Response
from src.models.market_data import TradeExecutionResult
from src.utils.log_manager import LogManager, LogCategory
from src.round.models import TradingRound
from src.models.order import OrderResponse


class DiscordNotifier:
    def __init__(self, webhook_url: str, log_manager: Optional[LogManager] = None):
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
            if self.log_manager:
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
                    return f"{float_val:,.2f}" if float_val != 0 else 0
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
            symbol = result.decision_result.symbol.upper()
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 메시지 생성
            message = f"""
{action_emoji} **{symbol} 주문 실행 결과** ({timestamp})
```ini
[주문 정보]
주문 가격: {safe_float(order_info.price if order_info else None)} KRW
주문 수량: {safe_str(order_info.volume if order_info else "N/A")}
주문 유형: {safe_str(order_info.side if order_info else "N/A")}

[매매 판단]
신뢰도: {safe_percent(decision.confidence)}
위험 수준: {safe_str(decision.risk_level)}
진입 가격: {safe_float(decision.entry_price)} KRW
목표 가격: {safe_float(decision.take_profit)} KRW
손절 가격: {safe_float(decision.stop_loss)} KRW

[시장 데이터]
현재 가격: {safe_float(market_data.current_price)} KRW
이동평균선:
• MA1: {safe_float(market_data.ma1)} KRW
• MA3: {safe_float(market_data.ma3)} KRW
• MA5: {safe_float(market_data.ma5)} KRW
• MA10: {safe_float(market_data.ma10)} KRW

RSI 지표:
• 3분: {safe_float(market_data.rsi_3)}
• 7분: {safe_float(market_data.rsi_7)}
• 14분: {safe_float(market_data.rsi_14)}

변동성:
• 3분: {safe_percent(market_data.volatility_3m)}
• 5분: {safe_percent(market_data.volatility_5m)}
• 10분: {safe_percent(market_data.volatility_10m)}
• 15분: {safe_percent(market_data.volatility_15m)}

호가 정보:
• 매수/매도 비율: {safe_float(market_data.order_book_ratio)}
• 스프레드: {safe_percent(market_data.spread)}

선물 시장:
• 프리미엄: {safe_percent(market_data.premium_rate)}
• 펀딩비율: {safe_percent(market_data.funding_rate)}

캔들 분석:
• 캔들 강도: {safe_str(market_data.candle_strength)}
• 실체비율: {safe_percent(market_data.candle_body_ratio)}
• 신규 고가: {'O' if market_data.new_high_5m else 'X'}
• 신규 저가: {'O' if market_data.new_low_5m else 'X'}

[판단 근거]
{safe_str(decision.reason)}

[다음 판단]
다음 판단 시간: {safe_str(decision.next_decision.interval_minutes if decision.next_decision else "N/A")}분 후
```"""
            return message
            
        except Exception as e:
            if self.log_manager:
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
            
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.DISCORD,
                    message=f"매매 알림 전송 완료",
                    data={
                        "message": message
                    }
                )
            
        except Exception as e:
            if self.log_manager:
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
        if self.log_manager:
            self.log_manager.log(
                category=LogCategory.DISCORD,
                message="에러 알림 전송 완료",
                data={"error_message": error_message}
            )
    
    def send_end_scalping(self, entry_order: OrderResponse, exit_order: OrderResponse) -> bool:
        """스캘핑 종료 알림을 Discord로 전송합니다."""
        try:
            entry_price = entry_order.price_per_unit
            exit_price = exit_order.price_per_unit
            volume = exit_order.total_volume

            # 수익 계산
            profit = (exit_price - entry_price) * volume
            profit_rate = (exit_price - entry_price) / entry_price * 100 if entry_price else 0

            # 수수료 포함 수익 계산
            fee = float(entry_order.paid_fee) + float(exit_order.paid_fee)
            total_profit = profit - fee
            profit_rate_with_fee = total_profit / (entry_price * volume) * 100

            # 이모지
            result_emoji = "🔥" if profit_rate >= 0 else "💧"
            result_label = "익절 성공" if profit_rate >= 0 else "손절 처리"
            
            holding_time = exit_order.created_at - entry_order.created_at
            hours = holding_time.total_seconds() // 3600
            minutes = (holding_time.total_seconds() % 3600) // 60
            seconds = holding_time.total_seconds() % 60

            message = f"""```ini
    [{result_emoji} 스캘핑 종료 알림]

    [매매 결과]
    • 심볼: {entry_order.market}
    
    • 매수가: {entry_price:,.0f} KRW
    • 매도가: {exit_price:,.0f} KRW
    • 수량: {volume}
    
    • 수익: {profit:,.0f} KRW
    • 수익률: {profit_rate:+.2f}%
    
    • 수수료: {fee:,.0f} KRW
    • 순수익: {total_profit:,.0f} KRW
    • 수익률: {profit_rate_with_fee:+.2f}%
    
    • 홀딩 시간: {int(hours)}시간 {int(minutes)}분 {int(seconds)}초

    [{result_label}] 거래가 종료되었습니다.
    ```"""
            self._send_message(message)
            return True

        except Exception as e:
            print(f"스캘핑 종료 알림 전송 실패 {e}\nentry_order: {entry_order}\nexit_order: {exit_order}")
            
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message=f"스캘핑 종료 알림 전송 실패: {str(e)}",
                    data={
                        "entry_order": entry_order.uuid,
                        "exit_order": exit_order.uuid,
                        "market": entry_order.market
                    }
                )
            return False
    
    def send_start_scalping(self, response: OrderResponse, target_price: int, stop_loss_price: int) -> bool:
        """스캘핑 시작 알림을 Discord로 전송합니다."""
        try:
            # 체결가 및 수량
            entry_price = response.price_per_unit
            entry_volume = float(response.total_volume or 0)
            entry_time = response.created_at

            message = f"""```ini
    [🚀 스캘핑 시작 알림]

    [기본 정보]
    • 심볼: {response.market}
    • 주문 ID: {response.uuid}
    • 주문 시각: {entry_time}

    [매수 정보]
    • 체결가: {entry_price:,.0f} KRW
    • 체결 수량: {entry_volume}
    
    [타겟 가격]
    • 목표가: {target_price:,.0f} KRW
    • 손절가: {stop_loss_price:,.0f} KRW

    트레이딩 모니터링을 시작합니다... 🔍
    ```"""
            self._send_message(message)
            return True

        except Exception as e:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message=f"스캘핑 시작 알림 전송 실패: {str(e)}",
                    data={"order_uuid": response.uuid, "market": response.market}
                )
            return False
                    
                    
    def send_start_round_notification(self, round: TradingRound) -> bool:
        """라운드 시작 알림을 Discord로 전송합니다."""
        try:
            # 수익률 계산
            target_profit_rate = ((round.take_profit - round.entry_order.price) / round.entry_order.price) * 100
            stop_loss_rate = ((round.stop_loss - round.entry_order.price) / round.entry_order.price) * 100
            
            # 진입 근거 포맷팅
            entry_reasons = "\n".join(f"  ▸ {reason}" for reason in round.entry_reason)
            
            message = f"""```ini
[🎯 새로운 트레이딩 라운드 시작]

[기본 정보]
• 라운드 ID: {round.id}
• 심볼: {round.symbol}
• 시작 시간: {round.start_time.strftime('%Y-%m-%d %H:%M:%S')}
• 상태: {round.status}

[매매 정보]
• 매수가: {round.entry_order.price:,.0f} KRW
• 목표가: {round.take_profit:,.0f} KRW (수익률: {target_profit_rate:+.2f}%)
• 손절가: {round.stop_loss:,.0f} KRW (손실률: {stop_loss_rate:+.2f}%)
• 수량: {round.entry_order.volume}

[진입 근거]
{entry_reasons}

트레이딩 시그널 대기 중... 🔍
```"""
            self._send_message(message)
            return True
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message=f"라운드 시작 알림 전송 실패: {str(e)}",
                    data={
                    "round_id": round.id,
                    "symbol": round.symbol,
                    "error": str(e)
                }
            )
            return False
    
    def send_scalping_notification(self, entry_order: OrderResponse, exit_order: OrderResponse  ) -> bool:
        """스캐핑 알림을 Discord로 전송합니다."""
        
    
    def send_end_round_notification(self, round: TradingRound) -> bool:
        """라운드 종료 알림을 Discord로 전송합니다."""
        try:
            # 수익률 계산
            entry_price = float(round.entry_order.price)
            exit_price = float(round.exit_order.price)
            profit = exit_price - entry_price
            profit_rate = profit / entry_price * 100
            volume = float(round.exit_order.volume)
            
            # 수수료 계산
            entry_fee = float(round.entry_order.order_result.paid_fee)
            exit_fee = float(round.exit_order.order_result.paid_fee)
            total_fee = entry_fee + exit_fee
            
            # 순수익 계산
            total_profit = (profit * volume) - total_fee
            profit_rate_with_fee = total_profit / (entry_price * volume) * 100
            
            # 승패 결정 및 이모지 선택
            was_victorious = profit_rate_with_fee > 0
            result_emoji = "🔥" if was_victorious else "💧"
            result_text = "승리" if was_victorious else "패배"
            
            # 홀딩 시간 계산
            try:
                # 주문 시간 기준으로 계산
                entry_time = round.entry_order.timestamp
                exit_time = round.exit_order.timestamp
                if entry_time and exit_time:
                    holding_time = exit_time - entry_time
                    hours = holding_time.total_seconds() // 3600
                    minutes = (holding_time.total_seconds() % 3600) // 60
                else:
                    # 라운드 시간 기준으로 계산 (대체 로직)
                    holding_time = round.exit_time - round.entry_time
                    hours = holding_time.total_seconds() // 3600
                    minutes = (holding_time.total_seconds() % 3600) // 60
            except Exception as e:
                if self.log_manager:
                    self.log_manager.log(
                        category=LogCategory.WARNING,
                        message="홀딩 시간 계산 실패",
                        data={
                        "round_id": round.id,
                        "error": str(e)
                    }
                )
                hours = 0
                minutes = 0
                
            # 진입/청산 근거 포맷팅
            entry_reasons = "\n".join(f"  ▸ {reason}" for reason in round.entry_reason)
            exit_reasons = "\n".join(f"  ▸ {reason}" for reason in round.exit_reason)
            
            message = f"""```ini
[{result_emoji} 트레이딩 라운드 종료 {result_emoji}]

[기본 정보]
• 라운드 ID: {round.id}
• 심볼: {round.symbol}
• 결과: {result_text}
• 홀딩 시간: {int(hours)}시간 {int(minutes)}분

[매매 정보]
• 매수가: {entry_price:,.0f} KRW
• 매도가: {exit_price:,.0f} KRW
• 거래량: {volume} {round.symbol}
• 순수익: {total_profit:,.0f} KRW

[수익률 분석]
• 단순 수익률: {profit_rate:+.2f}%
• 수수료 합계: {total_fee:,.0f} KRW
  ⤷ 매수 수수료: {entry_fee:,.0f} KRW
  ⤷ 매도 수수료: {exit_fee:,.0f} KRW
• 최종 수익률: {profit_rate_with_fee:+.2f}%

[매매 근거]
[진입]
{entry_reasons}

[청산]
{exit_reasons}
```"""
            self._send_message(message)
            return True
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message=f"라운드 종료 알림 전송 실패: {str(e)}",
                    data={
                    "round_id": round.id,
                    "symbol": round.symbol,
                    "error": str(e)
                }
            )
            return False