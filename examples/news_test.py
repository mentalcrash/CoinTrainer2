from src.news import News

def main():
    news = News()
    
    # BTC 뉴스 수집
    btc_news = news.get_news(
        symbol="BTC",
        max_age_hours=24,
        limit=5
    )
    print(news.format_news(btc_news))
    
    # ETH 뉴스 수집
    eth_news = news.get_news(
        symbol="ETH",
        max_age_hours=24,
        limit=5
    )
    print(news.format_news(eth_news))

if __name__ == "__main__":
    main() 