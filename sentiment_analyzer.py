import nltk
from nltk.sentiment import SentimentIntensityAnalyzer
import spacy
import json
import logging

logger = logging.getLogger(__name__)

class SentimentAnalyzer:
    def __init__(self):
        self.nlp = spacy.load("en_core_web_sm")
        self.sia = SentimentIntensityAnalyzer()
    
    def analyze_text(self, text):
        """Analyze sentiment of text
        
        Args:
            text (str): Text to analyze
            
        Returns:
            dict: Dictionary containing sentiment analysis results
        """
        logger.info(f"Starting text analysis, length: {len(text)}")
        logger.info(f"First 500 characters: {text[:500]}")
        
        doc = self.nlp(text)
        sentences = [sent.text.strip() for sent in doc.sents]
        logger.info(f"Sentence splitting result: {len(sentences)} sentences")
        for i, sent in enumerate(sentences[:3]):
            logger.info(f"Example sentence {i+1}: {sent}")
        
        overall_scores = self.sia.polarity_scores(text)
        logger.info(f"Overall sentiment scores: {overall_scores}")
        
        sentence_sentiments = []
        for sentence in sentences:
            scores = self.sia.polarity_scores(sentence)
            sentence_sentiments.append({
                'text': sentence,
                'polarity': scores['compound'],
                'subjectivity': (scores['pos'] + scores['neg']) / 2
            })
            
        logger.info(f"Sentiment scores for first 3 sentences:")
        for i, sent in enumerate(sentence_sentiments[:3]):
            logger.info(f"Sentence {i+1} - Polarity: {sent['polarity']}, Subjectivity: {sent['subjectivity']}")
        
        return {
            'overall_sentiment': {
                'polarity': overall_scores['compound'],
                'subjectivity': (overall_scores['pos'] + overall_scores['neg']) / 2
            },
            'sentence_sentiments': sentence_sentiments
        }
    
    def analyze_document(self, doc_path):
        """Analyze sentiment of a document
        
        Args:
            doc_path (str): Path to JSON format document
            
        Returns:
            dict: Dictionary containing document sentiment analysis results
        """
        try:
            logger.info(f"Starting document analysis: {doc_path}")
            with open(doc_path, 'r', encoding='utf-8') as f:
                doc_data = json.load(f)
            
            texts = []
            def extract_text(obj):
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        if key == 'TYPE' and value == 'text':
                            if 'VALUE' in obj:
                                texts.append(obj['VALUE'])
                        elif isinstance(value, (dict, list)):
                            extract_text(value)
                elif isinstance(obj, list):
                    for item in obj:
                        extract_text(item)
            
            extract_text(doc_data)
            logger.info(f"Extracted {len(texts)} text segments from document")
            
            full_text = ' '.join(texts)
            logger.info(f"Combined text length: {len(full_text)}")
            
            return self.analyze_text(full_text)
            
        except Exception as e:
            logger.error(f"Error analyzing document: {str(e)}")
            return {
                'error': f'Error analyzing document: {str(e)}'
            }
    
    def get_sentiment_label(self, polarity):
        """Get sentiment label based on polarity
        
        Args:
            polarity (float): Sentiment polarity value (-1.0 to 1.0)
            
        Returns:
            str: Sentiment label
        """
        if polarity > 0.3:
            return 'Positive'
        elif polarity < -0.3:
            return 'Negative'
        else:
            return 'Neutral'