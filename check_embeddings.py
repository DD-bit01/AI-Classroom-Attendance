import database as db
import numpy as np

conn = db.get_connection()
c = conn.cursor()
c.execute('''
    SELECT s.id as student_id, s.name, e.id as emb_id, e.source_photo, e.vector 
    FROM students s 
    JOIN student_embeddings e ON s.id = e.student_id
''')
rows = c.fetchall()
conn.close()

embs = np.array([np.frombuffer(r['vector'], dtype=np.float32) for r in rows])
print(f"Total enrolled embeddings: {len(rows)}")

# Intra-student consistency check
student_map = {}
for i, r in enumerate(rows):
    sid = r['student_id']
    if sid not in student_map:
        student_map[sid] = {'name': r['name'], 'indices': []}
    student_map[sid]['indices'].append(i)

print("\n--- INTRA-STUDENT CONSISTENCY CHECK ---")
bad_embs = []
for sid, data in student_map.items():
    idxs = data['indices']
    if len(idxs) > 1:
        sub_embs = embs[idxs]
        pairwise = sub_embs @ sub_embs.T
        for i in range(len(idxs)):
            for j in range(i+1, len(idxs)):
                sim = pairwise[i, j]
                if sim < 0.30:
                    e1 = rows[idxs[i]]
                    e2 = rows[idxs[j]]
                    print(f"SUSPICIOUS: {data['name']} (sid={sid}): emb {e1['emb_id']} vs {e2['emb_id']} sim={sim:.3f}")
                    print(f"   Photo 1: {e1['source_photo']}")
                    print(f"   Photo 2: {e2['source_photo']}")
                    bad_embs.append(e1['emb_id'])

print("\n--- INTER-STUDENT HIGH SIMILARITY CHECK ---")
for i in range(len(rows)):
    for j in range(i+1, len(rows)):
        if rows[i]['student_id'] != rows[j]['student_id']:
            sim = float(np.dot(embs[i], embs[j]))
            if sim >= 0.40:
                print(f"HIGH CROSS-MATCH: {rows[i]['name']} (emb {rows[i]['emb_id']}) vs {rows[j]['name']} (emb {rows[j]['emb_id']}): sim={sim:.3f}")
                print(f"   {rows[i]['source_photo']}  VS  {rows[j]['source_photo']}")
