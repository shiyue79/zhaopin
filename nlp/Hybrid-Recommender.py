"""
混合推荐算法（Hybrid Recommender）
整合基于内容的推荐和基于物品的协同过滤推荐
支持动态权重调整和冷启动处理
"""

import os
import sys
import django

# 设置 Django 环境
sys.path.append(r'E:\project\python\djzhao')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'djzhao.settings')
django.setup()

import pandas as pd
import numpy as np
from collections import defaultdict
from scipy.sparse import csr_matrix
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from myApp.models import History, Joblist, User
import json
import jieba
import jieba.analyse
from pathlib import Path
import pdfplumber
import docx

class HybridRecommender:
    """混合推荐器：基于内容 + 基于物品的协同过滤"""

    def __init__(self,
                 alpha=0.5,           # 初始内容推荐权重（0-1之间）
                 top_k=20,            # 推荐数量
                 min_interactions=5,  # 最小互动量阈值
                 item_cf_weight=0.7,  # 互动充足时 CF 权重
                 content_weight=0.3,  # 互动充足时内容权重
                 cold_start_weight=0.8): # 冷启动时内容权重

        self.alpha = alpha
        self.top_k = top_k
        self.min_interactions = min_interactions
        self.item_cf_weight = item_cf_weight
        self.content_weight = content_weight
        self.cold_start_weight = cold_start_weight

        # 基于内容的推荐相关
        self.content_recommender = None
        self.job_features = None
        self.job_ids = None
        self.jobs_df = None
        self.tfidf_vectorizer = TfidfVectorizer(max_features=5000)

        # 基于物品的协同过滤相关
        self.user_item_matrix = None
        self.item_similarity = None
        self.user_id_to_idx = {}
        self.item_id_to_idx = {}
        self.idx_to_user_id = {}
        self.idx_to_item_id = {}

        # 数据
        self.histories_df = None
        self.users_df = None
        self.jobs_df_raw = None

    def extract_job_features(self, job):
        """从岗位数据中提取特征文本（用于内容推荐）"""
        features = []

        # 岗位名称（权重较高，重复4次）
        features.append(job.get('name', '') * 4)

        # 关键词列表（从 keyList 字段）
        key_list = job.get('keyList', '[]')
        try:
            if key_list and key_list != '[]':
                keywords = json.loads(key_list)
                if isinstance(keywords, dict):
                    features.append(' '.join(keywords.keys()) * 4)
                elif isinstance(keywords, list):
                    features.append(' '.join(keywords) * 4)
        except:
            pass

        # 经验要求
        features.append(job.get('exp', '') * 2)

        # 学历要求
        features.append(job.get('edu', '') * 2)

        # 公司规模
        features.append(job.get('comSize', '') * 2)

        # 薪资范围
        features.append(str(job.get('salaryMin', '')))
        features.append(str(job.get('salaryMax', '')))
        features.append(str(job.get('salaryBonus', '')))

        # 职位描述
        features.append(job.get('content', '') * 2)

        # 行业
        features.append(job.get('industry', '') * 2)

        # 城市
        features.append(job.get('city', '') * 2)

        # 过滤空值并拼接
        job_text = ' '.join([str(item) for item in features if item and item != 'None'])
        return job_text

    def extract_user_features(self, user):
        """从求职者数据中提取特征文本"""
        features = []

        # 意向岗位（权重较高）
        features.append(user.get('work', '') * 4)

        # 学历
        features.append(user.get('edu', '') * 2)

        # 工作经验
        features.append(user.get('exp', '') * 2)

        # 意向城市
        features.append(user.get('city', '') * 2)

        # 如果有简历文本，提取关键词
        resume_folder = "E:\project\python\djzhao\media"
        resume_filename = user.get('resume', '')
        resume_path = os.path.join(resume_folder, resume_filename)

        resume_text = ''
        if os.path.exists(resume_path):
            file_extension = Path(resume_path).suffix.lower()
            if file_extension in ['.docx', '.doc']:
                doc = docx.Document(resume_path)
                resume_text = '\n'.join([para.text for para in doc.paragraphs])
            elif file_extension == '.pdf':
                with pdfplumber.open(resume_path) as pdf:
                    resume_text = '\n'.join([page.extract_text() or '' for page in pdf.pages])

        try:
            if resume_text:
                # 使用 TextRank 提取关键词
                textrank_keywords = jieba.analyse.textrank(resume_text, topK=30, withWeight=False)
                features.append(' '.join(textrank_keywords) * 2)

                # 使用 TF-IDF 提取关键词
                tfidf_keywords = jieba.analyse.extract_tags(resume_text, topK=30, withWeight=False)
                features.append(' '.join(tfidf_keywords) * 2)

                # 提取英文技术术语
                import re
                english_pattern = r'\b[A-Z][a-z]+[A-Z][a-z]+\b|\b[A-Z]{2,}\b'
                english_matches = re.findall(english_pattern, resume_text)
                features.append(' '.join([m.lower() for m in english_matches]) * 2)
        except:
            pass

        user_text = ' '.join([str(item) for item in features if item and item != 'None'])
        return user_text

    def prepare_content_features(self, jobs_df):
        """准备基于内容的推荐特征"""
        print("\n 正在提取岗位内容特征...")

        job_texts = []
        self.job_ids = []

        for _, job in jobs_df.iterrows():
            job_text = self.extract_job_features(job.to_dict())
            job_texts.append(job_text)
            self.job_ids.append(job['id'])

        # 计算 TF-IDF 特征矩阵
        print("📊 正在计算 TF-IDF 特征矩阵...")
        self.job_features = self.tfidf_vectorizer.fit_transform(job_texts)
        self.jobs_df = jobs_df

        print(f"✅ 岗位内容特征提取完成，特征维度: {self.job_features.shape}")

        return True


    def build_user_item_matrix(self, histories_df):
        """构建用户-物品交互矩阵（用于协同过滤）"""
        print("\n 正在构建用户-物品交互矩阵...")

        users = histories_df['user_id'].unique()
        items = histories_df['job_id'].unique()

        self.user_id_to_idx = {uid: idx for idx, uid in enumerate(users)}
        self.item_id_to_idx = {iid: idx for idx, iid in enumerate(items)}
        self.idx_to_user_id = {idx: uid for uid, idx in self.user_id_to_idx.items()}
        self.idx_to_item_id = {idx: iid for iid, idx in self.item_id_to_idx.items()}

        print(f"✅ 用户数: {len(users)}")
        print(f"✅ 物品数: {len(items)}")

        # 构建稀疏矩阵
        rows = histories_df['user_id'].map(self.user_id_to_idx).values
        cols = histories_df['job_id'].map(self.item_id_to_idx).values
        values = histories_df['count'].values

        self.user_item_matrix = csr_matrix(
            (values, (rows, cols)),
            shape=(len(users), len(items))
        )

        print(f"✅ 矩阵形状: {self.user_item_matrix.shape}")
        print(f"✅ 非零元素: {self.user_item_matrix.nnz}")
        print(f"✅ 稀疏度: {(1 - self.user_item_matrix.nnz / (len(users) * len(items))) * 100:.4f}%")

    def compute_item_similarity(self):
        """计算物品相似度矩阵"""
        print("\n🔍 正在计算物品相似度...")

        # 转置矩阵，按物品计算相似度
        item_matrix = self.user_item_matrix.T.toarray()

        # 计算余弦相似度
        self.item_similarity = cosine_similarity(item_matrix)

        # 排除自身相似度
        np.fill_diagonal(self.item_similarity, 0)

        print(f"✅ 物品相似度矩阵形状: {self.item_similarity.shape}")
        print(f"✅ 平均相似度: {np.mean(self.item_similarity):.4f}")

    def train(self, jobs_df, histories_df, users_df):
        """训练混合推荐模型"""
        print("="*60)
        print("🚀 混合推荐算法训练")
        print("="*60)

        self.histories_df = histories_df
        self.users_df = users_df
        self.jobs_df_raw = jobs_df

        # 1. 准备内容特征
        if not self.prepare_content_features(jobs_df):
            print("❌ 内容特征提取失败")
            return False

        # 2. 构建用户-物品矩阵
        self.build_user_item_matrix(histories_df)

        # 3. 计算物品相似度
        self.compute_item_similarity()

        # 4. 处理异常值
        self.item_similarity = np.nan_to_num(
            self.item_similarity, nan=0.0, posinf=0.0, neginf=0.0
        )

        print(f"\n✅ 混合推荐模型训练完成！")
        return True

    def get_user_interaction_count(self, user_id):
        """获取用户的互动次数"""
        if user_id not in self.user_id_to_idx:
            return 0
        user_idx = self.user_id_to_idx[user_id]
        user_interactions = self.user_item_matrix[user_idx].toarray().flatten()
        return np.sum(user_interactions > 0)

    def calculate_dynamic_weights(self, user_id):
        """根据用户互动量动态计算权重"""
        interaction_count = self.get_user_interaction_count(user_id)

        if interaction_count < self.min_interactions:
            # 冷启动：内容推荐权重高
            content_w = self.cold_start_weight
            cf_w = 1 - content_w
            print(f"   冷启动用户（互动 {interaction_count} 次），内容权重: {content_w:.2f}, CF权重: {cf_w:.2f}")
        else:
            # 互动充足：使用配置的权重
            content_w = self.content_weight
            cf_w = self.item_cf_weight
            print(f"   活跃用户（互动 {interaction_count} 次），内容权重: {content_w:.2f}, CF权重: {cf_w:.2f}")

        return content_w, cf_w

    def content_based_recommend(self, user_dict, top_n=None):
        """基于内容的推荐"""
        if top_n is None:
            top_n = self.top_k

        if self.job_features is None:
            return []

        # 提取用户特征向量
        user_text = self.extract_user_features(user_dict)
        user_vector = self.tfidf_vectorizer.transform([user_text])

        # 应用相同的 SVD 降维
        if hasattr(self, 'svd_model'):
            user_vector = self.svd_model.transform(user_vector)

        # 计算余弦相似度
        similarities = cosine_similarity(user_vector, self.job_features).flatten()

        # 获取 Top-N 推荐
        top_indices = np.argsort(similarities)[::-1][:top_n]

        recommendations = []
        for idx in top_indices:
            job_id = self.job_ids[idx]
            job = self.jobs_df[self.jobs_df['id'] == job_id]
            if not job.empty:
                recommendations.append({
                    'job_id': int(job_id),
                    'job_name': job.iloc[0]['name'],
                    'score': float(similarities[idx]),
                    'city': job.iloc[0].get('city', ''),
                    'salary': f"{job.iloc[0].get('salaryMin', 0)}-{job.iloc[0].get('salaryMax', 0)}k"
                })

        return recommendations

    def item_cf_recommend(self, user_id, top_n=None):
        """基于物品的协同过滤推荐"""
        if top_n is None:
            top_n = self.top_k

        if user_id not in self.user_id_to_idx:
            return []

        user_idx = self.user_id_to_idx[user_id]
        user_items = self.user_item_matrix[user_idx].toarray().flatten()

        # 获取用户已交互的物品
        interacted_items = np.where(user_items > 0)[0]

        if len(interacted_items) == 0:
            return []

        # 计算推荐分数
        recommendation_scores = np.zeros(self.user_item_matrix.shape[1])

        for item_idx in interacted_items:
            # 获取与该物品相似的物品
            similar_items = self.item_similarity[item_idx]

            # 加权求和
            recommendation_scores += similar_items * user_items[item_idx]

        # 排除已交互的物品
        recommendation_scores[interacted_items] = 0

        # 获取 Top-N 推荐
        top_items = np.argsort(recommendation_scores)[::-1][:top_n]

        recommendations = []
        for item_idx in top_items:
            if recommendation_scores[item_idx] > 0:
                job_id = self.idx_to_item_id[item_idx]
                job = self.jobs_df_raw[self.jobs_df_raw['id'] == job_id]
                if not job.empty:
                    recommendations.append({
                        'job_id': int(job_id),
                        'job_name': job.iloc[0]['name'],
                        'score': float(recommendation_scores[item_idx]),
                        'city': job.iloc[0].get('city', ''),
                        'salary': f"{job.iloc[0].get('salaryMin', 0)}-{job.iloc[0].get('salaryMax', 0)}k"
                    })

        return recommendations

    def hybrid_recommend(self, user_id, user_dict, top_n=None):
        """混合推荐：动态调整内容和 CF 的权重"""
        if top_n is None:
            top_n = self.top_k

        # 1. 计算动态权重
        content_w, cf_w = self.calculate_dynamic_weights(user_id)

        # 2. 获取基于内容的推荐
        content_recs = self.content_based_recommend(user_dict, top_n=top_n * 2)
        content_rec_dict = {rec['job_id']: rec['score'] for rec in content_recs}

        # 3. 获取基于物品的协同过滤推荐
        cf_recs = self.item_cf_recommend(user_id, top_n=top_n * 2)
        cf_rec_dict = {rec['job_id']: rec['score'] for rec in cf_recs}

        # 4. 合并推荐结果
        all_job_ids = set(list(content_rec_dict.keys()) + list(cf_rec_dict.keys()))

        hybrid_scores = {}
        for job_id in all_job_ids:
            content_score = content_rec_dict.get(job_id, 0.0)
            cf_score = cf_rec_dict.get(job_id, 0.0)

            # 混合评分
            hybrid_score = content_w * content_score + cf_w * cf_score
            hybrid_scores[job_id] = hybrid_score

        # 5. 排序并获取 Top-N
        sorted_jobs = sorted(hybrid_scores.items(), key=lambda x: x[1], reverse=True)

        recommendations = []
        for job_id, score in sorted_jobs[:top_n]:
            job = self.jobs_df_raw[self.jobs_df_raw['id'] == job_id]
            if not job.empty:
                recommendations.append({
                    'job_id': int(job_id),
                    'job_name': job.iloc[0]['name'],
                    'score': float(score),
                    'city': job.iloc[0].get('city', ''),
                    'salary': f"{job.iloc[0].get('salaryMin', 0)}-{job.iloc[0].get('salaryMax', 0)}k",
                    'content_score': content_rec_dict.get(job_id, 0.0),
                    'cf_score': cf_rec_dict.get(job_id, 0.0)
                })

        return recommendations

    def recommend_with_details(self, user_id, user_dict, top_n=None):
        """为用户推荐并显示详细信息"""
        if top_n is None:
            top_n = self.top_k

        # 获取用户信息
        user_info = {
            'id': user_id,
            'username': user_dict.get('username', 'Unknown'),
            'work': user_dict.get('work', 'N/A')
        }

        # 获取推荐
        recommendations = self.hybrid_recommend(user_id, user_dict, top_n=top_n)

        # 打印详细信息
        print("\n" + "="*60)
        print(f"🎯 为用户 {user_id} 推荐岗位（混合算法）")
        print("="*60)
        print(f"👤 用户信息:")
        print(f"   用户ID: {user_id}")
        print(f"   用户名: {user_info['username']}")
        print(f"   期望职位: {user_info['work']}")
        print(f"   互动次数: {self.get_user_interaction_count(user_id)}")
        print(f"\n📋 推荐岗位列表 (Top-{top_n}):")
        print("="*120)
        print(f"{'排名':<6} {'岗位ID':<10} {'岗位名称':<30} {'城市':<15} {'薪资':<15} {'混合分数':<12} {'内容分数':<12} {'CF分数':<12}")
        print("="*120)

        for i, rec in enumerate(recommendations, 1):
            print(f"{i:<6} {rec['job_id']:<10} {rec['job_name']:<30} {rec['city']:<15} {rec['salary']:<15} {rec['score']:.4f}{'':<6} {rec['content_score']:.4f}{'':<6} {rec['cf_score']:.4f}")

        print("="*120)
        print(f"\n📊 统计信息:")
        print(f"   总岗位数: {len(self.jobs_df_raw)}")
        print(f"   用户互动数: {self.get_user_interaction_count(user_id)}")
        print("="*60)

        return recommendations

    def evaluate(self, test_df, users_df, jobs_df, top_n=None):
        """评估混合推荐系统"""
        if top_n is None:
            top_n = self.top_k

        print(f"\n🎯 开始评估混合推荐系统 (Top-{top_n})...")

        precisions = []
        recalls = []
        f1_scores = []
        hit_rates = []

        # 统计每个用户的测试集岗位
        user_test_jobs = defaultdict(set)
        for _, row in test_df.iterrows():
            user_test_jobs[row['user_id']].add(row['job_id'])

        total_users = len(user_test_jobs)
        evaluated_users = 0

        for user_id, test_jobs in user_test_jobs.items():
            # 获取用户信息
            user_data = users_df[users_df['id'] == user_id]
            if user_data.empty:
                continue

            user_dict = user_data.iloc[0].to_dict()

            # 生成推荐列表
            recommendations = self.hybrid_recommend(user_id, user_dict, top_n=top_n)
            recommended_job_ids = set([rec['job_id'] for rec in recommendations])

            if not recommended_job_ids:
                continue

            evaluated_users += 1

            # 计算指标
            hits = len(test_jobs & recommended_job_ids)

            precision = hits / len(recommended_job_ids) if recommended_job_ids else 0
            recall = hits / len(test_jobs) if test_jobs else 0
            f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0
            hit_rate = 1 if hits > 0 else 0

            precisions.append(precision)
            recalls.append(recall)
            f1_scores.append(f1)
            hit_rates.append(hit_rate)

        # 计算平均指标
        avg_precision = np.mean(precisions) if precisions else 0
        avg_recall = np.mean(recalls) if recalls else 0
        avg_f1 = np.mean(f1_scores) if f1_scores else 0
        avg_hit_rate = np.mean(hit_rates) if hit_rates else 0

        print(f"\n📊 评估结果:")
        print(f"   评估用户数: {evaluated_users}/{total_users}")
        print(f"   平均准确率 (Precision@{top_n}): {avg_precision:.4f} ({avg_precision*100:.2f}%)")
        print(f"   平均召回率 (Recall@{top_n}): {avg_recall:.4f} ({avg_recall*100:.2f}%)")
        print(f"   平均 F1 Score: {avg_f1:.4f}")
        print(f"   命中率 (Hit Rate@{top_n}): {avg_hit_rate:.4f} ({avg_hit_rate*100:.2f}%)")

        return {
            'precision': avg_precision,
            'recall': avg_recall,
            'f1': avg_f1,
            'hit_rate': avg_hit_rate,
            'evaluated_users': evaluated_users,
            'total_users': total_users
        }


