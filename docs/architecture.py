import graphviz

g = graphviz.Digraph('DesignGuard', format='png')
g.attr(rankdir='TB', bgcolor='white', fontname='Helvetica', pad='0.4', nodesep='0.35', ranksep='0.55')
g.attr('node', fontname='Helvetica', fontsize='11')
g.attr('edge', fontname='Helvetica', fontsize='9', color='#5b6b85')

NAVY = "#1A1A2E"
BLUE = "#2F6FED"
GREEN = "#1F9D55"
AMBER = "#C07A00"
RED = "#C0392B"
GREY = "#e2e6ee"

def node(name, label, color, shape='box', fill='white'):
    g.node(name, label, shape=shape, style='filled,rounded' if shape=='box' else 'filled',
           color=color, fillcolor=fill, fontcolor=NAVY, penwidth='1.6')

with g.subgraph(name='cluster_data') as c:
    c.attr(label='Data Layer (SQLite)', style='rounded', color=GREY, fontcolor='#6b7688', fontsize='11')
    node('elements', 'Flagged Design\nElements', BLUE)
    node('tokens', 'Design Token\nLibrary', BLUE)
    node('kb', 'Resolved Case\nKnowledge Base', BLUE)

node('triage', 'Triage Agent\n(ensemble merit model +\nexplainability)', GREEN)
node('resolution', 'Resolution Agent\n(precedent retrieval +\ngrounded recommendation)', GREEN)
node('qa', 'QA / Policy Agent\n(hard-coded rule gate)', AMBER)
node('escalation', 'Escalation Agent\n(routes final status)', AMBER)

node('human', 'Design-System\nReviewer', RED, shape='ellipse', fill='#fdecec')
node('auto', 'Auto-Fixed to\nToken/Library', GREEN, shape='ellipse', fill='#e6f6ec')
node('audit', 'Audit Trail\n(every step logged)', NAVY, shape='note', fill='#eef1f7')
node('dash', 'Dashboard\n(Flask + JS)', BLUE, shape='component', fill='#eaf1ff')

g.edge('elements', 'triage', label='flagged violation')
g.edge('tokens', 'triage', label='token deviation')
g.edge('triage', 'resolution', label='merit score +\nconfidence')
g.edge('kb', 'resolution', label='similarity search')
g.edge('resolution', 'qa', label='draft recommendation')
g.edge('qa', 'escalation', label='blocked? y/n')
g.edge('escalation', 'auto', label='not blocked')
g.edge('escalation', 'human', label='blocked \u2192\npending review', color=RED, fontcolor=RED)
g.edge('human', 'audit', style='dashed')
g.edge('auto', 'audit', style='dashed')
g.edge('triage', 'audit', style='dotted', color='#aab2c5')
g.edge('resolution', 'audit', style='dotted', color='#aab2c5')
g.edge('qa', 'audit', style='dotted', color='#aab2c5')
g.edge('audit', 'dash', label='decision trace')
g.edge('dash', 'human', label='review queue UI', dir='both')

g.render('/home/claude/designguard/docs/architecture', cleanup=True)
print("done")
