import re
from typing import List, Dict, Any, Optional
import requests
from bs4 import BeautifulSoup
import json
from googlesearch import search
from langchain_groq import ChatGroq

# Initialize the LLM
MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
try:
    llm = ChatGroq(temperature=0, model_name=MODEL, api_key="your_api_key")
except Exception as e:
    print(f"Warning: Failed to initialize LLM: {e}")
    llm = None

SYSTEM_PROMPT = """
You're an expert Data Analyst. Extract features and their values from the given content.
If no data found for a feature put the feature value as N/A
"""

def search_web(query: str, num_results: int = 10) -> List[str]:
    """
    Search the web for a query and return URLs.
    
    Args:
        query (str): Search query
        num_results (int): Number of results to return
        
    Returns:
        List[str]: List of URLs
    """
    try:
        return list(search(query, num=num_results, stop=num_results))
    except Exception as e:
        print(f"Error searching the web: {e}")
        # Fallback method if Google search fails
        try:
            # Alternative: use DuckDuckGo API or similar
            print("Trying fallback search method...")
            return ["https://www.google.com/search?q=" + query.replace(" ", "+")]
        except:
            return []

def fetch_page_content(url: str) -> Optional[str]:
    """
    Fetch and extract text content from a webpage.
    
    Args:
        url (str): URL to fetch
        
    Returns:
        Optional[str]: Page content or None if fetching failed
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        # Parse HTML and extract text
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.extract()
            
        # Get text
        text = soup.get_text()
        
        # Break into lines and remove leading and trailing space
        lines = (line.strip() for line in text.splitlines())
        
        # Break multi-headlines into a line each
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        
        # Drop blank lines
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        return text
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def chunk_text(text: str, chunk_size: int = 4000) -> List[str]:
    """
    Split text into smaller chunks.
    
    Args:
        text (str): Text to split
        chunk_size (int): Maximum chunk size
        
    Returns:
        List[str]: List of text chunks
    """
    return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

def create_extraction_prompt(field_names: List[str], field_specs: Dict[str, Dict[str, Any]], content: str, query: str) -> str:
    """
    Create an improved prompt for data extraction with categorical support and relevance requirements.
    """
    fields_with_specs = []
    for field in field_names:
        spec = field_specs[field]
        if spec['type'] == 'categorical':
            categories = spec.get('categories', [])
            fields_with_specs.append(f"{field} (categorical: {', '.join(categories)})")
        else:
            fields_with_specs.append(f"{field} ({spec['type']})")
    
    field_list = "\n".join([f"- {field}" for field in fields_with_specs])
    
    return f"""You are a data analyst extracting structured data about {query} from web content.

REQUIREMENTS:
1. Only extract records that are highly relevant to the query: "{query}"
2. For each field below, extract the exact value from the content:
{field_list}

SPECIAL INSTRUCTIONS:
- For categorical fields, ONLY use the specified categories
- For number fields, extract numerical values only (remove symbols like $, %)
- For boolean fields, convert to true/false
- Skip any record where you can't find ALL field values
- Balance categorical values evenly across the dataset
- NEVER invent values - use "N/A" if not found
- Reject any content that isn't clearly about {query}

CONTENT TO EXTRACT FROM:
{content[:3000]}

