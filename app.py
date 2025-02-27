from flask import Flask, jsonify, request, render_template
import logging
from flask_cors import CORS
from prototype import get_connection, build_query, initialize_database
from sentiment_analyzer import SentimentAnalyzer
from paper_clustering import PaperClusterer
from arxiv_client import ArxivClient
import sqlite3
import json
from collections import Counter
from datetime import datetime
import os
from flask_swagger_ui import get_swaggerui_blueprint

# Configure Swagger UI
SWAGGER_URL = '/api/docs'  # URL for accessing Swagger UI
API_URL = '/static/swagger.yaml'  # URL for swagger.yaml file

swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={
        'app_name': "Paper Analysis System API"
    }
)

app = Flask(__name__)
app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)
CORS(app)
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

initialize_database()
sentiment_analyzer = SentimentAnalyzer()
paper_clusterer = PaperClusterer()
arxiv_client = ArxivClient()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['GET'])
def search_papers():
    try:
        entity_type = request.args.get('type', '').lower()
        entity_name = request.args.get('name', '')
        limit = request.args.get('limit', 'all')

        logger.info(f"Received search request - type: {entity_type}, name: {entity_name}, limit: {limit}")

        if not entity_type or not entity_name:
            return jsonify({
                'status': 'error',
                'message': 'Missing required parameters: type and name'
            }), 400

        if entity_type not in ['person', 'organisation', 'work']:
            return jsonify({
                'status': 'error',
                'message': 'Invalid entity type. Must be one of: person, organisation, work'
            }), 400

        if limit not in ['one', 'all']:
            return jsonify({
                'status': 'error',
                'message': 'Invalid limit. Must be one of: one, all'
            }), 400

        query_string = f"get {limit} papers that mention {entity_type} {entity_name}"
        logger.debug(f"Built query string: {query_string}")
        
        conn = get_connection("data/test_db.sqlite")
        cur = conn.cursor()
        
        sql_query = build_query(query_string)
        logger.debug(f"Generated SQL query: {sql_query}")
        cur.execute(sql_query)
        results = cur.fetchall()
        logger.info(f"Found {len(results)} results")
        
        formatted_results = []
        for result in results:
            formatted_results.append({
                'paper_id': result[0],
                'paper_title': result[1],
                'paper_pdf': result[2],
                'paper_docx': result[3],
                'paper_json': result[4],
                'paper_entities': result[5],
                'entity_name': result[9],
                'entity_type': result[10]
            })
        
        return jsonify({
            'status': 'success',
            'count': len(formatted_results),
            'results': formatted_results
        })
    
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
    finally:
        if 'conn' in locals():
            conn.close()

