from src.new.api.bithumb.client import BithumbApiClient
from src.new.models.bithumb.response import Ticker
from src.new.utils.scalping_candidate_selector import ScalpingCandidateSelector

if __name__ == "__main__":
    scalping_candidate_selector = ScalpingCandidateSelector()
    candidates = scalping_candidate_selector.select_candidates()
    print(candidates)
        
        