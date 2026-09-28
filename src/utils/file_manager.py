import os
from datetime import datetime

def create_job_folder():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    job_id = f"job_{timestamp}"
    
    base_path = os.path.join("/app/jobs", job_id)  
    sub_folders = ["images", "audios", "video"]
    
    for folder in sub_folders:
        os.makedirs(os.path.join(base_path, folder), exist_ok=True)
        
    return base_path, job_id