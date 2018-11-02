import networkx as nx
import requests


def login(username, password):
    url = 'https://www.familysearch.org/auth/familysearch/login'
    r = requests.get(url, params={'ldsauth': False}, allow_redirects=False)
    url = r.headers['Location']
    r = requests.get(url, allow_redirects=False)
    r.text.index('name="params" value="')
    idx = r.text.index('name="params" value="')
    span = r.text[idx + 21:].index('"')
    params = r.text[idx + 21:idx + 21 + span]
    url = 'https://ident.familysearch.org/cis-web/oauth2/v3/authorization'
    r = requests.post(url, data={'params': params, 'userName': username,
                                 'password': password}, allow_redirects=False)
    url = r.headers['Location']
    r = requests.get(url, allow_redirects=False)
    return r.cookies['fssessionid']


def retrieve_user(cookie):
    base_url = 'https://familysearch.org'
    url = '/platform/users/current.json'
    return requests.get('https://familysearch.org' + url, cookies={'fssessionid': cookie}, timeout=60)


def retrieve_person(cookie, person_id):
    base_url = 'https://familysearch.org/'
    persons_url = '/platform/tree/persons.json?pids='
    return requests.get(base_url+persons_url+person_id, cookies={'fssessionid': cookie}, timeout=60)


def recurse_tree(G, center, cookie, distance, origin):
    r = retrieve_person(cookie, center)
    print(r.json()['persons'][0]['names'][0]['nameForms'][0]['fullText'])
    print('shortest path to origin = '+str(len(nx.shortest_path(G, source=origin, target=center))))

    # Work out program flow

    # too far up
    tooFarUp = len(nx.shortest_path(G, source=origin, target=center)) > distance

    # center == origin
    centerEqualsOrigin = center == origin

    # mother or father
    relationships = r.json()['childAndParentsRelationships'][0]
    relationships = None
    for relationship in r.json()['childAndParentsRelationships']:
        if relationship['child']['resourceId'] == center:
            relationships = relationship
            break

    if not relationships:
        mother = False
        father = False
    else:
        if 'father' in relationships.keys():
            if 'father' in [G.get_edge_data(*e)['relationship'] for e in G.out_edges(center)]:
                father = False
            else:
                father = True
        else:
            father = False
        if 'mother' in relationships.keys():
            if 'mother' in [G.get_edge_data(*e)['relationship'] for e in G.out_edges(center)]:
                mother = False
            else:
                mother = True
        else:
            mother = False

        if father:
            relationship_type = 'father'
        elif mother:
            relationship_type = 'mother'

    if tooFarUp:
        print('too far up')
        return recurse_tree(G, list(G.predecessors(center))[0], cookie, distance, origin)
    else:
        if father or mother:
            print('adding '+relationship_type)
            pid = relationships[relationship_type]['resourceId']
            if pid in G.nodes:
                print(relationship_type+' already in tree')
                G.add_edge(center, pid, relationship=relationship_type)
                return recurse_tree(G, center, cookie, distance, origin)
            else:
                r = retrieve_person(cookie, pid)
                name = r.json()['persons'][0]['names'][0]['nameForms'][0]['fullText']
                birthplace = ''
                for fact in r.json()['persons'][0]['facts']:
                    if fact['type'] == 'http://gedcomx.org/Birth':
                        if 'place' in fact.keys():
                            birthplace = fact['place']['original']
                            break
                # Check Mauritius
                if 'mauritius' in birthplace.lower():
                    print('#######################')
                    print(name + ' ' + pid + ' WAS BORN IN MAURITIUS')
                    print('#######################')
                ####################

                G.add_node(pid, name=name, birthplace=birthplace)
                G.add_edge(center, pid, relationship=relationship_type)
                return recurse_tree(G, pid, cookie, distance, origin)
        else:
            if centerEqualsOrigin:
                print('done recursion')
                return G
            else:
                print('both parents added, going back down')
                return recurse_tree(G, list(G.predecessors(center))[0], cookie, distance, origin)
