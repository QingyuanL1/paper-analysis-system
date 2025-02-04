from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
import numpy as np
import json
import logging
import pandas as pd
from collections import defaultdict

logger = logging.getLogger(__name__)

class PaperClusterer:
    def __init__(self, n_clusters=5):
        self.n_clusters = n_clusters
        self.vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words='english',
            ngram_range=(1, 2)
        )
        self.kmeans = KMeans(
            n_clusters=n_clusters,
            random_state=42
        )
        self.pca = PCA(n_components=2)
        
    def process_papers(self, papers_data):
        """处理论文数据并进行聚类
        
        Args:
            papers_data (list): 包含论文信息的列表
            
        Returns:
            dict: 包含聚类结果的字典
        """
        try:
            # 提取文本数据(标题 + 摘要)
            texts = []
            paper_ids = []
            titles = []
            
            for paper in papers_data:
                combined_text = f"{paper.get('title', '')} {paper.get('abstract', '')}"
                texts.append(combined_text)
                paper_ids.append(paper.get('paper_id'))
                titles.append(paper.get('title'))
            
            # 转换文本为TF-IDF特征
            logger.info(f"Converting {len(texts)} papers to TF-IDF features")
            features = self.vectorizer.fit_transform(texts)
            
            # 执行聚类
            logger.info("Performing clustering")
            cluster_labels = self.kmeans.fit_predict(features)
            
            # 降维用于可视化
            logger.info("Reducing dimensions for visualization")
            coords = self.pca.fit_transform(features.toarray())
            
            # 为每个簇收集论文
            clusters = defaultdict(list)
            for i, label in enumerate(cluster_labels):
                clusters[int(label)].append({
                    'paper_id': paper_ids[i],
                    'title': titles[i],
                    'x': float(coords[i][0]),
                    'y': float(coords[i][1])
                })
            
            # 获取每个簇的关键词
            logger.info("Extracting key terms for each cluster")
            cluster_terms = self._get_cluster_terms(features, cluster_labels)
            
            return {
                'clusters': dict(clusters),
                'cluster_terms': cluster_terms
            }
            
        except Exception as e:
            logger.error(f"Error in paper clustering: {str(e)}")
            return {
                'error': f'Error in paper clustering: {str(e)}'
            }
    
    def _get_cluster_terms(self, features, labels, top_n=5):
        """获取每个簇的主要关键词
        
        Args:
            features: TF-IDF特征矩阵
            labels: 聚类标签
            top_n: 每个簇返回的关键词数量
            
        Returns:
            dict: 每个簇的关键词列表
        """
        terms = self.vectorizer.get_feature_names_out()
        cluster_terms = {}
        
        for i in range(self.n_clusters):
            # 获取该簇的所有文档
            cluster_docs = features[labels == i]
            if cluster_docs.shape[0] == 0:
                continue
                
            # 计算该簇的平均TF-IDF值
            centroid = cluster_docs.mean(axis=0).A1
            # 获取最重要的词条
            top_term_indices = centroid.argsort()[-top_n:][::-1]
            cluster_terms[i] = [terms[idx] for idx in top_term_indices]
            
        return cluster_terms 