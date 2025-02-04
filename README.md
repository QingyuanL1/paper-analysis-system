# Academic Paper Analysis System

A comprehensive system for analyzing academic papers, featuring arXiv integration, paper clustering, and sentiment analysis.

## Features

### 1. Paper Search and Management
- Local paper search with entity recognition
- Real-time arXiv paper search
- Automatic paper metadata extraction
- PDF download support

### 2. Paper Clustering
- Topic-based paper clustering
- Interactive visualization of paper clusters
- Keyword extraction for each cluster
- Customizable number of clusters

### 3. Content Analysis
- Sentiment analysis of paper content
- Entity recognition and extraction
- Detailed paper statistics
- Full-text search capabilities

## Technology Stack

- Backend: Python, Flask
- Frontend: HTML5, Bootstrap, ECharts
- Data Processing: scikit-learn, NLTK
- Database: SQLite

## Installation

1. Clone the repository:
```bash
git clone [repository-url]
cd paper-analysis-system
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run the application:
```bash
python app.py
```

The application will be available at `http://127.0.0.1:5002`

## Usage

### Local Paper Analysis
1. Navigate to "Local Papers"
2. Select entity type and enter keywords
3. View search results and analyze paper content

### arXiv Paper Search
1. Navigate to "arXiv Papers"
2. Enter search keywords
3. Configure clustering options if needed
4. View papers and cluster visualization

## API Endpoints

### Paper Search
- `GET /search` - Search local papers
- `GET /arxiv/search` - Search arXiv papers
- `GET /arxiv/paper/<arxiv_id>` - Get specific paper details

### Analysis
- `GET /papers/clusters` - Get paper clustering results
- `POST /analyze/sentiment` - Analyze paper sentiment

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a new Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
