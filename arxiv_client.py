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
        
    def search_papers(self, query, start=0, max_results=10):
        """搜索arXiv论文
        
        Args:
            query (str): 搜索查询
            start (int): 结果的起始索引
            max_results (int): 返回的最大结果数
            
        Returns:
            list: 论文数据列表
        """
        try:
            self._enforce_rate_limit()
            
            params = {
                'search_query': query,
                'start': start,
                'max_results': max_results,
                'sortBy': 'submittedDate',
                'sortOrder': 'descending'
            }
            
            url = self.BASE_URL + urllib.parse.urlencode(params)
            logger.info(f"Querying arXiv API: {url}")
            
            response = urllib.request.urlopen(url)
            feed = feedparser.parse(response.read())
            
            papers = []
            for entry in feed.entries:
                paper = {
                    'arxiv_id': entry.id.split('/abs/')[-1],
                    'title': entry.title,
                    'abstract': entry.summary,
                    'authors': [author.name for author in entry.authors],
                    'categories': [t['term'] for t in entry.tags],
                    'published': entry.published,
                    'updated': entry.updated,
                    'pdf_url': f"https://arxiv.org/pdf/{entry.id.split('/abs/')[-1]}.pdf",
                }
                papers.append(paper)
                
            return papers
            
        except Exception as e:
            logger.error(f"Error searching arXiv papers: {str(e)}")
            return {'error': str(e)}
    
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
                    json_data TEXT
                )
            """)
            
            for paper in papers:
                cur.execute("""
                    INSERT OR REPLACE INTO arxiv_papers 
                    (arxiv_id, title, abstract, authors, categories, published, updated, pdf_url, json_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    paper['arxiv_id'],
                    paper['title'],
                    paper.get('abstract', ''),
                    json.dumps(paper.get('authors', [])),
                    json.dumps(paper.get('categories', [])),
                    paper.get('published', ''),
                    paper.get('updated', ''),
                    paper.get('pdf_url', ''),
                    json.dumps(paper)
                ))
            
            conn.commit()
            logger.info(f"Saved {len(papers)} papers to database")
            
        except Exception as e:
            logger.error(f"Error saving papers to database: {str(e)}")
            conn.rollback()
            raise 