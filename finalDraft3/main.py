from flask import Flask, request, jsonify, render_template, send_file
import os
import json
import pandas as pd
import zipfile
import io
import dicttoxml
import requests
import numpy as np
from PIL import Image

app = Flask(__name__)

# Create data directory if it doesn't exist
DATA_FOLDER = "data"
if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/extract_images', methods=['POST'])
def extract_images():
    try:
        data = request.json
        categories = [cat.strip() for cat in data.get('categories', '').split(',') if cat.strip()]
        size = int(data.get('size', 5))
        processing = data.get('processing', {})
        
        if not categories:
            return jsonify({"error": "Please provide at least one category"}), 400
        
        # Create a zip file in memory
        memory_file = io.BytesIO()
        successful_downloads = 0
        
        with zipfile.ZipFile(memory_file, 'w') as zipf:
            for category in categories:
                category_folder = category.replace(' ', '_')
                downloaded = 0
                
                # Try multiple image sources in order
                if downloaded < size:
                    downloaded += try_pexels(category, size - downloaded, zipf, category_folder, processing)
                if downloaded < size:
                    downloaded += try_unsplash(category, size - downloaded, zipf, category_folder, processing)
                
                successful_downloads += downloaded
        
        # Check if we got any images
        if successful_downloads == 0:
            return jsonify({
                "error": f"Could not find any images for: {', '.join(categories)}. Try different terms."
            }), 400
        
        memory_file.seek(0)
        return send_file(
            memory_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name='image_dataset.zip'
        )
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def try_pexels(query, count, zipf, folder, processing):
    """Try to get images from Pexels API"""
    pexels_key = "2aObS1TlGYthVoT8lbOJTIFaFOYVScciDMFO7LPEh7vFv159LIP1IIrN"  # Replace with actual key
    headers = {'Authorization': pexels_key}
    url = f"https://api.pexels.com/v1/search?query={query}&per_page={count}"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        downloaded = 0
        for photo in response.json().get('photos', [])[:count]:
            try:
                img_url = photo['src']['medium']
                img_response = requests.get(img_url, stream=True, timeout=10)
                img_response.raise_for_status()
                
                # Process the image
                img = Image.open(io.BytesIO(img_response.content))
                
                # Apply processing
                if processing.get('greyscale'):
                    img = img.convert('L')
                
                if processing.get('resize'):
                    img = img.resize(
                        (int(processing['resize']['width']), int(processing['resize']['height'])),
                        Image.Resampling.LANCZOS
                    )
                
                # Save to buffer
                img_buffer = io.BytesIO()
                img_format = processing.get('format', 'jpg')
                save_kwargs = {'format': img_format}
                
                if img_format in ('jpg', 'webp'):
                    save_kwargs['quality'] = 90
                
                img.save(img_buffer, **save_kwargs)
                
                # Add to zip
                zipf.writestr(f"{folder}/image_{downloaded+1}.{img_format}", img_buffer.getvalue())
                downloaded += 1
            except Exception as e:
                print(f"Error processing Pexels image: {e}")
        
        return downloaded
    except Exception as e:
        print(f"Pexels API failed for {query}: {e}")
        return 0

def try_unsplash(query, count, zipf, folder, processing):
    """Try to get images from Unsplash"""
    downloaded = 0
    for i in range(count):
        try:
            # Use random endpoint with specific size and query
            url = f"https://source.unsplash.com/random/300x300/?{query}&sig={i}"
            response = requests.get(url, stream=True, timeout=10)
            response.raise_for_status()
            
            # Check if we actually got an image (not the default placeholder)
            if response.headers.get('Content-Type', '').startswith('image/'):
                # Process the image
                img = Image.open(io.BytesIO(response.content))
                
                # Apply processing
                if processing.get('greyscale'):
                    img = img.convert('L')
                
                if processing.get('resize'):
                    img = img.resize(
                        (int(processing['resize']['width']), int(processing['resize']['height'])),
                        Image.Resampling.LANCZOS
                    )
                
                # Save to buffer
                img_buffer = io.BytesIO()
                img_format = processing.get('format', 'jpg')
                save_kwargs = {'format': img_format}
                
                if img_format in ('jpg', 'webp'):
                    save_kwargs['quality'] = 90
                
                img.save(img_buffer, **save_kwargs)
                
                # Add to zip
                zipf.writestr(f"{folder}/image_{downloaded+1}.{img_format}", img_buffer.getvalue())
                downloaded += 1
        except Exception as e:
            print(f"Error processing Unsplash image: {e}")
    
    return downloaded

