# Paper Analysis System

## Overview

The Paper Analysis System is an integrated academic paper search and analysis platform that provides the following features:

- Local paper search and analysis
- Real-time arXiv paper search
- Paper sentiment analysis
- Paper clustering analysis
- arXiv metadata statistical analysis

## System Requirements

- Python 3.7+
- SQLite3
- Required Python packages (see requirements.txt)

## Installation

### 方法一：直接安装

1. Navigate to the project repository:
```bash
cd paper-analysis-system
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Start the application:
```bash
python app.py
```

### 方法二：使用Docker（推荐）

1. 确保已安装Docker和Docker Compose，然后在项目目录中运行：
```bash
docker-compose up -d
```

2. 应用将在后台启动，可通过以下地址访问：
```
http://localhost:5002
```

3. 查看应用日志：
```bash
docker-compose logs -f
```

4. 停止应用：
```bash
docker-compose down
```

## Main Features

### 1. Unified Search Interface (/)

- Support simultaneous search in local database and arXiv
- Search by entity type (person, organization, work)
- Support result clustering analysis
- Provide sentiment analysis functionality

### 2. arXiv Paper Search (/arxiv)

- Real-time arXiv paper library search
- Keyword search support
- Clustering analysis
- Detailed paper information view

### 3. arXiv Data Analysis (/arxiv/analysis)

- Paper category distribution statistics
- Publication time trend analysis
- Version distribution analysis
- Active author statistics

## API Documentation

### Local Search API

- GET `/search`
  - Parameters:
    - type: Entity type (person/organisation/work)
    - name: Entity name
    - limit: Result limit

### arXiv Search API

- GET `/arxiv/search`
  - Parameters:
    - query: Search keywords
    - max_results: Maximum number of results
    - cluster: Whether to perform clustering
    - n_clusters: Number of clusters

### Sentiment Analysis API

- POST `/analyze/sentiment`
  - Parameters:
    - paper_id: Paper ID
    - text: Text to analyze

### Metadata Analysis API

- GET `/arxiv/metadata/analysis`
  - Parameters:
    - limit: Amount of data to analyze

## Usage Examples

### 1. Unified Search

1. Visit homepage "/"
2. Select search scope (All/Local/arXiv)
3. Enter search criteria
4. Optionally enable clustering
5. Click search button

### 2. Paper Sentiment Analysis

1. Select a paper from search results
2. Click "Sentiment Analysis" button
3. View analysis results, including:
   - Overall sentiment
   - Polarity value
   - Subjectivity degree
   - Sentence-level analysis

### 3. arXiv Data Analysis

1. Visit "/arxiv/analysis"
2. Set analysis data amount
3. View various statistical charts:
   - Paper category distribution
   - Time trends
   - Version distribution
   - Author statistics

## Important Notes

1. arXiv API Limitations:
   - Maximum 3 requests per second
   - Recommended to use smaller max_results values

2. Clustering Analysis:
   - Recommended cluster count between 2-10
   - May require longer processing time for large datasets

## License

MIT License
