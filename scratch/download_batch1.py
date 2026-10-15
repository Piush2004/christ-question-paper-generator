import urllib.request
import csv
import hashlib
import time
import datetime
from pathlib import Path

def download_batch_1():
    base_dir = Path("d:/Projects/Christ Question Paper model/data/raw/knowledgepro")
    catalog_path = base_dir / "discovery" / "bca_catalog.csv"
    docs_dir = base_dir / "documents"
    manifest_path = base_dir / "manifests" / "knowledgepro_manifest.csv"
    
    docs_dir.mkdir(parents=True, exist_ok=True)
    base_dir.joinpath("manifests").mkdir(exist_ok=True)
    
    with open(catalog_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        catalog = list(reader)
        
    sem1 = [row for row in catalog if row['semester'] == '1']
    print(f"Starting BATCH 1: Semester 1 ({len(sem1)} papers)")
    
    manifest_exists = manifest_path.exists()
    
    # We will log everything to manifest
    fieldnames = [
        'record_id', 'source_platform', 'programme', 'semester', 'course_name', 
        'course_code', 'exam_type', 'original_filename', 'source_url', 
        'download_timestamp', 'local_path', 'file_size_bytes', 'sha256', 
        'mime_type', 'validation_status', 'metadata_provenance'
    ]
    
    with open(manifest_path, 'a', newline='', encoding='utf-8') as mf:
        writer = csv.DictWriter(mf, fieldnames=fieldnames)
        if not manifest_exists:
            writer.writeheader()
            
        for idx, row in enumerate(sem1):
            url = row['download_url']
            original_filename = url.split('/')[-1]
            local_file = docs_dir / original_filename
            
            print(f"[{idx+1}/{len(sem1)}] Downloading {original_filename}...")
            
            try:
                # Add headers to avoid 403
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=15) as res:
                    data = res.read()
                
                # Validation (PDF magic bytes)
                validation_status = 'VALID_PDF' if data.startswith(b'%PDF') else 'INVALID'
                
                # Checksum
                sha256_hash = hashlib.sha256(data).hexdigest()
                file_size = len(data)
                
                # Save identical bytes
                with open(local_file, 'wb') as df:
                    df.write(data)
                
                # Write manifest row
                writer.writerow({
                    'record_id': f"KP_BCA_SEM1_{idx:03d}",
                    'source_platform': 'Knowledge Pro / Data Bank',
                    'programme': row['programme'],
                    'semester': row['semester'],
                    'course_name': row['course_name'],
                    'course_code': row['course_code'],
                    'exam_type': row['exam_name'],
                    'original_filename': original_filename,
                    'source_url': url,
                    'download_timestamp': datetime.datetime.now().isoformat(),
                    'local_path': str(local_file.relative_to(base_dir)),
                    'file_size_bytes': file_size,
                    'sha256': sha256_hash,
                    'mime_type': 'application/pdf' if validation_status == 'VALID_PDF' else 'application/octet-stream',
                    'validation_status': validation_status,
                    'metadata_provenance': 'SOURCE_VISIBLE'
                })
                mf.flush()
                
            except Exception as e:
                print(f"Failed to download {original_filename}: {e}")
                writer.writerow({
                    'record_id': f"KP_BCA_SEM1_{idx:03d}",
                    'source_platform': 'Knowledge Pro / Data Bank',
                    'programme': row['programme'],
                    'semester': row['semester'],
                    'course_name': row['course_name'],
                    'course_code': row['course_code'],
                    'exam_type': row['exam_name'],
                    'original_filename': original_filename,
                    'source_url': url,
                    'download_timestamp': datetime.datetime.now().isoformat(),
                    'local_path': '',
                    'file_size_bytes': 0,
                    'sha256': '',
                    'mime_type': '',
                    'validation_status': 'FAILED',
                    'metadata_provenance': 'SOURCE_VISIBLE'
                })
                mf.flush()
                
            time.sleep(1) # Polite delay
            
    print("Batch 1 acquisition complete.")

if __name__ == '__main__':
    download_batch_1()
