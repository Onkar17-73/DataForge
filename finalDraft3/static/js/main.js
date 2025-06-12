document.addEventListener('DOMContentLoaded', function() {
    // Global variables
    let currentDataset = [];
    let currentPage = 1;
    let itemsPerPage = 10;
    let preprocessingSteps = {
        handle_nulls: {},
        normalization: {},
        encoding: {}
    };

    // Initialize field type change listeners
    document.addEventListener('change', function(e) {
        if (e.target.classList.contains('field-type')) {
            const row = e.target.closest('.field-row');
            const categoriesInput = row.querySelector('.field-categories');
            if (e.target.value === 'categorical') {
                categoriesInput.classList.remove('d-none');
            } else {
                categoriesInput.classList.add('d-none');
            }
        }
    });

    // Add field button
    const addFieldBtn = document.getElementById('addFieldBtn');
    if (addFieldBtn) {
        addFieldBtn.addEventListener('click', function() {
            const fieldsContainer = document.getElementById('fieldsContainer');
            const fieldRow = document.createElement('div');
            fieldRow.className = 'row field-row mb-2';
            fieldRow.innerHTML = `
                <div class="col-md-4">
                    <input type="text" class="form-control field-name" placeholder="Field Name" required>
                </div>
                <div class="col-md-4">
                    <input type="text" class="form-control field-description" placeholder="Description">
                </div>
                <div class="col-md-3">
                    <select class="form-select field-type">
                        <option value="str">String</option>
                        <option value="number">Number</option>
                        <option value="bool">Boolean</option>
                        <option value="categorical">Categorical</option>
                    </select>
                </div>
                <div class="col-md-3 field-categories d-none">
                    <input type="text" class="form-control" placeholder="Categories (comma separated)">
                </div>
                <div class="col-md-1">
                    <button type="button" class="btn btn-outline-danger btn-sm remove-field">X</button>
                </div>
            `;
            fieldsContainer.appendChild(fieldRow);
            
            fieldRow.querySelector('.remove-field').addEventListener('click', function() {
                fieldsContainer.removeChild(fieldRow);
            });
        });
    }
    
    // Initial remove field buttons
    document.querySelectorAll('.remove-field').forEach(button => {
        button.addEventListener('click', function() {
            const row = this.closest('.field-row');
            row.parentNode.removeChild(row);
        });
    });
    
    // Structured data form submission
    const structuredForm = document.getElementById('structuredForm');
    if (structuredForm) {
        structuredForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // Show loading indicator
            const loadingIndicator = document.getElementById('loadingIndicator');
            const statusAlert = document.getElementById('statusAlert');
            
            if (loadingIndicator) loadingIndicator.classList.remove('d-none');
            if (statusAlert) {
                statusAlert.classList.remove('d-none');
                statusAlert.textContent = "Preparing your structured dataset...";
                statusAlert.className = 'alert alert-info mt-4';
            }
            
            // Collect field data
            const fields = {};
            document.querySelectorAll('.field-row').forEach(row => {
                const name = row.querySelector('.field-name').value.trim();
                const description = row.querySelector('.field-description').value.trim();
                const type = row.querySelector('.field-type').value;
                const categories = type === 'categorical' ? 
                    row.querySelector('.field-categories input').value.trim() : '';
                
                if (name) {
                    fields[name] = {
                        description: description || name,
                        type: type
                    };
                    if (categories) {
                        fields[name].categories = categories;
                    }
                }
            });
            
            // Prepare request data
            const queryInput = document.getElementById('query');
            const recordCountInput = document.getElementById('recordCount');
            
            const requestData = {
                query: queryInput ? queryInput.value.trim() : '',
                fields: fields,
                record_count: recordCountInput ? parseInt(recordCountInput.value) : 10
            };
            
            // Send request to server
            fetch('/extract_structured', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestData)
            })
            .then(response => {
                if (loadingIndicator) loadingIndicator.classList.add('d-none');
                
                if (response.ok) {
                    return response.json();
                } else {
                    return response.json().then(data => {
                        throw new Error(data.error || "Failed to extract data");
                    });
                }
            })
            .then(data => {
                if (data.error) throw new Error(data.error);
                
                // Store the data globally for download
                window.currentDataset = data.preview_data;
                
                // Show preview
                showDataPreview(data.preview_data);
                
                // Update status
                if (statusAlert) {
                    statusAlert.className = 'alert alert-success mt-4';
                    statusAlert.textContent = `Found ${data.total_records} records. Review and download below.`;
                    setTimeout(() => statusAlert.classList.add('d-none'), 3000);
                }
            })
            .catch(error => {
                showError(error.message);
            });
        });
    }
    
    // Image dataset form submission
    const imagesForm = document.getElementById('imagesForm');
    if (imagesForm) {
        imagesForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const loadingIndicator = document.getElementById('loadingIndicator');
            const statusAlert = document.getElementById('statusAlert');
            const submitBtn = this.querySelector('button[type="submit"]');
            
            // Disable button during processing
            submitBtn.disabled = true;
            if (loadingIndicator) loadingIndicator.classList.remove('d-none');
            if (statusAlert) {
                statusAlert.classList.remove('d-none');
                statusAlert.textContent = "Collecting image dataset...";
                statusAlert.className = 'alert alert-info mt-4';
            }
            
            const categoriesInput = document.getElementById('categories');
            const sizeInput = document.getElementById('size');
            
            const requestData = {
                categories: categoriesInput ? categoriesInput.value.trim() : '',
                size: sizeInput ? parseInt(sizeInput.value) : 5,
                processing: {
                    greyscale: document.getElementById('greyscaleCheck').checked,
                    normalize: document.getElementById('normalizeCheck').checked,
                    resize: {
                        width: parseInt(document.querySelector('.resize-width').value) || 224,
                        height: parseInt(document.querySelector('.resize-height').value) || 224
                    },
                    format: document.querySelector('.image-format-select').value
                }
            };
            
            if (!requestData.categories) {
                showError("Please enter at least one category");
                submitBtn.disabled = false;
                return;
            }
            
            fetch('/extract_images', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(requestData)
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(err => { throw new Error(err.error); });
                }
                return response.blob();
            })
            .then(blob => {
                // Check if blob is too small to be valid
                if (blob.size < 1024) {  // At least 1KB
                    throw new Error("No images found for these categories. Try different search terms.");
                }
                
                showSuccess("Downloading image dataset...");
                triggerDownload(blob, 'image_dataset.zip');
            })
            .catch(error => {
                showError(error.message);
            })
            .finally(() => {
                if (loadingIndicator) loadingIndicator.classList.add('d-none');
                submitBtn.disabled = false;
            });
        });
    }

    // Helper functions
    function showError(message) {
        const statusAlert = document.getElementById('statusAlert');
        if (statusAlert) {
            statusAlert.className = 'alert alert-danger mt-4';
            statusAlert.textContent = "Error: " + message;
            setTimeout(() => statusAlert.classList.add('d-none'), 5000);
        }
    }

    function showSuccess(message) {
        const statusAlert = document.getElementById('statusAlert');
        if (statusAlert) {
            statusAlert.className = 'alert alert-success mt-4';
            statusAlert.textContent = message;
            setTimeout(() => statusAlert.classList.add('d-none'), 3000);
        }
    }

    function triggerDownload(blob, filename) {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    }