def load_data():
    """加载数据"""
    print("="*60)
    print("📊 加载数据")
    print("="*60)

    # 加载岗位数据
    print("\n 正在加载岗位数据...")
    jobs_df = pd.DataFrame(list(Joblist.objects.filter(delete=0).values()))
    print(f"✅ 加载了 {len(jobs_df)} 个岗位")

    # 加载用户数据
    print("\n 正在加载用户数据...")
    users_df = pd.DataFrame(list(User.objects.values()))
    print(f"✅ 加载了 {len(users_df)} 个用户")

    # 加载浏览历史
    print("\n📥 正在加载浏览历史...")
    history_df = pd.DataFrame(list(History.objects.values()))
    print(f"✅ 加载了 {len(history_df)} 条浏览记录")

    return jobs_df, users_df, history_df


def run_hybrid_recommendation():
    """运行混合推荐系统"""
    # 1. 加载数据
    jobs_df, users_df, history_df = load_data()

    if history_df.empty:
        print("❌ 没有浏览历史数据，无法进行评估")
        return

    # 2. 划分训练集和测试集
    print("\n 正在划分训练集/测试集 (测试集比例: 0.2)...")
    train_data = []
    test_data = []

    for user_id, user_histories in history_df.groupby('user_id'):
        if len(user_histories) < 2:
            train_data.extend(user_histories.to_dict('records'))
            continue

        if 'time' in user_histories.columns:
            user_histories = user_histories.sort_values('time')

        train_subset, test_subset = train_test_split(
            user_histories,
            test_size=0.2,
            random_state=42,
            shuffle=False
        )

        train_data.extend(train_subset.to_dict('records'))
        test_data.extend(test_subset.to_dict('records'))

    train_df = pd.DataFrame(train_data)
    test_df = pd.DataFrame(test_data)

    print(f"✅ 划分完成:")
    print(f"   训练集: {len(train_df)} 条记录")
    print(f"   测试集: {len(test_df)} 条记录")

    # 3. 初始化混合推荐器
    print("\n🔧 正在初始化混合推荐器...")
    hybrid_recommender = HybridRecommender(
        alpha=0.5,                # 初始内容推荐权重
        top_k=20,                 # 推荐数量
        min_interactions=5,       # 最小互动量阈值
        item_cf_weight=0.7,       # 互动充足时 CF 权重
        content_weight=0.3,       # 互动充足时内容权重
        cold_start_weight=0.8     # 冷启动时内容权重
    )

    # 4. 训练模型
    if not hybrid_recommender.train(jobs_df, train_df, users_df):
        print("❌ 模型训练失败")
        return

    # 5. 示例推荐
    print("\n🎯 示例推荐:")
    if len(users_df) > 0:
        sample_user = users_df.iloc[0].to_dict()
        recommendations = hybrid_recommender.recommend_with_details(
            sample_user['id'],
            sample_user,
            top_n=10
        )

    # 6. 评估系统
    results = hybrid_recommender.evaluate(test_df, users_df, jobs_df, top_n=20)

    print("\n" + "="*60)
    print("✅ 混合推荐系统评估完成")
    print("="*60)

    return results


if __name__ == '__main__':
    results = run_hybrid_recommendation()
