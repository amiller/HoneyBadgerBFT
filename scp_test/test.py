

# Generate a random graph
import networkx as nx
import numpy as np

def random_graph(n=50,f=50/3,deg=5):
    g = nx.random_graphs.random_regular_graph(deg,n)
    print 'random regular graph with degree:', deg

    print 'connected:', nx.connected
    print 'diameter:', 'inf' if not nx.is_connected(g) else nx.diameter(g)

    # Corrupt f nodes
    x = range(n)
    np.random.shuffle(x)
    crupt = x[:f]
    for i in g.nodes(): 
        g.node[i]['correct'] = True
    for i in crupt: 
        g.node[i]['correct'] = False

    for i in g.nodes():
        # Determine the quorum slices according to the rule:
        #  any 2/3 are valid  #???
        pass

    return g

def mazieres_graph(n=30,tier1=10,k1=8,k=11,f=10):
    """
    Maybe a more realistic scheme would be that there are 10 "tier one
nodes", and every node chooses some fraction of them like 9, plus a few
other nodes, and then requires 8-10 of those for a quorum.  The idea
being to model that not everyone agrees what a tier-one node is
    """
    g = nx.DiGraph()
    tier1nodes = range(tier1)
    tier2nodes = range(tier1,n)

    # Each node connects to q random tier1 nodes, and k-q tier2 nodes
    for i in tier1nodes:
        # first handle tier1 nodes
        nodes = list(tier1nodes)
        nodes.remove(i)
        np.random.shuffle(nodes)
        for tgt in nodes[:k1-1]:
            g.add_edge(i,tgt)
        nodes = list(tier2nodes)
        np.random.shuffle(nodes)
        for tgt in nodes[:k-(k1-1)]:
            g.add_edge(i,tgt)

    for i in tier2nodes:
        nodes = list(tier1nodes)
        np.random.shuffle(nodes)
        for tgt in nodes[:k1]:
            g.add_edge(i,tgt)
        nodes = list(tier2nodes)
        nodes.remove(i)
        np.random.shuffle(nodes)
        for tgt in nodes[:k-k1]:
            g.add_edge(i,tgt)

    # Corrupt f nodes
    x = range(n)
    np.random.shuffle(x)
    crupt = x[:f]
    print g.nodes()
    for i in g.nodes(): 
        g.node[i]['correct'] = True
    for i in crupt: 
        g.node[i]['correct'] = False
    print crupt, g.node

    return g

def check_dset(g,B,q):
    # B is a set of nodes
    # q is the number of peers needed to reach a quorum
    # Is B a dispensable set?
    g = g.copy()
    g.remove_nodes_from(B)
    
    # Check quorum intersection
    for src in g.nodes():
        for tgt in g.nodes():
            if src == tgt: continue
            n1 = g[src].keys()
            n2 = g[tgt].keys()
            overlap = set(g[src]).intersection(set(g[tgt]))
            if len(n1)-len(overlap) >= q:
                print src,tgt,overlap,n1,n2
                return False # There is a quorum that does not overlap!
            if len(n2)-len(overlap) >= q:
                print src,tgt,overlap,n1,n2
                return False # There is a quorum that does not overlap!

    # Check quorum availability
    avail_violated=[]
    for i in g.nodes():
        if g.out_degree(i) < q: 
            print 'Quorum availability violated', i
            avail_violated.append(i)
    if avail_violated: return False, avail_violated
    return True

def correct_subgraph(g):
    return g.subgraph(n for n in g.nodes() if g.node[n]['correct'])

def compute_score(g):
    # Input: g
    #   a graph where edges represent inclusion, and 
    #   node label 'correct'] indicates whether failed
    # Output:
    #   a labelled graph with 'befouled'
    pass

def draw_graph(g,pos=None):
    colors = []
    for n in g.nodes():
        colors.append('white' if g.node[n]['correct'] else 'red')
    nx.draw_networkx(g, pos=pos, node_color=colors, with_labels=True)

def test(n=40, tier1=10, k1=9, k=11, f=10, q=8):
    global g
    g = mazieres_graph(n=n,tier1=tier1,k1=k1,k=k,f=f)
    pos = nx.spring_layout(g, iterations=200)
    crupt = [i for i in g.nodes() if not g.node[i]['correct']]

    figure(1);
    clf();
    draw_graph(g, pos)
    title('2Tier random graph (n=%d,tier1=%d,k1=%d,k=%d,f=%d)' % (n, tier1, k1, k, f))

    figure(2);
    clf();
    title('Graph with ill-behaved removed')
    draw_graph(correct_subgraph(g), pos)

    figure(3);
    clf();
    outcome = check_dset(g, crupt, q)
    if type(outcome) is tuple and outcome[0] == False:
        befouled = set(outcome[1])
        g2 = correct_subgraph(g)
        colors = []
        for i in g.nodes():
            colors.append('white' if i not in befouled else 'yellow')
        nx.draw_networkx(g2, pos=pos, node_color=colors, with_labels=True)
        title('Befouled nodes are yellow (q=%d)' % (q,))

    else:
        title('crupt is a DSet, no nodes befouled')
