import urllib.request
import urllib.parse
import feedparser
import time
import logging
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class ArxivClient:
    """arXiv API客户端类"""
    
    BASE_URL = 'http://export.arxiv.org/api/query?'
    
    def __init__(self):
        self.last_request_time = 0
        
    def _enforce_rate_limit(self):
        """强制执行API速率限制（每秒最多3个请求）"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        if time_since_last_request < 0.34:  # 稍微低于1/3秒以确保安全
            time.sleep(0.34 - time_since_last_request)
        self.last_request_time = time.time()
        
    def search_papers(self, query, start=0, max_results=10, search_type='keyword'):
        """搜索arXiv论文
        
        Args:
            query (str): 搜索查询
            start (int): 结果的起始索引
            max_results (int): 返回的最大结果数
            search_type (str): 搜索类型 ('keyword', 'author', 'title')
            
        Returns:
            dict: 包含论文数据和总结果数的字典
        """
        try:
            self._enforce_rate_limit()
            
            # 根据 search_type 构建查询字符串
            if search_type == 'author':
                # 对作者名进行精确查询，包含引号
                formatted_query = f'au:"{query}"'
                is_author_search = True
            elif search_type == 'title':
                # 对标题进行精确查询，包含引号
                formatted_query = f'ti:"{query}"'
                is_author_search = False
            else: # default to keyword search
                formatted_query = f'all:{query}'
                is_author_search = False
            
            logger.info(f"Constructed arXiv query: {formatted_query}")
            
            params = {
                'search_query': formatted_query,
                'start': start,
                'max_results': max_results,
                'sortBy': 'submittedDate',
                'sortOrder': 'descending'
            }
            
            # URL编码查询参数，特别是包含特殊字符的查询
            encoded_params = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
            url = self.BASE_URL + encoded_params
            logger.info(f"Querying arXiv API: {url}")
            
            response = urllib.request.urlopen(url)
            feed = feedparser.parse(response.read())
            
            papers = []
            for entry in feed.entries:
                # 提取更详细的作者信息
                authors = [author.name for author in entry.authors]
                
                # 为作者搜索计算相关性分数
                relevance_score = 1.0
                if is_author_search:
                    # 查找查询的作者名字是否出现在作者列表中
                    query_lower = query.lower()
                    exact_match = any(query_lower == author.lower() for author in authors)
                    partial_match = any(query_lower in author.lower() for author in authors)
                    
                    if exact_match:
                        relevance_score = 1.0  # 精确匹配
                    elif partial_match:
                        relevance_score = 0.8  # 部分匹配
                    else:
                        relevance_score = 0.4  # 可能在内容中提到的作者
                
                paper = {
                    'arxiv_id': entry.id.split('/abs/')[-1],
                    'title': entry.title,
                    'abstract': entry.summary,
                    'authors': authors,
                    'categories': [t['term'] for t in entry.tags],
                    'published': entry.published,
                    'updated': entry.updated,
                    'pdf_url': f"https://arxiv.org/pdf/{entry.id.split('/abs/')[-1]}.pdf",
                    'relevance_score': relevance_score  # 添加相关性分数
                }
                papers.append(paper)
                
            # 从 feed 中获取总结果数
            total_results = 0
            if hasattr(feed, 'feed') and hasattr(feed.feed, 'opensearch_totalresults'):
                try:
                    total_results = int(feed.feed.opensearch_totalresults)
                except (ValueError, TypeError):
                    logger.warning("Could not parse opensearch_totalresults")
            else:
                 # Fallback if total results not available (e.g., error or unexpected feed format)
                 total_results = len(papers) 
                 if len(papers) == max_results:
                    logger.warning("opensearch_totalresults not found in feed. Using len(papers) as total_results, which might be inaccurate.")
            
            # 如果是作者搜索，按相关性分数排序
            if is_author_search:
                papers.sort(key=lambda x: x['relevance_score'], reverse=True)
            
            # Return both papers and total results
            return {
                'papers': papers,
                'total_results': total_results
            }
            
        except Exception as e:
            logger.error(f"Error searching arXiv papers: {str(e)}")
            return {'error': str(e), 'papers': [], 'total_results': 0} # Ensure structure consistency on error
    
    def get_paper_by_id(self, arxiv_id):
        """通过ID获取特定论文
        
        Args:
            arxiv_id (str): arXiv论文ID
            
        Returns:
            dict: 论文数据
        """
        try:
            self._enforce_rate_limit()
            
            url = f"{self.BASE_URL}id_list={arxiv_id}"
            logger.info(f"Fetching paper from arXiv API: {url}")
            
            response = urllib.request.urlopen(url)
            feed = feedparser.parse(response.read())
            
            if not feed.entries:
                return {'error': 'Paper not found'}
                
            entry = feed.entries[0]
            return {
                'arxiv_id': entry.id.split('/abs/')[-1],
                'title': entry.title,
                'abstract': entry.summary,
                'authors': [author.name for author in entry.authors],
                'categories': [t['term'] for t in entry.tags],
                'published': entry.published,
                'updated': entry.updated,
                'pdf_url': f"https://arxiv.org/pdf/{entry.id.split('/abs/')[-1]}.pdf",
            }
            
        except Exception as e:
            logger.error(f"Error fetching arXiv paper: {str(e)}")
            return {'error': str(e)}
            
    def save_papers_to_db(self, papers, conn):
        """将论文保存到数据库
        
        Args:
            papers (list): 论文数据列表
            conn: 数据库连接
        """
        try:
            cur = conn.cursor()
            
            # 确保arxiv_papers表存在
            cur.execute("""
                CREATE TABLE IF NOT EXISTS arxiv_papers (
                    arxiv_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    abstract TEXT,
                    authors TEXT,
                    categories TEXT,
                    published TEXT,
                    updated TEXT,
                    pdf_url TEXT,
                    relevance_score REAL DEFAULT 1.0,
                    json_data TEXT
                )
            """)
            
            for paper in papers:
                # 确保论文有 relevance_score 字段
                relevance_score = paper.get('relevance_score', 1.0)
                
                cur.execute("""
                    INSERT OR REPLACE INTO arxiv_papers 
                    (arxiv_id, title, abstract, authors, categories, published, updated, pdf_url, relevance_score, json_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    paper['arxiv_id'],
                    paper['title'],
                    paper.get('abstract', ''),
                    json.dumps(paper.get('authors', [])),
                    json.dumps(paper.get('categories', [])),
                    paper.get('published', ''),
                    paper.get('updated', ''),
                    paper.get('pdf_url', ''),
                    relevance_score,
                    json.dumps(paper)
                ))
            
            conn.commit()
            logger.info(f"Saved {len(papers)} papers to database")
            
        except Exception as e:
            logger.error(f"Error saving papers to database: {str(e)}")
            conn.rollback()
            raise

    def search_by_author(self, author_name, start=0, max_results=10):
        """特定于作者的arXiv搜索
        
        Args:
            author_name (str): 作者姓名
            start (int): 结果的起始索引
            max_results (int): 返回的最大结果数
            
        Returns:
            list: 论文数据列表
        """
        # 尝试不同的作者名格式
        results = []
        
        # 尝试精确作者名搜索
        logger.info(f"使用精确作者名搜索: {author_name}")
        exact_results = self.search_papers(author_name, start, max_results, search_type='author')
        
        if isinstance(exact_results, dict) and 'papers' in exact_results:
            results.extend(exact_results['papers'])
        
        # 如果作者名包含空格，尝试调整格式
        if ' ' in author_name and not results:
            # 尝试姓氏在前
            name_parts = author_name.split()
            if len(name_parts) == 2:  # 如果只有姓+名
                surname_first = f"{name_parts[1]}, {name_parts[0]}"
                logger.info(f"尝试姓氏在前的作者搜索: {surname_first}")
                surname_results = self.search_papers(surname_first, start, max_results, search_type='author')
                
                if isinstance(surname_results, dict) and 'papers' in surname_results:
                    results.extend(surname_results['papers'])
        
        # 如果有首字母缩写，尝试完整搜索
        if '.' in author_name and not results:
            # 去掉点，试试只保留首字母或姓氏
            simplified_name = author_name.replace('.', ' ').replace('  ', ' ').strip()
            logger.info(f"尝试简化首字母的作者搜索: {simplified_name}")
            simplified_results = self.search_papers(simplified_name, start, max_results, search_type='author')
            
            if isinstance(simplified_results, dict) and 'papers' in simplified_results:
                results.extend(simplified_results['papers'])
        
        # 如果所有尝试都没有结果，回退到普通关键词搜索
        if not results:
            logger.info(f"没有找到精确作者匹配，尝试关键词搜索: {author_name}")
            keyword_results = self.search_papers(author_name, start, max_results, search_type='keyword')
            
            if isinstance(keyword_results, dict) and 'papers' in keyword_results:
                results.extend(keyword_results['papers'])
        
        # 删除重复项（基于arxiv_id）
        unique_results = []
        seen_ids = set()
        for paper in results:
            if isinstance(paper, dict) and 'arxiv_id' in paper:
                if paper['arxiv_id'] not in seen_ids:
                    seen_ids.add(paper['arxiv_id'])
                    unique_results.append(paper)
        
        # 再次按相关性排序
        unique_results.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        return {
            'papers': unique_results,
            'total_results': len(unique_results)
        } 