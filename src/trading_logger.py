import os
import json
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from google.oauth2 import service_account
from googleapiclient.discovery import build
from src.utils.log_manager import LogManager, LogCategory
from src.models.market_data import TradeExecutionResult

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
                'Timestamp', 'Symbol',
                # 매매 판단 정보
                'Action', 'Entry Price', 'Take Profit', 'Stop Loss',
                'Confidence', 'Risk Level', 'Decision Reason',
                # 주문 정보
                'Order Type', 'Order Side', 'Order Volume', 'Order Price', 'Order Amount',
                # 체결 정보
                'Order Status', 'Executed Price', 'Executed Volume', 'Total Amount', 'Fee',
                # 자산 정보
                'Balance', 'Locked', 'Average Buy Price', 'Current Value',
                'Profit Loss', 'Profit Loss Rate', 'KRW Balance',
                # 시장 정보
                'Current Market Price', 'MA5', 'RSI', 'Volatility',
                'Market State', 'Signal Strength', 'Overall Signal'
            ],
            'Asset History': [
                'ID', 'Timestamp', 'Symbol', 'Balance', 'Locked', 'Average Buy Price',
                'Current Value', 'Profit Loss', 'Profit Loss Rate', 
                'KRW Balance', 'KRW Locked', 'Total Asset Value'
            ],
            'Performance': [
                'Timestamp', 'Symbol', 'Daily ROI', 'Weekly ROI',
                'Monthly ROI', 'Total Profit Loss', 'Win Rate'
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
            try:
                price = float(order_result.get('price', 0.0))
                if not price and not is_bid:
                    # 매도 주문이고 price가 없는 경우, locked/executed_volume으로 계산
                    executed_volume = float(order_result['executed_volume'])
                    locked = float(order_result['locked'])
                    if executed_volume > 0:
                        price = locked / executed_volume
            except (ValueError, TypeError, ZeroDivisionError):
                price = 0.0
            
            # 총 거래 금액 계산
            try:
                executed_volume = float(order_result['executed_volume'])
                total_amount = price * executed_volume
            except (ValueError, TypeError):
                executed_volume = 0.0
                total_amount = 0.0
            
            # 남은 수량 처리
            try:
                remaining_volume = float(order_result.get('remaining_volume', 0.0))
            except (ValueError, TypeError):
                remaining_volume = 0.0
            
            # 예약 수수료 처리
            try:
                reserved_fee = float(order_result.get('reserved_fee', 0.0))
            except (ValueError, TypeError):
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
            symbol (str): 자산 심볼 (예: XRP)
            decision_data (Dict): 매매 판단 데이터
            {
                "action": "매수" | "매도" | "관망",
                "reason": "판단 이유 (최대 100자)",
                "entry_price": float,  # 매수/매도 희망가격
                "stop_loss": float,    # 손절가격
                "take_profit": float,  # 목표가격
                "confidence": float,   # 확신도 (0.0 ~ 1.0)
                "risk_level": "상" | "중" | "하",
                "next_decision": {
                    "interval_minutes": 1 | 2 | 3 | 5,
                    "reason": str  # 다음 판단 시점 선택 이유
                }
            }
        """
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 다음 판단 시각 계산
            try:
                interval_minutes = int(decision_data['next_decision']['interval_minutes'])
                next_decision_time = (
                    datetime.now().replace(second=0, microsecond=0) +
                    timedelta(minutes=interval_minutes)
                ).strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError) as e:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message="다음 판단 시각 계산 실패",
                    data={
                        "error": str(e),
                        "interval_minutes": decision_data['next_decision'].get('interval_minutes')
                    }
                )
                # 기본값으로 5분 설정
                next_decision_time = (
                    datetime.now().replace(second=0, microsecond=0) +
                    timedelta(minutes=5)
                ).strftime("%Y-%m-%d %H:%M:%S")
            
            # 진입 타이밍 결정
            entry_timing = "즉시" if decision_data['action'] != "관망" else "대기"
            
            # 긴급도 결정
            urgency_level = {
                "상": "높음",
                "중": "중간",
                "하": "낮음"
            }.get(decision_data['risk_level'], "중간")
            
            values = [[
                id,                                     # 기록 ID
                now,                                    # 기록 시각
                symbol,                                 # 심볼
                decision_data['action'],                # 매매 행동
                str(decision_data['entry_price']),      # 진입 가격
                str(decision_data['take_profit']),      # 목표가
                str(decision_data['stop_loss']),        # 손절가
                str(decision_data['confidence']),       # 확신도
                decision_data['risk_level'],            # 리스크 레벨
                entry_timing,                           # 진입 타이밍
                urgency_level,                          # 긴급도
                decision_data['reason'],                # 판단 근거
                next_decision_time,                     # 다음 판단 시각
                decision_data['next_decision']['reason'] # 다음 판단 이유
            ]]
            
            self._append_values(self.SHEETS['decisions'], values)
            
            # 매매 판단의 중요도에 따라 로그 카테고리 결정
            log_category = (
                LogCategory.TRADING 
                if decision_data['action'] in ['매수', '매도'] and decision_data['risk_level'] == '하'
                else LogCategory.SYSTEM
            )
            
            self.log_manager.log(
                category=log_category,
                message=f"매매 판단 저장 완료: {symbol}",
                data={
                    "id": id,
                    "symbol": symbol,
                    "action": decision_data['action'],
                    "confidence": decision_data['confidence'],
                    "entry_timing": entry_timing,
                    "urgency_level": urgency_level,
                    "entry_price": decision_data['entry_price'],
                    "take_profit": decision_data['take_profit'],
                    "stop_loss": decision_data['stop_loss'],
                    "risk_level": decision_data['risk_level'],
                    "next_decision_time": next_decision_time,
                    "next_decision_reason": decision_data['next_decision']['reason']
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
            symbol (str): 자산 심볼 (예: XRP)
            market_data (Dict): 시장 데이터
            {
                'current_price': float,       # 현재가
                'ma1': float,                 # 1분 이동평균
                'ma3': float,                 # 3분 이동평균
                'ma5': float,                 # 5분 이동평균
                'rsi_1': float,               # 1분 RSI
                'rsi_3': float,               # 3분 RSI
                'volatility_3m': float,       # 3분 변동성
                'volatility_5m': float,       # 5분 변동성
                'price_trend_1m': str,        # 1분 가격 추세
                'volume_trend_1m': str,       # 1분 거래량 추세
                'vwap_3m': float,            # 3분 VWAP
                'bb_width': float,           # 볼린저 밴드 폭
                'order_book_ratio': float,   # 매수/매도 호가 비율
                'spread': float,             # 호가 스프레드
                'premium_rate': float,       # 선물 프리미엄/디스카운트
                'funding_rate': float,       # 선물 펀딩비율
                'price_stability': float,    # 가격 안정성 점수
                'price_signal': str,         # 가격 신호
                'momentum_signal': str,      # 모멘텀 신호
                'volume_signal': str,        # 거래량 신호
                'orderbook_signal': str,     # 호가창 신호
                'futures_signal': str,       # 선물 신호
                'market_state': str,         # 시장 상태
                'overall_signal': str,       # 종합 신호
                'signal_strength': float,    # 신호 강도
                'entry_timing': str          # 진입 타이밍
            }
        """
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            values = [[
                id,                                     # ID
                now,                                    # Timestamp
                symbol,                                 # Symbol
                str(market_data['current_price']),      # Current Price
                str(market_data['ma1']),                # MA1
                str(market_data['ma3']),                # MA3
                str(market_data['ma5']),                # MA5
                str(market_data['vwap_3m']),           # VWAP (3m)
                str(market_data['rsi_1']),             # RSI (1m)
                str(market_data['rsi_3']),             # RSI (3m)
                str(market_data['bb_width']),          # BB Width
                str(market_data['volatility_3m']),     # Volatility (3m)
                str(market_data['volatility_5m']),     # Volatility (5m)
                str(market_data['order_book_ratio']),  # Order Book Ratio
                str(market_data['spread']),            # Spread
                str(market_data['premium_rate']),      # Premium Rate
                str(market_data['funding_rate']),      # Funding Rate
                str(market_data['price_stability']),   # Price Stability
                market_data['price_trend_1m'],         # Price Trend (1m)
                market_data['volume_trend_1m'],        # Volume Trend (1m)
                market_data['price_signal'],           # Price Signal
                market_data['momentum_signal'],        # Momentum Signal
                market_data['volume_signal'],          # Volume Signal
                market_data['orderbook_signal'],       # Orderbook Signal
                market_data['futures_signal'],         # Futures Signal
                market_data['market_state'],           # Market State
                market_data['overall_signal'],         # Overall Signal
                str(market_data['signal_strength']),   # Signal Strength
                market_data['entry_timing']            # Entry Timing
            ]]
            
            self._append_values(self.SHEETS['market'], values)
            
            # 시장 상태 설명 생성
            market_status = self._get_market_status_description(market_data)
            
            self.log_manager.log(
                category=LogCategory.MARKET,
                message=f"시장 데이터 저장 완료: {symbol}",
                data={
                    "id": id,
                    "symbol": symbol,
                    "current_price": market_data['current_price'],
                    "market_status": market_status,
                    "signals": {
                        "price": market_data['price_signal'],
                        "momentum": market_data['momentum_signal'],
                        "volume": market_data['volume_signal'],
                        "orderbook": market_data['orderbook_signal'],
                        "futures": market_data['futures_signal'],
                        "overall": market_data['overall_signal']
                    },
                    "indicators": {
                        "rsi_1": market_data['rsi_1'],
                        "rsi_3": market_data['rsi_3'],
                        "volatility_3m": market_data['volatility_3m'],
                        "order_book_ratio": market_data['order_book_ratio'],
                        "premium_rate": market_data['premium_rate']
                    },
                    "market_state": market_data['market_state'],
                    "signal_strength": market_data['signal_strength'],
                    "entry_timing": market_data['entry_timing']
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
    
    def _get_market_status_description(self, market_data: Dict) -> str:
        """시장 상태에 대한 설명을 생성합니다."""
        try:
            descriptions = []
            
            # RSI 상태 확인
            rsi_1 = float(market_data['rsi_1'])
            if rsi_1 >= 70:
                descriptions.append("단기 과매수")
            elif rsi_1 <= 30:
                descriptions.append("단기 과매도")
            
            # 변동성 상태 확인
            volatility_3m = float(market_data['volatility_3m'])
            if volatility_3m > 1.0:
                descriptions.append("높은 변동성")
            elif volatility_3m < 0.2:
                descriptions.append("낮은 변동성")
            
            # 호가창 상태 확인
            order_book_ratio = float(market_data['order_book_ratio'])
            if order_book_ratio > 1.2:
                descriptions.append("강한 매수세")
            elif order_book_ratio < 0.8:
                descriptions.append("강한 매도세")
            
            # 선물 시장 상태 확인
            premium_rate = float(market_data['premium_rate'])
            if abs(premium_rate) > 0.5:
                state = "프리미엄" if premium_rate > 0 else "디스카운트"
                descriptions.append(f"높은 선물 {state}")
            
            # 시장 안정성 확인
            if market_data['market_state'] == "불안정":
                descriptions.append("시장 불안정")
            
            return ", ".join(descriptions) if descriptions else "안정적인 시장"
            
        except (ValueError, KeyError) as e:
            self.log_manager.log(
                category=LogCategory.ERROR,
                message="시장 상태 설명 생성 실패",
                data={"error": str(e)}
            )
            return "상태 분석 불가"

    def log_trade_record(
        self,
        symbol: str,
        result: TradeExecutionResult
    ):
        """통합된 매매 기록을 저장합니다.
        
        Args:
            symbol (str): 매매 심볼 (예: BTC)
            result (TradeExecutionResult): 매매 실행 결과
        """
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            decision = result.decision_result.decision
            analysis = result.decision_result.analysis
            order_info = result.order_info
            order_result = result.order_result
            
            values = [[
                now,                                    # Timestamp
                symbol,                                 # Symbol
                
                # 매매 판단 정보
                decision.action,                        # Action
                str(decision.entry_price),              # Entry Price
                str(decision.take_profit),              # Take Profit
                str(decision.stop_loss),                # Stop Loss
                str(decision.confidence),               # Confidence
                decision.risk_level,                    # Risk Level
                decision.reason,                        # Decision Reason
                
                # 주문 정보
                order_info.order_type,                  # Order Type
                order_info.side,                        # Order Side
                str(order_info.volume),                 # Order Volume
                str(order_info.price),                  # Order Price
                str(order_info.krw_amount),             # Order Amount
                
                # 체결 정보
                order_result.state if order_result else "미체결",  # Order Status
                str(order_result.price if order_result else 0),    # Executed Price
                str(order_result.executed_volume if order_result else 0),  # Executed Volume
                str(order_result.total_amount if order_result else 0),    # Total Amount
                str(order_result.paid_fee if order_result else 0),        # Fee
                
                # 자산 정보
                str(analysis.asset_info.balance),       # Balance
                str(analysis.asset_info.locked),        # Locked
                str(analysis.asset_info.avg_buy_price), # Average Buy Price
                str(analysis.asset_info.current_value), # Current Value
                str(analysis.asset_info.profit_loss),   # Profit Loss
                str(analysis.asset_info.profit_loss_rate), # Profit Loss Rate
                str(analysis.asset_info.krw_balance),   # KRW Balance
                
                # 시장 정보
                str(analysis.market_data.current_price), # Current Market Price
                str(analysis.market_data.ma5),          # MA5
                str(analysis.market_data.rsi_1),        # RSI
                str(analysis.market_data.volatility_3m), # Volatility
                analysis.market_data.market_state,      # Market State
                str(analysis.market_data.signal_strength), # Signal Strength
                analysis.market_data.overall_signal     # Overall Signal
            ]]
            
            self._append_values(self.SHEETS['trades'], values)
            
            self.log_manager.log(
                category=LogCategory.TRADING,
                message=f"{symbol} 매매 기록 저장 완료",
                data=result.to_dict()
            )
            
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ERROR,
                message=f"{symbol} 매매 기록 저장 실패: {str(e)}"
            )
            raise 