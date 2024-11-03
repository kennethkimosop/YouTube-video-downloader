// Static/js/app.js
document.getElementById('downloadForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const statusDiv = document.getElementById('status');
    const submitBtn = document.getElementById('submitBtn');
    
    try {
        // Disable button and show loading state
        submitBtn.disabled = true;
        statusDiv.innerHTML = 'Starting download...';
        
        // Get form values
        const url = document.getElementById('url').value;
        const quality = document.getElementById('quality').value;
        const fileType = document.getElementById('fileType').value;
        
        // Make API request to start download
        const response = await fetch('/api/download', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url, quality, file_type: fileType })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Download failed');
        }
        
        const data = await response.json();
        statusDiv.innerHTML = `Processing: ${data.title}`;
        
        // Poll for status
        while (true) {
            const statusResponse = await fetch(`/api/status/${data.download_id}`);
            const statusData = await statusResponse.json();
            
            if (statusData.status === 'completed') {
                // Create download link
                const downloadUrl = `/api/download/${data.download_id}`;
                statusDiv.innerHTML = `
                    <p>Download ready!</p>
                    <p>Title: ${data.title}</p>
                    <p>Author: ${data.author}</p>
                    <a href="${downloadUrl}" class="download-link">Click here to download</a>
                `;
                break;
            } else if (statusData.status === 'error') {
                throw new Error(statusData.detail || 'Download failed');
            }
            
            // Wait before polling again
            await new Promise(resolve => setTimeout(resolve, 1000));
        }
    } catch (error) {
        statusDiv.innerHTML = `Error: ${error.message}`;
        console.error('Download error:', error);
    } finally {
        submitBtn.disabled = false;
    }
});