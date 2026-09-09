import csv

manifest_path = 'public_release/06_exclusion_screening_pipeline/results/query_stage_manifest_gemini.csv'
lines = open(manifest_path, encoding='utf-8-sig').read().splitlines()
header = lines[0]
ok_lines = [header]

for l in lines[1:]:
    try:
        r = list(csv.reader([l]))[0]
        if len(r) == 14:
            ok_lines.append(l)
    except:
        pass

with open(manifest_path, 'w', encoding='utf-8-sig', newline='') as f:
    f.write('\n'.join(ok_lines) + '\n')