// Add this to your main.js
function showDataPreview(data) {
    currentDataset = data;
    currentPage = 1;
    itemsPerPage = parseInt(document.querySelector('.items-per-page').value) || 10;
    
    const previewSection = document.getElementById('previewSection');
    previewSection.classList.remove('d-none');
    
    // Populate column selects
    updateColumnSelects();
    
    // Render initial data
    renderPaginatedData();
}

function updateColumnSelects() {
    if (!currentDataset || currentDataset.length === 0) return;
    
    const columns = Object.keys(currentDataset[0]);
    
    // Update all column dropdowns
    document.querySelectorAll('.null-column-select, .numeric-column-select, .categorical-column-select').forEach(select => {
        const currentValue = select.value;
        select.innerHTML = '<option value="">Select column</option>' + 
            columns.map(col => `<option value="${col}">${col}</option>`).join('');
        
        // Restore previous selection if still available
        if (columns.includes(currentValue)) {
            select.value = currentValue;
        }
    });
}

function renderPaginatedData(data = null) {
    const previewTable = document.getElementById('previewTable');
    const paginationControls = document.getElementById('paginationControls');
    
    // Use provided data or fall back to currentDataset
    const displayData = data || currentDataset;
    const columns = Object.keys(displayData[0] || {});
    
    // Calculate pagination
    const totalPages = itemsPerPage > 0 ? Math.ceil(displayData.length / itemsPerPage) : 1;
    const startIdx = itemsPerPage > 0 ? (currentPage - 1) * itemsPerPage : 0;
    const endIdx = itemsPerPage > 0 ? startIdx + itemsPerPage : displayData.length;
    const pageData = displayData.slice(startIdx, endIdx);
    
    // Create table headers
    previewTable.querySelector('thead').innerHTML = '';
    const headerRow = document.createElement('tr');
    columns.forEach(col => {
        const th = document.createElement('th');
        th.textContent = col;
        headerRow.appendChild(th);
    });
    previewTable.querySelector('thead').appendChild(headerRow);
    
    // Create table rows
    previewTable.querySelector('tbody').innerHTML = '';
    pageData.forEach(row => {
        const tr = document.createElement('tr');
        columns.forEach(col => {
            const td = document.createElement('td');
            // Handle array values (like one-hot encoded columns)
            const value = Array.isArray(row[col]) ? row[col].join(', ') : row[col];
            td.textContent = value || 'N/A';
            if (row[col] === "N/A" || row[col] === "" || row[col] === null) {
                td.classList.add('text-danger');
            }
            tr.appendChild(td);
        });
        previewTable.querySelector('tbody').appendChild(tr);
    });
    
    // Create pagination controls
    updatePaginationControls(totalPages);
    
    // Update items per page selector
    document.querySelector('.items-per-page').addEventListener('change', function() {
        itemsPerPage = parseInt(this.value) || 10;
        currentPage = 1;
        renderPaginatedData();
    });
}

