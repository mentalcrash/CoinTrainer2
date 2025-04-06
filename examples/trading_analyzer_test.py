import os
from dotenv import load_dotenv
from src.trading_analyzer import TradingAnalyzer

def test_trading_analyzer():
    """TradingAnalyzer 테스트"""
    
    # 환경 변수 로드
    load_dotenv()
    
    # API 키 가져오기
    api_key = os.getenv('BITHUMB_API_KEY')
    secret_key = os.getenv('BITHUMB_SECRET_KEY')
    
    if not all([api_key, secret_key]):
        print("API 키가 설정되지 않았습니다.")
        return
        
    # TradingAnalyzer 초기화
    analyzer = TradingAnalyzer(api_key, secret_key)
    
    # BTC 분석
    print(f"\n{'=' * 80}")
    print(analyzer.format_analysis('BTC'))
    print(f"{'=' * 80}")

    print("########################")
    print(analyzer)

if __name__ == "__main__":
    test_trading_analyzer() 