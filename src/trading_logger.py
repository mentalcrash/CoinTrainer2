import os
import json
import logging
from datetime import datetime
from typing import Dict, Optional, List
from google.oauth2 import service_account
from googleapiclient.discovery import build
from src.utils.logger import setup_logger

logger = setup_logger('trading_logger')

class TradingLogger:
    """Google Sheets를 이용한 트레이딩 로거"""
    
    def __init__(self, credentials_path: str):
        """
        Args:
            credentials_path (str): Google 서비스 계정 키 파일 경로
        """
        self.SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
        self.SPREADSHEET_ID = os.getenv('GOOGLE_SHEETS_ID')  # 스프레드시트 ID
        
        if not self.SPREADSHEET_ID:
            raise ValueError("GOOGLE_SHEETS_ID 환경 변수가 설정되지 않았습니다.")
        
        self.service = self._get_sheets_service(credentials_path)
        
        # 시트 이름 정의
        self.SHEETS = {
            'trades': 'Trading History',    # 매매 기록
            'assets': 'Asset History',      # 자산 현황
            'performance': 'Performance',    # 성과 지표
            'decisions': 'Trading Decisions' # 매매 판단
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
            logger.error(f"Google Sheets API 서비스 생성 실패: {str(e)}")
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
            
            logger.info("시트 초기화 완료")
            
        except Exception as e:
            logger.error(f"시트 초기화 실패: {str(e)}")
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
            
            logger.info(f"시트 생성 완료: {sheet_name}")
            
        except Exception as e:
            logger.error(f"시트 생성 실패: {str(e)}")
            raise
    
    def _initialize_headers(self, sheet_name: str):
        """시트의 헤더를 초기화합니다."""
        headers = {
            'Trading History': [
                'Timestamp', 'Symbol', 'Action', 'Price', 'Quantity',
                'Fee', 'Total Amount', 'Reason', 'Confidence'
            ],
            'Asset History': [
                'Timestamp', 'Symbol', 'Balance', 'Average Buy Price',
                'Current Value', 'Profit Loss Rate', 'KRW Balance'
            ],
            'Performance': [
                'Timestamp', 'Symbol', 'Daily ROI', 'Weekly ROI',
                'Monthly ROI', 'Total Profit Loss', 'Win Rate'
            ],
            'Trading Decisions': [
                'Timestamp', 'Symbol', 'Decision', 'Target Price',
                'Stop Loss', 'Confidence', 'Reasons', 'Risk Factors'
            ]
        }
        
        if sheet_name in headers:
            values = [headers[sheet_name]]
            self._update_values(sheet_name, 'A1', values)
            logger.info(f"{sheet_name} 헤더 초기화 완료")
    
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
            logger.error(f"값 업데이트 실패: {str(e)}")
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
            logger.error(f"행 추가 실패: {str(e)}")
            raise
    
    def log_trade(self, trade_data: Dict):
        """매매 기록을 저장합니다."""
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            values = [[
                now,
                trade_data['symbol'],
                trade_data['decision']['action'],
                trade_data['order_result']['executed_price'],
                trade_data['order_result']['quantity'],
                trade_data['order_result']['fee'],
                trade_data['order_result']['total_amount'],
                trade_data['decision']['reason'],
                trade_data['decision']['confidence']
            ]]
            
            self._append_values(self.SHEETS['trades'], values)
            logger.info(f"매매 기록 저장 완료: {trade_data['symbol']}")
            
        except Exception as e:
            logger.error(f"매매 기록 저장 실패: {str(e)}")
    
    def log_asset_status(self, asset_data: Dict):
        """자산 현황을 저장합니다."""
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            values = [[
                now,
                asset_data['symbol'],
                asset_data['balance'],
                asset_data['avg_buy_price'],
                asset_data['current_value'],
                asset_data['profit_loss_rate'],
                asset_data['krw_balance']
            ]]
            
            self._append_values(self.SHEETS['assets'], values)
            logger.info(f"자산 현황 저장 완료: {asset_data['symbol']}")
            
        except Exception as e:
            logger.error(f"자산 현황 저장 실패: {str(e)}")
    
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
            logger.info(f"성과 지표 저장 완료: {performance_data['symbol']}")
            
        except Exception as e:
            logger.error(f"성과 지표 저장 실패: {str(e)}")
    
    def log_decision(self, decision_data: Dict):
        """매매 판단을 저장합니다."""
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            values = [[
                now,
                decision_data['symbol'],
                decision_data['decision'],
                decision_data['target_price'],
                decision_data['stop_loss'],
                decision_data['confidence'],
                '\n'.join(decision_data['reasons']),
                '\n'.join(decision_data['risk_factors'])
            ]]
            
            self._append_values(self.SHEETS['decisions'], values)
            logger.info(f"매매 판단 저장 완료: {decision_data['symbol']}")
            
        except Exception as e:
            logger.error(f"매매 판단 저장 실패: {str(e)}") 