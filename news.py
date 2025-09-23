from newsapi import NewsApiClient
from dotenv import load_dotenv
import os
import pandas as pd
from datetime import datetime, timedelta

load_dotenv()
api_key = os.getenv("NEWS_API_KEY")
newsapi = NewsApiClient(api_key=api_key)

def fetch_crime_news(user_lat=None, user_lon=None, radius_km=10):
    from_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    to_date = datetime.now().strftime("%Y-%m-%d")

    query = "assault OR violence OR catcalling OR rape OR acid attack"

    sources_data = newsapi.get_sources(language='en', country='in')
    indian_sources = [s['id'] for s in sources_data['sources']]
    if not indian_sources:
        raise ValueError("No Indian English sources found on NewsAPI.")

    all_articles = []
    for page in range(1, 6):
        response = newsapi.get_everything(
            q=query,
            language='en',
            sources=",".join(indian_sources),
            from_param=from_date,
            to=to_date,
            sort_by='relevancy',
            page=page
        )
        all_articles.extend(response.get('articles', []))

    crime_keywords = [ 'murder', 'assault', 'violence', 'rape','catcalling','kill']

    filtered_articles = []
    for article in all_articles:
        title = article.get('title') or ""
        description = article.get('description') or ""
        combined_text = f"{title} {description}".lower()
        if any(keyword in combined_text for keyword in crime_keywords):
            filtered_articles.append({
                "title": article['title'],
                "description": article['description'],
                "publishedAt": article['publishedAt'],
                "source": article['source']['name'],
                "url": article['url'],
                "lat": user_lat, #get from frontend
                "lon": user_lon
            })

    df = pd.DataFrame(filtered_articles)
    df.to_csv("indian_crime_articles_dynamic.csv", index=False)
    print(f"Fetched {len(filtered_articles)} articles with user lat/lon.")
    return df

# Example usage
if __name__ == "__main__":
    # Frontend can send these dynamically
    user_lat, user_lon = 19.0760, 72.8777
    fetch_crime_news(user_lat, user_lon)


#getting all articles, make it geoaware
#get lat-lon post retrieval of articles