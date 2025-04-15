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

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

initialize_database()
sentiment_analyzer = SentimentAnalyzer()
paper_clusterer = PaperClusterer()
arxiv_client = ArxivClient()

@app.route('/')
def index():
    # Serve arxiv.html as the homepage
    return render_template('arxiv.html')

@app.route('/search', methods=['GET'])
def search_papers():
    try:
        entity_type = request.args.get('type', '').lower()
        entity_name = request.args.get('name', '')
        limit = request.args.get('limit', 'all')

        logger.info(f"Received search request - type: {entity_type}, name: {entity_name}, limit: {limit}")

        if not entity_type or not entity_name:
            logger.warning("Missing required parameters: type and name")
            return jsonify({
                'status': 'error',
                'message': 'Missing required parameters: type and name'
            }), 400

        if entity_type not in ['person', 'organisation', 'work']:
            logger.warning(f"Invalid entity type: {entity_type}")
            return jsonify({
                'status': 'error',
                'message': 'Invalid entity type. Must be one of: person, organisation, work'
            }), 400

        if limit not in ['one', 'all']:
            logger.warning(f"Invalid limit: {limit}")
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
        
        # 实体类型映射，确保前后端一致
        entity_type_mapping = {
            'person': 'person',
            'PERSON': 'person',
            'organisation': 'organisation',
            'organization': 'organisation',
            'ORG': 'organisation',
            'work': 'work'
        }
        
        formatted_results = []
        for result in results:
            try:
                # 规范化实体类型
                db_entity_type = result[10] if len(result) > 10 else None
                # 确保db_entity_type是字符串类型
                if isinstance(db_entity_type, str):
                    normalized_entity_type = entity_type_mapping.get(db_entity_type, db_entity_type.lower())
                else:
                    # 如果是int或其他类型，直接使用entity_type
                    normalized_entity_type = entity_type
                
                formatted_result = {
                    'paper_id': result[0],
                    'paper_title': result[1],
                    'paper_name': result[1],  # 添加一致的字段名
                    'title': result[1],       # 添加一致的字段名
                    'paper_pdf': result[2],
                    'pdf_path': result[2],   # 添加一致的字段名
                    'paper_docx': result[3],
                    'docx_path': result[3],  # 添加一致的字段名
                    'paper_json': result[4],
                    'json_path': result[4],  # 添加一致的字段名
                    'paper_entities': result[5],
                    'entities': result[5],   # 添加一致的字段名
                    'entity_name': result[9] if len(result) > 9 and result[9] is not None else entity_name,
                    'entity_type': normalized_entity_type
                }
                formatted_results.append(formatted_result)
                
                # 记录详细结果用于调试
                logger.debug(f"Result: {formatted_result}")
            except Exception as e:
                logger.error(f"处理搜索结果时出错: {str(e)}, 结果: {result}")
                continue
        
        # 记录查询结果统计
        if formatted_results:
            entity_types = {}
            for res in formatted_results:
                et = res['entity_type']
                if et in entity_types:
                    entity_types[et] += 1
                else:
                    entity_types[et] = 1
            logger.info(f"Entity type distribution in results: {entity_types}")
        
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
        # Get search_type from request, default to 'keyword'
        search_type = request.args.get('search_type', 'keyword').lower()
        start = int(request.args.get('start', 0))
        max_results = int(request.args.get('max_results', 10))
        should_cluster = request.args.get('cluster', 'false').lower() == 'true'
        n_clusters = int(request.args.get('n_clusters', 5))

        # Log the received search type
        logger.info(f"Searching arXiv papers: query={query}, type={search_type}, start={start}, max_results={max_results}, cluster={should_cluster}")

        # Pass search_type to the client method
        search_result = arxiv_client.search_papers(query, start, max_results, search_type=search_type)

        # Extract papers and total results from the dictionary
        papers = search_result.get('papers', [])
        total_results = search_result.get('total_results', 0)
        
        # Check for errors after getting papers and total_results
        if 'error' in search_result:
            return jsonify({
                'status': 'error',
                'message': search_result['error']
            }), 500

        # Perform sentiment analysis on abstracts
        try:
            for paper in papers:
                if paper.get('abstract'):
                    # Assuming sentiment_analyzer has a method for direct text analysis
                    # You might need to adapt this based on your SentimentAnalyzer implementation
                    sentiment_score = sentiment_analyzer.analyze_text(paper['abstract'])
                    if sentiment_score and 'overall_sentiment' in sentiment_score:
                         polarity = sentiment_score['overall_sentiment']['polarity']
                         paper['sentiment_label'] = sentiment_analyzer.get_sentiment_label(polarity)
                         paper['sentiment_score'] = round(polarity, 2)
                    else:
                        paper['sentiment_label'] = 'N/A' # Mark if analysis failed
                        paper['sentiment_score'] = 'N/A'
                else:
                    paper['sentiment_label'] = 'N/A' # No abstract
                    paper['sentiment_score'] = 'N/A'
        except Exception as e:
            logger.error(f"Error during sentiment analysis for arXiv results: {str(e)}")
            # Optionally mark all papers as N/A or handle differently
            for paper in papers:
                paper['sentiment_label'] = 'Error'
                paper['sentiment_score'] = 'Error'

        # 保存到数据库 (pass the list of papers)
        conn = get_connection("data/test_db.sqlite")
        try:
            if papers: # Only save if there are papers
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
                'total_results': total_results, # Include total results
                'clusters': clustering_results
            })

        return jsonify({
            'status': 'success',
            'papers': papers,
            'total_results': total_results # Include total results
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
        
        logger.info(f"统一搜索请求 - 类型: {search_type}, 实体类型: {entity_type}, 实体名称: {entity_name}, 额外查询: {query}")
        
        # 实体类型映射，确保前后端一致
        entity_type_mapping = {
            'person': 'person',
            'PERSON': 'person',
            'organisation': 'organisation',
            'organization': 'organisation',
            'ORG': 'organisation',
            'work': 'work'
        }
        
        # 处理人名查询的特殊情况
        is_person_query = entity_type == 'person'
        
        results = {
            'status': 'success',
            'local_results': [],
            'arxiv_results': [],
            'clusters': None,
            'query_info': {
                'entity_type': entity_type,
                'entity_name': entity_name,
                'is_person_query': is_person_query
            }
        }
        
        conn = get_connection("data/test_db.sqlite")
        cur = conn.cursor()
        
        # 执行本地搜索
        if search_type in ['local', 'all'] and entity_type and entity_name:
            try:
                logger.info(f"执行本地搜索 - 实体类型: {entity_type}, 实体名称: {entity_name}")
                # 记录数据库中的实体类型情况
                try:
                    cur.execute("SELECT DISTINCT entity_type FROM entities")
                    db_entity_types = [row[0] for row in cur.fetchall()]
                    logger.info(f"数据库中的实体类型: {db_entity_types}")
                    
                    # 添加针对work类型的日志
                    if entity_type == 'work':
                        try:
                            cur.execute("SELECT entity_id, entity_name FROM entities WHERE entity_type = 'work' LIMIT 5")
                            sample_works = cur.fetchall()
                            logger.info(f"数据库中的work类型实体样例: {sample_works}")
                        except Exception as e:
                            logger.error(f"获取work类型实体时出错: {str(e)}")
                    
                    # 查看是否有匹配的组织
                    if entity_type in ['organisation', 'organization']:
                        cur.execute("SELECT entity_id, entity_name FROM entities WHERE entity_type = 'ORG' LIMIT 5")
                        sample_orgs = cur.fetchall()
                        logger.info(f"数据库中的ORG类型实体样例: {sample_orgs}")
                except Exception as e:
                    logger.error(f"获取实体类型时出错: {str(e)}")
                
                # 对于人名的特殊处理，可以尝试多种姓名格式
                if is_person_query:
                    # 尝试使用精确查询
                    exact_query_string = f"get {limit} papers that mention {entity_type} {entity_name}"
                    logger.info(f"精确人名搜索查询: {exact_query_string}")
                    
                    exact_sql_query = build_query(exact_query_string)
                    logger.info(f"精确人名SQL查询: {exact_sql_query}")
                    
                    cur.execute(exact_sql_query)
                    local_results = cur.fetchall()
                    logger.info(f"精确人名搜索找到 {len(local_results)} 个结果")
                    logger.info(f"精确人名搜索结果: {local_results}")
                    
                    # 如果精确查询没有找到结果，尝试使用部分姓名或名字
                    if len(local_results) == 0 and ' ' in entity_name:
                        # 分解姓名
                        name_parts = entity_name.split()
                        
                        # 可能的姓氏或名字
                        for name_part in name_parts:
                            if len(name_part) < 3:  # 忽略过短的部分
                                continue
                                
                            partial_query_string = f"get {limit} papers that mention {entity_type} {name_part}"
                            logger.info(f"部分人名搜索查询: {partial_query_string}")
                            
                            partial_sql_query = build_query(partial_query_string)
                            cur.execute(partial_sql_query)
                            partial_results = cur.fetchall()
                            logger.info(f"部分人名搜索 '{name_part}' 找到 {len(partial_results)} 个结果")
                            
                            # 将部分匹配结果添加到主结果集
                            for result in partial_results:
                                # 检查是否已存在
                                if not any(r[0] == result[0] for r in local_results):
                                    local_results.append(result)
                # 对于组织类型的特殊处理
                elif entity_type in ['organisation', 'organization']:
                    # 尝试使用精确查询
                    exact_query_string = f"get {limit} papers that mention {entity_type} {entity_name}"
                    logger.info(f"精确组织搜索查询: {exact_query_string}")
                    
                    exact_sql_query = build_query(exact_query_string)
                    logger.info(f"精确组织SQL查询: {exact_sql_query}")
                    
                    cur.execute(exact_sql_query)
                    local_results = cur.fetchall()
                    logger.info(f"精确组织搜索找到 {len(local_results)} 个结果")
                    
                    # 如果精确查询没有找到结果，尝试使用部分组织名称
                    if len(local_results) == 0 and ' ' in entity_name:
                        # 构建部分匹配查询 - 使用更灵活的搜索方式
                        words = entity_name.split()
                        significant_words = [w for w in words if len(w) > 3]
                        
                        for word in significant_words:
                            partial_query_string = f"get {limit} papers that mention {entity_type} {word}"
                            logger.info(f"部分组织名称搜索查询: {partial_query_string}")
                            
                            partial_sql_query = build_query(partial_query_string)
                            cur.execute(partial_sql_query)
                            partial_results = cur.fetchall()
                            logger.info(f"部分组织搜索 '{word}' 找到 {len(partial_results)} 个结果")
                            
                            # 将部分匹配结果添加到主结果集
                            for result in partial_results:
                                # 检查是否已存在
                                if not any(r[0] == result[0] for r in local_results):
                                    local_results.append(result)
                                    
                    # 尝试直接从实体表搜索包含关键词的组织
                    if len(local_results) == 0:
                        direct_query = """
                            SELECT p.* FROM papers p
                            JOIN papers_have_entities phe ON p.paper_id = phe.paper_id
                            JOIN entities e ON phe.entity_id = e.entity_id
                            WHERE e.entity_type = 'ORG' AND e.entity_name LIKE ?
                        """
                        search_term = f"%{entity_name}%"
                        logger.info(f"直接实体表查询: {direct_query} with term: {search_term}")
                        
                        cur.execute(direct_query, (search_term,))
                        direct_results = cur.fetchall()
                        logger.info(f"直接实体表搜索找到 {len(direct_results)} 个结果")
                        
                        # 添加到主结果集
                        for result in direct_results:
                            if not any(r[0] == result[0] for r in local_results):
                                local_results.append(result)
                else:
                    # 非人名实体的常规查询
                    query_string = f"get {limit} papers that mention {entity_type} {entity_name}"
                    logger.info(f"本地搜索查询字符串: {query_string}")
                    
                    sql_query = build_query(query_string)
                    logger.info(f"生成的SQL查询: {sql_query}")
                    
                    cur.execute(sql_query)
                    local_results = cur.fetchall()
                    logger.info(f"本地搜索找到 {len(local_results)} 个结果")
                
                formatted_local_results = []
                for result in local_results:
                    # 确保结果有足够的列
                    if len(result) < 11:
                        logger.warning(f"结果格式不正确，跳过此条: {result}")
                        continue
                        
                    try:
                        # 规范化实体类型
                        db_entity_type = result[10] if len(result) > 10 else None
                        # 确保db_entity_type是字符串类型
                        if isinstance(db_entity_type, str):
                            normalized_entity_type = entity_type_mapping.get(db_entity_type, db_entity_type.lower())
                        else:
                            # 如果是int或其他类型，直接使用entity_type
                            normalized_entity_type = entity_type
                        
                        # 使用一致的字段名格式化结果
                        paper_data = {
                            'source': 'local',
                            'paper_id': result[0],
                            'title': result[1],
                            'paper_name': result[1],
                            'pdf_path': result[2],
                            'docx_path': result[3],
                            'json_path': result[4],
                            'entities': result[5],
                            'entity_name': result[9] if len(result) > 9 and result[9] is not None else entity_name,
                            'entity_type': normalized_entity_type,
                            'relevance_score': 1.0  # 默认相关性分数
                        }
                        
                        # 计算相关性分数 - 用于排序
                        if is_person_query:
                            # 对于人名搜索，精确匹配得分高
                            entity_name_lower = entity_name.lower()
                            # 确保result[9]是字符串且不为None
                            result_entity = result[9] if len(result) > 9 and result[9] is not None else ""
                            result_entity_lower = result_entity.lower() if isinstance(result_entity, str) else ""
                            
                            if result_entity_lower == entity_name_lower:
                                paper_data['relevance_score'] = 1.0  # 精确匹配
                            elif entity_name_lower in result_entity_lower or result_entity_lower in entity_name_lower:
                                paper_data['relevance_score'] = 0.8  # 部分匹配
                            else:
                                # 尝试从论文内容中找名字
                                try:
                                    with open(result[4], 'r', encoding='utf-8') as f:
                                        paper_json = json.load(f)
                                    paper_text = ""
                                    for item in paper_json:
                                        if isinstance(item, dict) and item.get('TYPE') == 'text':
                                            paper_text += item.get('VALUE', '') + " "
                                
                                    if entity_name_lower in paper_text.lower():
                                        paper_data['relevance_score'] = 0.6  # 内容中找到名字
                                    else:
                                        paper_data['relevance_score'] = 0.4  # 相关实体但不是直接匹配
                                except Exception as e:
                                    logger.error(f"解析论文内容时出错: {str(e)}")
                                    paper_data['relevance_score'] = 0.3  # 无法检查内容
                        
                        formatted_local_results.append(paper_data)
                    except Exception as e:
                        logger.error(f"处理搜索结果时出错: {str(e)}, 结果: {result}")
                        continue
                
                # 根据相关性分数排序结果
                formatted_local_results.sort(key=lambda x: x['relevance_score'], reverse=True)
                results['local_results'] = formatted_local_results
                
                # 记录检索到的实体信息，用于调试
                if formatted_local_results:
                    for i, paper in enumerate(formatted_local_results[:3]):  # 只记录前3条用于调试
                        logger.info(f"结果 {i+1}: ID={paper['paper_id']}, 标题={paper['title']}, 实体={paper['entity_type']}:{paper['entity_name']}, 相关性={paper['relevance_score']}")

                # 如果是本地搜索，也用实体名称搜索arXiv
                if not query and entity_name:
                    if is_person_query:
                        # 使用专门的作者搜索功能
                        logger.info(f"使用专门的作者搜索功能搜索arXiv: {entity_name}")
                        arxiv_papers = arxiv_client.search_by_author(entity_name, start, max_results)
                    else:
                        # 普通实体搜索
                        arxiv_query = entity_name
                        logger.info(f"使用实体名称搜索arXiv: {arxiv_query}")
                        arxiv_papers = arxiv_client.search_papers(arxiv_query, start, max_results)
                    
                    if isinstance(arxiv_papers, dict) and 'error' in arxiv_papers:
                        results['arxiv_error'] = arxiv_papers['error']
                    else:
                        logger.info(f"从arXiv找到 {len(arxiv_papers)} 个结果")
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
                # 对于人名搜索，使用专门的作者搜索功能
                if is_person_query and query:
                    logger.info(f"使用专门的作者搜索功能搜索arXiv: {query}")
                    arxiv_papers = arxiv_client.search_by_author(query, start, max_results)
                else:
                    logger.info(f"使用普通关键词搜索arXiv: {query}")
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

@app.route('/api/papers', methods=['GET'])
def get_papers():
    """获取论文列表的API"""
    source = request.args.get('source', 'all')
    try:
        conn = get_connection("data/test_db.sqlite")
        
        if source == 'local':
            # 使用简化的查询逻辑获取本地论文
            query = "SELECT rowid as id, * FROM papers"
            papers = query_db(conn, query)
            
        elif source == 'arxiv':
            # 从arxiv_papers表获取论文
            query = """
                SELECT 
                    arxiv_id as id,
                    title,
                    abstract,
                    authors,
                    categories,
                    published,
                    updated,
                    pdf_url,
                    relevance_score,
                    json_data
                FROM arxiv_papers
                ORDER BY relevance_score DESC, published DESC
            """
            papers = query_db(conn, query)
            
            # 处理json格式的字段
            for paper in papers:
                try:
                    paper['authors'] = json.loads(paper['authors']) if paper['authors'] else []
                    paper['categories'] = json.loads(paper['categories']) if paper['categories'] else []
                except:
                    paper['authors'] = []
                    paper['categories'] = []
                
                # 确保各字段存在
                paper['entity_type'] = 'arxiv'
                if paper.get('id') and not paper.get('arxiv_id'):
                    paper['arxiv_id'] = paper['id']
                    
        elif source == 'all':
            # 合并本地和arxiv的查询结果
            local_query = "SELECT rowid as id, * FROM papers"
            arxiv_query = """
                SELECT 
                    arxiv_id as id,
                    title,
                    abstract,
                    authors,
                    categories,
                    published,
                    updated,
                    pdf_url,
                    relevance_score,
                    json_data,
                    'arxiv' as source
                FROM arxiv_papers
            """
            
            papers = query_db(conn, local_query)
            for paper in papers:
                paper['source'] = 'local'
            
            arxiv_papers = query_db(conn, arxiv_query)
            # 处理json格式的字段
            for paper in arxiv_papers:
                try:
                    paper['authors'] = json.loads(paper['authors']) if paper['authors'] else []
                    paper['categories'] = json.loads(paper['categories']) if paper['categories'] else []
                except:
                    paper['authors'] = []
                    paper['categories'] = []
                
                # 确保各字段存在
                paper['entity_type'] = 'arxiv'
                if paper.get('id') and not paper.get('arxiv_id'):
                    paper['arxiv_id'] = paper['id']
            
            papers.extend(arxiv_papers)
            
            # 按发布日期排序
            papers.sort(key=lambda x: x.get('published', ''), reverse=True)
        
        conn.close()
        return jsonify({'papers': papers})
    
    except Exception as e:
        logger.error(f"获取论文列表失败: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    logger.info("Starting Flask application...")
    app.run(host='0.0.0.0', port=5002, debug=True) 