function updatePaginationControls(totalPages) {
    const paginationControls = document.getElementById('paginationControls');
    paginationControls.innerHTML = '';
    
    // Previous button
    const prevLi = document.createElement('li');
    prevLi.className = `page-item ${currentPage === 1 ? 'disabled' : ''}`;
    prevLi.innerHTML = `<a class="page-link" href="#">Previous</a>`;
    prevLi.addEventListener('click', (e) => {
        e.preventDefault();
        if (currentPage > 1) {
            currentPage--;
            renderPaginatedData();
        }
    });
    paginationControls.appendChild(prevLi);
    
    // Page numbers
    const maxVisiblePages = 5;
    let startPage = Math.max(1, currentPage - Math.floor(maxVisiblePages/2));
    let endPage = Math.min(totalPages, startPage + maxVisiblePages - 1);
    
    if (endPage - startPage + 1 < maxVisiblePages) {
        startPage = Math.max(1, endPage - maxVisiblePages + 1);
    }
    
    for (let i = startPage; i <= endPage; i++) {
        const pageLi = document.createElement('li');
        pageLi.className = `page-item ${i === currentPage ? 'active' : ''}`;
        pageLi.innerHTML = `<a class="page-link" href="#">${i}</a>`;
        pageLi.addEventListener('click', (e) => {
            e.preventDefault();
            currentPage = i;
            renderPaginatedData();
        });
        paginationControls.appendChild(pageLi);
    }
    
    // Next button
    const nextLi = document.createElement('li');
    nextLi.className = `page-item ${currentPage === totalPages ? 'disabled' : ''}`;
    nextLi.innerHTML = `<a class="page-link" href="#">Next</a>`;
    nextLi.addEventListener('click', (e) => {
        e.preventDefault();
        if (currentPage < totalPages) {
            currentPage++;
            renderPaginatedData();
        }
    });
    paginationControls.appendChild(nextLi);
}

