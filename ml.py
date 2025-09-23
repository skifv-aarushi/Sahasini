import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer, util
from sklearn.cluster import DBSCAN
from datetime import datetime
from sqlalchemy.orm import Session
from database import SessionLocal, Base, engine
from models import Incident

df = pd.read_csv("indian_crime_articles_dynamic.csv") #will switch to passing of data frame in final product, need csv for testing

# Ensure lat/lon columns exist
if 'lat' not in df.columns or 'lon' not in df.columns:
    df['lat'] = np.nan
    df['lon'] = np.nan

# --- Step 1: Semantic embeddings ---
model = SentenceTransformer('all-MiniLM-L6-v2')
texts = (df['title'].fillna('') + '. ' + df['description'].fillna('')).tolist()
embeddings = model.encode(texts, convert_to_tensor=True)

similarity_matrix = util.cos_sim(embeddings, embeddings).cpu().numpy()

merge_suggestions = []
conflict_flags = []

for i in range(len(df)):
    for j in range(i+1, len(df)):
        sim = similarity_matrix[i, j]
        if sim > 0.8:
            merge_suggestions.append((i, j, sim))
        elif 0.5 <= sim <= 0.7:
            text_i = (df.loc[i, 'title'] + ' ' + df.loc[i, 'description']).lower()
            text_j = (df.loc[j, 'title'] + ' ' + df.loc[j, 'description']).lower()
            if ('safe' in text_i and 'unsafe' in text_j) or ('unsafe' in text_i and 'safe' in text_j):
                conflict_flags.append((i, j, sim))

# --- Step 2: Semantic clustering ---
semantic_clustering = DBSCAN(eps=0.5, min_samples=2, metric='cosine')
df['semantic_cluster'] = semantic_clustering.fit_predict(embeddings.cpu().numpy())

# --- Step 3: Geo clustering ---
if not df['lat'].isnull().all():
    coords = df[['lat', 'lon']].to_numpy()
    geo_clustering = DBSCAN(eps=0.01, min_samples=2)  # ~1 km
    df['geo_cluster'] = geo_clustering.fit_predict(coords)
else:
    df['geo_cluster'] = -1

# --- Step 4: Recency ---
df['publishedAt'] = pd.to_datetime(df['publishedAt']).dt.tz_localize(None)
now = datetime.now()
df['days_ago'] = (now - df['publishedAt']).dt.days
df['recency_score'] = 1 - df['days_ago']/30  # recent articles get higher score

# --- Step 5: Dynamic severity ---
severity_dict = {
    'murder': 5,
    'assault': 3,
    'violence': 2,
    'rape': 5,
    'catcalling': 1,
    'acid attack': 4,
    'dowry': 3
}

def get_severity(text):
    text = text.lower()
    for keyword, score in severity_dict.items():
        if keyword in text:
            return score
    return 1  # default if no keyword matches

df['severity'] = (df['title'].fillna('') + ' ' + df['description'].fillna('')).apply(get_severity)

# --- Step 6: Risk scoring ---
risk_scores = {}
for cluster_id, cluster_df in df.groupby('geo_cluster'):
    frequency = len(cluster_df)
    avg_severity = cluster_df['severity'].mean()
    avg_recency = cluster_df['recency_score'].mean()
    risk = 0.6*frequency + 0.3*avg_severity + 0.1*avg_recency
    risk_norm = min(risk/10, 1)
    if risk_norm < 0.3:
        risk_level = 'Low'
    elif risk_norm < 0.7:
        risk_level = 'Medium'
    else:
        risk_level = 'High'
    risk_scores[cluster_id] = {'risk_score': risk_norm, 'risk_level': risk_level}

df['risk_score'] = df['geo_cluster'].apply(lambda x: risk_scores[x]['risk_score'])
df['risk_level'] = df['geo_cluster'].apply(lambda x: risk_scores[x]['risk_level'])

db: Session = SessionLocal()
try:
    for _, row in df.iterrows():
        incident = Incident(
            title=row['title'],
            description=row['description'],
            latitude=row['lat'],
            longitude=row['lon'],
            incident_type='crime',  # default, or parse from text
            timestamp=row['publishedAt'].isoformat(),
            parent_id=None,
            merged_into=None,
            semantic_cluster=int(row['semantic_cluster']),
            geo_cluster=int(row['geo_cluster']),
            risk_score=float(row['risk_score']),
            risk_level=row['risk_level']
        )
        db.add(incident)
    db.commit()
finally:
    db.close()

print("ML pipeline completed.")
print(f"Merge suggestions: {merge_suggestions[:5]}")
print(f"Conflict flags: {conflict_flags[:5]}")
print(df.head())


#Fetch location dynamically from article text → geo-aware risk.

#Use approximate nearest neighbors for semantic similarity to reduce runtime. O(n^2) fix

#Store embeddings once in a local cache / database so you don’t recompute every run.

#Expand severity_dict or use NLP-based severity scoring for more nuanced assessment.