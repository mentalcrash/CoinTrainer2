import os
import sys
from dotenv import load_dotenv
from tabulate import tabulate

# src 디렉토리를 파이썬 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.account import Account

def format_number(value: float) -> str:
    """숫자를 보기 좋게 포맷팅"""
    if value >= 1:
        return f"{value:,.2f}"
    else:
        return f"{value:.8f}"

def test_balance():
    """잔고 조회 테스트"""
    # API 키 로드
    load_dotenv()
    api_key = os.getenv('BITHUMB_API_KEY')
    secret_key = os.getenv('BITHUMB_SECRET_KEY')
    
    if not api_key or not secret_key:
        print("Error: API 키가 설정되지 않았습니다. .env 파일을 확인해주세요.")
        return
    
    try:
        # 계정 객체 생성
        account = Account(api_key, secret_key)
        
        # 전체 잔고 조회
        print("\n=== 전체 잔고 조회 ===")
        balances = account.get_balance()
        
        if balances:
            # 보유 중인 자산만 필터링
            active_balances = [b for b in balances if float(b['balance']) > 0 or float(b['locked']) > 0]
            
            # 테이블 형식으로 출력
            table_data = []
            for balance in active_balances:
                table_data.append([
                    balance['currency'],
                    format_number(balance['balance']),
                    format_number(balance['locked']),
                    format_number(balance['avg_buy_price']),
                    'Yes' if balance['avg_buy_price_modified'] else 'No',
                    balance['unit_currency']
                ])
            
            headers = ['코인', '주문가능', '거래중', '매수평균가', '평단가수정', '기준화폐']
            print(tabulate(table_data, headers=headers, tablefmt='grid'))
            
            # 총 보유량 계산
            for balance in active_balances:
                total = float(balance['balance']) + float(balance['locked'])
                print(f"\n{balance['currency']} 총 보유량: {format_number(total)}")
                
    except Exception as e:
        print(f"Error: 테스트 중 오류 발생: {e}")

if __name__ == "__main__":
    test_balance() 