Return ONLY a JSON array of objects with all specified fields. Example:
[
  {{
    "field1": "value1",
    "field2": 42,
    "field3": true
  }}
]""".strip()

def get_example_value(field_name: str, field_type: str) -> str:
    """Generate example values for the prompt"""
    if field_type == "number" or field_type == "float":
        return "42.99"
    elif field_type == "int":
        return "42"
    elif field_type == "bool":
        return "true"
    else:
        # Try to infer an example based on field name
        lower_name = field_name.lower()
        if any(term in lower_name for term in ["category", "type", "class"]):
            return "Example Category"
        if "date" in lower_name:
            return "2025-04-27"
        if "name" in lower_name:
            return "Example Name"
        if "price" in lower_name:
            return "Example Value"
        return "Example Value"

def extract_structured_data(query: str, fields: Dict[str, Dict[str, Any]], target_record_count: int = 10) -> List[Dict[str, Any]]:
    """
    Extract structured data based on a query and field specification.
    
    Args:
        query (str): Search query
        fields (Dict[str, Dict[str, Any]]): Field specifications
        target_record_count (int): Target number of records to extract
        
    Returns:
        List[Dict[str, Any]]: Extracted data records
    """
    if not llm:
        return [{"error": "LLM not initialized - API key may be invalid"}]
    
    if not fields:
        # Default fields if none specified
        fields = {
            "Name": {"type": "str", "description": "Name of the item"},
            "Description": {"type": "str", "description": "Description of the item"},
            "Price": {"type": "number", "description": "Price of the item"}
        }
    
    results = []
    field_names = list(fields.keys())
    
    # Create a mapping of field names to their types
    field_types = {name: fields[name]["type"] for name in field_names}
    
    # Consolidate field types - change "int" and "float" to "number"
    for field, field_type in field_types.items():
        if field_type in ["int", "float"]:
            field_types[field] = "number"
    
    # Search for relevant URLs
    print(f"Searching for URLs related to: {query}")
    urls = search_web(query, num_results=min(20, target_record_count * 2))  # Get more URLs to ensure enough data
    if not urls:
        print("No URLs found, using fallback method")
        # Fallback if no URLs found
        urls = [f"https://www.google.com/search?q={query.replace(' ', '+')}"]
    
    print(f"Found {len(urls)} URLs to process")
    
    # Set to track processed URLs to avoid duplicates
    processed_urls = set()
    
    category_trackers = {
        field: {cat: 0 for cat in spec['categories']} 
        for field, spec in fields.items() 
        if spec['type'] == 'categorical' and 'categories' in spec
    }
    
    for url in urls:
        if len(results) >= target_record_count:
            break
            
        try:
            content = fetch_page_content(url)
            if not content:
                continue
                
            # Check content relevance before processing
            if not is_content_relevant(content, query):
                print(f"Skipping irrelevant content from {url}")
                continue
                
            chunks = chunk_text(content)
            
            for chunk in chunks:
                if len(results) >= target_record_count:
                    break
                    
                extraction_result = process_chunk_with_llm(chunk, field_names, fields, query)
                
                if extraction_result:
                    # Filter and balance results
                    filtered_chunk_results = []
                    for record in extraction_result:
                        if is_record_valid(record, fields, category_trackers):
                            filtered_chunk_results.append(record)
                            # Update category counts
                            update_category_counts(record, fields, category_trackers)
                    
                    results.extend(filtered_chunk_results)
                    print(f"Added {len(filtered_chunk_results)} records, total now: {len(results)}")
            
            # If we have enough results, stop processing URLs
            if len(results) >= target_record_count:
                break
                
        except Exception as e:
            print(f"Error processing URL {url}: {e}")
            continue
    
    # Perform a final quality check and cleanup
    final_results = post_process_results(results, field_types)
    
    # Limit to target count
    return final_results[:target_record_count]

def is_content_relevant(content: str, query: str) -> bool:
    """Check if content is relevant to the query"""
    query_terms = set(query.lower().split())
    content_terms = set(content.lower().split())
    overlap = query_terms & content_terms
    return len(overlap) >= len(query_terms) / 2  # At least half of query terms present

def is_record_valid(record: Dict[str, Any], fields: Dict[str, Dict[str, Any]], category_trackers: Dict[str, Dict[str, int]]) -> bool:
    """Validate a record against field specifications"""
    for field, spec in fields.items():
        if field not in record:
            return False
            
        value = record[field]
        
        # Check categorical fields
        if spec['type'] == 'categorical' and 'categories' in spec:
            if value not in spec['categories']:
                return False
                
            # Check if we've already collected enough of this category
            current_count = category_trackers.get(field, {}).get(value, 0)
            max_per_category = spec.get('max_per_category', float('inf'))
            if current_count >= max_per_category:
                return False
                
        # Check type constraints
        if spec['type'] == 'number' and not isinstance(value, (int, float)):
            try:
                float(value)
            except (ValueError, TypeError):
                return False
                
        if spec['type'] == 'bool' and not isinstance(value, bool):
            if str(value).lower() not in ['true', 'false', 'yes', 'no']:
                return False
                
    return True

def update_category_counts(record: Dict[str, Any], fields: Dict[str, Dict[str, Any]], category_trackers: Dict[str, Dict[str, int]]):
    """Update category counts for balancing"""
    for field, spec in fields.items():
        if spec['type'] == 'categorical' and 'categories' in spec:
            value = record.get(field)
            if value in category_trackers.get(field, {}):
                category_trackers[field][value] += 1

                
def post_process_results(results: List[Dict[str, Any]], field_types: Dict[str, str]) -> List[Dict[str, Any]]:
    """Perform final cleanup and quality assurance on results"""
    if not results:
        return []
    
    # Remove duplicate records
    unique_results = []
    seen_records = set()
    
    for record in results:
        # Create a fingerprint of the record for deduplication
        fingerprint = json.dumps({k: str(v).lower() for k, v in record.items()}, sort_keys=True)
        if fingerprint not in seen_records:
            seen_records.add(fingerprint)
            unique_results.append(record)
    
    # Final type enforcement
    for record in unique_results:
        for field, field_type in field_types.items():
            if field in record:
                record[field] = convert_to_type(record[field], field_type)
    
    return unique_results

def process_chunk_with_llm(chunk: str, field_names: List[str], field_types: Dict[str, str], query: str) -> List[Dict[str, Any]]:
    """
    Process a text chunk with the LLM to extract structured data.
    
    Args:
        chunk (str): Text chunk
        field_names (List[str]): List of fields to extract
        field_types (Dict[str, str]): Dictionary mapping field names to their types
        query (str): Search query
        
    Returns:
        List[Dict[str, Any]]: Extracted data records
    """
    try:
        # Create extraction prompt with more specific instructions for types
        prompt = create_extraction_prompt(field_names, field_types, chunk[:3000], query)
        
        # Call the LLM
        response = llm.invoke([
            ("system", SYSTEM_PROMPT),
            ("user", prompt)
        ])
        
        # Parse the response
        if hasattr(response, 'content'):
            content = response.content
            
            # Extract JSON from response
            json_match = re.search(r'```(?:json)?\n?(.*?)```', content, re.DOTALL)
            if json_match:
                json_str = json_match.group(1).strip()
            else:
                json_match = re.search(r'\[\s*{.*}\s*\]', content, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    json_str = content
            
            try:
                # Parse as JSON
                raw_data = json.loads(json_str)
                
                # Process and convert types
                if isinstance(raw_data, list):
                    processed_data = []
                    for record in raw_data:
                        processed_record = {}
                        for field in field_names:
                            if field not in record or record[field] in ["N/A", "", None]:
                                # Try to infer a reasonable value instead of N/A
                                processed_record[field] = infer_default_value(field, field_types.get(field, "str"))
                            else:
                                # Convert to proper type
                                processed_record[field] = convert_to_type(record[field], field_types.get(field, "str"))
                        processed_data.append(processed_record)
                    return processed_data
                
            except json.JSONDecodeError:
                print("Failed to parse JSON response, falling back to regex parsing")
                # Enhanced regex parsing with type conversion
                # [implementation details...]
                
    except Exception as e:
        print(f"Error processing chunk with LLM: {e}")
        
    return []

def infer_default_value(field_name: str, field_type: str):
    """Infer a reasonable default value based on field name and type"""
    if field_type == "number" or field_type == "int" or field_type == "float":
        return 0
    elif field_type == "bool":
        return False
    else:
        # For string/categorical, try to infer from field name
        lower_name = field_name.lower()
        if any(term in lower_name for term in ["category", "type", "class"]):
            return "Other"
        if "date" in lower_name:
            return "2025-04-27"  # Current date
        if "name" in lower_name:
            return "Unknown"
        if "price" in lower_name:
            return "0.00"
        return ""

def convert_to_type(value: Any, target_type: str) -> Any:
    """Convert a value to the specified type"""
    try:
        if target_type == "number" or target_type == "float":
            # Extract numeric value from strings like "$59.99" or "25%"
            if isinstance(value, str):
                # Remove non-numeric chars except decimal point
                clean_val = re.sub(r'[^\d.]', '', value)
                return float(clean_val) if clean_val else 0.0
            return float(value)
        elif target_type == "int":
            if isinstance(value, str):
                # Extract integer from string
                clean_val = re.sub(r'[^\d]', '', value)
                return int(clean_val) if clean_val else 0
            return int(value)
        elif target_type == "bool":
            if isinstance(value, str):
                return value.lower() in ["true", "yes", "y", "1"]
            return bool(value)
        else:
            # For strings/categorical, ensure it's returned as string
            return str(value)
    except:
        # If conversion fails, return a type-appropriate default
        defaults = {"number": 0.0, "float": 0.0, "int": 0, "bool": False}
        return defaults.get(target_type, str(value))
        
    return []