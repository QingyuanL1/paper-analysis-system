#!/bin/bash

# Paper Analysis System API Test Script
echo "===== Paper Analysis System API Test Script ====="
echo "Testing arXiv API endpoints..."
echo ""

# Constants
BASE_URL="http://localhost:5002"
BLUE='\033[0;34m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Function to print header for each test
print_test_header() {
    echo -e "${BLUE}===== Testing: $1 =====${NC}"
}

# Function to make API calls and check response status
call_api() {
    local endpoint=$1
    local description=$2
    local expected_status_key=$3
    local expected_status_value=$4
    
    echo -e "${YELLOW}Request:${NC} curl -s -X GET \"${BASE_URL}${endpoint}\""
    response=$(curl -s -X GET "${BASE_URL}${endpoint}")
    status=$(echo $response | grep -o "\"status\":\"[^\"]*\"" | cut -d ":" -f2 | tr -d '"')
    
    echo -e "${YELLOW}Response (truncated):${NC} ${response:0:150}..."
    
    if [[ "$status" == "$expected_status_value" ]]; then
        echo -e "${GREEN}✓ Success: Status '${status}' matches expected value${NC}"
    else
        echo -e "${RED}✗ Failed: Expected status '${expected_status_value}' but got '${status}'${NC}"
    fi
    echo ""
}

# 1. Test Health Check Endpoint
print_test_header "Health Check"
call_api "/health" "Basic health check endpoint" "status" "healthy"

# 2. Test arXiv Paper Search - Keyword
print_test_header "arXiv Paper Search - Keyword"
call_api "/arxiv/search?query=quantum+computing&search_type=keyword&max_results=5" "Search for quantum computing papers" "status" "success"

# 3. Test arXiv Paper Search - Author
print_test_header "arXiv Paper Search - Author"
call_api "/arxiv/search?query=Einstein&search_type=author&max_results=5" "Search for papers by Einstein" "status" "success"

# 4. Test arXiv Paper Search - Title
print_test_header "arXiv Paper Search - Title"
call_api "/arxiv/search?query=quantum&search_type=title&max_results=5" "Search for papers with quantum in title" "status" "success"

# 5. Test arXiv Paper Search with Clustering
print_test_header "arXiv Paper Search with Clustering"
call_api "/arxiv/search?query=quantum+computing&search_type=keyword&max_results=5&cluster=true&n_clusters=3" "Search with clustering" "status" "success"

# 6. Test arXiv Metadata Analysis
print_test_header "arXiv Metadata Analysis"
call_api "/arxiv/metadata/analysis?limit=1000&type=all" "Get arXiv metadata analysis" "status" "success"

# 7. Test arXiv Metadata Analysis - Categories Only
print_test_header "arXiv Metadata Analysis - Categories Only"
call_api "/arxiv/metadata/analysis?limit=1000&type=categories" "Get arXiv categories analysis" "status" "success"

# 8. Test arXiv Metadata Analysis - Authors Only
print_test_header "arXiv Metadata Analysis - Authors Only"
call_api "/arxiv/metadata/analysis?limit=1000&type=authors" "Get arXiv authors analysis" "status" "success"

# 9. Test arXiv Metadata Analysis - Time Trends
print_test_header "arXiv Metadata Analysis - Time Trends"
call_api "/arxiv/metadata/analysis?limit=1000&type=time" "Get arXiv time trends analysis" "status" "success"

echo "===== Test Summary ====="
echo "All tests completed. Check above results for status."
echo "Note: Some tests may fail if specific data is not available in your system."
echo "Ensure that arXiv API is accessible."

echo ""
echo "===== Frontend Pages ====="
echo "To test the frontend pages, open these URLs in your browser:"
echo "1. arXiv Search: http://localhost:5002/"
echo "2. arXiv Analysis: http://localhost:5002/arxiv/analysis" 