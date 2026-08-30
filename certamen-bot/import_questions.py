import glob
import csv
import json
import os
import re

FILE_CONFIG = {
    'culture_daily_life.csv': {'category': 'culture', 'difficulty': 'intermediate', 'prefix': 'cult'},
    'derivative.csv': {'category': 'grammar', 'difficulty': 'intermediate', 'prefix': 'deriv'},
    'empire.csv': {'category': 'history', 'difficulty': 'intermediate', 'prefix': 'emp'},
    'gmdr.csv': {'category': 'grammar', 'difficulty': 'advanced', 'prefix': 'gmdr'},
    'gmdr_a-n.csv': {'category': 'grammar', 'difficulty': 'advanced', 'prefix': 'gmdran'},
    'grammar.csv': {'category': 'grammar', 'difficulty': 'intermediate', 'prefix': 'gram'},
    'greek_derivatives.csv': {'category': 'grammar', 'difficulty': 'advanced', 'prefix': 'gkderiv'},
    'history.csv': {'category': 'history', 'difficulty': 'intermediate', 'prefix': 'hist'},
    'literature.csv': {'category': 'literature', 'difficulty': 'intermediate', 'prefix': 'lit'},
    'mixed.csv': {'category': 'culture', 'difficulty': 'intermediate', 'prefix': 'mix'},
    'myth.csv': {'category': 'mythology', 'difficulty': 'intermediate', 'prefix': 'myth'},
    'pmaq.csv': {'category': 'culture', 'difficulty': 'advanced', 'prefix': 'pmaq'},
    'pw.csv': {'category': 'history', 'difficulty': 'advanced', 'prefix': 'pw'},
    'translation.csv': {'category': 'grammar', 'difficulty': 'intermediate', 'prefix': 'trans'},
    'LFIFTH_inflection.csv': {'category': 'grammar', 'difficulty': 'novice', 'prefix': 'l5inf'},
    'LHALF_inflection.csv': {'category': 'grammar', 'difficulty': 'novice', 'prefix': 'lhinf'},
    'L1_inflection.csv': {'category': 'grammar', 'difficulty': 'novice', 'prefix': 'l1inf'},
    'L2_inflection.csv': {'category': 'grammar', 'difficulty': 'intermediate', 'prefix': 'l2inf'},
    'LADV_inflection.csv': {'category': 'grammar', 'difficulty': 'advanced', 'prefix': 'ladvinf'},
    'inflection.csv': {'category': 'grammar', 'difficulty': 'intermediate', 'prefix': 'inf'},
}

def parse_answers(ans_raw):
    ans_raw = ans_raw.strip()
    answers = []
    
    parts = re.split(r'\s*\(or\s+|\s+or\s+|\s*;\s*', ans_raw, flags=re.IGNORECASE)
    for p in parts:
        cleaned = p.strip().rstrip(')').strip()
        cleaned = re.sub(r'^[`\'"]|[`\'"]$', '', cleaned).strip()
        if cleaned and cleaned not in answers:
            answers.append(cleaned)
    if not answers:
        answers = [ans_raw]
    return answers

def main():
    json_path = 'src/data/questions.json'
    with open(json_path, 'r', encoding='utf-8') as f:
        existing_questions = json.load(f)
    print(f"Initial questions.json count: {len(existing_questions)}")

    existing_ids = {q['id'] for q in existing_questions}
    all_questions = list(existing_questions)

    for fname, cfg in FILE_CONFIG.items():
        fpath = os.path.join('questions', fname)
        if not os.path.exists(fpath):
            print(f"Skipping missing file: {fpath}")
            continue
        
        with open(fpath, 'r', encoding='utf-8', errors='ignore') as fp:
            reader = csv.reader(fp)
            file_q_count = 0
            for idx, row in enumerate(reader):
                if not row or len(row) < 2:
                    continue
                qid = row[0].strip()
                tossup = row[1].strip()
                ans_raw = row[2].strip() if len(row) > 2 else ''

                tossup = tossup.replace('\\n', '\n').replace('>', ',')
                
                if not tossup or not ans_raw:
                    continue
                
                final_id = f"{cfg['prefix']}-{qid}" if qid else f"{cfg['prefix']}-{idx+1}"
                if final_id in existing_ids:
                    final_id = f"{final_id}-{idx+1}"
                existing_ids.add(final_id)
                
                answers = [a.replace('>', ',') for a in parse_answers(ans_raw)]
                
                q_obj = {
                    'id': final_id,
                    'category': cfg['category'],
                    'difficulty': cfg['difficulty'],
                    'tossup': tossup,
                    'answers': answers
                }
                all_questions.append(q_obj)
                file_q_count += 1
            print(f"Processed {fname}: {file_q_count} questions")

    print(f"Total questions generated: {len(all_questions)}")
    
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(all_questions, f, indent=2, ensure_ascii=False)
    print("Successfully written to src/data/questions.json")

if __name__ == '__main__':
    main()
