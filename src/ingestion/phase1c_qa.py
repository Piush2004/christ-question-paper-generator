import os
import json
import glob
from pathlib import Path

def analyze_json_extractions(input_dir):
    json_files = glob.glob(os.path.join(input_dir, "*.json"))
    
    total_files = len(json_files)
    stats = {
        'total_questions': 0,
        'missing_marks': 0,
        'missing_co': 0,
        'missing_rbt': 0,
        'missing_section': 0,
        'total_alternatives': 0
    }
    
    paper_issues = []
    
    for jf in json_files:
        with open(jf, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        questions = data.get('questions', [])
        file_issues = []
        
        has_sections = False
        
        for q in questions:
            stats['total_questions'] += 1
            if q.get('marks') is None:
                stats['missing_marks'] += 1
                file_issues.append(f"Missing marks on Q{q.get('question_number_raw')}")
            
            if q.get('course_outcome') is None:
                stats['missing_co'] += 1
            
            if q.get('bloom') is None:
                stats['missing_rbt'] += 1
                
            if q.get('section_label'):
                has_sections = True
            
            if q.get('is_alternative'):
                stats['total_alternatives'] += 1
                
        if not has_sections:
            stats['missing_section'] += 1
            file_issues.append("No sections detected")
            
        if file_issues:
            paper_issues.append({
                'file': data.get('source_file'),
                'issues': list(set(file_issues))[:3] # sample
            })
            
    print(f"Total Papers Analyzed: {total_files}")
    print(f"Total Questions: {stats['total_questions']}")
    print(f"Missing Marks: {stats['missing_marks']} ({(stats['missing_marks']/max(1, stats['total_questions']))*100:.1f}%)")
    print(f"Missing CO: {stats['missing_co']} ({(stats['missing_co']/max(1, stats['total_questions']))*100:.1f}%)")
    print(f"Missing RBT: {stats['missing_rbt']} ({(stats['missing_rbt']/max(1, stats['total_questions']))*100:.1f}%)")
    print(f"Papers Missing Sections: {stats['missing_section']} ({(stats['missing_section']/max(1, total_files))*100:.1f}%)")
    print(f"Total Alternatives (OR): {stats['total_alternatives']}")
    
    print("\nSample Issues:")
    for pi in paper_issues[:5]:
        print(f"  {pi['file']}: {', '.join(pi['issues'])}")

if __name__ == "__main__":
    analyze_json_extractions("data/interim/extraction/databank")
