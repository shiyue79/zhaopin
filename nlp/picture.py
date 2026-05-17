from wordcloud import WordCloud
import matplotlib.pyplot as plt
import numpy as np
from sqlalchemy import create_engine, text
from sklearn.feature_extraction.text import TfidfVectorizer


def get_img(field, res):
    engine = create_engine(
        'mysql+pymysql://root:123456@localhost:3306/zhaopin',
        echo=False,
        pool_pre_ping=True
    )
    with engine.connect() as conn:
        sql = f"select {field} from job"
        result = conn.execute(text(sql))
        data = result.fetchall()
        content = []
        for row in data:
            if row[0] is not None:
                content.append(row[0])
    engine.dispose()
    tfidf_vectorizer = TfidfVectorizer(max_features=200, token_pattern=r'(?u)\b\w{1,6}\b')
    tfidf_vectorizer.fit(content)
    feature_names = tfidf_vectorizer.get_feature_names_out()
    tfidf_matrix = tfidf_vectorizer.transform(content)
    word_scores = np.asarray(tfidf_matrix.mean(axis=0)).ravel()
    top_indices = np.argsort(word_scores)[::-1]
    top_words = [(feature_names[i], word_scores[i]) for i in top_indices]
    stopwords = set()
    with open('./stopwords.txt', 'r', encoding='utf-8') as f:
        for line in f:
            if len(line.strip()) > 0:
                stopwords.add(line.strip())
    data_result = [word for word, score in top_words if word not in stopwords and len(word) <= 4]
    string = ' '.join(data_result)
    wc = WordCloud(background_color='white', font_path='simhei.ttf', max_words=100, random_state=42,collocations=False,colormap='viridis')
    wc.generate(string)
    fig = plt.figure(figsize=(16, 8))
    plt.imshow(wc)
    plt.axis('off')
    fig.tight_layout(pad=0)
    fig.savefig(res, dpi=800)

get_img('keyList', 'E:\project\python\djzhao\static\key_cloud.png')
