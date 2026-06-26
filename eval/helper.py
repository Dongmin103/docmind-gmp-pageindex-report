import json, sys

STRUCT = json.load(open('results/gmp_guidance_structure.json'))['structure']
PAGES = json.load(open('/tmp/gmp_pages.json'))

# build node index with parent paths
NODE = {}
def index(nodes, path):
    for n in nodes:
        p = path + [n['title']]
        NODE[n['node_id']] = {'title': n['title'], 'path': p,
                              'start': n.get('start_index'), 'end': n.get('end_index'),
                              'has_children': bool(n.get('nodes'))}
        if n.get('nodes'):
            index(n['nodes'], p)
index(STRUCT, [])

def path_of(node_id):
    return NODE[node_id]['path']

def page(n):
    return PAGES[str(n)]

def show(node_id):
    info = NODE[node_id]
    print(f"=== [{node_id}] {info['start']}-{info['end']} ===")
    print(" / ".join(info['path']))
    print("---")
    for p in range(info['start'], info['end']+1):
        print(f"\n----- p.{p} -----")
        print(page(p))

if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'show':
        show(sys.argv[2])
    elif cmd == 'pages':
        for p in range(int(sys.argv[2]), int(sys.argv[3])+1):
            print(f"\n----- p.{p} -----")
            print(page(p))
    elif cmd == 'path':
        print(" / ".join(path_of(sys.argv[2])))
