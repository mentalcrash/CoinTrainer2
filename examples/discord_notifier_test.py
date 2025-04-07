import os
import logging
from dotenv import load_dotenv

from src.discord_notifier import DiscordNotifier

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_discord_notifier():
    """Discord 알림 테스트"""
    # 환경 변수 로드
    load_dotenv()
    
    # Discord 웹훅 URL 확인
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        raise ValueError("DISCORD_WEBHOOK_URL 환경 변수가 설정되지 않았습니다.")

    # Discord 알림 객체 생성
    notifier = DiscordNotifier(webhook_url)

    # 테스트용 데이터
    symbol = "BTC"
    decision = {
        "decision": "매수",
        "quantity_percent": 20,
        "confidence": 0.85,
        "target_price": 120000000,
        "stop_loss": 115000000,
        "reasons": [
            "RSI가 30 이하로 과매도 구간",
            "MACD 골든크로스 발생",
            "거래량 급증"
        ],
        "risk_factors": [
            "단기 이동평균선이 장기 이동평균선 아래에 위치",
            "전반적인 시장 하락세"
        ],
        "next_decision": {
            "interval_minutes": 30
        }
    }

    order_result = {
        "type": "매수",
        "status": "완료",
        "volume": 0.1,
        "price": 119500000,
        "executed_volume": 0.1,
        "remaining_volume": 0
    }

    asset_info = {
        "balance": 0.5,
        "avg_buy_price": 118000000,
        "current_value": 59750000,
        "profit_loss_rate": 1.27,
        "krw_balance": 1000000
    }

    try:
        # 매매 알림 전송
        logger.info("매매 알림 전송 테스트 시작...")
        notifier.send_trade_notification(symbol, decision, order_result, asset_info)
        logger.info("매매 알림 전송 성공")

        # 에러 알림 전송
        logger.info("에러 알림 전송 테스트 시작...")
        notifier.send_error_notification("API 호출 중 오류가 발생했습니다: Connection timeout")
        logger.info("에러 알림 전송 성공")

    except Exception as e:
        logger.error(f"알림 전송 실패: {str(e)}")
        raise

if __name__ == "__main__":
    test_discord_notifier() 