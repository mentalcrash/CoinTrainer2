import os
import sys
from dotenv import load_dotenv
from src.news_summarizer import NewsSummarizer
from src.news import News
from src.utils.logger import setup_logger

# 로거 설정
logger = setup_logger('news_summarizer_test')

# .env 파일 로드
load_dotenv()

def test_news_summarizer(dev_mode: bool = False):
    """뉴스 요약기 테스트
    
    Args:
        dev_mode: 개발 모드 여부 (True일 경우 API 호출 없이 더미 데이터 사용)
    """
    try:
        # API 키 확인 (개발 모드가 아닐 때만)
        api_key = os.getenv("OPENAI_API_KEY")
        if not dev_mode and not api_key:
            logger.error("OPENAI_API_KEY가 설정되지 않았습니다.")
            sys.exit(1)
            
        api_endpoint = "https://api.openai.com/v1/chat/completions"
        
        # News와 NewsSummarizer 인스턴스 생성
        logger.info("뉴스 수집기와 요약기 초기화...")
        news = News()
        summarizer = NewsSummarizer(api_key, api_endpoint)
        
        # BTC와 ETH 뉴스 분석
        for symbol in ["BTC", "ETH"]:
            logger.info(f"{symbol} 뉴스 분석 시작...")
            
            # 뉴스 수집
            logger.info(f"{symbol} 뉴스 수집 중...")
            news_items = news.get_news(
                symbol=symbol,
                max_age_hours=24,  # 시간 범위를 늘려서 더 많은 뉴스를 수집
                limit=5
            )
            
            if not news_items:
                logger.warning(f"{symbol} 뉴스가 수집되지 않았습니다.")
                continue
                
            logger.info(f"{symbol} 뉴스 {len(news_items)}개 수집 완료")
            
            # 뉴스 분석 실행
            logger.info(f"{symbol} 뉴스 분석 중...")
            try:
                result = summarizer.analyze_news(
                    news_items=news_items,
                    dev_mode=False
                )
                
                if result["success"]:
                    logger.info(f"{symbol} 뉴스 분석 완료")
                    # 결과 출력
                    print("\n" + "=" * 80)
                    print(summarizer.format_analysis(result))
                    print("=" * 80 + "\n")
                else:
                    logger.error(f"{symbol} 뉴스 분석 실패: {result.get('error')}")
                    
            except Exception as e:
                logger.error(f"분석 중 오류 발생: {str(e)}", exc_info=True)

    except Exception as e:
        logger.error(f"테스트 실행 중 오류 발생: {str(e)}")
        raise

if __name__ == "__main__":
    # 환경 변수로 개발 모드 설정
    dev_mode = os.getenv("DEV_MODE", "false").lower() == "true"
    test_news_summarizer(dev_mode) 