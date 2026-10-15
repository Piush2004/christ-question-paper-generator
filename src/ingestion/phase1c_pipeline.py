import os
import sys
import hashlib
import json
import csv
from pathlib import Path
from datetime import datetime

# Add the project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.ingestion.loaders import load_document, DocumentLoadError, EncryptedDocumentError, UnsupportedFormatError
from src.extraction.engine import QuestionExtractor
import dataclasses

def compute_sha256(filepath):
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        if isinstance(o, Path):
            return str(o)
        return super().default(o)

def run_pipeline(input_dir, output_dir, manifest_path):
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Inventory & Hashes
    all_files = list(input_dir.glob("*.pdf"))
    file_hashes = {}
    duplicates = set()
    
    print(f"Phase 1C Pipeline Starting. Found {len(all_files)} files.")
    
    # Identify duplicates
    for fp in all_files:
        h = compute_sha256(fp)
        if h in file_hashes:
            duplicates.add(fp)
            print(f"Duplicate detected: {fp.name} matches {file_hashes[h].name}")
        else:
            file_hashes[h] = fp
            
    manifest_rows = []
    
    extractor = QuestionExtractor()
    
    # Metrics
    metrics = {
        'total_files': len(all_files),
        'valid_files': 0,
        'failed_files': 0,
        'duplicates': len(duplicates),
        'total_sections': 0,
        'total_questions': 0,
        'total_subquestions': 0,
        'total_alternatives': 0
    }
    
    for idx, fp in enumerate(all_files):
        print(f"[{idx+1}/{len(all_files)}] Processing {fp.name}...")
        h = compute_sha256(fp)
        
        status = 'UNKNOWN'
        error_msg = ''
        questions = []
        page_count = 0
        
        try:
            doc = load_document(fp)
            page_count = len(doc.pages)
            questions = extractor.extract(doc)
            
            status = 'SUCCESS'
            metrics['valid_files'] += 1
            
            # Basic stats
            secs = set()
            for q in questions:
                if q.section_label: secs.add(q.section_label)
                if getattr(q, 'is_subquestion', False):
                    metrics['total_subquestions'] += 1
                else:
                    metrics['total_questions'] += 1
                if getattr(q, 'is_alternative', False):
                    metrics['total_alternatives'] += 1
            metrics['total_sections'] += len(secs)
            
            # Save structured output
            out_json = output_dir / f"{h}.json"
            with open(out_json, "w", encoding="utf-8") as f:
                json.dump({
                    "source_file": fp.name,
                    "source_hash": h,
                    "questions": questions
                }, f, cls=EnhancedJSONEncoder, indent=2)
                
        except EncryptedDocumentError:
            status = 'ENCRYPTED'
            metrics['failed_files'] += 1
            error_msg = 'Encrypted document'
        except DocumentLoadError as e:
            status = 'FAILED_LOAD'
            metrics['failed_files'] += 1
            error_msg = str(e)
        except Exception as e:
            status = 'FAILED_EXTRACTION'
            metrics['failed_files'] += 1
            error_msg = str(e)
            
        manifest_rows.append({
            'dataset_version': '1.0',
            'extraction_version': '1C',
            'timestamp': datetime.utcnow().isoformat(),
            'source': 'DATA_BANK',
            'file_name': fp.name,
            'file_path': str(fp.resolve()),
            'file_hash': h,
            'is_duplicate': fp in duplicates,
            'status': status,
            'page_count': page_count,
            'extracted_questions': len(questions),
            'error_message': error_msg
        })
        
    print("\nExtraction Complete. Saving manifest...")
    
    with open(manifest_path, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = manifest_rows[0].keys()
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(manifest_rows)
        
    print("Metrics:")
    for k, v in metrics.items():
        print(f"  {k}: {v}")
    
    print("\nPipeline complete.")

if __name__ == "__main__":
    run_pipeline(
        input_dir="data/raw/databank",
        output_dir="data/interim/extraction/databank",
        manifest_path="data/interim/extraction/databank_manifest.csv"
    )