function applyPreprocessingAndUpdatePreview() {
    if (!window.currentDataset || window.currentDataset.length === 0) {
        showError("No data available to preview");
        return;
    }

    // Show loading indicator
    const loadingIndicator = document.getElementById('loadingIndicator');
    if (loadingIndicator) loadingIndicator.classList.remove('d-none');

    // Get current preprocessing steps
    const preprocessingSteps = {
        handle_nulls: {},
        normalization: {},
        encoding: {}
    };

    // Collect null handling strategies
    document.querySelectorAll('#nullHandlingList > div').forEach(item => {
        const col = item.querySelector('span:nth-child(2)').textContent;
        const strategy = item.querySelector('.badge').textContent.toLowerCase().includes('drop column') ? 'drop_column' : 'drop_row';
        preprocessingSteps.handle_nulls[col] = strategy;
    });

    // Collect normalization methods
    document.querySelectorAll('#featureEngineeringList > div').forEach(item => {
        const col = item.querySelector('span:nth-child(2)').textContent;
        const badgeText = item.querySelector('.badge').textContent.toLowerCase();
        
        if (badgeText.includes('normalize')) {
            preprocessingSteps.normalization[col] = 'minmax';
        } else if (badgeText.includes('standardize')) {
            preprocessingSteps.normalization[col] = 'zscore';
        } else if (badgeText.includes('label')) {
            preprocessingSteps.encoding[col] = 'label';
        } else if (badgeText.includes('one-hot')) {
            preprocessingSteps.encoding[col] = 'onehot';
        }
    });

    // Send to server for preprocessing
    fetch('/preview_preprocessed', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            data: window.currentDataset,
            preprocessing: preprocessingSteps
        })
    })
    .then(response => {
        if (loadingIndicator) loadingIndicator.classList.add('d-none');
        
        if (response.ok) {
            return response.json();
        } else {
            return response.json().then(data => {
                throw new Error(data.error || "Failed to preprocess data");
            });
        }
    })
    .then(data => {
        // Update the preview with preprocessed data
        renderPaginatedData(data);
    })
    .catch(error => {
        showError(error.message);
    });
}

// Add event listeners for preprocessing buttons
document.querySelectorAll('.remove-nulls-btn, .drop-column-btn, .normalize-btn, .standardize-btn, .label-encode-btn, .onehot-encode-btn').forEach(btn => {
    btn.addEventListener('click', function() {
        setTimeout(applyPreprocessingAndUpdatePreview, 100);
    });
});

// Add event listener for preview changes button
document.getElementById('previewChangesBtn')?.addEventListener('click', applyPreprocessingAndUpdatePreview);

