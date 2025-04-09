import os
import json
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from google.oauth2 import service_account
from googleapiclient.discovery import build
from src.utils.log_manager import LogManager, LogCategory

class TradingLogger:
    """Google Sheets를 이용한 트레이딩 로거"""
    
    def __init__(self, log_manager: LogManager):
        """
        Args:
            log_manager (LogManager): 로깅을 담당할 LogManager 인스턴스
            
        Environment Variables:
            GOOGLE_SHEETS_ID: 구글 스프레드시트 ID
            GOOGLE_CREDENTIALS_PATH: 구글 서비스 계정 키 파일 경로
        """
        self.SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
        self.SPREADSHEET_ID = os.getenv('GOOGLE_SHEETS_ID')  # 스프레드시트 ID
        self.log_manager = log_manager
        
        if not self.SPREADSHEET_ID:
            raise ValueError("GOOGLE_SHEETS_ID 환경 변수가 설정되지 않았습니다.")
        
        credentials_path = os.getenv('GOOGLE_CREDENTIALS_PATH')
        if not credentials_path:
            raise ValueError("GOOGLE_CREDENTIALS_PATH 환경 변수가 설정되지 않았습니다.")
        
        self.service = self._get_sheets_service(credentials_path)
        
        # 시트 이름 정의
        self.SHEETS = {
            'trades': 'Trading History',    # 매매 기록
            'assets': 'Asset History',      # 자산 현황
            'performance': 'Performance',    # 성과 지표
            'decisions': 'Trading Decisions', # 매매 판단
            'market': 'Market Data'         # 시장 데이터
        }
        
        # 시트 초기화
        self._initialize_sheets()
    
    def _get_sheets_service(self, credentials_path: str):
        """Google Sheets API 서비스 인스턴스를 생성합니다."""
        try:
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path,
                scopes=self.SCOPES
            )
            return build('sheets', 'v4', credentials=credentials)
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ERROR,
                message="Google Sheets API 서비스 생성 실패",
                data={"error": str(e)}
            )
            raise
    
    def _initialize_sheets(self):
        """필요한 시트들을 초기화합니다."""
        try:
            # 기존 시트 목록 조회
            sheets = self.service.spreadsheets().get(
                spreadsheetId=self.SPREADSHEET_ID
            ).execute().get('sheets', [])
            
            existing_sheets = [sheet['properties']['title'] for sheet in sheets]
            
            # 필요한 시트 생성
            for sheet_name in self.SHEETS.values():
                if sheet_name not in existing_sheets:
                    self._create_sheet(sheet_name)
                    self._initialize_headers(sheet_name)
            
            self.log_manager.log(
                category=LogCategory.SYSTEM,
                message="시트 초기화 완료"
            )
            
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ERROR,
                message="시트 초기화 실패",
                data={"error": str(e)}
            )
            raise
    
    def _create_sheet(self, sheet_name: str):
        """새로운 시트를 생성합니다."""
        try:
            request = {
                'addSheet': {
                    'properties': {
                        'title': sheet_name
                    }
                }
            }
            
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.SPREADSHEET_ID,
                body={'requests': [request]}
            ).execute()
            
            self.log_manager.log(
                category=LogCategory.SYSTEM,
                message=f"시트 생성 완료: {sheet_name}"
            )
            
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ERROR,
                message="시트 생성 실패",
                data={"sheet_name": sheet_name, "error": str(e)}
            )
            raise
    
    def _initialize_headers(self, sheet_name: str):
        """시트의 헤더를 초기화합니다."""
        headers = {
            'Trading History': [
                'ID', 'Timestamp', 'Symbol', 'Order ID', 'Action', 'Order Type', 'Order Status',
                'Price', 'Executed Volume', 'Remaining Volume', 'Total Amount',
                'Fee Paid', 'Reserved Fee', 'Trades Count', 'Created At'
            ],
            'Asset History': [
                'ID', 'Timestamp', 'Symbol', 'Balance', 'Locked', 'Average Buy Price',
                'Current Value', 'Profit Loss', 'Profit Loss Rate', 
                'KRW Balance', 'KRW Locked', 'Total Asset Value'
            ],
            'Performance': [
                'Timestamp', 'Symbol', 'Daily ROI', 'Weekly ROI',
                'Monthly ROI', 'Total Profit Loss', 'Win Rate'
            ],
            'Trading Decisions': [
                'ID', 'Timestamp', 'Symbol', 'Decision', 'Quantity (%)',
                'Target Price', 'Stop Loss', 'Confidence', 'Entry Timing', 'Urgency Level',
                'Short-term Outlook', 'Long-term Outlook',
                'Decision Reasons', 'Risk Factors', 'Key Events',
                'Next Decision Time', 'Next Decision Reason'
            ],
            'Market Data': [
                'ID', 'Timestamp', 'Symbol', 
                # 가격 및 거래량 정보
                'Current Price', 'Minute Change (%)', 'Minute Volume',
                # 이동평균선
                'MA5', 'MA20', 
                # 기술적 지표
                'RSI-14', 'Volatility',
                # 추세 정보
                'Price Trend', 'Volume Trend', 'Volume Slope',
                # 매매 시그널
                'MA Signal', 'RSI Signal', 'Volume Signal', 'Trend Signal',
                'Overall Signal', 'Signal Strength'
            ]
        }
        
        if sheet_name in headers:
            values = [headers[sheet_name]]
            self._update_values(sheet_name, 'A1', values)
            self.log_manager.log(
                category=LogCategory.SYSTEM,
                message=f"{sheet_name} 헤더 초기화 완료"
            )
    
    def _update_values(self, sheet_name: str, range_: str, values: List[List]):
        """시트의 값을 업데이트합니다."""
        try:
            range_name = f"{sheet_name}!{range_}"
            body = {
                'values': values
            }
            
            self.service.spreadsheets().values().update(
                spreadsheetId=self.SPREADSHEET_ID,
                range=range_name,
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()
            
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ERROR,
                message="값 업데이트 실패",
                data={"error": str(e)}
            )
            raise
    
    def _append_values(self, sheet_name: str, values: List[List]):
        """시트에 새로운 행을 추가합니다."""
        try:
            range_name = f"{sheet_name}!A:Z"
            body = {
                'values': values
            }
            
            self.service.spreadsheets().values().append(
                spreadsheetId=self.SPREADSHEET_ID,
                range=range_name,
                valueInputOption='USER_ENTERED',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()
            
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ERROR,
                message="행 추가 실패",
                data={"error": str(e)}
            )
            raise
    
    def log_trade(self, id: str, order_result: Dict):
        """매매 기록을 저장합니다.
        
        Args:
            id (str): 거래 기록의 고유 식별자 (다른 시트와의 연결을 위한 키)
            order_result (Dict): 주문 실행 결과
            {
                # 공통 필드
                "uuid": str,           # 주문 ID
                "side": str,           # 주문 방향 ("bid" 또는 "ask")
                "ord_type": str,       # 주문 타입
                "state": str,          # 주문 상태
                "market": str,         # 마켓 정보
                "created_at": str,     # 주문 생성 시각
                "trades_count": int,   # 거래 횟수
                "paid_fee": float,     # 지불된 수수료
                "executed_volume": str, # 체결된 수량

                # 매수 주문일 때 추가되는 필드
                "price": Optional[float],        # 주문 가격
                "reserved_fee": Optional[float], # 예약된 수수료
                "locked": float or str,         # 잠긴 금액 (KRW) 또는 수량 (코인)

                # 매도 주문일 때 추가되는 필드
                "volume": Optional[float],         # 주문 수량
                "remaining_volume": Optional[float] # 남은 수량
            }
        """
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            symbol = order_result['market'].split('-')[1]  # KRW-BTC에서 BTC 추출
            is_bid = order_result['side'] == "bid"
            
            # 가격 처리: 매수일 때는 price 필드 사용, 매도일 때는 locked/executed_volume으로 계산
            price = order_result.get('price', 0.0)
            if not price and not is_bid:
                # 매도 주문이고 price가 없는 경우, locked/executed_volume으로 계산
                try:
                    executed_volume = float(order_result['executed_volume'])
                    if executed_volume > 0:
                        price = float(order_result['locked']) / executed_volume
                except (ValueError, ZeroDivisionError):
                    price = 0.0
            
            # 총 거래 금액 계산
            executed_volume = float(order_result['executed_volume'])
            total_amount = price * executed_volume
            
            # 남은 수량 처리
            remaining_volume = order_result.get('remaining_volume', 0.0)
            if remaining_volume is None:
                remaining_volume = 0.0
            
            # 예약 수수료 처리
            reserved_fee = order_result.get('reserved_fee', 0.0)
            if reserved_fee is None:
                reserved_fee = 0.0
            
            values = [[
                id,                                     # ID (새로 추가)
                now,                                    # Timestamp
                symbol,                                 # Symbol
                order_result['uuid'],                  # Order ID
                "매수" if is_bid else "매도",            # Action
                order_result['ord_type'],              # Order Type
                order_result['state'],                 # Order Status
                str(price),                            # Price
                str(executed_volume),                  # Executed Volume
                str(remaining_volume),                 # Remaining Volume
                str(total_amount),                     # Total Amount
                str(order_result['paid_fee']),         # Fee Paid
                str(reserved_fee),                     # Reserved Fee
                order_result['trades_count'],          # Trades Count
                order_result['created_at']             # Created At
            ]]
            
            self._append_values(self.SHEETS['trades'], values)
            self.log_manager.log(
                category=LogCategory.TRADING,
                message=f"매매 기록 저장 완료: {symbol}",
                data={
                    "id": id,
                    "order_id": order_result['uuid'],
                    "symbol": symbol,
                    "action": "매수" if is_bid else "매도",
                    "price": price,
                    "executed_volume": executed_volume,
                    "total_amount": total_amount
                }
            )
            
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ERROR,
                message="매매 기록 저장 실패",
                data={"error": str(e)}
            )
            raise
    
    def log_asset_status(self, id: str, symbol: str, asset_data: Dict):
        """자산 현황을 저장합니다.
        
        Args:
            id (str): 자산 기록의 고유 식별자
            symbol (str): 자산 심볼 (예: BTC)
            asset_data (Dict): 자산 현황 데이터
            {
                'balance': float,        # 보유 수량
                'locked': float,         # 거래 중인 수량
                'avg_buy_price': float,  # 평균 매수가
                'current_value': float,  # 현재 평가 금액
                'profit_loss': float,    # 평가 손익
                'profit_loss_rate': float, # 수익률
                'krw_balance': float,    # 보유 원화
                'krw_locked': float      # 거래 중인 원화
            }
        """
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 총 자산 가치 계산 (코인 평가금액 + 보유 원화 + 거래 중인 원화)
            total_asset_value = (
                asset_data['current_value'] + 
                asset_data['krw_balance'] + 
                asset_data['krw_locked']
            )
            
            values = [[
                id,                                 # ID
                now,                                # Timestamp
                symbol,                             # Symbol
                str(asset_data['balance']),         # Balance
                str(asset_data['locked']),          # Locked
                str(asset_data['avg_buy_price']),   # Average Buy Price
                str(asset_data['current_value']),   # Current Value
                str(asset_data['profit_loss']),     # Profit Loss
                str(asset_data['profit_loss_rate']), # Profit Loss Rate
                str(asset_data['krw_balance']),     # KRW Balance
                str(asset_data['krw_locked']),      # KRW Locked
                str(total_asset_value)              # Total Asset Value
            ]]
            
            self._append_values(self.SHEETS['assets'], values)
            self.log_manager.log(
                category=LogCategory.ASSET,
                message=f"자산 현황 저장 완료: {symbol}",
                data={
                    "id": id,
                    "symbol": symbol,
                    "balance": asset_data['balance'],
                    "locked": asset_data['locked'],
                    "current_value": asset_data['current_value'],
                    "profit_loss_rate": asset_data['profit_loss_rate'],
                    "total_asset_value": total_asset_value,
                    "krw_balance": asset_data['krw_balance'],
                    "krw_locked": asset_data['krw_locked']
                }
            )
            
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ERROR,
                message="자산 현황 저장 실패",
                data={
                    "id": id,
                    "symbol": symbol,
                    "error": str(e)
                }
            )
            raise
    
    def log_performance(self, performance_data: Dict):
        """성과 지표를 저장합니다."""
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            values = [[
                now,
                performance_data['symbol'],
                performance_data['daily_roi'],
                performance_data['weekly_roi'],
                performance_data['monthly_roi'],
                performance_data['total_profit_loss'],
                performance_data['win_rate']
            ]]
            
            self._append_values(self.SHEETS['performance'], values)
            self.log_manager.log(
                category=LogCategory.SYSTEM,
                message=f"성과 지표 저장 완료: {performance_data['symbol']}"
            )
            
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ERROR,
                message="성과 지표 저장 실패",
                data={"error": str(e)}
            )
            raise
    
    def log_decision(self, id: str, symbol: str, decision_data: Dict):
        """매매 판단을 저장합니다.
        
        Args:
            id (str): 매매 판단 기록의 고유 식별자
            symbol (str): 자산 심볼 (예: BTC)
            decision_data (Dict): 매매 판단 데이터
            {
                "decision": str,           # "매수" / "매도" / "관망"
                "quantity_percent": float,  # 매매 수량 비율 (0~100)
                "target_price": float,     # 목표가 (KRW)
                "stop_loss": float,        # 손절가 (KRW)
                "confidence": float,       # 신뢰도 (0.0 ~ 1.0)
                "reasons": List[str],      # 판단 이유 목록
                "risk_factors": List[str], # 위험 요소 목록
                "additional_info": {
                    "short_term_outlook": str,  # 단기 전망
                    "long_term_outlook": str,   # 장기 전망
                    "key_events": List[str]     # 주목할 이벤트 목록
                },
                "next_decision": {
                    "interval_minutes": int,  # 다음 판단까지 대기 시간
                    "reason": str            # 시간 간격 선택 이유
                },
                "entry_timing": str,      # "즉시" / "1분 후" / "조건 충족 시"
                "urgency_level": str      # "높음" / "중간" / "낮음"
            }
        """
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 다음 판단 시각 계산
            next_decision_time = (
                datetime.now().replace(second=0, microsecond=0) +
                timedelta(minutes=decision_data['next_decision']['interval_minutes'])
            ).strftime("%Y-%m-%d %H:%M:%S")
            
            values = [[
                id,                                     # ID
                now,                                    # Timestamp
                symbol,                                 # Symbol
                decision_data['decision'],              # Decision
                str(decision_data['quantity_percent']), # Quantity (%)
                str(decision_data['target_price']),     # Target Price
                str(decision_data['stop_loss']),        # Stop Loss
                str(decision_data['confidence']),       # Confidence
                decision_data['entry_timing'],          # Entry Timing
                decision_data['urgency_level'],         # Urgency Level
                decision_data['additional_info']['short_term_outlook'],  # Short-term Outlook
                decision_data['additional_info']['long_term_outlook'],   # Long-term Outlook
                '\n'.join(decision_data['reasons']),    # Decision Reasons
                '\n'.join(decision_data['risk_factors']), # Risk Factors
                '\n'.join(decision_data['additional_info']['key_events']), # Key Events
                next_decision_time,                     # Next Decision Time
                decision_data['next_decision']['reason'] # Next Decision Reason
            ]]
            
            self._append_values(self.SHEETS['decisions'], values)
            
            # 매매 판단의 중요도에 따라 로그 카테고리 결정
            log_category = (
                LogCategory.TRADING 
                if decision_data['decision'] in ['매수', '매도'] and decision_data['urgency_level'] == '높음'
                else LogCategory.SYSTEM
            )
            
            self.log_manager.log(
                category=log_category,
                message=f"매매 판단 저장 완료: {symbol}",
                data={
                    "id": id,
                    "symbol": symbol,
                    "decision": decision_data['decision'],
                    "confidence": decision_data['confidence'],
                    "entry_timing": decision_data['entry_timing'],
                    "urgency_level": decision_data['urgency_level'],
                    "target_price": decision_data['target_price'],
                    "stop_loss": decision_data['stop_loss'],
                    "quantity_percent": decision_data['quantity_percent'],
                    "short_term_outlook": decision_data['additional_info']['short_term_outlook'],
                    "next_decision_time": next_decision_time,
                    "reasons_count": len(decision_data['reasons']),
                    "risk_factors_count": len(decision_data['risk_factors']),
                    "key_events_count": len(decision_data['additional_info']['key_events'])
                }
            )
            
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ERROR,
                message="매매 판단 저장 실패",
                data={
                    "id": id,
                    "symbol": symbol,
                    "error": str(e)
                }
            )
            raise
    
    def log_market_data(self, id: str, symbol: str, market_data: Dict):
        """시장 데이터를 저장합니다.
        
        Args:
            id (str): 시장 데이터 기록의 고유 식별자
            symbol (str): 자산 심볼 (예: BTC)
            market_data (Dict): 시장 데이터
            {
                'current_price': float,    # 현재가
                'minute_change': float,    # 분당 변화율(%)
                'minute_volume': float,    # 분당 거래량
                'ma5': float,             # 5분 이동평균
                'ma20': float,            # 20분 이동평균
                'rsi_14': float,          # RSI(14) 지표
                'volatility': float,      # 변동성
                'price_trend': str,       # 가격 추세
                'volume_trend': str,      # 거래량 추세
                'volume_slope': float,    # 거래량 기울기
                'ma_signal': int,         # 이동평균 시그널
                'rsi_signal': int,        # RSI 시그널
                'volume_signal': int,     # 거래량 시그널
                'trend_signal': int,      # 추세 시그널
                'overall_signal': int,    # 종합 시그널
                'signal_strength': float  # 시그널 강도
            }
        """
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            values = [[
                id,                                    # ID
                now,                                   # Timestamp
                symbol,                                # Symbol
                str(market_data['current_price']),     # Current Price
                str(market_data['minute_change']),     # Minute Change (%)
                str(market_data['minute_volume']),     # Minute Volume
                str(market_data['ma5']),              # MA5
                str(market_data['ma20']),             # MA20
                str(market_data['rsi_14']),           # RSI-14
                str(market_data['volatility']),       # Volatility
                market_data['price_trend'],           # Price Trend
                market_data['volume_trend'],          # Volume Trend
                str(market_data['volume_slope']),     # Volume Slope
                str(market_data['ma_signal']),        # MA Signal
                str(market_data['rsi_signal']),       # RSI Signal
                str(market_data['volume_signal']),    # Volume Signal
                str(market_data['trend_signal']),     # Trend Signal
                str(market_data['overall_signal']),   # Overall Signal
                str(market_data['signal_strength'])   # Signal Strength
            ]]
            
            self._append_values(self.SHEETS['market'], values)
            
            # 중요한 시장 상태 변화나 강한 시그널이 감지될 때 더 자세한 로그 기록
            signal_description = self._get_signal_description(market_data)
            
            self.log_manager.log(
                category=LogCategory.MARKET,
                message=f"시장 데이터 저장 완료: {symbol}",
                data={
                    "id": id,
                    "symbol": symbol,
                    "current_price": market_data['current_price'],
                    "minute_change": market_data['minute_change'],
                    "price_trend": market_data['price_trend'],
                    "rsi_14": market_data['rsi_14'],
                    "overall_signal": market_data['overall_signal'],
                    "signal_strength": market_data['signal_strength'],
                    "signal_description": signal_description
                }
            )
            
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ERROR,
                message="시장 데이터 저장 실패",
                data={
                    "id": id,
                    "symbol": symbol,
                    "error": str(e)
                }
            )
            raise
    
    def _get_signal_description(self, market_data: Dict) -> str:
        """시장 데이터로부터 시그널 설명을 생성합니다."""
        signals = []
        
        # RSI 과매수/과매도 체크
        if market_data['rsi_14'] >= 70:
            signals.append("RSI 과매수 구간")
        elif market_data['rsi_14'] <= 30:
            signals.append("RSI 과매도 구간")
        
        # 이동평균선 골든/데드 크로스 체크
        if market_data['ma_signal'] > 0:
            signals.append("골든 크로스 발생")
        elif market_data['ma_signal'] < 0:
            signals.append("데드 크로스 발생")
        
        # 거래량 급증 체크
        if market_data['volume_signal'] > 1:
            signals.append("거래량 급증")
        
        # 강한 추세 체크
        if abs(market_data['signal_strength']) >= 0.7:
            trend = "상승" if market_data['overall_signal'] > 0 else "하락"
            signals.append(f"강한 {trend} 추세")
        
        return ", ".join(signals) if signals else "특이사항 없음" 