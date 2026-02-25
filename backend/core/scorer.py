from decimal import Decimal
from .indicators import IndicatorEngine

class Scorer:
    def __init__(self, fundamental_data: dict, technical_data: dict):
        self.fundamentals = fundamental_data
        self.technical = technical_data

    def calculate_total_score(self):
        value = self.calculate_value_score()
        trend = self.calculate_trend_score()
        stability = self.calculate_stability_score()
        risk = self.calculate_risk_penalty()
        
        total = value + trend + stability - risk
        return max(0, min(100, total))

    def calculate_value_score(self):
        # 40pts Max
        score = 0
        
        # PER (15pts)
        per = self.fundamentals.get('per', 999)
        if per < 10: score += 15
        elif per < 20: score += 10
        elif per < 30: score += 5
        
        # PBR (10pts)
        pbr = self.fundamentals.get('pbr', 999)
        if pbr < 1.0: score += 10
        elif pbr < 1.5: score += 6
        
        # ROE (10pts)
        roe = self.fundamentals.get('roe', 0)
        if roe > 15: score += 10
        elif roe > 10: score += 7
        
        # EPS Growth (5pts)
        eps_growth = self.fundamentals.get('eps_growth', 0)
        if eps_growth > 10: score += 5
        
        return score

    def calculate_trend_score(self):
        # 30pts Max
        score = 0
        ma20 = self.technical.get('ma20')
        ma60 = self.technical.get('ma60')
        ma120 = self.technical.get('ma120')
        
        # MA Alignment (10pts)
        if ma20 and ma60 and ma120:
            if ma20 > ma60 > ma120:
                score += 10
        
        # RSI (5pts)
        rsi = self.technical.get('rsi', 50)
        if 40 <= rsi <= 60:
            score += 5
            
        # Returns (10pts)
        ret_60d = self.technical.get('return_60d', 0)
        if ret_60d > 0: score += 10 # Example logic
        
        return score

    def calculate_stability_score(self):
        # 20pts Max
        score = 15 # Baseline
        volatility = self.technical.get('volatility', 0)
        if volatility < 0.02: score += 5
        return score

    def calculate_risk_penalty(self):
        # -10pts Max
        penalty = 0
        if self.fundamentals.get('net_loss', False): penalty += 10
        if self.fundamentals.get('high_debt', False): penalty += 5
        return min(10, penalty)