// Add event listener for items per page change
document.querySelector('.items-per-page')?.addEventListener('change', function() {
    itemsPerPage = parseInt(this.value) || 10;
    currentPage = 1;
    renderPaginatedData();
});
    // Handle null value removal
    document.querySelector('.remove-nulls-btn')?.addEventListener('click', function() {
        const column = document.querySelector('.null-column-select').value;
        if (!column) {
            showError("Please select a column first");
            return;
        }
        
        preprocessingSteps.handle_nulls[column] = 'drop_row';
        addPreprocessingStep('null', column, 'Remove rows with nulls');
    });

    // Handle column dropping
    document.querySelector('.drop-column-btn')?.addEventListener('click', function() {
        const column = document.querySelector('.null-column-select').value;
        if (!column) {
            showError("Please select a column first");
            return;
        }
        
        preprocessingSteps.handle_nulls[column] = 'drop_column';
        addPreprocessingStep('null', column, 'Drop entire column');
    });

    // Handle normalization
    document.querySelector('.normalize-btn')?.addEventListener('click', function() {
        const column = document.querySelector('.numeric-column-select').value;
        if (!column) {
            showError("Please select a column first");
            return;
        }
        
        preprocessingSteps.normalization[column] = 'minmax';
        addPreprocessingStep('normalization', column, 'Normalize (0-1)');
    });

    // Handle standardization
    document.querySelector('.standardize-btn')?.addEventListener('click', function() {
        const column = document.querySelector('.numeric-column-select').value;
        if (!column) {
            showError("Please select a column first");
            return;
        }
        
        preprocessingSteps.normalization[column] = 'zscore';
        addPreprocessingStep('normalization', column, 'Standardize (Z-score)');
    });

    // Handle label encoding
    document.querySelector('.label-encode-btn')?.addEventListener('click', function() {
        const column = document.querySelector('.categorical-column-select').value;
        if (!column) {
            showError("Please select a column first");
            return;
        }
        
        preprocessingSteps.encoding[column] = 'label';
        addPreprocessingStep('encoding', column, 'Label encode');
    });

    // Handle one-hot encoding
    document.querySelector('.onehot-encode-btn')?.addEventListener('click', function() {
        const column = document.querySelector('.categorical-column-select').value;
        if (!column) {
            showError("Please select a column first");
            return;
        }
        
        preprocessingSteps.encoding[column] = 'onehot';
        addPreprocessingStep('encoding', column, 'One-hot encode');
    });

    // Helper function to add preprocessing step to UI
    function addPreprocessingStep(type, column, description) {
        let container, badgeClass;
        
        if (type === 'null') {
            container = document.getElementById('nullHandlingList');
            badgeClass = 'bg-warning text-dark';
        } else if (type === 'normalization') {
            container = document.getElementById('featureEngineeringList');
            badgeClass = 'bg-success';
        } else if (type === 'encoding') {
            container = document.getElementById('featureEngineeringList');
            badgeClass = 'bg-info';
        } else {
            return;
        }
        
        const item = document.createElement('div');
        item.className = 'd-flex align-items-center mb-2 p-2 bg-light rounded';
        item.innerHTML = `
            <span class="badge ${badgeClass} me-2">${description}</span>
            <span>${column}</span>
            <button class="btn btn-sm btn-outline-danger ms-auto remove-btn">×</button>
        `;
        
        container.appendChild(item);
        
        item.querySelector('.remove-btn').addEventListener('click', function() {
            item.remove();
            if (type === 'null') {
                delete preprocessingSteps.handle_nulls[column];
            } else if (type === 'normalization') {
                delete preprocessingSteps.normalization[column];
            } else if (type === 'encoding') {
                delete preprocessingSteps.encoding[column];
            }
        });
    }

    // Handle download button click
    document.getElementById('downloadBtn')?.addEventListener('click', function() {
        if (!window.currentDataset || window.currentDataset.length === 0) {
            showError("No data available to download");
            return;
        }
        
        const formatInput = document.querySelector('input[name="downloadFormat"]:checked');
        
        const requestData = {
            data: window.currentDataset,
            format: formatInput ? formatInput.value : 'csv',
            preprocessing: preprocessingSteps
        };
        
        // Show loading
        const loadingIndicator = document.getElementById('loadingIndicator');
        if (loadingIndicator) loadingIndicator.classList.remove('d-none');
        
        fetch('/download_dataset', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestData)
        })
        .then(response => {
            if (response.ok) {
                return response.blob();
            } else {
                return response.json().then(data => {
                    throw new Error(data.error || "Failed to download dataset");
                });
            }
        })
        .then(blob => {
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            
            // Set the file name based on format
            let fileName = 'dataset';
            switch(requestData.format) {
                case 'json': fileName += '.json'; break;
                case 'xml': fileName += '.xml'; break;
                default: fileName += '.csv';
            }
            
            a.download = fileName;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
        })
        .catch(error => {
            showError(error.message);
        })
        .finally(() => {
            if (loadingIndicator) loadingIndicator.classList.add('d-none');
        });
    });
    // Add this to your event listeners
document.getElementById('previewChangesBtn')?.addEventListener('click', applyPreprocessingAndUpdatePreview);
    // Initialize Bootstrap tabs
    const tabElms = document.querySelectorAll('button[data-bs-toggle="tab"]');
    tabElms.forEach(tabEl => {
        tabEl.addEventListener('shown.bs.tab', function (event) {
            // Reset status alert when switching tabs
            const statusAlert = document.getElementById('statusAlert');
            if (statusAlert) {
                statusAlert.classList.add('d-none');
            }
        });
    });
});