@app.route('/extract_structured', methods=['POST'])
def extract_structured():
    try:
        data = request.json
        query = data.get('query')
        fields = data.get('fields', {})
        record_count = int(data.get('record_count', 10))
        
        if not query:
            return jsonify({"error": "Please provide a search query"}), 400
        
        # Process field specifications
        processed_fields = {}
        for field_name, field_spec in fields.items():
            processed_fields[field_name] = {
                'type': field_spec.get('type', 'str'),
                'description': field_spec.get('description', field_name)
            }
            if field_spec.get('type') == 'categorical' and field_spec.get('categories'):
                processed_fields[field_name]['categories'] = [
                    cat.strip() for cat in field_spec['categories'].split(',') 
                    if cat.strip()
                ]
                # Calculate max per category for balancing
                processed_fields[field_name]['max_per_category'] = max(
                    1, 
                    record_count // len(processed_fields[field_name]['categories'])
                )
        
        # Use your real extraction implementation
        from utils.structured_extractor import extract_structured_data
        all_results = extract_structured_data(query, processed_fields, record_count)
        
        # Filter results
        filtered_results = [
            record for record in all_results
            if sum(1 for value in record.values() if value == "N/A" or value == "" or value is None) < len(record) // 2
        ]
        
        if not filtered_results:
            return jsonify({"error": "No valid data extracted. Try adjusting your field specifications."}), 404
        
        return jsonify({
            "preview_data": filtered_results,
            "total_records": len(filtered_results)
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/download_dataset', methods=['POST'])
def download_dataset():
    try:
        data = request.json
        filtered_results = data.get('data')
        output_format = data.get('format', 'csv')
        preprocessing = data.get('preprocessing', {})
        
        if not filtered_results:
            return jsonify({"error": "No data to download"}), 400
        
        # Apply preprocessing
        processed_data = apply_preprocessing(filtered_results, preprocessing)
        
        # Convert to requested format
        if output_format == 'csv':
            output = io.StringIO()
            pd.DataFrame(processed_data).to_csv(output, index=False)
            output.seek(0)
            return send_file(
                io.BytesIO(output.getvalue().encode()),
                mimetype='text/csv',
                as_attachment=True,
                download_name='dataset.csv'
            )
        elif output_format == 'json':
            return send_file(
                io.BytesIO(json.dumps(processed_data, indent=2).encode()),
                mimetype='application/json',
                as_attachment=True,
                download_name='dataset.json'
            )
        elif output_format == 'xml':
            xml_data = dicttoxml.dicttoxml(processed_data)
            return send_file(
                io.BytesIO(xml_data),
                mimetype='application/xml',
                as_attachment=True,
                download_name='dataset.xml'
            )
        else:
            return jsonify({"error": "Unsupported output format"}), 400
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def apply_preprocessing(data, preprocessing):
    """Apply all preprocessing steps to the data"""
    if not data:
        return []
    
    # Convert to DataFrame for easier manipulation
    df = pd.DataFrame(data)
    
    # Handle null values
    if preprocessing.get('handle_nulls'):
        for col, strategy in preprocessing['handle_nulls'].items():
            if col not in df.columns:
                continue
                
            if strategy == 'drop_row':
                df = df.dropna(subset=[col])
            elif strategy == 'drop_column':
                df = df.drop(columns=[col])
            elif strategy == 'fill_mean' and pd.api.types.is_numeric_dtype(df[col]):
                df[col] = df[col].fillna(df[col].mean())
            elif strategy == 'fill_median' and pd.api.types.is_numeric_dtype(df[col]):
                df[col] = df[col].fillna(df[col].median())
            elif strategy == 'fill_mode':
                df[col] = df[col].fillna(df[col].mode()[0] if not df[col].mode().empty else None)
    
    # Apply normalization
    if preprocessing.get('normalization'):
        for col, method in preprocessing['normalization'].items():
            if col not in df.columns:
                continue
                
            if method == 'minmax' and pd.api.types.is_numeric_dtype(df[col]):
                min_val = df[col].min()
                max_val = df[col].max()
                if max_val != min_val:
                    df[col] = (df[col] - min_val) / (max_val - min_val)
                else:
                    df[col] = 0
            elif method == 'zscore' and pd.api.types.is_numeric_dtype(df[col]):
                mean_val = df[col].mean()
                std_val = df[col].std()
                if std_val != 0:
                    df[col] = (df[col] - mean_val) / std_val
                else:
                    df[col] = 0
    
    # Apply encoding
    if preprocessing.get('encoding'):
        for col, method in preprocessing['encoding'].items():
            if col not in df.columns:
                continue
                
            if method == 'label':
                df[col] = pd.factorize(df[col])[0]
            elif method == 'onehot':
                dummies = pd.get_dummies(df[col], prefix=col)
                df = pd.concat([df.drop(columns=[col]), dummies], axis=1)
    
    return df.to_dict('records')
@app.route('/preview_preprocessed', methods=['POST'])
def preview_preprocessed():
    try:
        data = request.json
        filtered_results = data.get('data')
        preprocessing = data.get('preprocessing', {})
        
        if not filtered_results:
            return jsonify({"error": "No data to preprocess"}), 400
        
        # Apply preprocessing
        processed_data = apply_preprocessing(filtered_results, preprocessing)
        
        return jsonify(processed_data)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)