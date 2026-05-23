"""
基于物品的协同过滤推荐系统（Item-Based CF）
参照示例代码的流程实现
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
from myApp.models import History, Joblist, User

class ItemBasedCFRecommender:
    """基于物品的协同过滤推荐器"""

    def __init__(self, top_k=20):
        self.top_k = top_k
        self.user_item_matrix = None
        self.item_similarity = None
        self.user_id_to_idx = {}
        self.item_id_to_idx = {}
        self.idx_to_user_id = {}
        self.idx_to_item_id = {}

    def create(self, data, user_col='user_id', item_col='job_id', rating_col='count'):
        """
        创建用户-物品矩阵
        对应示例: is_model.create(train_data, 'user', 'title')
        """
        print("="*60)
        print(" 正在构建用户-物品矩阵...")
        print("="*60)

        # 构建映射
        users = data[user_col].unique()
        items = data[item_col].unique()

        self.user_id_to_idx = {uid: idx for idx, uid in enumerate(users)}
        self.item_id_to_idx = {iid: idx for idx, iid in enumerate(items)}
        self.idx_to_user_id = {idx: uid for uid, idx in self.user_id_to_idx.items()}
        self.idx_to_item_id = {idx: iid for iid, idx in self.item_id_to_idx.items()}

        print(f"✅ 用户数: {len(users)}")
        print(f"✅ 物品数: {len(items)}")

        # 构建稀疏矩阵
        rows = data[user_col].map(self.user_id_to_idx).values
        cols = data[item_col].map(self.item_id_to_idx).values
        values = data[rating_col].values

        self.user_item_matrix = csr_matrix(
            (values, (rows, cols)),
            shape=(len(users), len(items))
        )

        print(f"✅ 矩阵形状: {self.user_item_matrix.shape}")
        print(f"✅ 非零元素: {self.user_item_matrix.nnz}")
        print(f"✅ 稀疏度: {(1 - self.user_item_matrix.nnz / (len(users) * len(items))) * 100:.4f}%")

        # 计算物品相似度
        self._compute_item_similarity()

    def _compute_item_similarity(self):
        """计算物品之间的相似度"""
        print("\n 正在计算物品相似度...")

        # 转置矩阵，按物品计算相似度
        item_matrix = self.user_item_matrix.T.toarray()

        # 计算余弦相似度
        self.item_similarity = cosine_similarity(item_matrix)

        # 排除自身相似度
        np.fill_diagonal(self.item_similarity, 0)

        print(f"✅ 物品相似度矩阵形状: {self.item_similarity.shape}")
        print(f"✅ 平均相似度: {np.mean(self.item_similarity):.4f}")

    def recommend(self, user_id, n_recommendations=10):
        """
        为用户推荐物品
        对应示例: is_model.recommend(user_id)
        """
        if user_id not in self.user_id_to_idx:
            print(f" 用户 {user_id} 不存在")
            return pd.DataFrame()

        user_idx = self.user_id_to_idx[user_id]
        user_items = self.user_item_matrix[user_idx].toarray().flatten()

        # 获取用户已交互的物品
        interacted_items = np.where(user_items > 0)[0]

        if len(interacted_items) == 0:
            print(f" 用户 {user_id} 没有任何交互记录")
            return pd.DataFrame()

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
        top_items = np.argsort(recommendation_scores)[::-1][:n_recommendations]

        # 构建推荐结果
        recommendations = []
        rank = 1
        for item_idx in top_items:
            if recommendation_scores[item_idx] > 0:
                recommendations.append({
                    'user_id': user_id,
                    'job_id': self.idx_to_item_id[item_idx],
                    'score': recommendation_scores[item_idx],
                    'rank': rank
                })
                rank += 1

        result_df = pd.DataFrame(recommendations)

        # 打印统计信息（对应示例输出）
        # print(f"\n 为用户 {user_id} 推荐:")
        # print(f"No. of unique jobs for the user: {len(interacted_items)}")
        # print(f"No. of unique jobs in the training set: {self.user_item_matrix.shape[1]}")
        # print(f"Non zero values in cooccurrence_matrix: {self.user_item_matrix.nnz}")
        # print(f"\n推荐结果:")
        # print(result_df.to_string(index=False))

        return result_df

    def get_user_items(self, user_id):
        """
        获取用户的交互物品
        对应示例: user_items = is_model.get_user_items(user_id)
        """
        if user_id not in self.user_id_to_idx:
            return []

        user_idx = self.user_id_to_idx[user_id]
        user_items = self.user_item_matrix[user_idx].toarray().flatten()

        interacted_items = np.where(user_items > 0)[0]
        item_ids = [self.idx_to_item_id[idx] for idx in interacted_items]

        return item_ids

def load_and_prepare_data():
    """加载和准备数据"""
    print("="*60)
    print("📊 数据加载与预处理")
    print("="*60)
    
    # 从数据库加载数据
    histories = list(History.objects.values('user_id', 'job_id', 'count'))
    
    # 转换为 DataFrame
    df = pd.DataFrame(histories)
    
    print(f"✅ 原始记录数: {len(df)}")
    print(f"✅ 用户数: {df['user_id'].nunique()}")
    print(f"✅ 岗位数: {df['job_id'].nunique()}")
    
    # 选择一小部分活跃用户和热门岗位
    print("\n🔍 正在筛选活跃用户和热门岗位...")
    
    # 统计用户查看量
    user_counts = df.groupby('user_id')['count'].sum().sort_values(ascending=False)
    user_subset = user_counts.head(5000)  # 前 5000 个用户
    
    # 统计岗位查看量
    job_counts = df.groupby('job_id')['count'].sum().sort_values(ascending=False)
    job_subset = job_counts.head(5000)  # 前 5000 个岗位
    
    # 筛选数据
    df_filtered = df[
        df['user_id'].isin(user_subset.index) & 
        df['job_id'].isin(job_subset.index)
    ]
    
    print(f"✅ 筛选后记录数: {len(df_filtered)}")
    print(f"✅ 筛选后用户数: {df_filtered['user_id'].nunique()}")
    print(f"✅ 筛选后岗位数: {df_filtered['job_id'].nunique()}")
    
    return df_filtered

def train_test_split_data(df, test_size=0.3):
    """
    划分训练集和测试集
    对应示例: train_data, test_data = train_test_split(..., test_size=0.30)
    """
    print("\n" + "="*60)
    print("📈 划分训练集和测试集")
    print("="*60)
    
    # 随机划分
    train_data, test_data = train_test_split(
        df, 
        test_size=test_size, 
        random_state=0  # 固定随机种子
    )
    
    print(f"✅ 训练集: {len(train_data)} 条记录 ({len(train_data)/len(df)*100:.1f}%)")
    print(f"✅ 测试集: {len(test_data)} 条记录 ({len(test_data)/len(df)*100:.1f}%)")
    
    return train_data, test_data

def get_job_info(job_id):
    """获取岗位详细信息"""
    try:
        job = Joblist.objects.get(id=job_id)
        return {
            'id': job.id,
            'name': job.name,
            'work': job.work if hasattr(job, 'work') else 'N/A'
        }
    except Joblist.DoesNotExist:
        return {
            'id': job_id,
            'name': 'Unknown',
            'work': 'N/A'
        }

def get_user_info(user_id):
    """获取用户详细信息"""
    try:
        user = User.objects.get(id=user_id)
        return {
            'id': user.id,
            'username': user.username if user.username else 'N/A',
            'work': user.work if hasattr(user, 'work') else 'N/A'
        }
    except User.DoesNotExist:
        return {
            'id': user_id,
            'username': 'Unknown',
            'work': 'N/A'
        }

def recommend_with_details(model, user_id, n_recommendations=10):
    """为用户推荐并显示详细信息"""
    if user_id not in model.user_id_to_idx:
        print(f" 用户 {user_id} 不存在")
        return pd.DataFrame()
    
    user_idx = model.user_id_to_idx[user_id]
    user_items = model.user_item_matrix[user_idx].toarray().flatten()
    
    # 获取用户已交互的物品
    interacted_items = np.where(user_items > 0)[0]
    
    if len(interacted_items) == 0:
        print(f"❌ 用户 {user_id} 没有任何交互记录")
        return pd.DataFrame()
    
    # 计算推荐分数
    recommendation_scores = np.zeros(model.user_item_matrix.shape[1])
    
    for item_idx in interacted_items:
        # 获取与该物品相似的物品
        similar_items = model.item_similarity[item_idx]
        
        # 加权求和
        recommendation_scores += similar_items * user_items[item_idx]
    
    # 排除已交互的物品
    recommendation_scores[interacted_items] = 0
    
    # 获取 Top-N 推荐
    top_items = np.argsort(recommendation_scores)[::-1][:n_recommendations]
    
    # 获取用户信息
    user_info = get_user_info(user_id)
    
    # 构建推荐结果
    recommendations = []
    rank = 1
    for item_idx in top_items:
        if recommendation_scores[item_idx] > 0:
            job_info = get_job_info(model.idx_to_item_id[item_idx])
            recommendations.append({
                'rank': rank,
                'user_id': user_id,
                'username': user_info['username'],
                'user_work': user_info['work'],
                'job_id': model.idx_to_item_id[item_idx],
                'job_name': job_info['name'],
                'job_work': job_info['work'],
                'score': recommendation_scores[item_idx]
            })
            rank += 1
    
    result_df = pd.DataFrame(recommendations)
    
    # 打印详细信息
    print("\n" + "="*60)
    print(f" 为用户 {user_id} 推荐岗位")
    print("="*60)
    print(f"👤 用户信息:")
    print(f"   用户ID: {user_id}")
    print(f"   用户名: {user_info['username']}")
    print(f"   期望职位: {user_info['work']}")
    print(f"   已浏览岗位数: {len(interacted_items)}")
    print("\n📋 推荐岗位列表 (Top-10):")
    print("="*100)
    print(f"{'排名':<6} {'岗位ID':<10} {'岗位名称':<40} {'岗位类型':<20} {'推荐分数':<12}")
    print("="*100)
    
    for rec in recommendations:
        print(f"{rec['rank']:<6} {rec['job_id']:<10} {rec['job_name']:<40} {rec['job_work']:<20} {rec['score']:.4f}")
    
    print("="*100)
    print(f"\n📊 统计信息:")
    print(f"   训练集岗位总数: {model.user_item_matrix.shape[1]}")
    print(f"   共现矩阵非零元素: {model.user_item_matrix.nnz}")
    print("="*60)
    
    return result_df

def evaluate_recommendations(model, test_data, user_col='user_id', item_col='job_id', top_n=10):
    """评估推荐结果"""
    print("\n" + "="*60)
    print(" 评估推荐结果")
    print("="*60)

    precisions = []
    recalls = []
    ndcgs = []

    # 获取测试集中的用户
    test_users = test_data[user_col].unique()

    for user_id in test_users[:100]:  # 评估前 100 个用户
        # 获取推荐
        recommendations = model.recommend(user_id, n_recommendations=top_n)

        if recommendations.empty:
            continue

        # 获取测试集中的真实交互
        true_items = test_data[test_data[user_col] == user_id][item_col].tolist()

        if not true_items:
            continue

        # 获取推荐的物品
        recommended_items = recommendations['job_id'].tolist()

        # 计算命中率
        hits = len(set(recommended_items) & set(true_items))

        if hits > 0:
            precisions.append(hits / len(recommended_items))
            recalls.append(hits / len(true_items))

            # 计算 NDCG
            dcg = sum([1 / np.log2(i + 2) for i in range(len(recommended_items))
                      if recommended_items[i] in true_items])
            idcg = sum([1 / np.log2(i + 2) for i in range(min(len(true_items), top_n))])
            ndcgs.append(dcg / idcg if idcg > 0 else 0)

    if precisions:
        print(f"\n 评估结果:")
        print(f"   平均 Precision@{top_n}: {np.mean(precisions):.4f}")
        print(f"   平均 Recall@{top_n}: {np.mean(recalls):.4f}")
        print(f"   平均 NDCG@{top_n}: {np.mean(ndcgs):.4f}")
        print(f"   评估用户数: {len(precisions)}/{len(test_users)}")

# 完整流程
if __name__ == '__main__':
    # 1. 加载数据
    df = load_and_prepare_data()
    
    # 2. 划分训练集和测试集
    train_data, test_data = train_test_split_data(df, test_size=0.3)
    
    # 3. 创建推荐模型
    is_model = ItemBasedCFRecommender(top_k=20)
    
    # 4. 训练模型（构建矩阵）
    is_model.create(train_data, user_col='user_id', item_col='job_id', rating_col='count')
    
    # 5. 为单个用户推荐（带详细信息）
    user_id = list(train_data['user_id'])[7]  # 取第 7 个用户
    recommendations = recommend_with_details(is_model, user_id, n_recommendations=10)
    
    # 6. 获取用户的交互物品
    user_items = is_model.get_user_items(user_id)
    print(f"\n 用户 {user_id} 的交互物品数: {len(user_items)}")
    
    # 7. 评估推荐效果
    evaluate_recommendations(is_model, test_data, top_n=10)
