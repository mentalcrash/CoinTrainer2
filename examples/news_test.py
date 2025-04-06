from src.news import News

def main():
    news = News()
    
    # BTC 뉴스 수집
    btc_news = news.get_news(
        symbol="BTC",
        max_age_hours=5,
        limit=10,
        use_cache=False
    )
    print(news.format_news(btc_news))

if __name__ == "__main__":
    main() 