@app.route('/analyze/sentiment', methods=['POST'])
def analyze_sentiment():
    try:
        data = request.get_json()
        doc_path = data.get('doc_path')
        
        if not doc_path:
            return jsonify({
                'status': 'error',
                'message': 'Missing document path'
            }), 400
            
        sentiment_results = sentiment_analyzer.analyze_document(doc_path)
        
        if 'error' in sentiment_results:
            return jsonify({
                'status': 'error',
                'message': sentiment_results['error']
            }), 500
            
        sentiment_results['sentiment_label'] = sentiment_analyzer.get_sentiment_label(
            sentiment_results['overall_sentiment']['polarity']
        )
        
        return jsonify({
            'status': 'success',
            'results': sentiment_results
        })
        
    except Exception as e:
        logger.error(f"Error analyzing sentiment: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/papers/<int:paper_id>/sentiment', methods=['GET'])
def get_paper_sentiment(paper_id):
    try:
        logger.info(f"Getting sentiment for paper ID: {paper_id}")
        
        conn = get_connection("data/test_db.sqlite")
        cur = conn.cursor()
        cur.execute("SELECT paper_json FROM papers WHERE paper_id = ?", (paper_id,))
        result = cur.fetchone()
        
        if not result:
            logger.error(f"Paper not found with ID: {paper_id}")
            return jsonify({
                'status': 'error',
                'message': 'Paper not found'
            }), 404
            
        json_path = result[0]
        logger.info(f"Found JSON path for paper: {json_path}")
            
        sentiment_results = sentiment_analyzer.analyze_document(json_path)
        
        if 'error' in sentiment_results:
            logger.error(f"Error in sentiment analysis: {sentiment_results['error']}")
            return jsonify({
                'status': 'error',
                'message': sentiment_results['error']
            }), 500
            
        sentiment_results['sentiment_label'] = sentiment_analyzer.get_sentiment_label(
            sentiment_results['overall_sentiment']['polarity']
        )
        
        logger.info("Sentiment analysis completed successfully")
        return jsonify({
            'status': 'success',
            'paper_id': paper_id,
            'results': sentiment_results
        })
        
    except Exception as e:
        logger.error(f"Error getting paper sentiment: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
    finally:
        if 'conn' in locals():
            conn.close()

@app.route('/papers/clusters', methods=['GET'])
def get_paper_clusters():
    try:
        # 获取查询参数
        n_clusters = int(request.args.get('n_clusters', 5))
        category = request.args.get('category', None)
        
        logger.info(f"Getting paper clusters with n_clusters={n_clusters}, category={category}")
        
        # 从数据库获取论文数据
        conn = get_connection("data/test_db.sqlite")
        cur = conn.cursor()
        
        if category:
            cur.execute("""
                SELECT paper_id, paper_name as title, paper_json
                FROM papers 
                WHERE paper_json LIKE ?
            """, (f"%{category}%",))
        else:
            cur.execute("""
                SELECT paper_id, paper_name as title, paper_json
                FROM papers
            """)
            
        papers = cur.fetchall()
        
        if not papers:
            return jsonify({
                'status': 'error',
                'message': 'No papers found'
            }), 404
            
        # 处理论文数据
        papers_data = []
        for paper in papers:
            try:
                with open(paper[2], 'r', encoding='utf-8') as f:
                    paper_json = json.load(f)
                    
                # 提取摘要
                abstract = ""
                for item in paper_json:
                    if isinstance(item, dict) and item.get('TYPE') == 'text':
                        abstract += item.get('VALUE', '') + " "
                        
                papers_data.append({
                    'paper_id': paper[0],
                    'title': paper[1],
                    'abstract': abstract.strip()
                })
            except Exception as e:
                logger.warning(f"Error processing paper {paper[0]}: {str(e)}")
                continue
        
        # 执行聚类
        paper_clusterer.n_clusters = n_clusters
        clustering_results = paper_clusterer.process_papers(papers_data)
        
        if 'error' in clustering_results:
            return jsonify({
                'status': 'error',
                'message': clustering_results['error']
            }), 500
            
        return jsonify({
            'status': 'success',
            'n_clusters': n_clusters,
            'results': clustering_results
        })
        
    except Exception as e:
        logger.error(f"Error getting paper clusters: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
    finally:
        if 'conn' in locals():
            conn.close()

@app.route('/health', methods=['GET'])
def health_check():
    logger.info("Health check requested")
    return jsonify({
        'status': 'healthy',
        'message': 'Service is running'
    })

@app.route('/arxiv/search', methods=['GET'])
def search_arxiv_papers():
    try:
        query = request.args.get('query', '')
        start = int(request.args.get('start', 0))
        max_results = int(request.args.get('max_results', 10))
        should_cluster = request.args.get('cluster', 'false').lower() == 'true'
        n_clusters = int(request.args.get('n_clusters', 5))
        
        logger.info(f"Searching arXiv papers: query={query}, start={start}, max_results={max_results}")
        
        # 搜索论文
        papers = arxiv_client.search_papers(query, start, max_results)
        
        if isinstance(papers, dict) and 'error' in papers:
            return jsonify({
                'status': 'error',
                'message': papers['error']
            }), 500
            
        # 保存到数据库
        conn = get_connection("data/test_db.sqlite")
        try:
            arxiv_client.save_papers_to_db(papers, conn)
        except Exception as e:
            logger.error(f"Error saving papers to database: {str(e)}")
            # 继续处理，因为这不是致命错误
        
        # 如果请求聚类
        if should_cluster and papers:
            papers_data = [{
                'paper_id': paper['arxiv_id'],
                'title': paper['title'],
                'abstract': paper['abstract']
            } for paper in papers]
            
            paper_clusterer.n_clusters = min(n_clusters, len(papers))
            clustering_results = paper_clusterer.process_papers(papers_data)
            
            if 'error' in clustering_results:
                return jsonify({
                    'status': 'error',
                    'message': clustering_results['error']
                }), 500
                
            return jsonify({
                'status': 'success',
                'papers': papers,
                'clusters': clustering_results
            })
        
        return jsonify({
            'status': 'success',
            'papers': papers
        })
        
    except Exception as e:
        logger.error(f"Error searching arXiv papers: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
    finally:
        if 'conn' in locals():
            conn.close()

@app.route('/arxiv/paper/<arxiv_id>', methods=['GET'])
def get_arxiv_paper(arxiv_id):
    try:
        logger.info(f"Getting arXiv paper: {arxiv_id}")
        
        # 先从数据库查找
        conn = get_connection("data/test_db.sqlite")
        cur = conn.cursor()
        
        cur.execute("SELECT json_data FROM arxiv_papers WHERE arxiv_id = ?", (arxiv_id,))
        result = cur.fetchone()
        
        if result:
            paper = json.loads(result[0])
        else:
            # 如果数据库中没有，从API获取
            paper = arxiv_client.get_paper_by_id(arxiv_id)
            if isinstance(paper, dict) and 'error' not in paper:
                try:
                    arxiv_client.save_papers_to_db([paper], conn)
                except Exception as e:
                    logger.error(f"Error saving paper to database: {str(e)}")
        
        if isinstance(paper, dict) and 'error' in paper:
            return jsonify({
                'status': 'error',
                'message': paper['error']
            }), 404 if paper['error'] == 'Paper not found' else 500
            
        return jsonify({
            'status': 'success',
            'paper': paper
        })
        
    except Exception as e:
        logger.error(f"Error getting arXiv paper: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
    finally:
        if 'conn' in locals():
            conn.close()

@app.route('/arxiv')
def arxiv_page():
    return render_template('arxiv.html')

@app.route('/unified_search', methods=['GET'])
def unified_search():
    try:
        # 获取通用搜索参数
        search_type = request.args.get('search_type', 'all')  # 可选值: local, arxiv, all
        query = request.args.get('query', '')
        start = int(request.args.get('start', 0))
        max_results = int(request.args.get('max_results', 10))
        should_cluster = request.args.get('cluster', 'false').lower() == 'true'
        n_clusters = int(request.args.get('n_clusters', 5))
        
        # 本地搜索特定参数
        entity_type = request.args.get('type', '').lower()
        entity_name = request.args.get('name', '')
        limit = request.args.get('limit', 'all')
        
        results = {
            'status': 'success',
            'local_results': [],
            'arxiv_results': [],
            'clusters': None
        }
        
        conn = get_connection("data/test_db.sqlite")
        cur = conn.cursor()
        
        # 执行本地搜索
        if search_type in ['local', 'all'] and entity_type and entity_name:
            try:
                query_string = f"get {limit} papers that mention {entity_type} {entity_name}"
                sql_query = build_query(query_string)
                cur.execute(sql_query)
                local_results = cur.fetchall()
                
                formatted_local_results = []
                for result in local_results:
                    formatted_local_results.append({
                        'source': 'local',
                        'paper_id': result[0],
                        'title': result[1],
                        'pdf_path': result[2],
                        'docx_path': result[3],
                        'json_path': result[4],
                        'entities': result[5],
                        'entity_name': result[9],
                        'entity_type': result[10]
                    })
                results['local_results'] = formatted_local_results

                # 如果是本地搜索，也用实体名称搜索arXiv
                if not query and entity_name:
                    arxiv_query = entity_name
                    arxiv_papers = arxiv_client.search_papers(arxiv_query, start, max_results)
                    if isinstance(arxiv_papers, dict) and 'error' in arxiv_papers:
                        results['arxiv_error'] = arxiv_papers['error']
                    else:
                        # 保存到arxiv_papers表
                        try:
                            arxiv_client.save_papers_to_db(arxiv_papers, conn)
                            
                            # 保存到papers表
                            for paper in arxiv_papers:
                                try:
                                    logger.info(f"Processing arXiv paper: {paper['title']}")
                                    # 检查论文是否已存在
                                    cur.execute("SELECT paper_id FROM papers WHERE paper_name = ?", (paper['title'],))
                                    existing_paper = cur.fetchone()
                                    
                                    if existing_paper:
                                        logger.info(f"Paper already exists in database with ID: {existing_paper[0]}")
                                        continue
                                        
                                    logger.info("Paper is new, inserting into papers table...")
                                    # 插入新论文
                                    cur.execute("""
                                        INSERT INTO papers (paper_name, paper_pdf, paper_docx, paper_json, paper_entities)
                                        VALUES (?, ?, ?, ?, ?)
                                    """, (
                                        paper['title'],
                                        paper['pdf_url'],
                                        '',  # docx_path为空
                                        json.dumps(paper),  # 将整个paper对象作为json存储
                                        json.dumps({'arxiv_id': paper['arxiv_id']})  # 存储arxiv_id作为标识
                                    ))
                                    paper_id = cur.lastrowid
                                    logger.info(f"Successfully inserted paper with ID: {paper_id}")
                                    
                                    # 为作者添加实体
                                    logger.info(f"Processing {len(paper['authors'])} authors...")
                                    for author in paper['authors']:
                                        # 插入作者实体
                                        cur.execute("""
                                            INSERT OR IGNORE INTO entities (entity_name, entity_type)
                                            VALUES (?, 'person')
                                        """, (author,))
                                        
                                        # 获取实体ID
                                        cur.execute("SELECT entity_id FROM entities WHERE entity_name = ? AND entity_type = 'person'", (author,))
                                        entity_id = cur.fetchone()[0]
                                        
                                        # 建立论文和实体的关联
                                        cur.execute("""
                                            INSERT OR IGNORE INTO papers_have_entities (paper_id, entity_id)
                                            VALUES (?, ?)
                                        """, (paper_id, entity_id))
                                        logger.info(f"Added author entity: {author} (ID: {entity_id})")
                                    
                                    # 为分类添加实体
                                    logger.info(f"Processing {len(paper['categories'])} categories...")
                                    for category in paper['categories']:
                                        # 插入分类实体
                                        cur.execute("""
                                            INSERT OR IGNORE INTO entities (entity_name, entity_type)
                                            VALUES (?, 'work')
                                        """, (category,))
                                        
                                        # 获取实体ID
                                        cur.execute("SELECT entity_id FROM entities WHERE entity_name = ? AND entity_type = 'work'", (category,))
                                        entity_id = cur.fetchone()[0]
                                        
                                        # 建立论文和实体的关联
                                        cur.execute("""
                                            INSERT OR IGNORE INTO papers_have_entities (paper_id, entity_id)
                                            VALUES (?, ?)
                                        """, (paper_id, entity_id))
                                        logger.info(f"Added category entity: {category} (ID: {entity_id})")
                                    
                                    logger.info(f"Successfully processed paper: {paper['title']}")
                                    
                                except Exception as e:
                                    logger.error(f"Error saving paper '{paper['title']}' to papers table: {str(e)}")
                                    continue
                                    
                            conn.commit()
                            logger.info("Successfully committed all changes to database")
                        except Exception as e:
                            logger.error(f"Error saving papers to database: {str(e)}")
                            conn.rollback()
                            logger.info("Rolling back database changes due to error")
                        
                        formatted_arxiv_results = [{
                            'source': 'arxiv',
                            **paper
                        } for paper in arxiv_papers]
                        results['arxiv_results'] = formatted_arxiv_results

            except Exception as e:
                logger.error(f"Error in local search: {str(e)}")
                results['local_error'] = str(e)
        
        # 执行arXiv搜索（如果有额外的arXiv查询关键词）
        if search_type in ['arxiv', 'all'] and query:
            try:
                arxiv_papers = arxiv_client.search_papers(query, start, max_results)
                if isinstance(arxiv_papers, dict) and 'error' in arxiv_papers:
                    results['arxiv_error'] = arxiv_papers['error']
                else:
                    # 保存到arxiv_papers表和papers表
                    try:
                        arxiv_client.save_papers_to_db(arxiv_papers, conn)
                        
                        # 保存到papers表
                        for paper in arxiv_papers:
                            try:
                                logger.info(f"Processing arXiv paper: {paper['title']}")
                                # 检查论文是否已存在
                                cur.execute("SELECT paper_id FROM papers WHERE paper_name = ?", (paper['title'],))
                                existing_paper = cur.fetchone()
                                
                                if existing_paper:
                                    logger.info(f"Paper already exists in database with ID: {existing_paper[0]}")
                                    continue
                                    
                                logger.info("Paper is new, inserting into papers table...")
                                # 插入新论文
                                cur.execute("""
                                    INSERT INTO papers (paper_name, paper_pdf, paper_docx, paper_json, paper_entities)
                                    VALUES (?, ?, ?, ?, ?)
                                """, (
                                    paper['title'],
                                    paper['pdf_url'],
                                    '',  # docx_path为空
                                    json.dumps(paper),  # 将整个paper对象作为json存储
                                    json.dumps({'arxiv_id': paper['arxiv_id']})  # 存储arxiv_id作为标识
                                ))
                                paper_id = cur.lastrowid
                                logger.info(f"Successfully inserted paper with ID: {paper_id}")
                                
                                # 为作者添加实体
                                logger.info(f"Processing {len(paper['authors'])} authors...")
                                for author in paper['authors']:
                                    # 插入作者实体
                                    cur.execute("""
                                        INSERT OR IGNORE INTO entities (entity_name, entity_type)
                                        VALUES (?, 'person')
                                    """, (author,))
                                    
                                    # 获取实体ID
                                    cur.execute("SELECT entity_id FROM entities WHERE entity_name = ? AND entity_type = 'person'", (author,))
                                    entity_id = cur.fetchone()[0]
                                    
                                    # 建立论文和实体的关联
                                    cur.execute("""
                                        INSERT OR IGNORE INTO papers_have_entities (paper_id, entity_id)
                                        VALUES (?, ?)
                                    """, (paper_id, entity_id))
                                    logger.info(f"Added author entity: {author} (ID: {entity_id})")
                                
                                # 为分类添加实体
                                logger.info(f"Processing {len(paper['categories'])} categories...")
                                for category in paper['categories']:
                                    # 插入分类实体
                                    cur.execute("""
                                        INSERT OR IGNORE INTO entities (entity_name, entity_type)
                                        VALUES (?, 'work')
                                    """, (category,))
                                    
                                    # 获取实体ID
                                    cur.execute("SELECT entity_id FROM entities WHERE entity_name = ? AND entity_type = 'work'", (category,))
                                    entity_id = cur.fetchone()[0]
                                    
                                    # 建立论文和实体的关联
                                    cur.execute("""
                                        INSERT OR IGNORE INTO papers_have_entities (paper_id, entity_id)
                                        VALUES (?, ?)
                                    """, (paper_id, entity_id))
                                    logger.info(f"Added category entity: {category} (ID: {entity_id})")
                                
                                logger.info(f"Successfully processed paper: {paper['title']}")
                                
                            except Exception as e:
                                logger.error(f"Error saving paper '{paper['title']}' to papers table: {str(e)}")
                                continue
                                
                        conn.commit()
                        logger.info("Successfully committed all changes to database")
                    except Exception as e:
                        logger.error(f"Error saving papers to database: {str(e)}")
                        conn.rollback()
                        logger.info("Rolling back database changes due to error")
                    
                    # 合并到现有的arXiv结果中
                    existing_ids = set(paper['arxiv_id'] for paper in results['arxiv_results'])
                    for paper in arxiv_papers:
                        if paper['arxiv_id'] not in existing_ids:
                            results['arxiv_results'].append({
                                'source': 'arxiv',
                                **paper
                            })
                            existing_ids.add(paper['arxiv_id'])
            except Exception as e:
                logger.error(f"Error in arXiv search: {str(e)}")
                results['arxiv_error'] = str(e)
        
        # 如果需要聚类，将所有结果合并后进行聚类
        if should_cluster:
            all_papers = []
            
            # 添加本地论文
            for paper in results['local_results']:
                try:
                    with open(paper['json_path'], 'r', encoding='utf-8') as f:
                        paper_json = json.load(f)
                    abstract = ""
                    for item in paper_json:
                        if isinstance(item, dict) and item.get('TYPE') == 'text':
                            abstract += item.get('VALUE', '') + " "
                    all_papers.append({
                        'paper_id': str(paper['paper_id']),
                        'title': paper['title'],
                        'abstract': abstract.strip()
                    })
                except Exception as e:
                    logger.warning(f"Error processing local paper {paper['paper_id']}: {str(e)}")
                    continue
            
            # 添加arXiv论文
            for paper in results['arxiv_results']:
                all_papers.append({
                    'paper_id': paper['arxiv_id'],
                    'title': paper['title'],
                    'abstract': paper['abstract']
                })
            
            if all_papers:
                paper_clusterer.n_clusters = min(n_clusters, len(all_papers))
                clustering_results = paper_clusterer.process_papers(all_papers)
                if 'error' not in clustering_results:
                    results['clusters'] = clustering_results
        
        return jsonify(results)
        
    except Exception as e:
        logger.error(f"Error in unified search: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
    finally:
        if 'conn' in locals():
            conn.close()

def load_arxiv_metadata(file_path, limit=None):
    """加载arXiv元数据文件"""
    papers = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if limit and i >= limit:
                    break
                try:
                    paper = json.loads(line.strip())
                    papers.append(paper)
                except json.JSONDecodeError:
                    continue
        return papers
    except Exception as e:
        logger.error(f"Error loading arXiv metadata: {str(e)}")
        return None

@app.route('/arxiv/metadata/analysis', methods=['GET'])
def analyze_arxiv_metadata():
    try:
        # 获取查询参数
        limit = request.args.get('limit', type=int)
        analysis_type = request.args.get('type', 'all')  # categories, authors, time, all
        
        # 加载数据
        file_path = os.path.join(os.path.dirname(__file__), 'arxiv', 'arxiv-metadata-oai-snapshot.json')
        papers = load_arxiv_metadata(file_path, limit)
        
        if not papers:
            return jsonify({
                'status': 'error',
                'message': 'Failed to load arXiv metadata'
            }), 500
            
        results = {}
        
        # 分类统计
        if analysis_type in ['categories', 'all']:
            category_counter = Counter()
            for paper in papers:
                categories = paper.get('categories', '').split()
                category_counter.update(categories)
            
            results['category_analysis'] = {
                'total_categories': len(category_counter),
                'category_distribution': dict(category_counter.most_common(20))
            }
        
        # 作者统计
        if analysis_type in ['authors', 'all']:
            author_counter = Counter()
            for paper in papers:
                authors_parsed = paper.get('authors_parsed', [])
                for author in authors_parsed:
                    if author and len(author) >= 2:
                        author_name = f"{author[0]}, {author[1]}"
                        author_counter[author_name] += 1
            
            results['author_analysis'] = {
                'total_authors': len(author_counter),
                'top_authors': dict(author_counter.most_common(20))
            }
        
        # 时间趋势分析
        if analysis_type in ['time', 'all']:
            time_counter = Counter()
            version_counter = Counter()
            
            for paper in papers:
                update_date = paper.get('update_date', '')
                if update_date:
                    try:
                        year = datetime.strptime(update_date, '%Y-%m-%d').year
                        time_counter[year] += 1
                    except ValueError:
                        continue
                
                versions = paper.get('versions', [])
                version_counter[len(versions)] += 1
            
            results['time_analysis'] = {
                'yearly_distribution': dict(sorted(time_counter.items())),
                'version_distribution': dict(sorted(version_counter.items()))
            }
        
        # 基本统计
        if analysis_type == 'all':
            results['basic_stats'] = {
                'total_papers': len(papers),
                'papers_with_doi': sum(1 for p in papers if p.get('doi')),
                'papers_with_license': sum(1 for p in papers if p.get('license')),
                'papers_with_journal_ref': sum(1 for p in papers if p.get('journal-ref'))
            }
        
        return jsonify({
            'status': 'success',
            'analysis_results': results
        })
        
    except Exception as e:
        logger.error(f"Error analyzing arXiv metadata: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/arxiv/analysis')
def arxiv_analysis_page():
    return render_template('arxiv_analysis.html')

if __name__ == '__main__':
    logger.info("Starting Flask application...")
    app.run(host='0.0.0.0', port=5002, debug=True) 